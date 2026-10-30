"""Write the latest edits from Supabase into translated_manazil.json, then rebuild with build_site.py.

    python source/bake_edits.py             # writes the JSON and prints what changed
    python source/bake_edits.py --dry-run   # only prints

Pages show edits live either way. This keeps the JSON a complete backup, and keeps the site
readable with recent edits if Supabase is ever down.

data-loc forms (L is a source line, n a verse, k a list index, lang is ar or en):
    pL.vn.h1.lang  pL.vn.h2.lang   a hemistich
    pL.intro.lang  pL.after.lang   prose around a poem
    pL.ik.lang                     a gloss inside a poem
    pL.nk                          a translator's note (English only)
    muqaddima.sL.lang  colophon.sL.lang   a prose paragraph
"""

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

DATA = Path(__file__).parent / "translated_manazil.json"
BASE = "https://duhsapgvvlpzrhtvnciu.supabase.co"
KEY = "sb_publishable_N19t8v31QEDJ_qIRKEjRig_rSDS5QoI"   # public; edits are publicly readable


def fetch_edits():
    rows, offset = [], 0
    while True:
        req = urllib.request.Request(f"{BASE}/rest/v1/edits?select=id,loc,rev,text&order=id&limit=1000&offset={offset}",
                                     headers={"apikey": KEY})
        with urllib.request.urlopen(req, timeout=60) as r:
            batch = json.load(r)
        rows += batch
        if len(batch) < 1000:
            return rows
        offset += 1000


def resolve(data, poems, loc):
    """The (container, key) holding a data-loc's text, or None if it names nothing."""
    m = re.fullmatch(r"(muqaddima|colophon)\.s(\d+)\.(ar|en)", loc)
    if m:
        section, line, lang = data[m[1]], int(m[2]), m[3]
        pars = section["paragraphs"] if lang == "ar" else ((section.get("translation") or {}).get("paragraphs") or [])
        return next(((x, "text") for x in pars if x["source_line"] == line and "text" in x), None)

    m = re.fullmatch(r"p(\d+)\.(.+)", loc)
    p = poems.get(int(m[1])) if m else None
    if not p:
        return None
    rest = m[2]
    t, pt = p.get("translation") or {}, p.get("prose_translation") or {}

    m = re.fullmatch(r"v(\d+)\.(h[12])\.(ar|en)", rest)
    if m:
        n = int(m[1])
        if m[3] == "ar":
            return (p["verses"][n - 1], m[2]) if 1 <= n <= len(p["verses"]) else None
        return next(((v, m[2]) for v in t.get("verses") or [] if v["n"] == n), None)

    m = re.fullmatch(r"(intro|after)\.(ar|en)", rest)
    if m:
        return (p, m[1]) if m[2] == "ar" else (pt, m[1])

    m = re.fullmatch(r"i(\d+)\.(ar|en)", rest)
    if m:
        k = int(m[1])
        if m[2] == "ar":
            inter = p.get("interludes") or []
            return (inter[k], "text") if k < len(inter) else None
        inter = pt.get("interludes") or []
        return (inter, k) if k < len(inter) else None

    m = re.fullmatch(r"n(\d+)", rest)
    if m:
        k, notes = int(m[1]), t.get("notes") or []
        return (notes[k], "note") if k < len(notes) else None
    return None


def poem_index(data):
    return {p["source_lines"][0]: p for p in data["poems"] if "embedded_in" not in p}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    newest = {}
    for row in fetch_edits():
        if row["loc"] not in newest or row["rev"] > newest[row["loc"]]["rev"]:
            newest[row["loc"]] = row

    data = json.loads(DATA.read_text(encoding="utf-8"))
    poems = poem_index(data)
    changes, unknown = [], []
    for loc, row in newest.items():
        place = resolve(data, poems, loc)
        if place is None:
            unknown.append(loc)
        elif place[0][place[1]] != row["text"]:
            changes.append((loc, place, row["text"]))
    if unknown:
        sys.exit(f"Edits name passages that don't exist, nothing written: {unknown[:10]}")

    print(f"{len(newest)} edited passages, {len(changes)} differ from the JSON")
    for loc, _, _ in changes:
        print("  ", loc)
    if changes and not args.dry_run:
        for _, (container, key), text in changes:
            container[key] = text
        DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
