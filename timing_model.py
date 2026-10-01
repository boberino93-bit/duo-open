stages = [
    ("visual demand -> host construction", "UNKNOWN", "UNKNOWN", "No new Gen2 delay proposed"),
    ("host addView -> attached callback", "UNKNOWN", "UNKNOWN", "Android/WindowManager scheduling"),
    ("frozen bind -> invalidate", "SOURCE: immediate call sequence", "SOURCE: immediate call sequence", "No timer"),
    ("invalidate -> frozen onDraw", "UNKNOWN", "UNKNOWN", "Choreographer/ViewRoot scheduling"),
    ("onDraw -> View frame commit", "UNOBSERVED in current frozen path", "MEASUREMENT REQUIRED", "Gen2 registerFrameCommitCallback; no intentional delay"),
    ("same draw -> marker transaction submit", "UNOBSERVED in current frozen path", "MEASUREMENT REQUIRED", "Gen2 applyTransactionOnDraw marker, atomically synced with ViewRoot draw"),
    ("transaction submit -> committed", "MEASUREMENT exists only for live mirror", "MEASUREMENT REQUIRED", "Gen2 identity-bearing for both paths"),
    ("committed -> completed/presented", "MEASUREMENT exists only for live mirror", "MEASUREMENT REQUIRED", "API 35 completed listener; no intentional delay"),
    ("framework presented -> photons visible", "UNKNOWN", "UNKNOWN", "Requires Fold7 external high-speed video"),
]
print("DUO OPEN PRESENTATION GEN2 TIMING BUDGET")
for i, (stage, current, gen2, note) in enumerate(stages, 1):
    print(f"{i}. STAGE={stage}")
    print(f"   CURRENT={current}")
    print(f"   GEN2={gen2}")
    print(f"   NOTE={note}")
print("INTENTIONAL_GEN2_SLEEP_OR_DELAY_MS=0")
print("DEVICE_MEASURED_LATENCY_NUMBERS=NONE")
