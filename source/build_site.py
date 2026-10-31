"""Build the static facing-text website from translated_manazil.json into the repo root.

    python source/build_site.py

One page per chapter plus the muqaddima and the colophon. Each verse and prose
paragraph is a row: English on the left, Arabic on the right. review.html lists
the translator's notes on the verse, sorted so the likeliest problems come first.

Editable text carries a data-loc (see bake_edits.py for what each form means).
edit.js overlays the latest edits from Supabase on it when a page loads.
"""

import html
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "translated_manazil.json"
SITE = ROOT.parent

SOURCE_URL = ("https://github.com/OpenITI/RELEASE/blob/master/data/0584IbnMunqidhShayzari/"
              "0584IbnMunqidhShayzari.ManazilWaDiyar/0584IbnMunqidhShayzari.ManazilWaDiyar.Shamela0005416-ara1.completed")
CREDIT = "Website by Dr. Nathaniel A. Miller"
DESCRIPTION = ("Usama ibn Munqidh's al-Manazil wa-l-Diyar (Abodes and Dwellings): "
               "the Arabic text facing a draft English translation.")

# English titles for the chapter headings.
CHAPTER_EN = {
    1: "On encampments (manāzil)",
    2: "On dwellings (diyār)",
    3: "On haunts (maghānī)",
    4: "On ruins (aṭlāl)",
    5: "On spring camps (rabʿ)",
    6: "On dung-marked traces (diman)",
    7: "On traces (rasm)",
    8: "On remains (āthār)",
    9: "On residences, stopping places, haunts, landmarks, waymarks and courtyards",
    10: "On the land (arḍ)",
    11: "On homelands (awṭān)",
    12: "On cities (mudun)",
    13: "On countries (bilād)",
    14: "On the house (dār)",
    15: "On the house (bayt)",
    16: "On weeping for family and brothers",
}

# Astra was told to note everything it was unsure of, so the notes are sorted by
# keyword into a reading order. First match wins, so these overlap on purpose.
TEXT_PROBLEM = re.compile(r"corrupt|garbled|misprint|typograph|\btypo\b|\bOCR\b|scribal|copyist|textual error"
                          r"|transcription|defective|lacuna|emend|erroneous|spelling error|printing error"
                          r"|displaced|misplaced|disrupted|hemistich division|rather than a verse", re.I)
UNCLEAR = re.compile(r"unclear|obscure|not understand|puzzling", re.I)
NAMES = re.compile(r"place[- ]?name|proper name|personal name|toponym|unidentified|identif|\bvocaliz|location", re.I)
UNSURE = re.compile(r"uncertain|tentativ|conjectur|difficult", re.I)

NOTE_GROUPS = [
    ("text", "The Arabic may be wrong",
     "The translator suspected a misprint, a corrupt word, or a misplaced line division, then translated its best guess."),
    ("meaning", "The meaning is unclear",
     "The translator could not settle what the words mean or how they fit together."),
    ("names", "Names and places",
     "A person or place the translator could not identify, or whose name it had to vocalize by guesswork."),
    ("readings", "One reading chosen among several",
     "The Arabic allows more than one sense, usually because it is unvocalized, and the translator chose one."),
]


def note_group(note):
    if TEXT_PROBLEM.search(note):
        return "text"
    if UNCLEAR.search(note):
        return "meaning"
    if NAMES.search(note):
        return "names"
    return "meaning" if UNSURE.search(note) else "readings"


