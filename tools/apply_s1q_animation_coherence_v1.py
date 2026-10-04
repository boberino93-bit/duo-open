#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path

GRADLE=Path('app/build.gradle.kts')
HINGE=Path('app/src/main/java/com/duoopen/fold/Fold7VirtualHingeGen5.kt')
HINGE_TEST=Path('app/src/test/java/com/duoopen/fold/Fold7VirtualHingeGen5Test.kt')
PANEL=Path('app/src/full/java/com/duoopen/overlay/PanelEngine.kt')
SHELL=Path('app/src/full/java/com/duoopen/shell/DuoShellService.kt')
EXPORTER=Path('app/src/main/java/com/duoopen/debug/DebugBundleExporter.kt')
MARKER='S1Q_ANIMATION_COHERENCE_V1'

def one(text,old,new,label):
    n=text.count(old)
    if n!=1: raise RuntimeError(f'{label}: expected exactly one match, found {n}')
    return text.replace(old,new,1)

def transform_gradle(t):
    if 'versionName = "5.1.0-beta2-zfold7-s1q"' in t: return t
    t=one(t,'        versionCode = 50\n','        versionCode = 51\n','versionCode')
    return one(t,'        versionName = "5.1.0-beta2-zfold7-s1p"\n','        versionName = "5.1.0-beta2-zfold7-s1q"\n','versionName')

def transform_hinge(t):
    if MARKER in t: return t
    t=one(t,'    private var visualAngle = CLOSED_SEED_DEG\n    private var lastFrameNs = Long.MIN_VALUE\n',f'''    private var visualAngle = CLOSED_SEED_DEG
    // {MARKER}: visual position and velocity are integrated together so a new
    // predicted target cannot create a visible velocity discontinuity.
    private var visualVelocityDps = 0f
    private var lastFrameNs = Long.MIN_VALUE
''','velocity field')
    t=one(t,'        visualAngle = initialAngle\n        lastFrameNs = nowNs\n','        visualAngle = initialAngle\n        visualVelocityDps = 0f\n        lastFrameNs = nowNs\n','start velocity reset')
    t=one(t,'        visualAngle = CLOSED_SEED_DEG\n        lastFrameNs = Long.MIN_VALUE\n','        visualAngle = CLOSED_SEED_DEG\n        visualVelocityDps = 0f\n        lastFrameNs = Long.MIN_VALUE\n','reset velocity')
    old='''        val maxStep =
            max(
                MIN_SLEW_DEG_PER_FRAME,
                (MAX_VISUAL_SPEED_DPS * (dtNs / 1_000_000_000.0)).toFloat(),
            )
        val delta = raw.desired - visualAngle
        val step = delta.coerceIn(-maxStep, maxStep)
        val next = (visualAngle + step).coerceIn(0f, 180f)
        val limited = abs(step - delta) > 0.0001f
        val correction = next - visualAngle
        visualAngle = next
'''
    new=f'''        // {MARKER}: acceleration-limited, frame-rate-invariant visual motion.
        val dtSec = (dtNs / 1_000_000_000.0).toFloat().coerceAtLeast(0.000_001f)
        val delta = raw.desired - visualAngle
        val desiredVelocity =
            (delta / dtSec).coerceIn(-MAX_VISUAL_SPEED_DPS, MAX_VISUAL_SPEED_DPS)
        val maxVelocityChange = MAX_VISUAL_ACCEL_DPS2 * dtSec
        val requestedVelocityChange = desiredVelocity - visualVelocityDps
        val velocityChange = requestedVelocityChange.coerceIn(-maxVelocityChange, maxVelocityChange)
        val nextVelocity =
            (visualVelocityDps + velocityChange).coerceIn(-MAX_VISUAL_SPEED_DPS, MAX_VISUAL_SPEED_DPS)

        var next = (visualAngle + nextVelocity * dtSec).coerceIn(0f, 180f)
        var committedVelocity = nextVelocity
        if (
            (delta > 0f && next > raw.desired) ||
            (delta < 0f && next < raw.desired) ||
            abs(delta) <= VISUAL_POSITION_EPSILON_DEG
        ) {{
            next = raw.desired.coerceIn(0f, 180f)
            committedVelocity = 0f
        }}

        val accelerationLimited = abs(velocityChange - requestedVelocityChange) > 0.0001f
        val speedLimited = abs(desiredVelocity) >= MAX_VISUAL_SPEED_DPS - 0.0001f
        val limited = accelerationLimited || speedLimited
        val correction = next - visualAngle
        visualAngle = next
        visualVelocityDps = committedVelocity
'''
    t=one(t,old,new,'motion integration')
    t=one(t,'        const val MAX_VISUAL_SPEED_DPS = 480.0\n        const val MIN_SLEW_DEG_PER_FRAME = 1.0f\n        const val DEFAULT_FRAME_NS = 16_666_667L\n','''        const val MAX_VISUAL_SPEED_DPS = 720f
        const val MAX_VISUAL_ACCEL_DPS2 = 24_000f
        const val VISUAL_POSITION_EPSILON_DEG = 0.04f
        const val DEFAULT_FRAME_NS = 16_666_667L
''','motion constants')
    return t

