import glob
import json
import os
import random
import statistics
import sys
import unittest
from pathlib import Path

sys.path.insert(0, '/mnt/data/gen6_pass1')
sys.path.insert(0, str(Path(__file__).parent))

from gen6_model import ContentMode, LeaseToken, VirtualHinge
from pass2_model import (
    ContentProvenanceGuard, DiagnosticEvent, DiagnosticTransportModel,
    FrameCadenceTracker, FrameTimelineSample, NativeFreshEvidenceV2,
    NativeFreshOracleV2, PixelLease, PresentationHost, ProvenanceKey,
    RecoveryEpoch, RefreshCoordinator, RefreshOwner, TimingSource,
    ZeroGapHostBridge,
)


def sample(i, frame_ns, expected_delta=16_666_666):
    return FrameTimelineSample(i, frame_ns+300_000, frame_ns, frame_ns+16_000_000, frame_ns+expected_delta)


class Pass2Tests(unittest.TestCase):
    def test_frame_timeline_is_primary_presentation_time(self):
        t=FrameCadenceTracker(); s=sample(1,1_000_000_000,33_333_333)
        target,src=t.target(s,s.callback_ns)
        self.assertEqual(src,TimingSource.FRAME_TIMELINE); self.assertEqual(target,s.expected_present_ns)

    def test_display_mode_never_proves_effective_120(self):
        r=RefreshCoordinator(); r.display_mode_hz=120.0
        for i in range(20): r.cadence.add(sample(i,1_000_000_000+i*16_666_667))
        self.assertEqual(r.cadence.cadence_class,'OBSERVED_60'); self.assertFalse(r.effective_120_proven())

    def test_observed_120_requires_direct_cadence(self):
        r=RefreshCoordinator(); r.display_mode_hz=60.0
        for i in range(20): r.cadence.add(sample(i,1_000_000_000+i*8_333_333,8_333_333))
        self.assertEqual(r.cadence.cadence_class,'OBSERVED_120'); self.assertTrue(r.effective_120_proven())

    def test_duplicate_vsync_does_not_fake_cadence(self):
        t=FrameCadenceTracker(); s=sample(7,1_000_000_000)
        self.assertTrue(t.add(s)); self.assertFalse(t.add(s)); self.assertEqual(t.duplicate_samples,1)

    def test_refresh_replacement_clears_old_view_and_surface_first(self):
        r=RefreshCoordinator()
        a=RefreshOwner(LeaseToken(1,'h1',1),'v1','s1'); b=RefreshOwner(LeaseToken(1,'h2',2),'v2','s2')
        r.replace(a); r.replace(b)
        acts=r.actions.actions
        self.assertEqual(acts[2][0],'CLEAR_VIEW'); self.assertEqual(acts[3][0],'CLEAR_SURFACE')
        self.assertEqual(acts[4][0],'REQUEST_VIEW'); self.assertEqual(acts[5][0],'REQUEST_SURFACE_SEAMLESS')
        self.assertFalse(r.clear_exact(a.token)); self.assertEqual(r.owner,b)

    def test_refresh_same_surface_new_generation_stale_clear_safe(self):
        r=RefreshCoordinator(); a=RefreshOwner(LeaseToken(1,'h',1),'v','s'); b=RefreshOwner(LeaseToken(2,'h',2),'v','s')
        r.replace(a); r.replace(b); self.assertFalse(r.clear_exact(a.token)); self.assertEqual(r.owner,b)

    def test_zero_gap_migration_keeps_old_until_new_presents(self):
        h=ZeroGapHostBridge(); a=PresentationHost(LeaseToken(1,'cover',1),'cover',1); b=PresentationHost(LeaseToken(1,'inner',2),'inner',0)
        h.bind_initial(a); h.start_migration(b); h.assert_no_owned_black_gap(True,True)
        self.assertEqual(h.current,a); self.assertTrue(h.pending_first_present(b.token,2)); h.assert_no_owned_black_gap(True,True)
        self.assertEqual(h.current.token,b.token); self.assertIn(a,h.retired)

    def test_host_loss_before_pending_ready_degrades_native_not_blank(self):
        h=ZeroGapHostBridge(); a=PresentationHost(LeaseToken(1,'cover',1),'cover',1); b=PresentationHost(LeaseToken(1,'inner',2),'inner',0)
        h.bind_initial(a); h.start_migration(b); h.lose_host(a.token)
        self.assertTrue(h.native_degraded); self.assertEqual(h.black_gap_count,0)

    def test_provenance_rejects_user_task_window_package_generation_drift(self):
        g=ContentProvenanceGuard(); base=ProvenanceKey(1,2,3,10,'app','w',7,4)
        l=g.capture(base,100,False,True); self.assertIsNotNone(l)
        variants=[
            ProvenanceKey(1,2,3,11,'app','w',7,4), ProvenanceKey(1,2,3,10,'other','w',7,4),
            ProvenanceKey(1,2,3,10,'app','w2',7,4), ProvenanceKey(1,2,3,10,'app','w',8,4),
            ProvenanceKey(1,2,4,10,'app','w',7,4), ProvenanceKey(1,3,3,10,'app','w',7,4),
        ]
        for v in variants:self.assertFalse(g.adopt(l,v,120))

    def test_secure_transition_drops_all_pixel_state(self):
        g=ContentProvenanceGuard(); k=ProvenanceKey(1,1,1,0,'bank','w',1,1)
        self.assertIsNotNone(g.capture(k,100,False,True)); g.secure_transition(); self.assertIsNone(g.current)
        self.assertIsNone(g.capture(k,110,True,True)); self.assertIsNone(g.current)

    def test_native_fresh_route_generation_fenced(self):
        ev=NativeFreshEvidenceV2(7,1,200,'launcher','w',useful_launcher=True)
        self.assertFalse(NativeFreshOracleV2.is_fresh(ContentMode.HOME_CANONICAL,'launcher',ev,8,100))
        self.assertTrue(NativeFreshOracleV2.is_fresh(ContentMode.HOME_CANONICAL,'launcher',ev,7,100))

    def test_home_wallpaper_only_is_never_fresh(self):
        ev=NativeFreshEvidenceV2(1,1,200,'launcher','w',useful_launcher=True,wallpaper_only=True)
        self.assertFalse(NativeFreshOracleV2.is_fresh(ContentMode.HOME_CANONICAL,'launcher',ev,1,100))

    def test_general_app_requires_current_layout_generation(self):
        ev=NativeFreshEvidenceV2(1,2,200,'app.a','w',useful_app=True,layout_generation=4)
        self.assertFalse(NativeFreshOracleV2.is_fresh(ContentMode.GENERAL_APP_BRIDGE,'app.a',ev,1,100,5))
        self.assertTrue(NativeFreshOracleV2.is_fresh(ContentMode.GENERAL_APP_BRIDGE,'app.a',ev,1,100,4))

    def test_secure_native_handoff_requires_secure_ready_not_pixels(self):
        ev=NativeFreshEvidenceV2(1,1,200,'bank','secure',secure_ready=True)
        self.assertTrue(NativeFreshOracleV2.is_fresh(ContentMode.SECURE_NATIVE_HANDOFF,'bank',ev,1,100))

    def test_diagnostic_schema_is_metadata_only(self):
        e=DiagnosticEvent(1,1,2,'h:2','HOME_CANONICAL','frame',100,vsync_id=9,frame_time_ns=90,expected_present_ns=110,measured_angle=30,visual_angle=34)
        e.assert_privacy_safe(); self.assertNotIn('pixels',e.as_dict())

    def test_diagnostic_transport_requires_https_key_and_checksum_receipt(self):
        b=b'gen6-diagnostic-bundle'; import hashlib; digest=hashlib.sha256(b).hexdigest()
        self.assertFalse(DiagnosticTransportModel(None,False).upload(b,digest))
        self.assertFalse(DiagnosticTransportModel('http://bad',True).upload(b,digest))
        t=DiagnosticTransportModel('https://relay.example/upload',True)
        self.assertFalse(t.upload(b,'0'*64)); self.assertTrue(t.upload(b,digest)); self.assertEqual(t.last_receipt_sha256,digest)

    def test_wallpaper_loss_not_terminal_but_faults_cleanup(self):
        for fault in ['app-death','accessibility-death','shizuku-death','service-restart','host-loss']:
            r=RecoveryEpoch(); r.begin(1); r.own_resources(); r.wallpaper_source_lost(); self.assertEqual(r.active_attempt,1)
            r.terminal_fault(fault); self.assertTrue(r.clean()); self.assertIsNone(r.active_attempt); self.assertEqual(r.native_fallbacks,1)
            # new epoch remains usable
            r.begin(2); self.assertEqual(r.active_attempt,2)

    def test_virtual_hinge_uses_frame_timeline_horizon(self):
        v=VirtualHinge(); v.start(0)
        v.add_measurement(10_000_000,10); v.add_measurement(20_000_000,20); v.add_measurement(30_000_000,30)
        short=v.frame(35_000_000,40_000_000)
        v2=VirtualHinge(); v2.start(0); v2.add_measurement(10_000_000,10); v2.add_measurement(20_000_000,20); v2.add_measurement(30_000_000,30)
        long=v2.frame(35_000_000,80_000_000)
        self.assertGreaterEqual(long,short); self.assertLessEqual(long,180)

    def test_refresh_lifecycle_100k_fuzz(self):
        rng=random.Random(0x6120); r=RefreshCoordinator(); owners=[]
        for i in range(100_000):
            if rng.random()<.58:
                tok=LeaseToken(rng.randint(1,2000),rng.choice(['cover','inner','proxy']),rng.randint(1,2000))
                o=RefreshOwner(tok,'v'+str(rng.randrange(4)),'s'+str(rng.randrange(4))); r.replace(o); owners.append(o)
            else:
                if owners:
                    cand=rng.choice(owners); old=r.owner; ok=r.clear_exact(cand.token)
                    if old is not None and cand.token != old.token:self.assertFalse(ok); self.assertEqual(r.owner,old)
        if r.owner:self.assertTrue(r.clear_exact(r.owner.token))
        self.assertIsNone(r.owner)

    def test_host_migration_100k_fuzz_no_owned_blank(self):
        rng=random.Random(0x600D); h=ZeroGapHostBridge(); attempt=1; gen=1
        first=PresentationHost(LeaseToken(attempt,'cover',gen),'cover',1); h.bind_initial(first); after=True
        for i in range(100_000):
            if h.native_degraded:
                attempt+=1; gen+=1; h=ZeroGapHostBridge(); h.bind_initial(PresentationHost(LeaseToken(attempt,'cover',gen),'cover',1)); after=True
            if rng.random()<.65:
                gen+=1; p=PresentationHost(LeaseToken(attempt,rng.choice(['cover','inner','proxy']),gen),'h',0); h.start_migration(p)
                if rng.random()<.85:h.pending_first_present(p.token,gen)
            elif h.pending and rng.random()<.5:h.lose_host(h.pending.token)
            elif h.current and rng.random()<.03:h.lose_host(h.current.token)
            h.assert_no_owned_black_gap(True,after)
        self.assertEqual(h.black_gap_count,0)

    def test_provenance_100k_fuzz_never_accepts_mismatch(self):
        rng=random.Random(0xC0DE); g=ContentProvenanceGuard()
        for i in range(100_000):
            k=ProvenanceKey(rng.randint(1,20),rng.randint(1,5),rng.randint(1,20),rng.randint(0,2),f'app{rng.randint(0,3)}',f'w{rng.randint(0,4)}',rng.randint(0,9),rng.randint(1,20))
            l=g.capture(k,i*1_000_000,False,True); self.assertTrue(g.adopt(l,k,i*1_000_000+1))
            fields=list(k.__dict__.values()); idx=rng.randrange(len(fields));
            if isinstance(fields[idx],int):fields[idx]+=1000
            else:fields[idx]=str(fields[idx])+'x'
            bad=ProvenanceKey(*fields); self.assertFalse(g.adopt(l,bad,i*1_000_000+2))


