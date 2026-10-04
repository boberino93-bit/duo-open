#!/usr/bin/env python3
from __future__ import annotations
import argparse
import re
from pathlib import Path

P=Path("app/src/full/java/com/duoopen/shell/ShellProtocol.kt")
S=Path("app/src/full/java/com/duoopen/shell/DuoShellService.kt")
B=Path("app/src/full/java/com/duoopen/shell/ShizukuBridge.kt")
F=Path("app/src/full/java/com/duoopen/overlay/FoldOverlayService.kt")
V=Path("app/src/full/java/com/duoopen/debug/VisualForensics.kt")
E=Path("app/src/main/java/com/duoopen/debug/DebugBundleExporter.kt")
M="STABILIZATION_S1H_VISUAL_FORENSICS_V1"
R="S1H_RENDER_STACK_CONTEXT_V1"

def one(t,o,n,label):
    c=t.count(o)
    if c!=1: raise RuntimeError(f"{label}: expected one match, found {c}")
    return t.replace(o,n,1)

def protocol(t):
    if "CAPTURE_PHYSICAL_FORENSIC" in t:return t
    a="    const val CB_ANGLE = 1\n"
    return one(t,a,"    // "+M+": read-only physical screenshot evidence.\n    const val CAPTURE_PHYSICAL_FORENSIC = 19\n\n"+a,"protocol")