CSS = """
:root {
  --paper: #edf0ec;
  --ink: #1d2a2e;
  --muted: #5f6e6b;
  --rule: #c6cec9;
  --accent: #2e6b62;
  --gloss: #e2e7e3;
  --en: "Gentium Book Plus", "Gentium Plus", Georgia, serif;
  --ar: "Amiri", "Traditional Arabic", "Times New Roman", serif;
}
* { box-sizing: border-box; }
html { background: var(--paper); color: var(--ink); }
body { margin: 0; font-family: var(--en); font-size: 1.0625rem; line-height: 1.6; }
a { color: var(--accent); text-underline-offset: .18em; }
a:focus-visible, summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
[lang="ar"] { font-family: var(--ar); font-size: 1.3rem; line-height: 1.9; }

/* Top bar */
.bar { position: sticky; top: 0; z-index: 2; background: var(--paper); border-bottom: 1px solid var(--rule); }
.bar-inner { max-width: 72rem; margin: 0 auto; padding: .55rem 1.25rem; display: flex; align-items: center;
  justify-content: space-between; gap: 1rem; }
.bar .home { font-family: var(--ar); font-size: 1.35rem; text-decoration: none; color: var(--ink); }
.bar details { position: relative; }
.bar summary { cursor: pointer; list-style: none; color: var(--accent); }
.bar summary::-webkit-details-marker { display: none; }
.bar details[open] summary { text-decoration: underline; }
.menu { position: absolute; right: 0; top: 2rem; width: min(30rem, 90vw); max-height: 75vh; overflow: auto;
  background: var(--paper); border: 1px solid var(--rule); padding: .5rem 0; box-shadow: 0 8px 24px rgba(29,42,46,.12); }
.menu a { display: grid; grid-template-columns: 1fr auto; gap: 1rem; padding: .35rem 1rem; text-decoration: none; color: var(--ink); }
.menu a:hover, .menu a[aria-current] { background: var(--gloss); }
.menu .ar { font-family: var(--ar); font-size: 1.1rem; }

main { max-width: 72rem; margin: 0 auto; padding: 0 1.25rem 5rem; }

/* Home */
.hero { padding: 4.5rem 0 3rem; display: grid; grid-template-columns: 1fr 1fr; align-items: end; gap: 2rem;
  border-bottom: 1px solid var(--rule); }
.hero h1 { grid-column: 2; grid-row: 1; margin: 0; font-family: var(--ar); font-weight: 700;
  font-size: clamp(4rem, 11vw, 8.5rem); line-height: 1.1; text-align: right; }
.hero .en { grid-column: 1; grid-row: 1; padding-bottom: 1.4rem; }
.hero .en p { margin: 0; }
.hero .title-en { font-size: 1.9rem; font-style: italic; line-height: 1.25; }
.hero .author { color: var(--muted); margin-top: .5rem !important; }
.epigraph { display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; padding: 2rem 0; border-bottom: 1px solid var(--rule); }
.epigraph .en { font-style: italic; color: var(--muted); align-self: center; }
.about { max-width: 38rem; color: var(--muted); padding: 1.5rem 0 0; }
.credit { max-width: 38rem; color: var(--muted); margin: 0; }
.contents { list-style: none; margin: 2.5rem 0 0; padding: 0; }
.contents li a { display: grid; grid-template-columns: 2.5rem 1fr 1fr; gap: 1rem; align-items: baseline;
  padding: .7rem 0; border-bottom: 1px solid var(--rule); text-decoration: none; color: var(--ink); }
.contents li a:hover .t-en { text-decoration: underline; color: var(--accent); }
.contents .num { color: var(--muted); font-variant-numeric: oldstyle-nums; }
.contents .t-ar { font-family: var(--ar); font-size: 1.3rem; text-align: right; }
.contents .count { display: block; color: var(--muted); font-size: .9rem; }

/* Chapter */
.chapter-head { padding: 3.5rem 0 2rem; display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; align-items: end;
  border-bottom: 1px solid var(--rule); }
.chapter-head h1 { margin: 0; font-weight: 400; font-size: 1.9rem; line-height: 1.25; font-style: italic; }
.chapter-head .ar { font-family: var(--ar); font-size: clamp(2.2rem, 5vw, 3.4rem); line-height: 1.3; text-align: right; }
.chapter-head + .prose { margin-top: 2rem; }
.sub { display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; margin: 3.5rem 0 0; }
.sub h2 { margin: 0; font-family: var(--ar); font-weight: 400; font-size: 1.8rem; grid-column: 2; text-align: right; }

.poem { padding: 2.25rem 0; border-bottom: 1px solid var(--rule); scroll-margin-top: 4rem; }
.row { display: grid; grid-template-columns: 1fr 1fr; gap: 2.5rem; }
.row > * { min-width: 0; }
.prose { margin: 0 0 1.1rem; }
.prose p { margin: 0; }
.prose [lang="ar"] { text-align: justify; }
.meta { color: var(--muted); font-size: .9rem; margin-bottom: .6rem; }
.meta [lang="ar"] { font-size: 1.1rem; text-align: right; }
.meta a { color: var(--muted); }

.verses { margin: .4rem 0 1rem; }
.verse { padding: .15rem 0; }
.verse .en span { display: block; padding-left: 1.6rem; text-indent: -1.6rem; }
.verse .en .h2 { padding-left: 3.2rem; }
/* An Arabic bayt: the two hemistichs side by side, the second towards the left. */
.verse [lang="ar"] { display: grid; grid-template-columns: 1fr 1fr; column-gap: 1.5rem; }
.verse [lang="ar"] .h2 { text-align: left; }
.verse [lang="ar"] .h1:only-child { grid-column: 1 / -1; text-align: center; }

.toc { margin: 1.5rem 0 2rem; }
.toc-title { margin-bottom: .4rem; font-style: italic; }
.toc-title [lang="ar"] { font-style: normal; }
.toc ol { list-style: none; margin: 0; padding: 0; border-top: 1px solid var(--rule); }
.toc li a { padding: .3rem 0; border-bottom: 1px solid var(--rule); text-decoration: none; color: var(--ink); }
.toc li a:hover .en { color: var(--accent); text-decoration: underline; }
.toc .n { color: var(--muted); font-variant-numeric: oldstyle-nums; }
.toc [lang="ar"] { font-size: 1.15rem; }

.gloss { background: var(--gloss); padding: .5rem .8rem; margin: .5rem 0 .7rem; font-size: .95rem; }
.gloss [lang="ar"] { font-size: 1.15rem; }

details.notes { margin-top: .8rem; font-size: .92rem; color: var(--muted); }
details.notes summary { cursor: pointer; color: var(--accent); width: fit-content; }
details.notes ul { margin: .5rem 0 0; padding-left: 1.2rem; max-width: 40rem; }

.pager { display: flex; justify-content: space-between; gap: 1rem; padding: 2.5rem 0 0; }
.pager a { text-decoration: none; }
.pager .ar { font-family: var(--ar); font-size: 1.15rem; }
.missing { color: var(--muted); font-style: italic; }

.site-foot { border-top: 1px solid var(--rule); color: var(--muted); font-size: .9rem; }
.site-foot-inner { max-width: 72rem; margin: 0 auto; padding: 1.25rem; display: flex; flex-wrap: wrap;
  justify-content: space-between; gap: .25rem 2rem; }

/* Review page */
.review-intro { max-width: 40rem; padding-top: 1.5rem; }
.review-intro p { margin: 0 0 .8rem; }
.review-jump { list-style: none; margin: 1.2rem 0 0; padding: 0; border-top: 1px solid var(--rule); }
.review-jump a { display: flex; justify-content: space-between; gap: 1rem; padding: .4rem 0;
  border-bottom: 1px solid var(--rule); text-decoration: none; }
.review-jump .count { color: var(--muted); font-variant-numeric: oldstyle-nums; white-space: nowrap; }
.review-group { margin-top: 3.5rem; scroll-margin-top: 4rem; }
.review-group > h2 { margin: 0; font-weight: 400; font-style: italic; font-size: 1.6rem; }
.review-group > p { margin: .3rem 0 0; color: var(--muted); max-width: 40rem; }
.flag { padding: 1.4rem 0; border-bottom: 1px solid var(--rule); }
.flag-where { display: block; margin-bottom: .4rem; color: var(--muted); font-size: .9rem; }
.flag-note { margin: .5rem 0 0; font-size: .95rem; max-width: 40rem; }

/* Editing */
.bar-tools { display: flex; align-items: center; gap: 1.25rem; }
.link-button { background: none; border: 0; padding: 0; font: inherit; color: var(--accent); cursor: pointer;
  text-decoration: underline; text-underline-offset: .18em; }
.verse { scroll-margin-top: 4rem; }
body.editing [data-loc] { cursor: text; }
body.editing [data-loc]:hover { background: var(--gloss); }
body.editing [data-loc]:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
body.editing .has-comment { border-bottom: 2px dotted var(--accent); }
.stale::after { content: " Arabic changed"; color: var(--accent); font-size: .78rem; font-style: italic; white-space: nowrap; }
.edit-dialog { width: min(40rem, calc(100vw - 2rem)); max-height: calc(100vh - 2rem); overflow: auto;
  background: var(--paper); color: var(--ink); border: 1px solid var(--rule); padding: 1.25rem; }
.edit-dialog::backdrop { background: rgba(29,42,46,.4); }
.edit-dialog h2 { margin: 0 0 .8rem; font-weight: 400; font-style: italic; font-size: 1.25rem; }
.edit-dialog label { display: block; margin: .6rem 0 .2rem; color: var(--muted); font-size: .9rem; }
.edit-dialog textarea, .edit-dialog input { width: 100%; padding: .5rem .6rem; color: var(--ink); background: #fff;
  border: 1px solid var(--rule); font-family: var(--en); font-size: 1rem; line-height: 1.5; }
.edit-dialog textarea[lang="ar"] { font-family: var(--ar); font-size: 1.3rem; line-height: 1.8; }
.edit-actions { display: flex; justify-content: flex-end; align-items: center; gap: 1rem; margin-top: .7rem; }
.primary { background: var(--accent); color: #fff; border: 0; padding: .4rem 1rem; font: inherit; cursor: pointer; }
.primary:disabled { opacity: .6; cursor: default; }
.edit-error { margin: .5rem 0 0; color: #9a2f22; font-size: .92rem; }
.edit-error:empty { display: none; }
.edit-also { margin: .9rem 0 0; font-size: .92rem; color: var(--muted); }
.edit-section { margin-top: .9rem; border-top: 1px solid var(--rule); padding-top: .6rem; font-size: .95rem; }
.edit-section summary { cursor: pointer; color: var(--accent); width: fit-content; }
.edit-history, .edit-comments { list-style: none; margin: .5rem 0; padding: 0; }
.edit-history li, .edit-comments li { padding: .45rem 0; border-bottom: 1px solid var(--rule); }
.edit-history-who { color: var(--muted); font-size: .85rem; }
.edit-history-text { display: block; }
.edit-help { margin: 0; padding-left: 1.2rem; }
.edit-help li { margin-bottom: .5rem; }
.edit-toast { position: fixed; left: 50%; bottom: 1.5rem; transform: translateX(-50%); z-index: 3; max-width: calc(100vw - 2rem);
  padding: .5rem 1rem; background: var(--ink); color: var(--paper); font-size: .95rem; }

@media (max-width: 760px) {
  .hero, .epigraph, .chapter-head, .row, .sub { grid-template-columns: 1fr; gap: .4rem; }
  .hero h1, .hero .en, .sub h2 { grid-column: 1; grid-row: auto; }
  .hero { padding-top: 2.5rem; }
  /* Arabic first, then English, on narrow screens. */
  .row > [lang="ar"], .epigraph > [lang="ar"], .chapter-head > .ar { order: -1; }
  .verse { padding: .4rem 0; }
  .contents li a { grid-template-columns: 2rem 1fr; }
  .contents .t-ar { grid-column: 2; text-align: right; }
  /* Stacked rows: the Arabic line already carries the chapter number. */
  .toc .en .n { display: none; }
}
@media (max-width: 480px) {
  /* Too narrow for hemistichs side by side: stack them, the second indented. */
  .verse [lang="ar"] { grid-template-columns: 1fr; }
  .verse [lang="ar"] .h2 { text-align: right; padding-right: 1.6rem; }
}
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Amiri:wght@400;700'
         '&family=Gentium+Book+Plus:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">')

FAVICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="4" fill="#2e6b62"/>'
           '<path d="M9 26V15a7 7 0 0 1 14 0v11z" fill="#edf0ec"/></svg>')

FOOTER = (f'<footer class="site-foot"><div class="site-foot-inner"><a href="{SOURCE_URL}">Arabic source text (OpenITI)</a>'
          f'<span>{CREDIT}</span></div></footer>')

e = html.escape


def chapter_number(name):
    m = re.match(r"\s*(\d+)\s*-", name or "")
    return int(m.group(1)) if m else None


def strip_number(name):
    return re.sub(r"^\s*\d+\s*-\s*", "", name or "")


def page(title, body, nav, edit_page="*", footer=FOOTER, base=""):
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">{base}'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{e(title)}</title><meta name="description" content="{e(DESCRIPTION)}">'
            f'<meta property="og:type" content="website"><meta property="og:title" content="{e(title)}">'
            f'<meta property="og:description" content="{e(DESCRIPTION)}"><meta name="theme-color" content="#edf0ec">'
            f'<link rel="icon" href="favicon.svg" type="image/svg+xml">{FONTS}<link rel="stylesheet" href="style.css">'
            f'<script src="edit.js" defer></script></head><body data-edit-page="{e(edit_page)}">'
            f'{nav}<main>{body}</main>{footer}</body></html>')


def nav_bar(chapters, current=None):
    links = []
    for ch in chapters:
        cur = ' aria-current="page"' if ch["file"] == current else ""
        links.append(f'<a href="{ch["file"]}"{cur}><span>{e(ch["en"])}</span>'
                     f'<span class="ar" lang="ar" dir="rtl">{e(ch["ar"])}</span></a>')
    cur = ' aria-current="page"' if current == "review.html" else ""
    links.append(f'<a href="review.html"{cur}><span>Uncertain passages</span></a>')
    return (f'<header class="bar"><div class="bar-inner"><a class="home" href="index.html" lang="ar" dir="rtl">'
            f'المنازل والديار</a><div class="bar-tools"><span id="account"></span>'
            f'<details><summary>Chapters</summary><nav class="menu">{"".join(links)}'
            f'</nav></details></div></div></header>')


def prose_row(ar, en, loc, cls="prose"):
    en_html = f'<p data-loc="{loc}.en">{e(en)}</p>' if en else '<p class="missing">Not yet translated.</p>'
    return (f'<div class="row {cls}"><div class="en">{en_html}</div>'
            f'<div lang="ar" dir="rtl"><p data-loc="{loc}.ar">{e(ar)}</p></div></div>')


def verse_row(v, t, loc, anchored=False):
    ar_h2 = f'<span class="h2" data-loc="{loc}.h2.ar">{e(v["h2"])}</span>' if v.get("h2") else ""
    if t:
        en = f'<span class="h1" data-loc="{loc}.h1.en">{e(t["h1"])}</span>'
        if t.get("h2"):
            en += f'<span class="h2" data-loc="{loc}.h2.en">{e(t["h2"])}</span>'
    else:
        en = '<span class="missing">Not yet translated.</span>'
    row_id = f' id="{loc.replace(".", "-")}"' if anchored else ""
    return (f'<div class="row verse"{row_id}><div class="en">{en}</div>'
            f'<div lang="ar" dir="rtl"><span class="h1" data-loc="{loc}.h1.ar">{e(v["h1"])}</span>{ar_h2}</div></div>')


def also_attr(p):
    """The other places a repeated poem appears, for the editor's warning."""
    return f' data-also="{e(" ".join(p["_also"]))}"' if p.get("_also") else ""


