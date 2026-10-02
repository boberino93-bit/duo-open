import json, math, os, random, re, statistics, unittest
from gen6_model import *


class Gen6Pass1Tests(unittest.TestCase):
    def test_exact_right_pane_transform_roundtrip_and_strip(self):
        self.assertAlmostEqual(CanonicalSceneMapper.SCALE, 15/13)
        self.assertEqual(CanonicalSceneMapper.inner_to_cover(984, 0), (0.0, 0.0))
        x,y = CanonicalSceneMapper.inner_to_cover(1920,2184)
        self.assertAlmostEqual(x,1080); self.assertAlmostEqual(y,2520)
        for x0,y0 in [(984,0),(1000,500),(1452,1092),(1919.5,2183.5)]:
            c = CanonicalSceneMapper.inner_to_cover(x0,y0); self.assertIsNotNone(c)
            p = CanonicalSceneMapper.cover_to_inner(*c)
            self.assertAlmostEqual(p[0],x0,places=6); self.assertAlmostEqual(p[1],y0,places=6)
        self.assertTrue(CanonicalSceneMapper.is_excluded_inner_strip(1950))
        self.assertIsNone(CanonicalSceneMapper.inner_to_cover(1950,100))

    def test_optics_and_geometry_independent_bounded_midpoint(self):
        self.assertAlmostEqual(glass_amount(0),0,places=7)
        self.assertAlmostEqual(glass_amount(90),1,places=7)
        self.assertAlmostEqual(glass_amount(180),0,places=7)
        self.assertAlmostEqual(geometry_tilt(0),0,places=7)
        self.assertAlmostEqual(geometry_tilt(180),0,places=7)
        self.assertGreater(geometry_tilt(90),50)
        e=0.01
        left=(geometry_tilt(90)-geometry_tilt(90-e))/e
        right=(geometry_tilt(90+e)-geometry_tilt(90))/e
        self.assertLess(abs(left-right),0.01)
        self.assertNotAlmostEqual(glass_amount(45)/glass_amount(90), geometry_tilt(45)/geometry_tilt(90), places=3)

    def test_wake_hint_starts_attempt_not_semantic_angle(self):
        m=Gen6Model(); self.assertTrue(m.start_from_wake_hint(0,1,0,True))
        self.assertTrue(m.wake_requested); self.assertIsNone(m.semantic_angle); self.assertFalse(m.semantic_open)
        a=m.attempt_id
        self.assertTrue(m.start_from_wake_hint(0,2,1_000_000,True)); self.assertEqual(a,m.attempt_id)

    def test_false_wake_hint_then_close_aborts_cleanly(self):
        m=Gen6Model(); m.start_from_wake_hint(0,1,0,True); m.measured_hinge(0,20_000_000)
        self.assertEqual(m.state,AttemptState.ABORTED); m.assert_invariants()

    def test_blackout_bootstrap_bounded_and_reacquisition(self):
        for blackout_ms in (300,500,1000):
            v=VirtualHinge(); v.start(0); vals=[]
            t=0
            while t < blackout_ms*1_000_000:
                t += 16_666_667; vals.append(v.frame(t,t+16_000_000))
            self.assertTrue(all(0 <= x <= 88 for x in vals)); self.assertTrue(all(b>=a for a,b in zip(vals,vals[1:])))
            v.add_measurement(t+1,40); before=v.visual_angle
            after=v.frame(t+16_666_667,t+33_000_000)
            self.assertLessEqual(abs(after-before),VirtualHinge.MAX_SLEW_DPS*0.040+1e-6)

    def test_host_make_before_break_and_stale_callbacks(self):
        m=Gen6Model(); m.start_from_wake_hint(0,1,0,True)
        a=m.bind_host('cover',1); self.assertEqual(m.host.current,a)
        b=m.bind_host('inner',2); self.assertEqual(m.host.current,a); self.assertEqual(m.host.pending,b)
        self.assertFalse(m.host.stale_clear(a))
        self.assertTrue(m.host_presented(b)); self.assertEqual(m.host.current,b); self.assertIn(a,m.host.retired)
        self.assertTrue(m.host.stale_clear(a)); self.assertEqual(m.host.current,b)
        self.assertFalse(m.refresh.clear_exact(a)); self.assertEqual(m.refresh.owner,b)

    def test_content_provenance_and_secure_no_pixels(self):
        m=Gen6Model(); m.start_from_wake_hint(0,1,0,True)
        old=m.capture_content(ContentMode.GENERAL_APP_BRIDGE,10,'pkg.a','w',1,True)
        self.assertTrue(m.adopt_content(old,20))
        m.abort('x'); m.start_from_wake_hint(0,1,100,True)
        self.assertFalse(m.adopt_content(old,110))
        self.assertIsNone(m.capture_content(ContentMode.SECURE_NATIVE_HANDOFF,120,'bank','secure',2,False))
        self.assertIsNone(m.content_lease); m.assert_invariants()

    def test_native_fresh_home_rejects_wallpaper_only(self):
        m=Gen6Model(); m.start_from_wake_hint(0,1,0,True); m.content_mode=ContentMode.HOME_CANONICAL
        m.measured_hinge(175,100)
        m.native_evidence(NativeEvidence(route_active=True,package='launcher',wallpaper_presented=True,presentation_ns=110))
        self.assertFalse(m.maybe_release())
        m.native_evidence(NativeEvidence(route_active=True,package='launcher',wallpaper_presented=True,useful_launcher_presented=True,presentation_ns=120))
        self.assertTrue(m.maybe_release()); m.assert_invariants()

    def test_general_app_relayout_native_fresh(self):
        m=Gen6Model(); m.start_from_wake_hint(0,2,0,True)
        m.capture_content(ContentMode.GENERAL_APP_BRIDGE,1,'reader','w',3,True); m.measured_hinge(174,10)
        m.native_evidence(NativeEvidence(route_active=True,package='reader',useful_app_presented=False,presentation_ns=20))
        self.assertFalse(m.maybe_release())
        m.native_evidence(NativeEvidence(route_active=True,package='reader',useful_app_presented=True,presentation_ns=30))
        self.assertTrue(m.maybe_release())

    def test_secure_native_handoff_and_reversal_no_leak(self):
        m=Gen6Model(); m.start_from_wake_hint(0,1,0,True)
        m.capture_content(ContentMode.SECURE_NATIVE_HANDOFF,1,'bank','secure',5,False)
        m.measured_hinge(70,10); m.measured_hinge(30,20); m.assert_invariants(); self.assertIsNone(m.content_lease)
        m.measured_hinge(0,30); self.assertEqual(m.state,AttemptState.ABORTED); m.assert_invariants()

    def test_terminal_cleanup_on_faults(self):
        for fault in ('accessibility-death','app-death','shizuku-death','display-host-loss','wallpaper-reader-loss','capture-failure'):
            m=Gen6Model(); m.start_from_wake_hint(0,1,0,True); m.bind_host('cover',1)
            m.capture_content(ContentMode.GENERAL_APP_BRIDGE,2,'pkg','w',1,True)
            m.fault_recover(fault); self.assertEqual(m.state,AttemptState.RECOVERED_NATIVE); m.assert_invariants()

    def test_close_terminal_reassert_fence(self):
        f=CloseAuthorityFence(); f.start_cycle(9,44); self.assertTrue(f.may_mutate(9,44))
        f.terminal_native_cover(9); self.assertFalse(f.may_mutate(9,44)); self.assertFalse(f.may_mutate(8,43))
        f.start_cycle(10,45); self.assertTrue(f.may_mutate(10,45))

    def test_oscillation_1000_loops_bounded(self):
        now=0
        for _ in range(1000):
            m=Gen6Model(); m.start_from_wake_hint(0,1,now,True)
            for a in (30,70,45,68,32,0):
                now += 20_000_000; m.measured_hinge(a,now)
                if m.state is AttemptState.ACTIVE:
                    v=m.virtual.frame(now,now+8_333_333); self.assertTrue(0 <= v <= 180)
                    m.assert_invariants()
            self.assertEqual(m.state,AttemptState.ABORTED); m.assert_invariants()

    def test_randomized_100k_lifecycle_events(self):
        rng=random.Random(0xD606)
        m=Gen6Model(); now=0; hosts=['cover','inner','fallback']
        for i in range(100_000):
            now += rng.randint(1,20)*1_000_000
            op=rng.randrange(13)
            if op==0 and m.state is not AttemptState.ACTIVE:
                m.start_from_wake_hint(0,rng.choice([1,2]),now,True)
            elif op==1 and m.state is AttemptState.ACTIVE:
                m.measured_hinge(rng.uniform(0,180),now)
            elif op==2 and m.state is AttemptState.ACTIVE:
                mode=rng.choice(list(ContentMode)); allowed=(mode is not ContentMode.SECURE_NATIVE_HANDOFF and rng.random()>0.08)
                m.capture_content(mode,now,rng.choice(['launcher','app.a','bank']),str(rng.randrange(4)),rng.randrange(8),allowed)
            elif op==3 and m.state is AttemptState.ACTIVE and m.attempt_id is not None:
                m.bind_host(rng.choice(hosts),rng.randrange(1,20))
            elif op==4 and m.state is AttemptState.ACTIVE and m.host.pending:
                m.host_presented(m.host.pending)
            elif op==5 and m.state is AttemptState.ACTIVE and m.host.current:
                stale=LeaseToken(max(0,(m.attempt_id or 1)-1),m.host.current.host_id,m.host.current.generation)
                m.refresh.clear_exact(stale)
            elif op==6 and m.state is AttemptState.ACTIVE:
                pkg=m.target_package or rng.choice(['launcher','app.a','bank'])
                m.native_evidence(NativeEvidence(True,pkg,'w',True,rng.choice([True,False]),rng.choice([True,False]),rng.choice([True,False]),now))
                m.maybe_release()
            elif op==7 and m.state is AttemptState.ACTIVE:
                m.fault_recover(rng.choice(['app-death','shizuku-death','display-loss']))
            elif op==8 and m.state is AttemptState.ACTIVE:
                m.abort('random-reversal-close')
            elif op==9 and m.state is AttemptState.ACTIVE:
                m.virtual.frame(now, now+rng.choice([8_333_333,16_666_667,33_333_333]))
            elif op==10:
                c=rng.randrange(1,50); g=rng.randrange(1,50); m.close_fence.start_cycle(c,g)
                if rng.random()<0.4:m.close_fence.terminal_native_cover(c)
            elif op==11 and m.state is not AttemptState.ACTIVE:
                m.state=AttemptState.IDLE
            elif op==12 and m.state is AttemptState.ACTIVE and m.host.current:
                m.host.stale_clear(LeaseToken((m.attempt_id or 0)+99,'old',99))
            m.assert_invariants()


