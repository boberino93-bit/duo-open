from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from math import pi, sin
from typing import Optional, Tuple, List, Dict


class ContentMode(Enum):
    HOME_CANONICAL = auto()
    GENERAL_APP_BRIDGE = auto()
    SECURE_NATIVE_HANDOFF = auto()


class AttemptState(Enum):
    IDLE = auto()
    ACTIVE = auto()
    RELEASED = auto()
    ABORTED = auto()
    RECOVERED_NATIVE = auto()


@dataclass(frozen=True)
class LeaseToken:
    attempt_id: int
    host_id: str
    generation: int


@dataclass(frozen=True)
class ContentLease:
    attempt_id: int
    lease_id: int
    mode: ContentMode
    captured_ns: int
    source_package: Optional[str]
    source_window: Optional[str]
    task_id: Optional[int]
    service_epoch: int
    generation: int
    contains_pixels: bool
    capture_permitted: bool


class CanonicalSceneMapper:
    INNER_WIDTH = 1968
    INNER_HEIGHT = 2184
    RIGHT_LEFT = 984
    RIGHT_RIGHT = 1920
    COVER_WIDTH = 1080
    COVER_HEIGHT = 2520
    SCALE = 15.0 / 13.0

    @classmethod
    def inner_to_cover(cls, x: float, y: float) -> Optional[Tuple[float, float]]:
        if not (cls.RIGHT_LEFT <= x <= cls.RIGHT_RIGHT and 0 <= y <= cls.INNER_HEIGHT):
            return None
        return ((x - cls.RIGHT_LEFT) * cls.SCALE, y * cls.SCALE)

    @classmethod
    def cover_to_inner(cls, x: float, y: float) -> Optional[Tuple[float, float]]:
        if not (0 <= x <= cls.COVER_WIDTH and 0 <= y <= cls.COVER_HEIGHT):
            return None
        return (cls.RIGHT_LEFT + x / cls.SCALE, y / cls.SCALE)

    @classmethod
    def is_excluded_inner_strip(cls, x: float) -> bool:
        return cls.RIGHT_RIGHT < x <= cls.INNER_WIDTH


def glass_amount(angle: float) -> float:
    a = max(0.0, min(180.0, angle))
    # Independent optical envelope: clear endpoints, max frost at 90 degrees.
    return sin(pi * a / 180.0) ** 0.72


def geometry_tilt(angle: float) -> float:
    a = max(0.0, min(180.0, angle))
    # Separate geometry control. Smooth/C1 through midpoint, bounded and endpoint-clear.
    return 56.0 * sin(pi * a / 180.0)