def transform_hinge_test(t):
    if 's1qAccelerationLimitKeepsVelocityContinuous' in t: return t
    t=t.replace('assertTrue(abs(after.angleDegrees - before) <= 8.2f)','assertTrue(abs(after.angleDegrees - before) <= 12.2f)',1)
    t=t.replace('assertTrue(abs(t.correctionDegrees) <= 8.5f)','assertTrue(abs(t.correctionDegrees) <= 12.5f)',1)
    tests=r'''

    @Test
    fun s1qAccelerationLimitKeepsVelocityContinuous() {
        val v = Fold7VirtualHingeGen5()
        v.startOpening(0L)
        v.addSample(sample(0, 10f)); v.addSample(sample(8, 20f)); v.addSample(sample(16, 30f)); v.addSample(sample(24, 40f))
        val a = v.targetForFrame(25_000_000L, 33_333_333L)
        val b = v.targetForFrame(33_333_333L, 41_666_666L)
        val c = v.targetForFrame(41_666_666L, 49_999_999L)
        val dt = 0.008333333f
        val va = a.correctionDegrees / dt
        val vb = b.correctionDegrees / dt
        val vc = c.correctionDegrees / dt
        val budget = Fold7VirtualHingeGen5.MAX_VISUAL_ACCEL_DPS2 * dt + 2f
        assertTrue(abs(vb - va) <= budget)
        assertTrue(abs(vc - vb) <= budget)
    }

    @Test
    fun s1qNoOvershootWhenPredictionTargetStops() {
        val v = Fold7VirtualHingeGen5()
        v.startOpening(0L)
        v.addSample(sample(0, 30f)); v.addSample(sample(8, 40f)); v.addSample(sample(16, 50f)); v.addSample(sample(24, 60f))
        repeat(20) { i ->
            val now = 25_000_000L + i * 8_333_333L
            val x = v.targetForFrame(now, now + 8_333_333L)
            assertTrue(x.angleDegrees in 0f..180f)
            if (x.correctionDegrees >= 0f) assertTrue(x.angleDegrees <= x.desiredAngleDegrees + 0.05f)
        }
    }

    @Test
    fun s1qConvergesSimilarlyAtSixtyAndOneTwentyHz() {
        fun run(frameNs: Long): Float {
            val v = Fold7VirtualHingeGen5()
            v.startOpening(0L)
            v.addSample(sample(0, 20f)); v.addSample(sample(8, 30f)); v.addSample(sample(16, 40f)); v.addSample(sample(24, 50f))
            var now = 25_000_000L
            val end = now + 200_000_000L
            var out = 0f
            while (now <= end) {
                out = v.targetForFrame(now, now + frameNs).angleDegrees
                now += frameNs
            }
            return out
        }
        assertTrue(abs(run(16_666_667L) - run(8_333_333L)) < 4f)
    }
'''
    i=t.rfind('\n}')
    if i<0: raise RuntimeError('test class end not found')
    return t[:i]+tests+t[i:]

