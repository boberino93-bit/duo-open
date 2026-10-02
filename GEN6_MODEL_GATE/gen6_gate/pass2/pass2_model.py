from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from hashlib import sha256
from statistics import median
from typing import Deque, Dict, List, Optional, Tuple

from gen6_model import ContentMode, LeaseToken


class TimingSource(Enum):
    FRAME_TIMELINE = auto()
    OBSERVED_CADENCE_FALLBACK = auto()
    UNKNOWN = auto()


@dataclass(frozen=True)
class FrameTimelineSample:
    vsync_id: int
    callback_ns: int
    frame_time_ns: int
    deadline_ns: int
    expected_present_ns: int


@dataclass
class FrameCadenceTracker:
    intervals_ns: Deque[int] = field(default_factory=lambda: deque(maxlen=120))
    last_vsync_id: Optional[int] = None
    last_frame_time_ns: Optional[int] = None
    accepted_samples: int = 0
    duplicate_samples: int = 0
    invalid_samples: int = 0

    def add(self, sample: FrameTimelineSample) -> bool:
        if (
            sample.vsync_id < 0
            or sample.frame_time_ns <= 0
            or sample.expected_present_ns < sample.frame_time_ns
            or sample.deadline_ns < sample.frame_time_ns
        ):
            self.invalid_samples += 1
            return False
        if self.last_vsync_id == sample.vsync_id and self.last_frame_time_ns == sample.frame_time_ns:
            self.duplicate_samples += 1
            return False
        if self.last_frame_time_ns is not None:
            d = sample.frame_time_ns - self.last_frame_time_ns
            if d <= 0:
                self.invalid_samples += 1
                return False
            # Ignore long callback outages for cadence classification, but keep the sample itself.
            if 4_000_000 <= d <= 40_000_000:
                self.intervals_ns.append(d)
        self.last_vsync_id = sample.vsync_id
        self.last_frame_time_ns = sample.frame_time_ns
        self.accepted_samples += 1
        return True

    @property
    def observed_hz(self) -> Optional[float]:
        if len(self.intervals_ns) < 8:
            return None
        m = median(self.intervals_ns)
        return 1_000_000_000.0 / m if m > 0 else None

    @property
    def cadence_class(self) -> str:
        hz = self.observed_hz
        if hz is None:
            return "INSUFFICIENT"
        if 105.0 <= hz <= 135.0:
            return "OBSERVED_120"
        if 50.0 <= hz <= 70.0:
            return "OBSERVED_60"
        return "OTHER"

    def target(self, sample: Optional[FrameTimelineSample], callback_ns: int) -> Tuple[int, TimingSource]:
        if sample is not None and sample.expected_present_ns >= callback_ns:
            # Bound pathological platform data without fabricating a display-mode-derived horizon.
            if sample.expected_present_ns - callback_ns <= 80_000_000:
                return sample.expected_present_ns, TimingSource.FRAME_TIMELINE
        if len(self.intervals_ns) >= 8:
            return callback_ns + int(median(self.intervals_ns)), TimingSource.OBSERVED_CADENCE_FALLBACK
        return callback_ns, TimingSource.UNKNOWN


@dataclass(frozen=True)
class RefreshOwner:
    token: LeaseToken
    view_id: str
    surface_id: str


@dataclass
class RefreshActions:
    actions: List[Tuple[str, str, LeaseToken]] = field(default_factory=list)

    def add(self, action: str, target: str, token: LeaseToken) -> None:
        self.actions.append((action, target, token))