class VirtualHinge:
    """Visual-only hinge. It never emits semantic state transitions."""

    BLIND_SPEED_DPS = 160.0
    BLIND_CAP_DEG = 88.0
    MAX_SLEW_DPS = 520.0
    MAX_PREDICT_NS = 55_000_000
    STALE_NS = 220_000_000

    def __init__(self) -> None:
        self.active = False
        self.start_ns = 0
        self.visual_angle = 0.0
        self.samples: List[Tuple[int, float]] = []
        self.last_frame_ns = 0
        self.last_direction = 0
        self.reversal_guard_until_ns = 0
        self.reversal_times: List[int] = []
        self.oscillation_guard_until_ns = 0

    def start(self, now_ns: int) -> None:
        self.active = True
        self.start_ns = now_ns
        self.visual_angle = 0.0
        self.samples.clear()
        self.last_frame_ns = now_ns
        self.last_direction = 0
        self.reversal_guard_until_ns = 0
        self.reversal_times.clear()
        self.oscillation_guard_until_ns = 0

    def stop(self) -> None:
        self.active = False
        self.samples.clear()
        self.reversal_times.clear()

    def add_measurement(self, now_ns: int, angle: float) -> None:
        if not self.active:
            return
        angle = max(0.0, min(180.0, angle))
        if self.samples and now_ns <= self.samples[-1][0]:
            return
        if self.samples:
            t0, a0 = self.samples[-1]
            dt = (now_ns - t0) / 1e9
            if dt > 0:
                v = (angle - a0) / dt
                sign = 1 if v > 7 else (-1 if v < -7 else 0)
                if sign and self.last_direction and sign != self.last_direction:
                    self.reversal_guard_until_ns = now_ns + 70_000_000
                    self.reversal_times = [t for t in self.reversal_times if now_ns - t < 550_000_000]
                    self.reversal_times.append(now_ns)
                    if len(self.reversal_times) >= 2:
                        self.oscillation_guard_until_ns = now_ns + 900_000_000
                if sign:
                    self.last_direction = sign
        self.samples.append((now_ns, angle))
        self.samples = self.samples[-7:]

    def frame(self, callback_ns: int, expected_present_ns: int) -> float:
        if not self.active:
            return self.visual_angle
        desired: float
        if not self.samples:
            elapsed = max(0, callback_ns - self.start_ns) / 1e9
            desired = min(self.BLIND_CAP_DEG, self.BLIND_SPEED_DPS * elapsed)
        else:
            t, a = self.samples[-1]
            age = max(0, callback_ns - t)
            guarded = callback_ns < max(self.reversal_guard_until_ns, self.oscillation_guard_until_ns)
            if guarded or age > self.STALE_NS or len(self.samples) < 3:
                desired = a
            else:
                t0, a0 = self.samples[-3]
                dt = max(1, t - t0) / 1e9
                v = max(-850.0, min(850.0, (a - a0) / dt))
                horizon = max(0, min(self.MAX_PREDICT_NS, expected_present_ns - t)) / 1e9
                desired = max(0.0, min(180.0, a + v * horizon))
        dt = max(0.004, min(0.040, (callback_ns - self.last_frame_ns) / 1e9))
        self.last_frame_ns = callback_ns
        step = self.MAX_SLEW_DPS * dt
        delta = max(-step, min(step, desired - self.visual_angle))
        self.visual_angle = max(0.0, min(180.0, self.visual_angle + delta))
        return self.visual_angle


@dataclass
class HostLeaseManager:
    current: Optional[LeaseToken] = None
    pending: Optional[LeaseToken] = None
    retired: set[LeaseToken] = field(default_factory=set)

    def bind_initial(self, token: LeaseToken) -> None:
        self.current = token
        self.pending = None

    def begin_migration(self, token: LeaseToken) -> None:
        if self.current == token:
            return
        self.pending = token

    def replacement_presented(self, token: LeaseToken) -> bool:
        if token != self.pending:
            return False
        old = self.current
        self.current = token
        self.pending = None
        if old:
            self.retired.add(old)
        return True

    def remove(self, token: LeaseToken) -> None:
        if token == self.pending:
            self.pending = None
        elif token == self.current:
            # Current host is not silently replaced by stale callbacks.
            self.retired.add(token)
            self.current = None
        else:
            self.retired.add(token)

    def stale_clear(self, token: LeaseToken) -> bool:
        if token == self.current or token == self.pending:
            return False
        self.retired.add(token)
        return True


@dataclass
class RefreshLeaseManager:
    owner: Optional[LeaseToken] = None
    cleared: List[LeaseToken] = field(default_factory=list)

    def replace(self, token: LeaseToken) -> None:
        if self.owner and self.owner != token:
            self.cleared.append(self.owner)
        self.owner = token

    def clear_exact(self, token: LeaseToken) -> bool:
        if token != self.owner:
            return False
        self.cleared.append(token)
        self.owner = None
        return True


@dataclass
class NativeEvidence:
    route_active: bool = False
    package: Optional[str] = None
    window: Optional[str] = None
    wallpaper_presented: bool = False
    useful_launcher_presented: bool = False
    useful_app_presented: bool = False
    secure_window_presented: bool = False
    presentation_ns: Optional[int] = None


