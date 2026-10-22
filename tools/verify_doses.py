"""Check doses.py against every weight table in the Bible's formulary.

For each mapped table column, recompute the value from weight × dose/kg ÷ concentration
and compare to the printed number. A printed value passes if it equals the computed value
after rounding to the printed number of decimals (±1 in the last digit allowed).
"""
import json, re, sys
from pathlib import Path
DATA = Path(__file__).resolve().parent.parent / "data"
from doses import D, TEXT_ONLY, calc

chunks = [json.loads(l) for l in open(DATA / "chunks.jsonl", encoding="utf-8")]
form = {c["drug"]: c for c in chunks if c["kind"] == "formulary" and c["drug"]}

# coverage
named = {r["drug"] for r in D} | set(TEXT_ONLY)
missing = [d for d in form if d not in named]
unknown = [d for d in named if d not in form]
print("formulary entries:", len(form), "| covered:", len(named & set(form)))
if missing: print("NOT COVERED:", missing)
if unknown: print("NAME MISMATCH:", unknown)

def tables(text):
    L = text.splitlines(); out = []; i = 0
    while i < len(L):
        if L[i].startswith("|"):
            j = i
            while j < len(L) and L[j].startswith("|"): j += 1
            rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in L[i:j]]
            out.append(rows[2:]); i = j
        else: i += 1
    return out

def R(drug, label):
    return next(r for r in D if r["drug"] == drug and r["regimen"] == label)

# (drug, table index, column, regimen label, output: "mL" or "amt")
MAP = [
 ("ALBON (Sulfadimethoxine)", 0, 2, "Day 1 loading dose", "mL"),
 ("ALBON (Sulfadimethoxine)", 1, 2, "Maintenance (day 2 onward)", "mL"),
 ("AMOXICILLIN / CLAVAMOX (Amoxicillin/Clavulanate)", 0, 1, "Standard", "mL"),
 ("FISH MOX (Amoxicillin — OTC, without Clavulanate)", 1, 2, "Standard", "mL"),
 ("BAYTRIL (Enrofloxacin)", 0, 2, "Standard 10 mg/kg/day, once daily", "mL"),
 ("BAYTRIL (Enrofloxacin)", 0, 3, "10 mg/kg/day split BID", "mL"),
 ("DOXYCYCLINE (Vibramycin)", 0, 2, "10 mg/kg/day once daily", "mL"),
 ("DOXYCYCLINE (Vibramycin)", 0, 3, "10 mg/kg/day split BID (preferred)", "mL"),
 ("METRONIDAZOLE (Flagyl)", 0, 2, "Oral", "mL"),
 ("NUFLOR (Florfenicol)", 0, 2, "Working solution", "mL"),
 ("PANACUR (Fenbendazole)", 0, 2, "Roundworm / hookworm / whipworm", "mL"),
 ("PANACUR (Fenbendazole)", 1, 2, "Giardia", "mL"),
 ("PONAZURIL (Marquis)", 1, 2, "50 mg/mL compound", "mL"),
 ("IVERMECTIN", 0, 2, "Protocol A — conservative", "mL"),
 ("IVERMECTIN", 0, 3, "Protocol A — confirmed mange", "mL"),
 ("IVERMECTIN", 1, 2, "Protocol B — demodectic mange", "mL"),
 ("GABAPENTIN", 0, 3, "Standard", "mL"),
 ("MELOXICAM (Metacam)", 1, 2, "Set A 0.2 mg/kg — cat Metacam", "mL"),
 ("MELOXICAM (Metacam)", 2, 2, "Set A 0.2 mg/kg — dog Metacam", "mL"),
 ("MELOXICAM (Metacam)", 3, 2, "Set B 1 mg/kg (BSAVA) — cat Metacam", "mL"),
 ("MELOXICAM (Metacam)", 4, 2, "Set B 1 mg/kg (BSAVA) — dog Metacam", "mL"),
 ("TRAMADOL", 0, 1, "Standard", "mL"),
 ("MARBOFLOXACIN (Zeniquin) — Oral Suspension", 0, 2, "Compounded 10 mg/mL [VET]", "mL"),
 ("SUCRALFATE (Carafate)", 0, 1, "Standard", "mL"),
 ("FAMOTIDINE (Pepcid)", 0, 1, "Standard", "mL"),
 ("ACTIVATED CHARCOAL (Toxiban)", 0, 1, "10 mL/kg (2 g/kg)", "mL"),
 ("CARPROFEN (Rimadyl)", 0, 2, "BSAVA", "amt"),
 ("BUTORPHANOL", 0, 2, "Low 0.2 mg/kg", "amt"),
 ("BUTORPHANOL", 0, 3, "Mid 1 mg/kg", "amt"),
 ("BUTORPHANOL", 0, 4, "High 2 mg/kg", "amt"),
 ("VITAMIN C (Ascorbic Acid)", 1, 1, "Maintenance 20 mg/kg/day", "amt"),
 ("VITAMIN C (Ascorbic Acid)", 1, 2, "Treatment 50 mg/kg/day", "amt"),
 ("VITAMIN D₃ (Cholecalciferol)", 1, 1, "Low 200 IU/kg/day", "amt"),
 ("VITAMIN D₃ (Cholecalciferol)", 1, 2, "High 400 IU/kg/day", "amt"),
]

num = lambda s: re.search(r"(\d+(?:\.\d+)?)", s.replace("\\", ""))
checked = fails = 0
problems = []
for drug, ti, col, label, kind in MAP:
    r = R(drug, label)
    rows = tables(form[drug]["text"])[ti]
    for row in rows:
        w = re.match(r"\s*(\d+)\s*g\b", row[0].replace("*", ""))
        if not w or col >= len(row): continue
        m = num(row[col].replace("*", ""))
        if not m: continue
        wg = int(w.group(1)); printed = float(m.group(1))
        dec = len(m.group(1).split(".")[1]) if "." in m.group(1) else 0
        amt, ml = calc(r, wg)
        val = ml if kind == "mL" else amt
        tol = 10 ** -dec * 1.01      # within one unit of the last printed digit
        checked += 1
        if abs(printed - val) > tol:
            fails += 1
            problems.append((drug, label, wg, row[col], round(val, 4)))

print(f"table values checked: {checked} | mismatches: {fails}")
for p in problems:
    print(f"  ✗ {p[0][:38]:38s} | {p[1][:34]:34s} | {p[2]:4d} g | Bible: {p[3][:40]:40s} | calc: {p[4]}")