def transform_panel(t):
    if 'S1Q_VSYNC_PHASE_LOCK' in t: return t
    t=one(t,'    private var gen5FrameCount = 0L\n    private var gen5LastMode: Fold7VirtualHingeGen5.Mode? = null\n','''    private var gen5FrameCount = 0L
    private var gen5LastMode: Fold7VirtualHingeGen5.Mode? = null
    // S1Q_VSYNC_PHASE_LOCK: high-resolution frame cadence calibrated once
    // into the uptime clock used by Gen5 sensor samples.
    private var gen5FrameClockOffsetNs = Long.MIN_VALUE
    private var gen5LastChoreographerFrameNs = Long.MIN_VALUE
    private var gen5FrameIntervalNs = 8_333_333L
''','vsync fields')
    old='''                val nowNs = SystemClock.uptimeMillis() * 1_000_000L
                val effectiveHz =
                    runCatching { display.mode.refreshRate }
                        .getOrDefault(60f)
                        .takeIf { it.isFinite() && it >= 30f }
                        ?: 60f
                val frameNs = (1_000_000_000.0 / effectiveHz).toLong()
                val target = gen5VirtualHinge.targetForFrame(
                    callbackTimeNs = nowNs,
                    expectedPresentationTimeNs = nowNs + frameNs,
                )
'''
    new='''                val effectiveHz =
                    runCatching { display.mode.refreshRate }
                        .getOrDefault(60f)
                        .takeIf { it.isFinite() && it >= 30f }
                        ?: 60f

                if (gen5FrameClockOffsetNs == Long.MIN_VALUE) {
                    gen5FrameClockOffsetNs = SystemClock.uptimeMillis() * 1_000_000L - frameTimeNanos
                    gen5FrameIntervalNs = (1_000_000_000.0 / effectiveHz).toLong()
                }
                if (gen5LastChoreographerFrameNs != Long.MIN_VALUE) {
                    val measured =
                        (frameTimeNanos - gen5LastChoreographerFrameNs).coerceIn(4_000_000L, 40_000_000L)
                    gen5FrameIntervalNs = ((gen5FrameIntervalNs * 3L) + measured) / 4L
                }
                gen5LastChoreographerFrameNs = frameTimeNanos

                val nowNs = frameTimeNanos + gen5FrameClockOffsetNs
                val target = gen5VirtualHinge.targetForFrame(
                    callbackTimeNs = nowNs,
                    expectedPresentationTimeNs = nowNs + gen5FrameIntervalNs,
                )
'''
    t=one(t,old,new,'vsync frame clock')
    t=one(t,'        gen5FrameCount = 0L\n        gen5LastMode = null\n','''        gen5FrameCount = 0L
        gen5LastMode = null
        gen5FrameClockOffsetNs = Long.MIN_VALUE
        gen5LastChoreographerFrameNs = Long.MIN_VALUE
        gen5FrameIntervalNs = 8_333_333L
''','opening clock reset')
    t=one(t,'        gen5FramePosted = false\n        gen5VirtualHinge.stop()\n        clearGen5RefreshRate()\n','''        gen5FramePosted = false
        gen5VirtualHinge.stop()
        gen5FrameClockOffsetNs = Long.MIN_VALUE
        gen5LastChoreographerFrameNs = Long.MIN_VALUE
        gen5FrameIntervalNs = 8_333_333L
        clearGen5RefreshRate()
''','stop clock reset')
    oldlog='''                            "slewLimited=${target.slewLimited} leadNs=${target.predictedLeadNs} " +
                            "requestedHz=$GEN5_REQUESTED_HZ effectiveHz=$effectiveHz",
'''
    newlog='''                            "slewLimited=${target.slewLimited} leadNs=${target.predictedLeadNs} " +
                            "frameIntervalNs=$gen5FrameIntervalNs clock=vsync-calibrated " +
                            "requestedHz=$GEN5_REQUESTED_HZ effectiveHz=$effectiveHz",
'''
    t=one(t,oldlog,newlog,'vsync telemetry')
    return t

