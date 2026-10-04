#!/usr/bin/env python3
"""Secret-safe verifier for Duo Open diagnostic transport configuration.

Accepts either a Duo Open APK or a GitHub Actions artifact ZIP containing exactly
one APK. Decodes com.duoopen.BuildConfig from classes*.dex and prints only
boolean/length/hash metadata. It never prints the upload URL or ingest key.

Exit codes:
  0 = policy satisfied
  2 = compiled configuration does not satisfy requested policy
  3 = metadata/compiled runtime truth disagree
  4 = malformed/unreadable input
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import struct
import sys
import zipfile
from pathlib import Path

TARGET_CLASS = "Lcom/duoopen/BuildConfig;"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def uleb(data: bytes, off: int):
    value = 0
    shift = 0
    while True:
        if off >= len(data):
            raise ValueError("truncated uleb128")
        c = data[off]
        off += 1
        value |= (c & 0x7F) << shift
        if not (c & 0x80):
            return value, off
        shift += 7
        if shift > 63:
            raise ValueError("uleb128 too large")


def parse_dex_buildconfig(data: bytes):
    if len(data) < 112 or not data.startswith(b"dex\n"):
        return None

    def u4(o):
        return struct.unpack_from("<I", data, o)[0]

    def u2(o):
        return struct.unpack_from("<H", data, o)[0]

    def sdata(off):
        _, p = uleb(data, off)
        end = data.index(0, p)
        return data[p:end].decode("utf-8", "replace")

    string_count, string_off = u4(56), u4(60)
    strings = [sdata(u4(string_off + i * 4)) for i in range(string_count)]
    type_count, type_off = u4(64), u4(68)
    types = [strings[u4(type_off + i * 4)] for i in range(type_count)]
    if TARGET_CLASS not in types:
        return None
    target_type = types.index(TARGET_CLASS)

    field_count, field_off = u4(80), u4(84)
    fields = []
    for i in range(field_count):
        o = field_off + i * 8
        fields.append((u2(o), u2(o + 2), u4(o + 4)))

    class_count, class_off = u4(96), u4(100)
    class_data_off = static_values_off = None
    for i in range(class_count):
        o = class_off + i * 32
        if u4(o) == target_type:
            class_data_off = u4(o + 24)
            static_values_off = u4(o + 28)
            break
    if class_data_off is None:
        return None

    nstatic, p = uleb(data, class_data_off)
    _, p = uleb(data, p)
    _, p = uleb(data, p)
    _, p = uleb(data, p)

    static_field_ids = []
    idx = 0
    for _ in range(nstatic):
        diff, p = uleb(data, p)
        _, p = uleb(data, p)
        idx += diff
        static_field_ids.append(idx)

    values = []
    if static_values_off:
        nvalues, q = uleb(data, static_values_off)
        for _ in range(nvalues):
            h = data[q]
            q += 1
            value_type, value_arg = h & 0x1F, h >> 5
            if value_type == 0x1F:
                values.append(("boolean", bool(value_arg)))
                continue
            if value_type == 0x1E:
                values.append(("null", None))
                continue
            width = value_arg + 1
            raw = data[q : q + width]
            q += width
            n = int.from_bytes(raw, "little", signed=False)
            if value_type == 0x17:
                values.append(("string", strings[n]))
            elif value_type == 0x04:
                values.append(("int", n))
            else:
                values.append((f"type_{value_type:x}", n))

    out = {}
    for pos, field_id in enumerate(static_field_ids):
        _, _, name_idx = fields[field_id]
        name = strings[name_idx]
        out[name] = values[pos] if pos < len(values) else ("default", None)
    return out


def extract_apk(input_path: Path):
    data = input_path.read_bytes()
    input_sha = sha256_bytes(data)
    if input_path.suffix.lower() == ".apk":
        return data, input_sha, None, None

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = z.namelist()
            apk_names = [n for n in names if n.lower().endswith(".apk")]
            if len(apk_names) != 1:
                raise ValueError(f"expected exactly one APK, found {len(apk_names)}")
            apk = z.read(apk_names[0])
            build_info = (
                z.read("BUILD-INFO.txt").decode("utf-8", "replace")
                if "BUILD-INFO.txt" in names
                else None
            )
            return apk, input_sha, apk_names[0], build_info
    except zipfile.BadZipFile as e:
        raise ValueError("input is neither an APK nor an artifact ZIP") from e


def verify(path: Path, require_key: bool, require_configured: bool):
    apk, input_sha, apk_name, build_info = extract_apk(path)
    apk_sha = sha256_bytes(apk)

    found = None
    with zipfile.ZipFile(io.BytesIO(apk)) as az:
        for name in sorted(
            n for n in az.namelist() if re.fullmatch(r"classes\d*\.dex", Path(n).name)
        ):
            parsed = parse_dex_buildconfig(az.read(name))
            if parsed is not None:
                found = (name, parsed)
                break
    if found is None:
        raise ValueError("app BuildConfig not found in APK")

    dex_name, fields = found
    url_kind, url = fields.get("DIAGNOSTIC_UPLOAD_URL", ("missing", None))
    key_kind, key = fields.get("DIAGNOSTIC_INGEST_KEY", ("missing", None))
    if url_kind != "string" or key_kind != "string":
        raise ValueError("diagnostic BuildConfig fields are not encoded strings")

    url = url or ""
    key = key or ""
    url_nonempty = bool(url.strip())
    url_https = url.strip().startswith("https://")
    key_nonempty = bool(key.strip())
    runtime_is_configured = url_https
    receipt_capable_policy = url_https and (key_nonempty or not require_key)

    metadata_configured = None
    if build_info is not None:
        m = re.search(r"^diagnosticUploadConfigured=(\w+)\s*$", build_info, re.M)
        if m:
            metadata_configured = m.group(1).lower() == "true"

    metadata_mismatch = (
        metadata_configured is not None and metadata_configured != runtime_is_configured
    )
    result = {
        "input_sha256": input_sha,
        "apk_sha256": apk_sha,
        "apk_name": apk_name,
        "buildconfig_dex": dex_name,
        "buildconfig_upload_url_nonempty": url_nonempty,
        "buildconfig_upload_url_https": url_https,
        "buildconfig_upload_url_length": len(url),
        "buildconfig_ingest_key_nonempty": key_nonempty,
        "buildconfig_ingest_key_length": len(key),
        "runtime_DebugBundleUploader_isConfigured": runtime_is_configured,
        "receipt_capable_policy": receipt_capable_policy,
        "require_key": require_key,
        "require_configured": require_configured,
        "build_info_diagnostic_configured": metadata_configured,
        "metadata_vs_runtime_mismatch": metadata_mismatch,
    }
    if metadata_mismatch:
        status, code = "FAIL_METADATA_RUNTIME_MISMATCH", 3
    elif require_configured and not receipt_capable_policy:
        status, code = "FAIL_RECEIPT_CAPABLE_CONFIG", 2
    else:
        status, code = "PASS", 0
    result["result"] = status
    return result, code


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("--require-configured", action="store_true")
    ap.add_argument("--require-key", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        result, code = verify(args.input, args.require_key, args.require_configured)
    except Exception as e:
        print(f"RESULT=ERROR {type(e).__name__}: {e}", file=sys.stderr)
        raise SystemExit(4)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        for k, v in result.items():
            print(f"{k}={str(v).lower() if isinstance(v, bool) else v}")
    raise SystemExit(code)


if __name__ == "__main__":
    main()