class TraceReplayTests(unittest.TestCase):
    def _trace(self):
        p=os.environ.get('GEN4_TRANSITION_JSONL')
        if not p or not os.path.exists(p): self.skipTest('GEN4_TRANSITION_JSONL unavailable')
        return p

    def test_real_trace_has_frame_timeline_not_synthetic_mode_timing(self):
        p=self._trace(); tracker=FrameCadenceTracker(); expected_leads=[]
        with open(p,errors='replace') as f:
            for line in f:
                try:r=json.loads(line)
                except:continue
                if r.get('eventType')!='vsync':continue
                if not all(k in r for k in ('vsyncId','frameTimeNs','deadlineNs','expectedPresentNs')):continue
                s=FrameTimelineSample(r['vsyncId'],r['timestampNs'],r['frameTimeNs'],r['deadlineNs'],r['expectedPresentNs'])
                if tracker.add(s): expected_leads.append((s.expected_present_ns-s.frame_time_ns)/1e6)
        self.assertGreater(tracker.accepted_samples,6000)
        self.assertEqual(tracker.cadence_class,'OBSERVED_60')
        self.assertGreater(statistics.median(expected_leads),16.0); self.assertLess(statistics.median(expected_leads),17.0)

    def test_real_trace_duplicate_events_do_not_distort_cadence(self):
        p=self._trace(); tracker=FrameCadenceTracker()
        with open(p,errors='replace') as f:
            for line in f:
                try:r=json.loads(line)
                except:continue
                if r.get('eventType')=='vsync' and all(k in r for k in ('vsyncId','frameTimeNs','deadlineNs','expectedPresentNs')):
                    tracker.add(FrameTimelineSample(r['vsyncId'],r['timestampNs'],r['frameTimeNs'],r['deadlineNs'],r['expectedPresentNs']))
        self.assertGreaterEqual(tracker.duplicate_samples,1)
        self.assertGreater(tracker.observed_hz,55); self.assertLess(tracker.observed_hz,65)


if __name__=='__main__': unittest.main(verbosity=2)
