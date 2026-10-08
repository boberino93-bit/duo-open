# Gen12.4 — Read-only direct Samsung angle sensor probe

Status: experiment specification only. No permission, settings, wallpaper, display-power, or system-state mutation is authorized by this document.

## Purpose

Determine whether the Shizuku shell process can subscribe directly to a fine-grained Samsung folding-angle sensor on the target Fold7. If it can, precise geometry can eventually stop depending on `FoldInteractive` wallpaper command routing.

The app process already discovers public/vendor fold-related sensors, but a vendor sensor can be present while app registration is permission-gated. A shell-side probe is therefore a separate question from app-side discovery.

## Read-only constraints

The probe may:

- enumerate `SensorManager.getSensorList(TYPE_ALL)`;
- inspect sensor metadata;
- inspect whether the shell context already has `com.samsung.permission.SSENSOR`;
- attempt ordinary `SensorManager.registerListener` calls using the shell process's existing authority;
- observe callback values for a bounded interval;
- unregister every listener it registered;
- return diagnostics to Duo Open.

The probe must not:

- grant or request a permission;
- change AppOps, package settings, system properties, secure/global/system settings, wallpaper, display power, or display routing;
- invoke root-only paths;
- write sensor values to persistent storage unless the normal user-requested Duo Open debug export is later created;
- classify a sensor as continuous geometry merely because registration returned true.

## Candidate inventory

Record for every fold/hinge-related sensor and Samsung private candidate:

- name;
- vendor;
- type and string type;
- resolution;
- maximum range;
- minimum delay;
- reporting mode;
- wake-up flag;
- registration result;
- exception class/message when registration fails;
- event count during the bounded observation window;
- first/last event uptime;
- min/max observed value;
- number of distinct values after 0.1-degree quantization.

Known types observed by other Fold7 work can be included in the probe set (for example public type 36 and Samsung private types in the 65686+ range), but **type number alone is never authority**.

## Classification

A probe result is one of:

### `DIRECT_FINE_AVAILABLE`

All must hold:

- listener registration succeeds;
- callbacks are actually received;
- values are finite and plausibly map into 0..180 degrees;
- declared/observed granularity is finer than the coarse public 0/90/180 posture source;
- movement produces more than endpoint/posture values.

### `PRESENT_PERMISSION_DENIED`

A plausible fine Samsung sensor is enumerated but listener registration throws/returns denial under the shell process's existing authority.

This result is final for the no-root/no-permission-mutation design. Duo Open must fall back rather than trying to escalate privilege.

### `COARSE_ONLY`

Only posture-like sources register or produce 0/90/180-class output.

These sources can support endpoint/posture safety but never continuous fold animation.

### `NO_CANDIDATE`

No plausible direct folding-angle producer is exposed to the shell process.

## Bounded probe timing

A physical probe should run for 5 seconds by default and always unregister in `finally`. It should be callable explicitly from diagnostics and should not run continuously merely because Duo Open is enabled.

If a candidate later becomes a production source, continuous registration requires a separate lifecycle design with Binder death handling, source-session fencing, timestamp validation, and an explicit source authority policy.

## Future source integration contract

A successful probe is not enough to splice sensor callbacks directly into rendering.

A direct precise producer must receive its own source session and sequence identity. The geometry authority layer should then prefer:

1. fresh direct Samsung fine sensor;
2. fresh target-attributed FoldInteractive precise source;
3. public/vendor coarse source for posture/endpoints only.

Switching between direct and wallpaper precise sources must be observable and fenced. A late callback from a demoted source must not retake geometry authority.

## Why this remains separate from the Gen12.4 runtime candidate

Gen12.4's current field question is whether target-attributed wallpaper polling survives One UI's native-cover topology transition. Adding a second live precise producer before that question is answered would confound the experiment.

Therefore the direct-sensor probe is deliberately specified now but should be integrated as a diagnostic transaction only after the target-authority runtime is compile-clean. It must not automatically become the rendering source in the same validation build.