def poem_html(p):
    t = p.get("translation") or {}
    pt = p.get("prose_translation") or {}
    en_verses = {v["n"]: v for v in (t.get("verses") or [])}
    anchor = f'p{p["source_lines"][0]}'
    parts = [f'<article class="poem" id="{anchor}"{also_attr(p)}>']

    meta_ar = []
    if p.get("poet") and p["poet"] != "؟":
        meta_ar.append(e(p["poet"]))
    if p.get("meter"):
        meta_ar.append("من " + e(p["meter"]))
    meta_en = []
    if p.get("id") is not None:
        shown_page = p.get("print_page") and not p.get("print_page_suspect")   # a suspect page is an OCR misread
        meta_en.append(f'Index {p["id"]}' + (f', page {p["print_page"]}' if shown_page else ""))
    if p.get("status") == "partial":
        meta_en.append("partial quotation")
    parts.append(f'<div class="row meta"><div><a href="#{anchor}">{"; ".join(meta_en) or "Poem"}</a></div>'
                 f'<div lang="ar" dir="rtl">{"، ".join(meta_ar)}</div></div>')

    if p.get("intro"):
        parts.append(prose_row(p["intro"], pt.get("intro"), f"{anchor}.intro"))

    glosses, inter_en = {}, pt.get("interludes") or []
    for k, x in enumerate(p.get("interludes") or []):
        en = inter_en[k] if k < len(inter_en) else None
        glosses.setdefault(x["after_verse"], []).append(prose_row(x["text"], en, f"{anchor}.i{k}", "gloss"))

    parts.append('<div class="verses">')
    for n, v in enumerate(p["verses"], 1):
        parts.append(verse_row(v, en_verses.get(n), f"{anchor}.v{n}", anchored=True))
        parts.extend(glosses.get(n, []))
    parts.append("</div>")

    if p.get("after"):
        parts.append(prose_row(p["after"], pt.get("after"), f"{anchor}.after"))

    notes = t.get("notes") or []
    if notes:
        items = "".join(f'<li>{"Line " + str(x["line"]) + ": " if x.get("line") else ""}'
                        f'<span data-loc="{anchor}.n{k}">{e(x["note"])}</span></li>'
                        for k, x in enumerate(notes))
        parts.append(f'<details class="notes"><summary>Translator\'s notes ({len(notes)})</summary>'
                     f'<ul>{items}</ul></details>')
    parts.append("</article>")
    return "".join(parts)