@dataclass
class RefreshCoordinator:
    owner: Optional[RefreshOwner] = None
    actions: RefreshActions = field(default_factory=RefreshActions)
    requested_hz: float = 120.0
    display_mode_hz: Optional[float] = None  # telemetry only, never proof
    cadence: FrameCadenceTracker = field(default_factory=FrameCadenceTracker)

    def replace(self, new: RefreshOwner) -> None:
        if self.owner == new:
            return
        old = self.owner
        if old is not None:
            self.actions.add("CLEAR_VIEW", old.view_id, old.token)
            self.actions.add("CLEAR_SURFACE", old.surface_id, old.token)
        self.owner = new
        self.actions.add("REQUEST_VIEW", new.view_id, new.token)
        self.actions.add("REQUEST_SURFACE_SEAMLESS", new.surface_id, new.token)

    def clear_exact(self, token: LeaseToken) -> bool:
        if self.owner is None or self.owner.token != token:
            return False
        old = self.owner
        self.actions.add("CLEAR_VIEW", old.view_id, old.token)
        self.actions.add("CLEAR_SURFACE", old.surface_id, old.token)
        self.owner = None
        return True

    def effective_120_proven(self) -> bool:
        return self.cadence.cadence_class == "OBSERVED_120"


@dataclass(frozen=True)
class PresentationHost:
    token: LeaseToken
    host_id: str
    presented_generation: int = 0


@dataclass
class ZeroGapHostBridge:
    current: Optional[PresentationHost] = None
    pending: Optional[PresentationHost] = None
    retired: List[PresentationHost] = field(default_factory=list)
    native_degraded: bool = False
    black_gap_count: int = 0

    def bind_initial(self, host: PresentationHost) -> None:
        self.current = host
        self.pending = None

    def start_migration(self, host: PresentationHost) -> None:
        if self.current and self.current.token == host.token:
            return
        self.pending = host

    def pending_first_present(self, token: LeaseToken, presentation_generation: int) -> bool:
        if self.pending is None or self.pending.token != token:
            return False
        old = self.current
        self.current = PresentationHost(token, self.pending.host_id, presentation_generation)
        self.pending = None
        if old:
            self.retired.append(old)
        return True

    def lose_host(self, token: LeaseToken) -> None:
        if self.pending and self.pending.token == token:
            self.pending = None
            return
        if self.current and self.current.token == token:
            self.retired.append(self.current)
            self.current = None
            if self.pending is None:
                self.native_degraded = True
                return
            # Never expose an empty Gen6-owned presentation interval. If the old host dies
            # before the replacement presents, Gen6 degrades to native rather than blanking.
            self.native_degraded = True

    def assert_no_owned_black_gap(self, active: bool, after_first_present: bool) -> None:
        if active and after_first_present and not self.native_degraded:
            if self.current is None:
                self.black_gap_count += 1
            assert self.current is not None


@dataclass(frozen=True)
class ProvenanceKey:
    attempt_id: int
    service_epoch: int
    generation: int
    user_serial: int
    package: str
    window_id: str
    task_id: int
    capture_generation: int


@dataclass(frozen=True)
class PixelLease:
    key: ProvenanceKey
    captured_ns: int
    secure: bool
    contains_pixels: bool


@dataclass
class ContentProvenanceGuard:
    current: Optional[PixelLease] = None
    discarded: int = 0

    def capture(self, key: ProvenanceKey, now_ns: int, secure: bool, capture_allowed: bool) -> Optional[PixelLease]:
        if secure or not capture_allowed:
            self.current = None
            return None
        lease = PixelLease(key, now_ns, secure=False, contains_pixels=True)
        self.current = lease
        return lease

    def adopt(self, lease: PixelLease, expected: ProvenanceKey, now_ns: int, max_age_ns: int = 180_000_000) -> bool:
        if lease.secure or not lease.contains_pixels or lease.key != expected:
            self.discarded += 1
            return False
        if now_ns < lease.captured_ns or now_ns - lease.captured_ns > max_age_ns:
            self.discarded += 1
            return False
        self.current = lease
        return True

    def secure_transition(self) -> None:
        self.current = None


@dataclass(frozen=True)
class NativeFreshEvidenceV2:
    route_generation: int
    presentation_generation: int
    presentation_ns: int
    package: str
    window_id: str
    useful_launcher: bool = False
    useful_app: bool = False
    secure_ready: bool = False
    wallpaper_only: bool = False
    layout_generation: int = 0