def shell(t):
    if M in t:return t
    if "STABILIZATION_S1G_FORENSIC_SUPERSET_V1" not in t:raise RuntimeError("S1G required")
    for x in ("STABILIZATION_S1C_ACTIVE_TRANSFER_V1","STABILIZATION_S1D_REAL_INNER_EDGE_V1"):
        if x in t:raise RuntimeError("mutation marker present: "+x)
    a='''                out.writeNoException()\n                out.writeBundle(result)\n            }\n            ShellProtocol.START_ANGLES -> {\n'''
    n='''                out.writeNoException()\n                out.writeBundle(result)\n            }\n            ShellProtocol.CAPTURE_PHYSICAL_FORENSIC -> {\n                // STABILIZATION_S1H_VISUAL_FORENSICS_V1\n                val physicalDisplayId = data.readLong()\n                val identity = clearCallingIdentity()\n                val result = try { capturePhysicalForensics(physicalDisplayId) } catch (e: Throwable) {\n                    Bundle().apply { putBoolean("ok", false); putString("status", "SCREENCAP_EXCEPTION"); putString("error", "${e.javaClass.simpleName}: ${e.message}") }\n                } finally { restoreCallingIdentity(identity) }\n                @Suppress("DEPRECATION") val fd: android.os.ParcelFileDescriptor? = result.getParcelable("fd")\n                out.writeNoException()\n                try { out.writeBundle(result) } finally { runCatching { fd?.close() } }\n            }\n            ShellProtocol.START_ANGLES -> {\n'''
    t=one(t,a,n,"transaction")
    a='''            putString(\n                "window_displays",\n                runProbe(\n                    "dumpsys window displays | head -n 250"\n                ),\n            )\n        }\n'''
    n='''            putString(\n                "window_displays",\n                runProbe(\n                    "dumpsys window displays | head -n 250"\n                ),\n            )\n            // S1H capture-policy context: distinguishes work policy, secure windows and backend faults.\n            putString("device_policy_capture", runProbe("dumpsys device_policy 2>/dev/null | grep -E -i 'Device Owner|Profile Owner|user(Id)?[=: ]|screen.?capture|screen_capture|no_screen_capture|DISALLOW_SCREEN_CAPTURE|setScreenCaptureDisabled' | head -n 260"))\n            putString("user_profiles", runProbe("dumpsys user 2>/dev/null | grep -E -i 'UserInfo\\\\{|profileGroupId|profileBadge|managed|work|quiet|running|state=' | head -n 220"))\n            putString("top_activity_user", runProbe("dumpsys activity activities 2>/dev/null | grep -E -i 'topResumedActivity|mResumedActivity|mCurrentFocus|ActivityRecord\\\\{|Task\\\\{' | head -n 120"))\n            putString("secure_windows", runProbe("dumpsys window windows 2>/dev/null | grep -E -i 'mCurrentFocus|mFocusedApp|FLAG_SECURE|secure=true|secure layer|isSecure|mAttrs' | head -n 180"))\n            putString("capture_backend", runCatching { api().name }.getOrElse { "unavailable: ${it.javaClass.simpleName}:${it.message}" })\n\n            // S1H rendering context: what Android/Samsung has prepared beneath the Duo overlay.\n            // These execute only in the post-burst forensic sweep, never in wake/route admission.\n            putString("wallpaper_render", runProbe("dumpsys wallpaper 2>/dev/null | grep -E -i 'Wallpaper|mWallpaper|visible|mVisible|Engine|mEngine|display|width|height|offset|padding|connection|component|service|surface|shown|draw' | head -n 320"))\n            putString("appwidget_render", runProbe("dumpsys appwidget 2>/dev/null | grep -E -i 'host|provider|widget|AppWidgetId|zombie|bound|package|user|options|views|update|RemoteViews' | head -n 340"))\n            putString("surface_layers", runProbe("dumpsys SurfaceFlinger --list 2>/dev/null | head -n 420"))\n            putString("window_render_layers", runProbe("dumpsys window windows 2>/dev/null | grep -E -i 'Window #|mCurrentFocus|mFocusedApp|mAttrs=|mHasSurface=|isVisible|mBaseLayer|mSubLayer|Wallpaper|Launcher|SystemUI|AppWidget|StatusBar|NavigationBar|InputMethod|TYPE_ACCESSIBILITY_OVERLAY|FLAG_SECURE|secure|duoopen|Duo Open' | head -n 420"))\n            putString("launcher_render", runProbe("sh -c 'echo HOME; cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME 2>/dev/null; echo TOP; dumpsys activity activities 2>/dev/null | grep -E -i \\\"Display #[0-9]+|RootTask|mResumedActivity|topResumedActivity|homeActivity|launcher|systemui|AppWidget|wallpaper\\\" | head -n 260'"))\n        }\n'''
    t=one(t,a,n,"policy and render context")
    h=r'''    // STABILIZATION_S1H_VISUAL_FORENSICS_V1: diagnostic physical-display screenshot.
    private fun capturePhysicalForensics(physicalDisplayId: Long): Bundle {
        val started=SystemClock.elapsedRealtime()
        if(physicalDisplayId<0L)return Bundle().apply{putBoolean("ok",false);putString("status","INVALID_PHYSICAL_ID")}
        val temp=java.io.File.createTempFile("duo-s1h-${Process.myPid()}-",".png",java.io.File("/data/local/tmp"))
        var p:java.lang.Process?=null
        try{
            p=ProcessBuilder("/system/bin/screencap","-p","-d",physicalDisplayId.toString(),temp.absolutePath).redirectErrorStream(true).start()
            if(!p.waitFor(1800L,TimeUnit.MILLISECONDS)){p.destroyForcibly();return Bundle().apply{putBoolean("ok",false);putString("status","SCREENCAP_TIMEOUT");putString("error","physical screencap timed out after 1800ms");putLong("ms",SystemClock.elapsedRealtime()-started)}}
            val output=runCatching{p.inputStream.bufferedReader().use{it.readText()}}.getOrDefault("").take(4000)
            val exit=p.exitValue();val size=temp.length()
            if(exit!=0||size<8L)return Bundle().apply{putBoolean("ok",false);putString("status",if(exit!=0)"SCREENCAP_EXIT_$exit" else "SCREENCAP_EMPTY");putString("error",output.ifBlank{"screencap failed"});putLong("fileBytes",size);putLong("ms",SystemClock.elapsedRealtime()-started)}
            val b=ByteArray(8);val r=java.io.FileInputStream(temp).use{it.read(b)}
            val png=r==8&&b.contentEquals(byteArrayOf(0x89.toByte(),0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a))
            if(!png)return Bundle().apply{putBoolean("ok",false);putString("status","SCREENCAP_NOT_PNG");putString("error","screencap output was not PNG")}
            val fd=android.os.ParcelFileDescriptor.open(temp,android.os.ParcelFileDescriptor.MODE_READ_ONLY)
            return Bundle().apply{putBoolean("ok",true);putString("status","CAPTURED");putLong("physicalDisplayId",physicalDisplayId);putLong("fileBytes",size);putLong("ms",SystemClock.elapsedRealtime()-started);putString("commandOutput",output);putParcelable("fd",fd)}
        }finally{runCatching{p?.destroy()};runCatching{temp.delete()}}
    }

'''
    return one(t,"    // ---- Samsung wallpaper angle reader -------------------------------------\n",h+"    // ---- Samsung wallpaper angle reader -------------------------------------\n","helper")

