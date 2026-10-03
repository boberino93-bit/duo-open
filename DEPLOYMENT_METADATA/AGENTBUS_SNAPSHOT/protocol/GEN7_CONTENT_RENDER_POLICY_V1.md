# Duo Open Gen7 Content Render Policy V1

## Precedence

Content security classification always outranks visual/media optimization.

### 1. SECURE / SCREENSHOT-BLOCKED / PRIVATE / UNKNOWN-SENSITIVE
Render: `PRIVATE_FROST`

Rules:
- procedural/neutral frosted glass only;
- zero protected-pixel capture, cache, mirror, bitmap materialization, or blur source;
- short-circuit secure capture BEFORE HardwareBuffer/asBitmap/copy/cache/publication;
- work-profile/private explicit policy remains PRIVATE_FROST;
- unknown startup/privacy-transition state fails closed;
- video playback NEVER overrides this classification.

### 2. PUBLIC + POSITIVE ACTIVE VIDEO OVERLAY/PLAYBACK EVIDENCE
Render: `VIDEO_PASSTHROUGH`

Goal:
- suppress the decorative fold glass/frost effect over active public video where the effect harms video playback or overlays video over the wallpaper/home composition.

Requirements:
- only for content already authorized PUBLIC;
- require positive, current playback/window/surface evidence; package name alone is insufficient;
- YouTube/Facebook/etc. are examples, not unconditional allowlists;
- disable/reduce the decorative effect only for the exact current public video presentation scope;
- revoke passthrough immediately when playback/window identity changes, privacy becomes PRIVATE/UNKNOWN, app changes, or attempt/generation changes;
- do not use pixel inspection to classify video;
- preserve continuity routing/wake/terminal fences.

### 3. PUBLIC non-video
Render: `PUBLIC_GLASS`

Use transparent/polished glass continuity effect with exact-current provenance.

## Proposed policy order

`PRIVATE_FROST > VIDEO_PASSTHROUGH > PUBLIC_GLASS`

Security classification occurs first. Media classification is evaluated only inside PUBLIC.

## Diagnostics

Every render decision must record:
- attemptId + currentGeneration;
- foreground/content revision;
- privacyEpoch;
- privacy classification and evidence;
- video state/evidence;
- selected render mode;
- revocation reason;
- no protected content bytes.

## Field gates

Test:
- FLAG_SECURE app;
- known screenshot-blocked app;
- work profile;
- unknown/startup state;
- public static app;
- public YouTube video;
- public Facebook/Reels-style video;
- transition public video -> secure/private;
- transition secure/private -> public video;
- PIP/overlay enter/exit;
- video pause/resume;
- app/task switch during fold.