class NativeFreshOracleV2:
    @staticmethod
    def is_fresh(
        mode: ContentMode,
        target_package: str,
        ev: NativeFreshEvidenceV2,
        required_route_generation: int,
        attempt_started_ns: int,
        required_layout_generation: int = 0,
    ) -> bool:
        if ev.route_generation != required_route_generation:
            return False
        if ev.presentation_generation <= 0 or ev.presentation_ns <= attempt_started_ns:
            return False
        if ev.wallpaper_only:
            return False
        if mode is ContentMode.HOME_CANONICAL:
            return ev.package in {"launcher", "home"} and ev.useful_launcher
        if mode is ContentMode.GENERAL_APP_BRIDGE:
            return (
                ev.package == target_package
                and ev.useful_app
                and ev.layout_generation >= required_layout_generation
            )
        if mode is ContentMode.SECURE_NATIVE_HANDOFF:
            return ev.package == target_package and ev.secure_ready
        return False


@dataclass(frozen=True)
class DiagnosticEvent:
    attempt_id: int
    service_epoch: int
    generation: int
    host_token: Optional[str]
    content_mode: str
    event: str
    time_ns: int
    vsync_id: Optional[int] = None
    frame_time_ns: Optional[int] = None
    expected_present_ns: Optional[int] = None
    measured_angle: Optional[float] = None
    visual_angle: Optional[float] = None
    reported_display_mode_hz: Optional[float] = None
    observed_cadence_hz: Optional[float] = None
    native_fresh_reason: Optional[str] = None
    recovery_reason: Optional[str] = None

    def as_dict(self) -> Dict[str, object]:
        return self.__dict__.copy()

    def assert_privacy_safe(self) -> None:
        # Diagnostic schema intentionally excludes screenshots, bitmap bytes,
        # content text, notification text, credentials, or secure-window pixels.
        forbidden = {"pixels", "bitmap", "screenshot", "content_text", "password", "notification_text"}
        assert forbidden.isdisjoint(self.as_dict())


@dataclass
class DiagnosticTransportModel:
    endpoint: Optional[str]
    ingest_key_present: bool
    last_receipt_sha256: Optional[str] = None

    @property
    def configured(self) -> bool:
        return bool(self.endpoint and self.endpoint.startswith("https://") and self.ingest_key_present)

    def upload(self, bundle: bytes, returned_receipt_sha256: str) -> bool:
        if not self.configured:
            return False
        local = sha256(bundle).hexdigest()
        if local != returned_receipt_sha256:
            return False
        self.last_receipt_sha256 = returned_receipt_sha256
        return True


@dataclass
class RecoveryEpoch:
    service_epoch: int = 1
    active_attempt: Optional[int] = None
    overlay_owned: bool = False
    refresh_owned: bool = False
    host_owned: bool = False
    content_owned: bool = False
    native_fallbacks: int = 0

    def begin(self, attempt_id: int) -> None:
        self.active_attempt = attempt_id
        self.overlay_owned = True

    def own_resources(self, refresh: bool = True, host: bool = True, content: bool = True) -> None:
        self.refresh_owned = refresh
        self.host_owned = host
        self.content_owned = content

    def wallpaper_source_lost(self) -> None:
        # Wallpaper source is not terminal authority; keep attempt alive.
        return

    def terminal_fault(self, kind: str) -> None:
        if kind in {"app-death", "accessibility-death", "shizuku-death", "service-restart", "host-loss"}:
            self.overlay_owned = False
            self.refresh_owned = False
            self.host_owned = False
            self.content_owned = False
            self.active_attempt = None
            self.native_fallbacks += 1
            self.service_epoch += 1

    def clean(self) -> bool:
        return not any((self.overlay_owned, self.refresh_owned, self.host_owned, self.content_owned))