def bridge(t):
    if "data class ForensicCaptureOutcome" in t:return t
    b=r'''    // STABILIZATION_S1H_VISUAL_FORENSICS_V1: preserve why capture failed.
    data class ForensicCaptureOutcome(val ok:Boolean,val status:String,val secureLayers:Boolean,val bitmap:Bitmap?,val error:String?,val captureMs:Long,val sourceWidth:Int,val sourceHeight:Int)
    data class PhysicalForensicCaptureOutcome(val ok:Boolean,val status:String,val error:String?,val captureMs:Long,val sourceBytes:Long,val commandOutput:String?)
    fun captureForensics(displayId:Int,excluded:List<SurfaceControl>,scale:Float):ForensicCaptureOutcome{
        val x=call(ShellProtocol.CAPTURE){p->p.writeInt(displayId);p.writeInt(excluded.size);excluded.forEach{p.writeTypedObject(it,0)};p.writeFloat(scale)}?:return ForensicCaptureOutcome(false,"CAPTURE_BACKEND_UNAVAILABLE",false,null,"Shizuku unavailable",-1,-1,-1)
        val secure=x.getBoolean("secure",false);@Suppress("DEPRECATION") val bm:Bitmap?=x.getParcelable("bitmap");val er=x.getString("error")
        if(secure){bm?.recycle();return ForensicCaptureOutcome(false,"SECURE_LAYER_BLOCKED",true,null,er,x.getLong("ms",-1),x.getInt("width",-1),x.getInt("height",-1))}
        if(!x.getBoolean("ok",false)||bm==null){bm?.recycle();val l=er.orEmpty().lowercase();val s=when{l.contains("timeout")->"CAPTURE_TIMEOUT";l.contains("no display")->"NO_LOGICAL_DISPLAY";l.contains("permission")||l.contains("security")->"CAPTURE_PERMISSION_OR_POLICY_ERROR";else->"CAPTURE_FAILED"};return ForensicCaptureOutcome(false,s,false,null,er?:"no bitmap",x.getLong("ms",-1),x.getInt("width",-1),x.getInt("height",-1))}
        return ForensicCaptureOutcome(true,"CAPTURED",false,bm,null,x.getLong("ms",-1),x.getInt("width",-1),x.getInt("height",-1))
    }
    fun capturePhysicalForensics(physicalDisplayId:Long,destination:java.io.File):PhysicalForensicCaptureOutcome{
        val x=call(ShellProtocol.CAPTURE_PHYSICAL_FORENSIC){it.writeLong(physicalDisplayId)}?:return PhysicalForensicCaptureOutcome(false,"CAPTURE_BACKEND_UNAVAILABLE","Shizuku unavailable",-1,0,null)
        val ok=x.getBoolean("ok",false);val status=x.getString("status")?:if(ok)"CAPTURED" else "CAPTURE_FAILED";val er=x.getString("error");val ms=x.getLong("ms",-1);val out=x.getString("commandOutput");@Suppress("DEPRECATION") val fd:android.os.ParcelFileDescriptor?=x.getParcelable("fd")
        if(!ok||fd==null){runCatching{fd?.close()};return PhysicalForensicCaptureOutcome(false,if(ok)"SCREENCAP_NO_FD" else status,er?:"no file descriptor",ms,x.getLong("fileBytes",0),out)}
        return runCatching{destination.parentFile?.mkdirs();val n=android.os.ParcelFileDescriptor.AutoCloseInputStream(fd).use{i->destination.outputStream().buffered().use{o->i.copyTo(o)}};PhysicalForensicCaptureOutcome(n>0,if(n>0)"CAPTURED" else "SCREENCAP_COPY_EMPTY",if(n>0)null else "empty FD",ms,n,out)}.getOrElse{e->runCatching{fd.close()};runCatching{destination.delete()};PhysicalForensicCaptureOutcome(false,"SCREENCAP_COPY_FAILED","${e.javaClass.simpleName}: ${e.message}",ms,0,out)}
    }

'''
    return one(t,"    /** Receives angles from the shell-side wallpaper log reader. */\n",b+"    /** Receives angles from the shell-side wallpaper log reader. */\n","bridge")

