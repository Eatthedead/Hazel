"""Usage: python tools/build_field_notes.py
Splits data/field_notes.md (Hazel's original quick-reference notes) into library
sections at data/field_notes.jsonl. The Bible stays primary; these fill small gaps."""
import json, re
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
MAX = 900
md = (DATA / "field_notes.md").read_text(encoding="utf-8")
out = []
for sec in re.split(r"\n(?=## )", md)[1:]:
    title = sec.splitlines()[0].lstrip("# ").strip()
    blocks, pack = re.split(r"\n\s*\n", sec.split("\n", 1)[1].strip()), []
    def emit(pack):
        text = "\n\n".join(pack).strip()
        n = sum(1 for c in out if c["heading"].startswith("Field Notes — " + title)) + 1
        heading = f"Field Notes — {title}" + (f" (part {n})" if n > 1 or len(text.split()) >= MAX else "")
        out.append(dict(id=f"f{len(out)+1:03d}", part="HAZEL'S ORIGINAL FIELD NOTES", chapter_num=None,
                        heading=heading, kind="field_notes", drug=None, audience="rehabber",
                        words=len(text.split()), clinical=False, provisional=False, has_dosing=False,
                        evidence=[], text=text, embed_text=f"{heading}\n\n{text}"))
    for b in blocks:
        if pack and len(" ".join(pack + [b]).split()) > MAX:
            emit(pack); pack = []
        pack.append(b)
    if pack: emit(pack)
with (DATA / "field_notes.jsonl").open("w", encoding="utf-8") as f:
    for c in out: f.write(json.dumps(c, ensure_ascii=False) + "\n")
print(len(out), "field-note sections,", sum(c["words"] for c in out), "words")