def section_html(section, poems_by_line, key):
    tr = {x["source_line"]: x for x in ((section.get("translation") or {}).get("paragraphs") or [])}
    out = []
    for par in section["paragraphs"]:
        if par["type"] == "poem":
            p = poems_by_line.get(par["source_line"])
            if p:
                out.append(poem_html(p))
        elif par["type"] == "contents":
            out.append(contents_html(par, tr.get(par["source_line"]) or {}))
        else:
            out.append(prose_row(par["text"], (tr.get(par["source_line"]) or {}).get("text"),
                                 f'{key}.s{par["source_line"]}'))
    return "".join(out)


def contents_html(par, tr):
    """The muqaddima's own table of chapters, each entry linking to its chapter page."""
    en = {i["n"]: i["text"] for i in tr.get("items") or []}
    rows = "".join(
        f'<li><a class="row" href="chapter-{i["n"]:02d}.html">'
        f'<span class="en"><span class="n">{i["n"]}.</span> {e(en.get(i["n"], ""))}</span>'
        f'<span lang="ar" dir="rtl"><span class="n">{i["n"]}</span> {e(i["text"])}</span></a></li>'
        for i in par["items"])
    return (f'<div class="toc"><div class="row toc-title"><div class="en">{e(tr.get("title") or "")}</div>'
            f'<div lang="ar" dir="rtl">{e(par["title"])}</div></div><ol>{rows}</ol></div>')