class FieldReplayTests(unittest.TestCase):
    def test_raw_gen4_replay_wake_hint_gain(self):
        path=os.environ.get('GEN4_FIELD_LOG')
        if not path or not os.path.exists(path): self.skipTest('GEN4_FIELD_LOG unavailable')
        with open(path, errors='replace') as fh:
            lines=fh.read().splitlines()
        up=re.compile(r'uptime=(\d+)'); ds=re.compile(r'device-state previous=(\d+) current=(\d+)')
        ang=re.compile(r'\[angle-authority\] accepted .* angle=([0-9.]+)')
        st=re.compile(r'\[fold7-state\] STATE .* -> OPENING_FROM_CLOSED')
        ev=[]
        for line in lines:
            um=up.search(line)
            if not um: continue
            t=int(um.group(1)); dm=ds.search(line)
            if dm: ev.append((t,'device',int(dm.group(1)),int(dm.group(2))))
            am=ang.search(line)
            if am and float(am.group(1))>0: ev.append((t,'angle',float(am.group(1)),None))
            if st.search(line): ev.append((t,'open_state',None,None))
        delays=[]; hint_modes=[]
        for i,e in enumerate(ev):
            if e[1]=='device' and e[2]==0 and e[3] in (1,2):
                nxt=next((x for x in ev[i+1:] if x[0]>=e[0] and x[1]=='open_state'),None)
                if nxt:
                    delays.append(nxt[0]-e[0]); hint_modes.append(e[3])
        self.assertGreaterEqual(len(delays),10)
        self.assertGreaterEqual(statistics.median(delays),500)
        self.assertGreater(max(delays),2000)
        self.assertGreaterEqual(hint_modes.count(1),9)


if __name__=='__main__': unittest.main(verbosity=2)
