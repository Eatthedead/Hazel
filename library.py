"""Hazel's library: the Comprehensive Squirrel Bible split into sections, plus
the deterministic dose calculator.

Data files (rebuilt with tools/chunk_bible.py and tools/doses.py):
  data/chunks.jsonl  one Bible section per line, with audience/clinical flags
  data/doses.json    structured formulary regimens (verified by tools/verify_doses.py)
  data/field_notes.jsonl  Hazel's original hand-written notes (tools/build_field_notes.py)
"""
import json, math, re
from collections import Counter
from pathlib import Path

DATA = Path(__file__).parent / "data"

CHUNKS = [json.loads(l) for l in (DATA / "chunks.jsonl").open(encoding="utf-8")]
_notes = DATA / "field_notes.jsonl"          # Hazel's original notes — fill small gaps in the Bible
if _notes.exists():
    CHUNKS += [json.loads(l) for l in _notes.open(encoding="utf-8")]
BY_ID = {c["id"]: c for c in CHUNKS}
_DOSES = json.loads((DATA / "doses.json").read_text(encoding="utf-8"))
REGIMENS = _DOSES["regimens"]

# Which sections each audience may read.
#   goodsam  -> public sections only
#   rehabber -> everything (website rehabber mode; dosing still withheld by prompt rule)
#   app      -> everything + dose calculator (Release Ready)
def allowed(chunk, mode):
    return mode != "goodsam" or chunk["audience"] == "public"


# ---------------------------------------------------------------- search (BM25)
_WORD = re.compile(r"[a-z0-9]+")
_STOP = set("""a an and are as at be but by can do does for from has have how i if in into is it its
my no not of on or our so that the their then there these they this to was we what when where which
who why will with you your""".split())

def _stem(w):
    for suf in ("ing", "ies", "es", "s"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w

def _tok(text):
    return [_stem(w) for w in _WORD.findall(text.lower()) if w not in _STOP]

_DOCS = [_tok(c["embed_text"]) for c in CHUNKS]
_HEAD = [_tok(c["heading"]) for c in CHUNKS]
_DF = Counter(w for d in _DOCS for w in set(d))
_N = len(_DOCS)
_AVG = sum(map(len, _DOCS)) / _N

def search(query, mode, k=6):
    q = _tok(query)
    scores = []
    for i, (d, h) in enumerate(zip(_DOCS, _HEAD)):
        c = CHUNKS[i]
        if not allowed(c, mode):
            continue
        tf = Counter(d); hs = set(h); s = 0.0
        for w in q:
            if w not in tf:
                continue
            idf = math.log(1 + (_N - _DF[w] + 0.5) / (_DF[w] + 0.5))
            f = tf[w]
            s += idf * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * len(d) / _AVG))
            if w in hs:
                s += 2 * idf          # a match in the heading is a strong signal
        if s:
            scores.append((s, c))
    scores.sort(key=lambda x: -x[0])
    return [dict(id=c["id"], heading=c["heading"], clinical=c["clinical"],
                 provisional=c["provisional"], preview=c["text"][:300])
            for _, c in scores[:k]]


def read_sections(ids, mode):
    out = []
    for i in ids[:4]:                     # cap per call so context stays lean
        c = BY_ID.get(i)
        if not c:
            out.append(dict(id=i, error="no such section")); continue
        if not allowed(c, mode):
            out.append(dict(id=i, error="this section is for rehabbers only")); continue
        out.append(dict(id=i, heading=c["heading"], provisional=c["provisional"],
                        evidence=c["evidence"], text=c["text"]))
    return out


def table_of_contents(mode):
    lines, part = [], None
    for c in CHUNKS:
        if not allowed(c, mode):
            continue
        if c["part"] != part:
            part = c["part"]; lines.append(f"\n{part}")
        flag = " ⚕" if c["clinical"] else ""
        lines.append(f"  {c['id']}  {c['heading'][:110]}{flag}")
    return "\n".join(lines).strip()


# ---------------------------------------------------------------- dose calculator
def list_regimens(drug_query=""):
    q = drug_query.lower()
    return [dict(drug=r["drug"], regimen=r["regimen"], kind=r["kind"])
            for r in REGIMENS if q in r["drug"].lower()]

def calculate_dose(drug, regimen, weight_g, concentration_mg_per_mL=None):
    """Exact arithmetic from the formulary. Never let the model do this math."""
    try:
        weight_g = float(weight_g)
    except (TypeError, ValueError):
        return dict(error="weight_g must be a number of grams")
    if not 5 <= weight_g <= 1500:
        return dict(error=f"{weight_g} g is outside the range this calculator accepts (5–1500 g). "
                          "Re-check the weight.")
    matches = [r for r in REGIMENS if r["drug"].lower() == drug.lower() and r["regimen"].lower() == regimen.lower()]
    if not matches:
        return dict(error="Unknown drug/regimen. Use list_regimens to get exact names.",
                    options=list_regimens(drug.split(" ")[0]))
    r = matches[0]
    amount = r["dose_per_kg"] * weight_g / 1000
    conc = concentration_mg_per_mL or r["concentration_mg_per_mL"]
    res = dict(drug=r["drug"], regimen=r["regimen"], weight_g=weight_g,
               dose_per_kg=f"{r['dose_per_kg']} {r['unit']}/kg" + ("/day" if r["per"] == "day" else ""),
               amount=f"{amount:.3g} {r['unit']}" + (" per day" if r["per"] == "day" else " per dose"),
               frequency=r["frequency"], route=r["route"], notes=r["notes"], flags=r["flags"])
    if conc:
        ml = amount / conc
        res["concentration"] = f"{conc} mg/mL"
        res["volume"] = f"{ml:.3f} mL per dose"
        if ml < 0.02:
            res["warning"] = ("Volume is under 0.02 mL and can't be measured accurately with a "
                              "standard syringe. Use the dilution described in this drug's formulary "
                              "entry, or ask your vet for a dilution, and recalculate with the new concentration.")
    elif r["kind"] == "mg_only":
        res["note"] = "Concentration depends on your product/vial — give concentration_mg_per_mL to get a volume."
    return res