def review_html(chapters):
    """Every translator's note on the verse, grouped by note_group, in text order within each group."""
    groups = {key: [] for key, _, _ in NOTE_GROUPS}
    noted_poems = set()
    for ch in chapters:
        for p in ch["poems"]:
            t = p.get("translation") or {}
            en_verses = {v["n"]: v for v in (t.get("verses") or [])}
            anchor = f'p{p["source_lines"][0]}'
            for k, x in enumerate(t.get("notes") or []):
                noted_poems.add(anchor)
                line = x.get("line")
                where = f'{ch["en"]}, ' + (f"line {line}" if line else "whole poem")
                on_verse = line and line <= len(p["verses"])
                verse = verse_row(p["verses"][line - 1], en_verses.get(line), f"{anchor}.v{line}") if on_verse else ""
                link = f'{ch["file"]}#{anchor}' + (f"-v{line}" if on_verse else "")
                groups[note_group(x["note"])].append(
                    f'<div class="flag" data-page="{ch["file"]}"{also_attr(p)}>'
                    f'<a class="flag-where" href="{link}">{e(where)}</a>'
                    f'{verse}<p class="flag-note" data-loc="{anchor}.n{k}">{e(x["note"])}</p></div>')
    total = sum(map(len, groups.values()))
    jump = "".join(f'<li><a href="#{key}"><span>{e(title)}</span>'
                   f'<span class="count">{len(groups[key])} notes</span></a></li>'
                   for key, title, _ in NOTE_GROUPS)
    sections = "".join(f'<section class="review-group" id="{key}"><h2>{e(title)}</h2><p>{e(blurb)}</p>'
                       f'{"".join(groups[key])}</section>'
                       for key, title, blurb in NOTE_GROUPS)
    return (f'<header class="chapter-head"><h1>Uncertain passages</h1></header>'
            f'<div class="review-intro"><p>{total} notes the verse translator left on {len(noted_poems)} poems, '
            f'with the likeliest problems first. They were sorted by keyword, so some will be in the wrong group. '
            f'The prose was translated separately and has no notes, so its errors will not appear here.</p>'
            f'<ol class="review-jump">{jump}</ol></div>{sections}')


