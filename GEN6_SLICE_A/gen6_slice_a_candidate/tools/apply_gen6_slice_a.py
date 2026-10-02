#!/usr/bin/env python3
from pathlib import Path
import shutil, subprocess, sys

ROOT=Path.cwd()
OBSERVER=ROOT/'app/src/full/java/com/duoopen/overlay/Fold7DeviceStateObserver.kt'
SERVICE=ROOT/'app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt'
PAYLOAD=Path(__file__).resolve().parents[1]/'payload'
EXPECTED={
    OBSERVER:'760d075332740e5ee0d73766766175b17e6f9122',
    SERVICE:'cfc4706458e1da197e0e86ce74dc80c83489a2e6',
}

def blob(path):
    return subprocess.check_output(['git','hash-object',str(path)], text=True).strip()

def require(cond,msg):
    if not cond: raise SystemExit('ERROR: '+msg)

for p,sha in EXPECTED.items():
    require(p.exists(), f'missing baseline file {p}')
    require(blob(p)==sha, f'baseline drift {p}: expected {sha}, got {blob(p)}')

obs=OBSERVER.read_text()
old='''    private val onOpeningEdge: (\n        previousStateId: Int,\n        currentStateId: Int,\n    ) -> Unit,\n) {'''
new='''    private val onWakeHint: (\n        previousStateId: Int,\n        currentStateId: Int,\n    ) -> Unit = { _, _ -> },\n    private val onOpeningEdge: (\n        previousStateId: Int,\n        currentStateId: Int,\n    ) -> Unit,\n) {'''
require(old in obs, 'observer constructor marker missing')
obs=obs.replace(old,new,1)
old='''        DuoDiagnostics.event(\n            "early-wake",\n            "device-state previous=$previousId current=$id " +\n                "folded=$inferredFolded source=$source",\n        )\n\n        if (\n            previousId != null &&\n            previousFolded == true &&\n            inferredFolded == false\n        ) {'''
new='''        DuoDiagnostics.event(\n            "early-wake",\n            "device-state previous=$previousId current=$id " +\n                "folded=$inferredFolded source=$source",\n        )\n\n        // Gen6 Slice A: leaving a state that was independently learned as\n        // native-cover closed rest is an early wake hint, even when Samsung's\n        // next posture (notably Fold7 state 1) still reports folded=true.\n        // This callback is observation/attempt identity only; semantic opening\n        // remains governed by the existing folded->unfolded condition below.\n        if (\n            previousId != null &&\n            previousId in learnedFoldedStateIds &&\n            id != previousId\n        ) {\n            onWakeHint(previousId, id)\n        }\n\n        if (\n            previousId != null &&\n            previousFolded == true &&\n            inferredFolded == false\n        ) {'''
require(old in obs, 'observer handleState marker missing')
obs=obs.replace(old,new,1)
OBSERVER.write_text(obs)

