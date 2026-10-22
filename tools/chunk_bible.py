"""Usage: python tools/chunk_bible.py <bible-export.md> data/chunks.jsonl

Split The Comprehensive Squirrel Bible (markdown export) into retrieval chunks.

Rules
- Unit of retrieval = a chapter ("## N. Title") or an unnumbered sub-chapter.
- Chapters longer than MAX_WORDS are split at ### boundaries; each piece keeps
  the chapter title as context. Tables and lists are never split mid-way.
- Formulary: each drug entry is one chunk (never split), because a dose table
  cut in half is dangerous. "## **Evidence: ...**" style lines inside entries
  are treated as body text, not new entries.
- Metadata flags let the server filter by audience (public vs rehabber).
"""
import json, re, sys
from pathlib import Path

MAX_WORDS = 1400

src = Path(sys.argv[1]).read_text(encoding="utf-8")

# Repair emoji that were double-encoded in the export (e.g. "ð\x9f\x94´" -> 🔴).
def _byte(ch):
    try:
        return ch.encode("cp1252")[0]
    except UnicodeEncodeError:
        return ord(ch)            # latin-1 range control chars
def _fix(m):
    try:
        return bytes(_byte(c) for c in m.group(0)).decode("utf-8")
    except (UnicodeDecodeError, ValueError):
        return m.group(0)
src = re.sub(r"ð[\u0080-\u00ff\u0152-\u2122]{3}", _fix, src)
lines = src.splitlines()

def clean(h):
    h = re.sub(r"^#+\s*", "", h)
    h = h.replace("**", "").replace("\\", "").strip()
    return h

def words(t):
    return len(re.findall(r"\S+", t))

FORMULARY_START = next(i for i, l in enumerate(lines) if l.startswith("# **APPENDIX A: VETERINARY FORMULARY"))

def is_formulary_entry_heading(l):
    if not l.startswith("## "):
        return False
    t = clean(l)
    if not t or set(t) <= {"_"}:
        return False
    if ":" in t:           # "Evidence: [A]...", "Drug Class / Type: ..." etc.
        return False
    # entry headings are drug names in caps, optionally "(Brand)" in mixed case
    head = t.split("(")[0]
    letters = [c for c in head if c.isalpha()]
    return bool(letters) and sum(c.isupper() for c in letters) / len(letters) > 0.8 or t.startswith("Quick Reference")

# ---- pass 1: segment into sections ----------------------------------------
sections = []   # dicts: part, chapter, title, start, end
part = "Front Matter"
cur = None

def open_section(i, title, chapter_num, kind):
    global cur
    if cur:
        cur["end"] = i
        sections.append(cur)
    cur = dict(part=part, chapter_num=chapter_num, title=title, start=i, kind=kind, parent=None)

last_numbered = None
for i, l in enumerate(lines):
    in_form = i >= FORMULARY_START
    if l.startswith("# "):
        t = clean(l)
        if t.startswith("Veterinary Formulary"):
            continue                       # sub-title, not a new part
        part = t
        open_section(i, t, None, "part_intro")
        last_numbered = None
        continue
    if l.startswith("## "):
        if in_form:
            if is_formulary_entry_heading(l):
                open_section(i, clean(l), None, "formulary")
            continue
        t = clean(l)
        m = re.match(r"^(\d+)\.\s*(.*)", t)
        if m:
            last_numbered = (int(m.group(1)), m.group(2))
            open_section(i, m.group(2), int(m.group(1)), "chapter")
        else:
            open_section(i, t, last_numbered[0] if last_numbered else None, "chapter")
            if last_numbered:
                cur["parent"] = last_numbered[1]
if cur:
    cur["end"] = len(lines)
    sections.append(cur)

# ---- pass 2: build chunks ---------------------------------------------------
def flags(text, title):
    return dict(
        clinical="⚕" in text or "⚕" in title,
        provisional=bool(re.search(r"PROVISIONAL|awaiting veterinarian", text, re.I)),
        has_dosing=bool(re.search(r"mg/kg|\bmL\b.*\|", text)),
        evidence=sorted(set(re.findall(r"\\?\[(A|B|C|VET|PROVISIONAL)\\?\]", text))),
    )

def strip_for_embedding(t):
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1", t)   # keep link text only
    t = t.replace("**", "").replace("\\", "")
    return t

chunks = []
def emit(sec, body_lines, sub=None):
    raw = "\n".join(body_lines).strip()
    if words(raw) < 8:
        return
    title = sec["title"]
    label = f"Ch. {sec['chapter_num']} — " if sec["chapter_num"] and sec["kind"] == "chapter" else ""
    heading = f"{label}{sec['parent'] + ' › ' if sec['parent'] else ''}{title}{' › ' + sub if sub else ''}"
    f = flags(raw, title)
    if sec["kind"] == "formulary" or sec["part"].startswith("PART V"):
        f["clinical"] = True
    chunks.append(dict(
        id=f"c{len(chunks)+1:04d}",
        part=sec["part"],
        chapter_num=sec["chapter_num"],
        heading=heading,
        kind=sec["kind"],
        drug=title if sec["kind"] == "formulary" and not title.startswith("Quick") else None,
        audience="rehabber" if (f["clinical"] or f["has_dosing"]) else "public",
        source_lines=[sec["start"] + 1, sec["end"]],
        words=words(raw),
        **f,
        text=raw,
        embed_text=f"{heading}\n\n{strip_for_embedding(raw)}",
    ))

for sec in sections:
    body = lines[sec["start"]:sec["end"]]
    if sec["kind"] == "formulary" or words("\n".join(body)) <= MAX_WORDS:
        emit(sec, body)
        continue
    # split long chapter at ### boundaries, then pack consecutive pieces up to MAX_WORDS
    pieces, curp, cur_title = [], [], None
    for l in body:
        if l.startswith("### ") and curp:
            pieces.append((cur_title, curp)); curp = []
            cur_title = clean(l)
        elif l.startswith("### "):
            cur_title = clean(l)
        curp.append(l)
    pieces.append((cur_title, curp))
    pack, pack_title = [], None
    for t, p in pieces:
        if pack and words("\n".join(pack + p)) > MAX_WORDS:
            emit(sec, pack, pack_title); pack, pack_title = [], None
        if pack_title is None:
            pack_title = t
        pack += p
    if pack:
        emit(sec, pack, pack_title)

out = Path(sys.argv[2])
with out.open("w", encoding="utf-8") as fh:
    for c in chunks:
        fh.write(json.dumps(c, ensure_ascii=False) + "\n")

# ---- report ------------------------------------------------------------------
tot = words(src)
cov = sum(c["words"] for c in chunks)
print(f"source words {tot}  chunked words {cov}  ({cov/tot:.1%})")
print(f"chunks {len(chunks)}  formulary entries {sum(c['kind']=='formulary' for c in chunks)}")
print(f"rehabber-only {sum(c['audience']=='rehabber' for c in chunks)}  public {sum(c['audience']=='public' for c in chunks)}")
print(f"provisional {sum(c['provisional'] for c in chunks)}")
ws = sorted(c["words"] for c in chunks)
print(f"words/chunk min {ws[0]} median {ws[len(ws)//2]} max {ws[-1]}")
for c in sorted(chunks, key=lambda c: -c["words"])[:6]:
    print(f"  big: {c['words']:5d}  {c['heading'][:90]}")