class NativeFreshOracle:
    @staticmethod
    def is_fresh(mode: ContentMode, target_package: Optional[str], ev: NativeEvidence) -> bool:
        if not ev.route_active or ev.presentation_ns is None:
            return False
        if mode is ContentMode.HOME_CANONICAL:
            return ev.package in {"launcher", "home"} and ev.useful_launcher_presented
        if mode is ContentMode.GENERAL_APP_BRIDGE:
            return bool(target_package and ev.package == target_package and ev.useful_app_presented)
        if mode is ContentMode.SECURE_NATIVE_HANDOFF:
            return bool(target_package and ev.package == target_package and ev.secure_window_presented)
        return False


@dataclass
class CloseAuthorityFence:
    active_cycle: int = 0
    generation: int = 0
    terminal_native_cover_cycle: int = -1

    def start_cycle(self, cycle: int, generation: int) -> None:
        self.active_cycle = cycle
        self.generation = generation

    def terminal_native_cover(self, cycle: int) -> None:
        self.terminal_native_cover_cycle = max(self.terminal_native_cover_cycle, cycle)

    def may_mutate(self, cycle: int, generation: int) -> bool:
        if cycle <= self.terminal_native_cover_cycle:
            return False
        return cycle == self.active_cycle and generation == self.generation