def service(t):
    if "VisualForensics.beginOpeningBurst" in t:return t
    t=one(t,"import com.duoopen.debug.DuoDiagnostics\n","import com.duoopen.debug.DuoDiagnostics\nimport com.duoopen.debug.VisualForensics\n","import")
    pat=re.compile(r'(?P<i>^[ \t]*)gen3Visual\.beginOpening\(\n(?P=i)    generation = continuity\.generation,\n(?P=i)    reason = reason,\n(?P=i)\)',re.M)
    matches=list(pat.finditer(t))
    if not matches:raise RuntimeError("no gen3Visual.beginOpening call found")
    def add(m):
        i=m.group('i')
        return m.group(0)+f'''\n\n{i}// {M}: diagnostic-only sparse screenshot burst.\n{i}val forensicExclusions = engines.values.flatMap {{ engine ->\n{i}    runCatching {{ engine.captureExclusionLayers() }}.getOrDefault(emptyList())\n{i}}}\n{i}VisualForensics.beginOpeningBurst(\n{i}    context = applicationContext,\n{i}    displayManager = displayManager,\n{i}    scope = scope,\n{i}    openingGeneration = continuity.generation,\n{i}    reason = reason,\n{i}    excludedLayers = forensicExclusions,\n{i})'''
    return pat.sub(add,t)

def visual(t):
    if R in t:return t
    t=one(t,
'''        val secureWindows: String,\n        val topUser: Int?,\n''',
'''        val secureWindows: String,\n        // S1H_RENDER_STACK_CONTEXT_V1: state of wallpaper/widgets/composition below overlay.\n        val wallpaperRender: String,\n        val appWidgetRender: String,\n        val surfaceLayers: String,\n        val windowRenderLayers: String,\n        val launcherRender: String,\n        val topUser: Int?,\n''',"visual context fields")
    t=one(t,
'''        val secureWindows = raw?.getString("secure_windows").orEmpty()\n\n        val topUser =''',
'''        val secureWindows = raw?.getString("secure_windows").orEmpty()\n        val wallpaperRender = raw?.getString("wallpaper_render").orEmpty()\n        val appWidgetRender = raw?.getString("appwidget_render").orEmpty()\n        val surfaceLayers = raw?.getString("surface_layers").orEmpty()\n        val windowRenderLayers = raw?.getString("window_render_layers").orEmpty()\n        val launcherRender = raw?.getString("launcher_render").orEmpty()\n\n        val topUser =''',"visual context extraction")
    t=one(t,
'''        return PolicyContext(raw, devicePolicy, users, topActivity, secureWindows,\n            topUser, managedUsers, restricted, secureHint)\n''',
'''        return PolicyContext(\n            raw, devicePolicy, users, topActivity, secureWindows,\n            wallpaperRender, appWidgetRender, surfaceLayers, windowRenderLayers, launcherRender,\n            topUser, managedUsers, restricted, secureHint,\n        )\n''',"visual context construction")
    t=one(t,
'''                appendLine("captureBackend=${context.raw?.getString(\"capture_backend\") ?: \"<unavailable>\"}")\n                appendLine("\\n=== device_policy_capture ===\\n${context.devicePolicy.ifBlank { \"<unavailable>\" }}")\n''',
'''                appendLine("captureBackend=${context.raw?.getString(\"capture_backend\") ?: \"<unavailable>\"}")\n                appendLine("renderStackContext=S1H_RENDER_STACK_CONTEXT_V1")\n                appendLine("\\n=== wallpaper_render ===\\n${context.wallpaperRender.ifBlank { \"<unavailable>\" }}")\n                appendLine("\\n=== appwidget_render ===\\n${context.appWidgetRender.ifBlank { \"<unavailable>\" }}")\n                appendLine("\\n=== surface_layers ===\\n${context.surfaceLayers.ifBlank { \"<unavailable>\" }}")\n                appendLine("\\n=== window_render_layers ===\\n${context.windowRenderLayers.ifBlank { \"<unavailable>\" }}")\n                appendLine("\\n=== launcher_render ===\\n${context.launcherRender.ifBlank { \"<unavailable>\" }}")\n                appendLine("\\n=== device_policy_capture ===\\n${context.devicePolicy.ifBlank { \"<unavailable>\" }}")\n''',"visual render context export")
    t=one(t,
'''            writePolicy(session, policy)\n            writeManifest(session, records, policy)\n            DuoDiagnostics.event("visual-forensics", "burst-complete generation=$openingGeneration records=${records.size}")\n''',
'''            writePolicy(session, policy)\n            writeManifest(session, records, policy)\n            fun compact(value: String): String = value.lineSequence()\n                .map { it.trim() }.filter { it.isNotBlank() }.take(12)\n                .joinToString(" | ").take(1800)\n            DuoDiagnostics.event("visual-forensics-render", "wallpaper=${compact(policy.wallpaperRender)}")\n            DuoDiagnostics.event("visual-forensics-render", "widgets=${compact(policy.appWidgetRender)}")\n            DuoDiagnostics.event("visual-forensics-render", "layers=${compact(policy.windowRenderLayers)}")\n            DuoDiagnostics.event("visual-forensics-render", "launcher=${compact(policy.launcherRender)}")\n            DuoDiagnostics.event("visual-forensics", "burst-complete generation=$openingGeneration records=${records.size}")\n''',"visual render context logging")
    return t

