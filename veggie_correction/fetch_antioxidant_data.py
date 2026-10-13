#!/usr/bin/env python3
"""Fetch the real NASA OSDR antioxidant assay files for the Veggie studies.

These files (ORAC, total phenolic content, anthocyanin content) are enumerated
in each study's `_file_manifest.json` in this repository but were never
downloaded -- only the ICP-OES elemental products were. Every antioxidant number
published in OSDR-Veggie-Nutrition-Dashboard is therefore untraceable to the
archive. This script closes that gap.

Design follows `real_osdr_fetcher.py` in this directory:

* **No synthetic fallback.** A failed download raises. A pipeline that cannot
  obtain its data stops; it does not substitute numbers that look like data.
* URLs are read from the committed manifests, not reconstructed, so the files
  fetched are exactly the ones the archive listing names.
* Downloaded bytes are checked to look like delimited text before being written.
  Archive content is untrusted input: this script only writes it to disk, and
  nothing is executed from the download directory.
* SHA256 for every file is recorded alongside, matching this repo's practice of
  checksumming its inputs.

Usage (run from the repository root):

    python3 -I veggie_correction/fetch_antioxidant_data.py
    python3 -I veggie_correction/fetch_antioxidant_data.py --dry-run

Stdlib only -- no requests/pandas dependency.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "data" / "raw"
STUDIES = ("OSD-745", "OSD-655")

# Assay-name fragments identifying the antioxidant products. Matched
# case-insensitively against the filename as the manifest lists it.
WANTED = (
    "anthocyanin",
    "oxygen radical absorbance capacity",
    "orac",
    "phenolic",
)

UA = "SpaceMineralAtlas-antioxidant-fetch/1.0"
THROTTLE_S = 2.0          # OSDR 502/503s without pacing; see project memory
TIMEOUT_S = 120


def manifest_entries(study: str) -> dict:
    path = RAW / study / "_file_manifest.json"
    if not path.exists():
        raise SystemExit(f"FATAL: manifest missing: {path}")
    data = json.loads(path.read_text())
    try:
        return data[study]["files"]
    except (KeyError, TypeError) as exc:
        raise SystemExit(f"FATAL: unexpected manifest shape in {path}: {exc}")


def select(files: dict) -> dict:
    out = {}
    for name, rec in files.items():
        if not name.lower().endswith(".csv"):
            continue
        if any(frag in name.lower() for frag in WANTED):
            out[name] = rec
    return out


def looks_like_table(blob: bytes, name: str) -> None:
    """Reject anything that is not plausibly the delimited text we asked for."""
    if not blob:
        raise SystemExit(f"FATAL: {name}: empty response")
    head = blob[:4096]
    for magic in (b"%PDF", b"PK\x03\x04", b"\x89PNG", b"\xff\xd8\xff", b"\x1f\x8b"):
        if head.startswith(magic):
            raise SystemExit(f"FATAL: {name}: binary payload, not a CSV")
    try:
        text = head.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise SystemExit(f"FATAL: {name}: not UTF-8 text")
    stripped = text.lstrip()
    low = stripped.lower()
    if low.startswith("<!doctype html") or low.startswith("<html"):
        raise SystemExit(f"FATAL: {name}: server returned an HTML page, not data")
    # The biodata REST endpoint returns a JSON *file record*, not file contents.
    # A one-line JSON blob contains commas, so a naive delimiter check passes it.
    # Reject JSON explicitly -- this silently produced 17 metadata files on the
    # first run of this script.
    if stripped.startswith("{") or stripped.startswith("["):
        raise SystemExit(
            f"FATAL: {name}: JSON metadata record, not CSV contents "
            "(wrong endpoint -- use the datamanager URL)"
        )
    first = text.splitlines()[0] if text.splitlines() else ""
    if "," not in first and "\t" not in first:
        raise SystemExit(f"FATAL: {name}: no delimiter in first line: {first[:120]!r}")


def fetch(url: str, name: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        if resp.status != 200:
            raise SystemExit(f"FATAL: {name}: HTTP {resp.status}")
        return resp.read()


def fetch_with_fallback(rec: dict, name: str) -> tuple[bytes, str]:
    """Download file CONTENTS. No silent failure.

    Order matters: the datamanager `URL` serves the bytes, while the biodata
    `REST_URL` serves a JSON metadata record describing the file. Asking the
    REST endpoint for data yields a plausible-looking file that is not data.
    """
    errors = []
    for key in ("URL", "REST_URL"):
        url = rec.get(key)
        if not url:
            continue
        try:
            blob = fetch(url, name)
            looks_like_table(blob, name)
            return blob, url
        except SystemExit:
            raise
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
            errors.append(f"{key}: {type(exc).__name__} {exc}")
            time.sleep(THROTTLE_S)
    raise SystemExit(f"FATAL: {name}: every URL failed -> {' | '.join(errors)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="list what would be fetched and exit")
    args = ap.parse_args()

    plan: list[tuple[str, str, dict]] = []
    for study in STUDIES:
        chosen = select(manifest_entries(study))
        if not chosen:
            raise SystemExit(f"FATAL: {study}: manifest lists no antioxidant CSVs")
        for name, rec in sorted(chosen.items()):
            plan.append((study, name, rec))

    print(f"{len(plan)} antioxidant files listed across {len(STUDIES)} studies:")
    for study, name, _ in plan:
        exists = (RAW / study / name).exists()
        print(f"  [{study}] {'present' if exists else 'MISSING'}  {name}")
    if args.dry_run:
        print("\n--dry-run: nothing downloaded.")
        return

    written, skipped, sums = [], [], []
    for study, name, rec in plan:
        dest = RAW / study / name
        if dest.exists():
            print(f"skip (already present): {name}")
            skipped.append(name)
            continue
        print(f"fetching [{study}] {name} ...", flush=True)
        blob, used = fetch_with_fallback(rec, name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob)
        digest = hashlib.sha256(blob).hexdigest()
        sums.append((digest, f"data/raw/{study}/{name}"))
        written.append({
            "study": study, "file": name, "bytes": len(blob),
            "sha256": digest, "source_url": used,
            "lines": blob.count(b"\n") + 1,
        })
        print(f"   {len(blob):,} bytes  sha256 {digest[:16]}...")
        time.sleep(THROTTLE_S)

    if written:
        prov = REPO / "data" / "raw" / "antioxidant_fetch_provenance.json"
        prov.write_text(json.dumps({
            "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "script": "veggie_correction/fetch_antioxidant_data.py",
            "note": ("Antioxidant assay products listed in each study's "
                     "_file_manifest.json. URLs taken from the manifest, not "
                     "reconstructed. No synthetic fallback exists in this script."),
            "files": written,
        }, indent=2) + "\n")
        sumfile = REPO / "fair" / "antioxidant_inputs.sha256"
        sumfile.parent.mkdir(parents=True, exist_ok=True)
        sumfile.write_text("".join(f"{d}  {p}\n" for d, p in sorted(sums, key=lambda x: x[1])))
        print(f"\nwrote {prov.relative_to(REPO)}")
        print(f"wrote {sumfile.relative_to(REPO)}")

    print(f"\n{len(written)} downloaded, {len(skipped)} already present.")
    if not written and not skipped:
        raise SystemExit("FATAL: nothing fetched and nothing present")


if __name__ == "__main__":
    sys.exit(main())