@dataclass
class Gen6Model:
    service_epoch: int = 1
    attempt_seq: int = 0
    generation: int = 0
    state: AttemptState = AttemptState.IDLE
    attempt_id: Optional[int] = None
    content_mode: ContentMode = ContentMode.HOME_CANONICAL
    target_package: Optional[str] = None
    wake_requested: bool = False
    wake_hint_state: Optional[int] = None
    semantic_angle: Optional[float] = None
    semantic_open: bool = False
    overlay_visible: bool = False
    content_lease: Optional[ContentLease] = None
    next_content_lease: int = 0
    host: HostLeaseManager = field(default_factory=HostLeaseManager)
    refresh: RefreshLeaseManager = field(default_factory=RefreshLeaseManager)
    native: NativeEvidence = field(default_factory=NativeEvidence)
    virtual: VirtualHinge = field(default_factory=VirtualHinge)
    close_fence: CloseAuthorityFence = field(default_factory=CloseAuthorityFence)
    trace: List[Dict] = field(default_factory=list)

    def _record(self, kind: str, **kwargs) -> None:
        self.trace.append({"kind": kind, **kwargs})
        if len(self.trace) > 500:
            self.trace = self.trace[-500:]

    def start_from_wake_hint(self, previous: int, current: int, now_ns: int, native_cover_rest: bool) -> bool:
        if previous != 0 or current not in (1, 2) or not native_cover_rest:
            return False
        if self.state is AttemptState.ACTIVE:
            return True
        self.attempt_seq += 1
        self.generation += 1
        self.attempt_id = self.attempt_seq
        self.state = AttemptState.ACTIVE
        self.wake_requested = True
        self.wake_hint_state = current
        self.semantic_angle = None  # hint is explicitly not hinge truth
        self.semantic_open = False
        self.overlay_visible = True
        self.content_lease = None
        self.host = HostLeaseManager()
        self.refresh = RefreshLeaseManager()
        self.native = NativeEvidence()
        self.virtual.start(now_ns)
        self._record("attempt-start", attempt=self.attempt_id, hint=current)
        return True

    def measured_hinge(self, angle: float, now_ns: int) -> None:
        if self.state is not AttemptState.ACTIVE:
            return
        angle = max(0.0, min(180.0, angle))
        self.semantic_angle = angle
        self.virtual.add_measurement(now_ns, angle)
        if angle >= 172.0:
            self.semantic_open = True
        if angle <= 1.0 and not self.semantic_open:
            self.abort("returned-closed")

    def capture_content(
        self,
        mode: ContentMode,
        now_ns: int,
        source_package: Optional[str],
        source_window: Optional[str],
        task_id: Optional[int],
        capture_permitted: bool,
    ) -> Optional[ContentLease]:
        if self.state is not AttemptState.ACTIVE or self.attempt_id is None:
            return None
        self.content_mode = mode
        self.target_package = source_package
        if mode is ContentMode.SECURE_NATIVE_HANDOFF or not capture_permitted:
            self.content_mode = ContentMode.SECURE_NATIVE_HANDOFF
            self.content_lease = None
            self._record("secure-content-free", attempt=self.attempt_id, package=source_package)
            return None
        self.next_content_lease += 1
        lease = ContentLease(
            attempt_id=self.attempt_id,
            lease_id=self.next_content_lease,
            mode=mode,
            captured_ns=now_ns,
            source_package=source_package,
            source_window=source_window,
            task_id=task_id,
            service_epoch=self.service_epoch,
            generation=self.generation,
            contains_pixels=True,
            capture_permitted=True,
        )
        self.content_lease = lease
        return lease

    def adopt_content(self, lease: ContentLease, now_ns: int, max_age_ns: int = 250_000_000) -> bool:
        if self.state is not AttemptState.ACTIVE or self.attempt_id is None:
            return False
        if lease.mode is ContentMode.SECURE_NATIVE_HANDOFF or not lease.capture_permitted:
            return False
        if lease.attempt_id != self.attempt_id or lease.service_epoch != self.service_epoch:
            return False
        if lease.generation != self.generation or now_ns - lease.captured_ns > max_age_ns:
            return False
        self.content_lease = lease
        return True

    def bind_host(self, host_id: str, host_generation: int) -> LeaseToken:
        assert self.attempt_id is not None
        tok = LeaseToken(self.attempt_id, host_id, host_generation)
        if self.host.current is None:
            self.host.bind_initial(tok)
            self.refresh.replace(tok)
        else:
            self.host.begin_migration(tok)
        return tok

    def host_presented(self, token: LeaseToken) -> bool:
        if token.attempt_id != self.attempt_id:
            return False
        if self.host.pending == token:
            old = self.host.current
            ok = self.host.replacement_presented(token)
            if ok:
                if old:
                    self.refresh.clear_exact(old)
                self.refresh.replace(token)
            return ok
        return token == self.host.current

    def native_evidence(self, ev: NativeEvidence) -> None:
        self.native = ev

    def maybe_release(self) -> bool:
        if self.state is not AttemptState.ACTIVE or not self.semantic_open:
            return False
        if not NativeFreshOracle.is_fresh(self.content_mode, self.target_package, self.native):
            return False
        self._terminal_cleanup(AttemptState.RELEASED, "native-fresh")
        return True

    def abort(self, reason: str) -> None:
        if self.state is AttemptState.ACTIVE:
            self._terminal_cleanup(AttemptState.ABORTED, reason)

    def fault_recover(self, failure: str) -> None:
        if self.state is AttemptState.ACTIVE:
            self._terminal_cleanup(AttemptState.RECOVERED_NATIVE, failure)

    def _terminal_cleanup(self, terminal: AttemptState, reason: str) -> None:
        current = self.host.current
        if current:
            self.refresh.clear_exact(current)
        if self.host.pending:
            self.host.retired.add(self.host.pending)
        if current:
            self.host.retired.add(current)
        self.host.current = None
        self.host.pending = None
        self.content_lease = None
        self.overlay_visible = False
        self.wake_requested = False
        self.virtual.stop()
        self.state = terminal
        self._record("attempt-end", terminal=terminal.name, reason=reason)

    def assert_invariants(self) -> None:
        if self.state is AttemptState.ACTIVE:
            assert self.attempt_id is not None
            assert self.overlay_visible
        if self.content_mode is ContentMode.SECURE_NATIVE_HANDOFF:
            assert self.content_lease is None or not self.content_lease.contains_pixels
        if self.content_lease is not None:
            assert self.content_lease.attempt_id == self.attempt_id
            assert self.content_lease.service_epoch == self.service_epoch
            assert self.content_lease.generation == self.generation
        if self.refresh.owner is not None:
            assert self.state is AttemptState.ACTIVE
            assert self.refresh.owner.attempt_id == self.attempt_id
            assert self.refresh.owner in {self.host.current, self.host.pending}
        if self.state in {AttemptState.RELEASED, AttemptState.ABORTED, AttemptState.RECOVERED_NATIVE}:
            assert not self.overlay_visible
            assert self.refresh.owner is None
            assert self.host.current is None
            assert self.host.pending is None
            assert self.content_lease is None