def validate(p,s,b,f,v,e):
    for text,need in ((p,["CAPTURE_PHYSICAL_FORENSIC = 19"]),(s,["/system/bin/screencap","device_policy_capture","secure_windows","capture_backend","wallpaper_render","appwidget_render","surface_layers","window_render_layers","launcher_render","ParcelFileDescriptor.MODE_READ_ONLY"]),(b,["ForensicCaptureOutcome","captureForensics(","capturePhysicalForensics(","SECURE_LAYER_BLOCKED"]),(f,["VisualForensics.beginOpeningBurst","captureExclusionLayers"]),(v,["logical-excluded","physical-screencap","WORK_PROFILE_SCREEN_CAPTURE_POLICY_BLOCKED","SECURE_OR_PROTECTED_CONTENT_BLOCKED","ROUTE_ABSENT_NOT_CAPTURE_FAILURE",R,"wallpaperRender","appWidgetRender","surfaceLayers","windowRenderLayers","launcherRender","visual-forensics-render"]),(e,["visualForensicSessions","visual-forensics/${session.name}","Recent timestamped panel screenshots"])):
        for n in need:
            if n not in text:raise RuntimeError("missing invariant: "+n)

def apply(repo,check):
    for x in (P,S,B,F,V,E):
        if not (repo/x).exists():raise RuntimeError("missing "+str(x))
    p=protocol((repo/P).read_text());s=shell((repo/S).read_text());b=bridge((repo/B).read_text());f=service((repo/F).read_text());v=visual((repo/V).read_text());e=(repo/E).read_text();validate(p,s,b,f,v,e)
    if not check:
        for x,t in ((P,p),(S,s),(B,b),(F,f),(V,v)):(repo/x).write_text(t)

def main():
    a=argparse.ArgumentParser();a.add_argument("--repo",default=".");a.add_argument("--check",action="store_true");a.add_argument("--self-test",action="store_true");q=a.parse_args()
    if q.self_test:
        assert "CAPTURE_PHYSICAL_FORENSIC" in protocol("object X {\n    const val CB_ANGLE = 1\n}\n")
        print("stabilization S1H visual forensics transformer self-test: PASS")
        if not q.check:return 0
    apply(Path(q.repo).resolve(),q.check);print("stabilization S1H visual forensics: "+("source shape verified" if q.check else "applied"));return 0
if __name__=="__main__":raise SystemExit(main())