def transform_shell(t):
    if 'S1Q_CANONICAL_PROXY_REGISTRATION' in t: return t
    marker='// S1P_HALL_OPTICAL_PROXY_V1: mirror the still-authoritative cover display instead of'
    start=t.find(marker)
    if start < 0: raise RuntimeError('S1P optical proxy creation marker not found')
    needle='Rect(0, 0, 1968, 2184),'
    dest=t.find(needle,start)
    if dest < 0: raise RuntimeError('S1P full-inner proxy destination not found after marker')
    replacement='''// S1Q_CANONICAL_PROXY_REGISTRATION: exact inverse of
                                // Fold7RightPaneComposer's cover/right-pane mapping.
                                Rect(984, 0, 1920, 2184),'''
    return t[:dest] + replacement + t[dest+len(needle):]

def transform_exporter(t):
    if 'animationCoherence=S1Q_ANIMATION_COHERENCE_V1' in t: return t
    anchor='''                        appendLine(
                            "hallOpticalProxyDeviceStateOverride=NONE"
                        )
'''
    add=anchor+'''                        appendLine(
                            "animationCoherence=S1Q_ANIMATION_COHERENCE_V1"
                        )
                        appendLine(
                            "animationClock=CHOREOGRAPHER_VSYNC_CALIBRATED_TO_UPTIME"
                        )
                        appendLine(
                            "animationMotion=C1_ACCELERATION_LIMITED_GEN5"
                        )
                        appendLine(
                            "proxyRegistration=CANONICAL_RIGHT_PANE_984_0_1920_2184"
                        )
'''
    return one(t,anchor,add,'export S1Q')

def validate(g,h,ht,p,s,e):
    req=((g,['versionCode = 51','versionName = "5.1.0-beta2-zfold7-s1q"']),
         (h,[MARKER,'visualVelocityDps','MAX_VISUAL_ACCEL_DPS2 = 24_000f','MAX_VISUAL_SPEED_DPS = 720f']),
         (ht,['s1qAccelerationLimitKeepsVelocityContinuous','s1qNoOvershootWhenPredictionTargetStops','s1qConvergesSimilarlyAtSixtyAndOneTwentyHz']),
         (p,['S1Q_VSYNC_PHASE_LOCK','gen5FrameClockOffsetNs','clock=vsync-calibrated']),
         (s,['S1Q_CANONICAL_PROXY_REGISTRATION','Rect(984, 0, 1920, 2184)']),
         (e,['animationCoherence=S1Q_ANIMATION_COHERENCE_V1','C1_ACCELERATION_LIMITED_GEN5','CANONICAL_RIGHT_PANE_984_0_1920_2184']))
    for txt,needles in req:
        for n in needles:
            if n not in txt: raise RuntimeError('missing S1Q invariant: '+n)
    for bad in ('cmd device_state state 5','scheduleConcurrentOuterRouteProbe','PROBE_CONCURRENT_OUTER_DEFAULT'):
        if bad in '\n'.join((p,s,e)): raise RuntimeError('rejected route override returned: '+bad)

def apply(repo: Path, check: bool):
    for x in (GRADLE,HINGE,HINGE_TEST,PANEL,SHELL,EXPORTER):
        if not (repo/x).exists(): raise RuntimeError('missing '+str(x))
    g=transform_gradle((repo/GRADLE).read_text())
    h=transform_hinge((repo/HINGE).read_text())
    ht=transform_hinge_test((repo/HINGE_TEST).read_text())
    p=transform_panel((repo/PANEL).read_text())
    s=transform_shell((repo/SHELL).read_text())
    e=transform_exporter((repo/EXPORTER).read_text())
    validate(g,h,ht,p,s,e)
    if not check:
        for rel,txt in ((GRADLE,g),(HINGE,h),(HINGE_TEST,ht),(PANEL,q),(SHELL,s),(EXPORTER,e)):
            (repo/rel).write_text(txt)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo',default='.'); ap.add_argument('--check',action='store_true'); ap.add_argument('--self-test',action='store_true'); a=ap.parse_args()
    if a.self_test:
        x=transform_gradle('        versionCode = 50\n        versionName = "5.1.0-beta2-zfold7-s1p"\n')
        assert 'versionCode = 51' in x and 's1q' in x
        print('S1Q animation coherence transformer self-test: PASS')
        if not a.check: return 0
    apply(Path(a.repo).resolve(),a.check)
    print('S1Q animation coherence: '+('source shape verified' if a.check else 'applied'))
    return 0
if __name__=='__main__': raise SystemExit(main())