svc=SERVICE.read_text()
old='''    private val gen2 =\n        Fold7Gen2Kernel<Bitmap>(serviceEpoch)\n    private var angleFeed: WallpaperAngleFeed? = null'''
new='''    private val gen2 =\n        Fold7Gen2Kernel<Bitmap>(serviceEpoch)\n    private val gen6OpeningAttempts =\n        Fold7Gen6OpeningAttemptOwner(serviceEpoch)\n    private var angleFeed: WallpaperAngleFeed? = null'''
require(old in svc, 'service owner marker missing')
svc=svc.replace(old,new,1)
old='''        deviceStateObserver =\n            Fold7DeviceStateObserver(\n                context = this,\n                handler = handler,\n            ) {\n                    previousStateId,\n                    currentStateId,\n                ->'''
new='''        deviceStateObserver =\n            Fold7DeviceStateObserver(\n                context = this,\n                handler = handler,\n                onWakeHint = { previousStateId, currentStateId ->\n                    val now = SystemClock.uptimeMillis()\n                    val attempt =\n                        gen6OpeningAttempts.onWakeHint(\n                            previousStateId = previousStateId,\n                            currentStateId = currentStateId,\n                            nowUptimeMs = now,\n                        )\n\n                    if (attempt != null) {\n                        val reason =\n                            "device-state:$previousStateId->$currentStateId"\n                        DuoDiagnostics.event(\n                            "gen6-opening-attempt",\n                            "WAKE_HINT attempt=${attempt.id} " +\n                                "serviceEpoch=${attempt.serviceEpoch} " +\n                                "reason=$reason semantic=false " +\n                                "precise=${hinge.lastAngle}",\n                        )\n                        com.duoopen.lab.TransitionLab.recordIngressStage(\n                            type = "gen6-wake-hint",\n                            serviceEpoch = serviceEpoch,\n                            presentationAttemptSequence = attempt.id,\n                            reason = reason,\n                        )\n                    }\n                },\n            ) {\n                    previousStateId,\n                    currentStateId,\n                ->'''
require(old in svc, 'service observer constructor marker missing')
svc=svc.replace(old,new,1)
old='''                if (\n                    beforeOpeningState ==\n                        Fold7ContinuityController.State.NATIVE_COVER &&\n                    continuity.state ==\n                        Fold7ContinuityController.State.OPENING_FROM_CLOSED\n                ) {\n                    gen3Visual.beginOpening('''
new='''                if (\n                    beforeOpeningState ==\n                        Fold7ContinuityController.State.NATIVE_COVER &&\n                    continuity.state ==\n                        Fold7ContinuityController.State.OPENING_FROM_CLOSED\n                ) {\n                    gen6OpeningAttempts\n                        .markSemanticAccepted(continuity.generation)\n                        ?.let { attempt ->\n                            DuoDiagnostics.event(\n                                "gen6-opening-attempt",\n                                "SEMANTIC_ACCEPT attempt=${attempt.id} " +\n                                    "generation=${continuity.generation}",\n                            )\n                        }\n                    gen3Visual.beginOpening('''
require(svc.count(old)>=2, 'expected two semantic-opening markers')
svc=svc.replace(old,new,2)
old='''        deviceStateObserver\n            ?.corroborateFoldedRest(\n                nativeCover =\n                    continuity.state ==\n                        Fold7ContinuityController.State.NATIVE_COVER,\n                preciseAngle =\n                    angle,\n            )\n\n        for (engine in engines.values.toList()) {'''
new='''        deviceStateObserver\n            ?.corroborateFoldedRest(\n                nativeCover =\n                    continuity.state ==\n                        Fold7ContinuityController.State.NATIVE_COVER,\n                preciseAngle =\n                    angle,\n            )\n\n        if (\n            continuity.state == Fold7ContinuityController.State.NATIVE_COVER &&\n            angle.isFinite() &&\n            angle <= GEN6_CLOSED_REST_MAX_DEG\n        ) {\n            gen6OpeningAttempts\n                .finish(\n                    reason = "corroborated-closed",\n                    nowUptimeMs = SystemClock.uptimeMillis(),\n                )\n                ?.let { terminal ->\n                    DuoDiagnostics.event(\n                        "gen6-opening-attempt",\n                        "END attempt=${terminal.attempt.id} " +\n                            "reason=${terminal.reason}",\n                    )\n                }\n        }\n\n        for (engine in engines.values.toList()) {'''
require(old in svc, 'service close-rest marker missing')
svc=svc.replace(old,new,1)
old='''        instance = null\n\n        deviceStateObserver'''
new='''        instance = null\n\n        gen6OpeningAttempts.finish(\n            reason = "service-destroy",\n            nowUptimeMs = SystemClock.uptimeMillis(),\n        )\n\n        deviceStateObserver'''
require(old in svc, 'service destroy marker missing')
svc=svc.replace(old,new,1)
old='''        const val MAX_GEN4_ROUTE_RETRIES = 3\n    }\n}'''
new='''        const val MAX_GEN4_ROUTE_RETRIES = 3\n        const val GEN6_CLOSED_REST_MAX_DEG = 12f\n    }\n}'''
require(old in svc, 'service companion marker missing')
svc=svc.replace(old,new,1)
SERVICE.write_text(svc)

for rel in [
 'app/src/full/java/com/duoopen/overlay/Fold7Gen6OpeningAttemptOwner.kt',
 'app/src/test/java/com/duoopen/overlay/Fold7Gen6OpeningAttemptOwnerTest.kt',
]:
    src=PAYLOAD/rel; dst=ROOT/rel; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
print('GEN6 SLICE A APPLY: PASS')