def pager(chapters, i):
    prev = chapters[i - 1] if i > 0 else None
    nxt = chapters[i + 1] if i + 1 < len(chapters) else None
    left = f'<a href="{prev["file"]}">Previous: {e(prev["en"])}</a>' if prev else "<span></span>"
    right = f'<a href="{nxt["file"]}">Next: {e(nxt["en"])}</a>' if nxt else "<span></span>"
    return f'<nav class="pager">{left}{right}</nav>'


def main():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    poems = [p for p in data["poems"] if "embedded_in" not in p]   # embedded ones repeat their host's verses
    muq_poems = {p["source_lines"][0]: p for p in poems if p["chapter"] == "المقدمة"}

    chapters = [{"file": "muqaddima.html", "ar": "المقدمة", "en": "Author's preface", "num": None, "poems": []}]
    for p in poems:
        if p["chapter"] == "المقدمة":
            continue
        if chapters[-1]["ar"] != strip_number(p["chapter"]):
            n = chapter_number(p["chapter"])
            chapters.append({"file": f"chapter-{n:02d}.html", "ar": strip_number(p["chapter"]),
                             "en": CHAPTER_EN.get(n, p["chapter"]), "num": n, "poems": []})
        chapters[-1]["poems"].append(p)
    chapters.append({"file": "colophon.html", "ar": "خاتمة الناسخ", "en": "Copyist's colophon", "num": None, "poems": []})

    places = {}
    for file, group in [("muqaddima.html", muq_poems.values())] + [(ch["file"], ch["poems"]) for ch in chapters]:
        for p in group:
            if p.get("id") is not None:
                places.setdefault(p["id"], []).append((p, f'{file}#p{p["source_lines"][0]}'))
    for copies in places.values():
        for p, here in copies:
            p["_also"] = [where for _, where in copies if where != here]

    if SITE.exists():
        shutil.rmtree(SITE / "assets", ignore_errors=True)
        for f in SITE.glob("*.html"):
            f.unlink()
    SITE.mkdir(exist_ok=True)
    (SITE / "style.css").write_text(CSS, encoding="utf-8")
    (SITE / ".nojekyll").write_text("", encoding="utf-8")
    (SITE / "favicon.svg").write_text(FAVICON, encoding="utf-8")

    for i, ch in enumerate(chapters):
        head = (f'<header class="chapter-head"><h1>{e(ch["en"])}</h1>'
                f'<div class="ar" lang="ar" dir="rtl">{e(ch["ar"])}</div></header>')
        if ch["file"] == "muqaddima.html":
            body = section_html(data["muqaddima"], muq_poems, "muqaddima")
        elif ch["file"] == "colophon.html":
            body = section_html(data["colophon"], {}, "colophon")
        else:
            parts, sub = [], None
            for p in ch["poems"]:
                if p.get("subchapter") != sub:
                    sub = p.get("subchapter")
                    if sub:
                        parts.append(f'<div class="sub"><h2 lang="ar" dir="rtl">{e(sub)}</h2></div>')
                parts.append(poem_html(p))
            body = "".join(parts)
        (SITE / ch["file"]).write_text(
            page(f'{ch["en"]}: al-Manazil wa-l-Diyar', head + body + pager(chapters, i),
                 nav_bar(chapters, ch["file"]), ch["file"]), encoding="utf-8")

    chapters[0]["poems"] = list(muq_poems.values())    # for the review page only; the muqaddima renders its own
    (SITE / "review.html").write_text(
        page("Uncertain passages: al-Manazil wa-l-Diyar", review_html(chapters), nav_bar(chapters, "review.html")),
        encoding="utf-8")
    chapters[0]["poems"] = []

    first = next(p for p in poems if p["chapter"] != "المقدمة")   # epigraph: the book's first poem
    v, tv = first["verses"][0], ((first.get("translation") or {}).get("verses") or [{}])[0]
    loc = f'p{first["source_lines"][0]}.v1'
    items = []
    for ch in chapters:
        num = ch["num"] if ch["num"] else ""
        count = f'<span class="count">{len(ch["poems"])} poems</span>' if ch["poems"] else ""
        items.append(f'<li><a href="{ch["file"]}"><span class="num">{num}</span>'
                     f'<span class="t-en">{e(ch["en"])}{count}</span>'
                     f'<span class="t-ar" lang="ar" dir="rtl">{e(ch["ar"])}</span></a></li>')
    home = (
        '<section class="hero"><h1 lang="ar" dir="rtl">المنازل والديار</h1>'
        '<div class="en"><p class="title-en">Abodes and Dwellings</p>'
        '<p class="author">Usama ibn Munqidh (d. 584/1188)</p></div></section>'
        f'<section class="epigraph" data-page="{chapters[1]["file"]}">'
        f'<p class="en"><span data-loc="{loc}.h1.en">{e(tv.get("h1", ""))}</span><br>'
        f'<span data-loc="{loc}.h2.en">{e(tv.get("h2", ""))}</span></p>'
        f'<p lang="ar" dir="rtl"><span data-loc="{loc}.h1.ar">{e(v["h1"])}</span><br>'
        f'<span data-loc="{loc}.h2.ar">{e(v["h2"])}</span></p></section>'
        f'<p class="about">Arabic text from the <a href="{SOURCE_URL}">Shamela edition by Mustafa Hijazi, via OpenITI</a>, '
        'with a draft machine '
        'translation: the verse by GPT-6 Astra, the prose by GPT-6.1 Sol. Scholars are correcting both the '
        'Arabic and the English, and their changes appear here as they are made. '
        '<a href="review.html">Start with the uncertain passages</a>.</p>'
        f'<p class="credit">{CREDIT}</p>'
        f'<ol class="contents">{"".join(items)}</ol>'
    )
    (SITE / "index.html").write_text(page("al-Manazil wa-l-Diyar", home, nav_bar(chapters), footer=""), encoding="utf-8")

    # Served for any bad path, however deep, so its links need the site root as their base.
    missing = ('<header class="chapter-head"><h1>Page not found</h1></header>'
               '<div class="review-intro"><p>There is nothing at this address. '
               '<a href="index.html">Go to the list of chapters</a>.</p></div>')
    (SITE / "404.html").write_text(
        page("Page not found: al-Manazil wa-l-Diyar", missing, nav_bar(chapters), "404.html",
             base='<base href="/manazil/">'), encoding="utf-8")
    print(f"Wrote {len(chapters) + 3} pages to {SITE}")


if __name__ == "__main__":
    main()
