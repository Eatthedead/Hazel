"""Structured dosing data for the Release Ready dose calculator.

Every number here is transcribed from Appendix A (Veterinary Formulary) of
The Comprehensive Squirrel Bible. verify_doses.py checks each regimen against
every weight table printed in the Bible.

volume_mL = dose_mg_per_kg * (weight_g / 1000) / concentration_mg_per_mL

kind:
  "volume"  -> calculator returns mg AND mL (concentration known)
  "mg_only" -> calculator returns mg (or IU); concentration set by vet/product
  "text"    -> no weight-based calculation; app shows the Bible entry verbatim
"""
import json
from pathlib import Path

D = []
def reg(drug, label, mg_per_kg, conc=None, freq="", route="PO", unit="mg",
        per="dose", notes="", flags=()):
    D.append(dict(drug=drug, regimen=label, kind="volume" if conc else "mg_only",
                  dose_per_kg=mg_per_kg, unit=unit, per=per,
                  concentration_mg_per_mL=conc, frequency=freq, route=route,
                  notes=notes, flags=list(flags)))

# --- antibiotics ---
reg("ALBON (Sulfadimethoxine)", "Day 1 loading dose", 55, 50, "Once (day 1)",
    notes="Use only if ponazuril is unavailable.")
reg("ALBON (Sulfadimethoxine)", "Maintenance (day 2 onward)", 27.5, 50, "SID (q24h)")
reg("AMOXICILLIN / CLAVAMOX (Amoxicillin/Clavulanate)", "Standard", 20, 62.5, "BID (q12h)",
    notes="Under 50 g: dilute 0.1 mL + 0.9 mL sterile water = 6.25 mg/mL.",
    flags=["dilute_under_50g"])
reg("AMOXICILLIN / CLAVAMOX (Amoxicillin/Clavulanate)", "Diluted 6.25 mg/mL (under 50 g)", 20, 6.25, "BID (q12h)")
reg("FISH MOX (Amoxicillin — OTC, without Clavulanate)", "Standard", 30, 33.33, "BID (q12h)",
    notes="33.33 mg/mL only if one 250 mg capsule is made up to exactly 7.5 mL.")
reg("BAYTRIL (Enrofloxacin)", "Standard 10 mg/kg/day, once daily", 10, 22.7, "SID",
    route="PO or SQ", notes="Range 2.5–15 mg/kg/day; 5 mild, 15 severe. Under 25 g: dilute per vet.")
reg("BAYTRIL (Enrofloxacin)", "10 mg/kg/day split BID", 5, 22.7, "BID", route="PO or SQ")
reg("DOXYCYCLINE (Vibramycin)", "10 mg/kg/day split BID (preferred)", 5, 5, "BID")
reg("DOXYCYCLINE (Vibramycin)", "10 mg/kg/day once daily", 10, 5, "SID")
reg("METRONIDAZOLE (Flagyl)", "Oral", 10, 5, "BID (q12h)",
    notes="5 mg/mL suspension from a crushed 250 mg tablet.")
reg("NUFLOR (Florfenicol)", "Working solution", 20, 30, "Two doses total, 48 h apart",
    notes="Dilute 300 mg/mL injectable 1:9 to 30 mg/mL. DO NOT give a third dose.")

# --- antiparasitics ---
reg("PANACUR (Fenbendazole)", "Roundworm / hookworm / whipworm", 20, 100, "SID × 5 days")
reg("PANACUR (Fenbendazole)", "Giardia", 50, 100, "SID × 5 days")
for c in (30, 50, 100):
    reg("PONAZURIL (Marquis)", f"{c} mg/mL compound", 20, c, "q48h × 2 doses",
        notes="Confirm the mg/mL on your bottle — compounded concentrations vary.")
reg("IVERMECTIN", "Protocol A — conservative", 0.4, 1, "Single dose, repeated per protocol",
    notes="1 mg/mL working solution (1:9). Propylene glycol dilution = ORAL ONLY.")
reg("IVERMECTIN", "Protocol A — confirmed mange", 0.5, 1, "Single dose, repeated per protocol")
reg("IVERMECTIN", "Protocol B — demodectic mange", 0.6, 1, "SID, minimum 2 months")

# --- pain / anti-inflammatory ---
reg("GABAPENTIN", "Standard", 12.5, 50, "BID (q12h)", flags=["no_squirrel_pk_data"])
reg("MELOXICAM (Metacam)", "Set A 0.2 mg/kg — cat Metacam", 0.2, 0.5, "SID")
reg("MELOXICAM (Metacam)", "Set A 0.2 mg/kg — dog Metacam", 0.2, 1.5, "SID")
reg("MELOXICAM (Metacam)", "Set B 1 mg/kg (BSAVA) — cat Metacam", 1, 0.5, "SID",
    notes="Use when your vet confirms 1 mg/kg.", flags=["vet_confirm"])
reg("MELOXICAM (Metacam)", "Set B 1 mg/kg (BSAVA) — dog Metacam", 1, 1.5, "SID", flags=["vet_confirm"])
reg("TRAMADOL", "Standard", 2, 5, "BID–TID (q8–12h)")
reg("CARPROFEN (Rimadyl)", "BSAVA", 5, None, "SID", route="SQ (BSAVA) / compounded PO")
for lo, lab in ((0.2, "Low"), (1, "Mid"), (2, "High")):
    reg("BUTORPHANOL", f"{lab} {lo} mg/kg", lo, None, "q4h as needed", route="SQ / IM — vet-administered",
        notes="Controlled. Vial is 2 or 10 mg/mL — enter your vial to get a volume.",
        flags=["controlled"])

# --- GI ---
reg("SUCRALFATE (Carafate)", "Standard", 75, 200, "q4–6h")
reg("FAMOTIDINE (Pepcid)", "Standard", 0.5, 1, "q12–24h")
reg("ACTIVATED CHARCOAL (Toxiban)", "10 mL/kg (2 g/kg)", 2000, 200, "Once",
    notes="Expressed as 200 mg/mL so 10 mL/kg falls out of the same formula.")

# --- vitamins (daily totals, mg/IU only) ---
reg("VITAMIN C (Ascorbic Acid)", "Maintenance 20 mg/kg/day", 20, None, "Daily total, split BID", per="day")
reg("VITAMIN C (Ascorbic Acid)", "Treatment 50 mg/kg/day", 50, None, "Daily total, split BID", per="day")
reg("VITAMIN D₃ (Cholecalciferol)", "Low 200 IU/kg/day", 200, None, "Daily", unit="IU", per="day")
reg("VITAMIN D₃ (Cholecalciferol)", "High 400 IU/kg/day", 400, None, "Daily", unit="IU", per="day")

TEXT_ONLY = [
  "BENADRYL (Diphenhydramine)", "BETADINE (Povidone-Iodine)", "BUPRENORPHINE",
  "CALCIUM (Calcium Carbonate / Calcium Gluconate / Calcium Glubionate)", "CAPSTAR (Nitenpyram)",
  "CHLORHEXIDINE (Nolvasan / Hibiclens)", "CLOTRIMAZOLE / LOTRIMIN",
  "DECONGESTANT SPRAY / AFRIN (Oxymetazoline)", "ALBUTEROL SULFATE (Salbutamol) — NEBULIZED",
  "GENTAMYCIN (Gentamicin / Gentocin)", "IBUPROFEN", "L-GLUTAMINE", "LACTATED RINGER’S SOLUTION (LRS)",
  "MYLICON (Simethicone)", "NEOSPORIN (Triple Antibiotic)", "OMEPRAZOLE (Prilosec)", "PERMETHRIN",
  "PREDNISONE (Prednisolone)", "REVOLUTION (Selamectin)", "SIMETHICONE (Infant Gas Drops)",
  "SSD CREAM / SILVADENE (Silver Sulfadiazine)", "TERRAMYCIN (Oxytetracycline)", "TRAZODONE",
  "ZINC TOXICITY", "XYLITOL", "FRONTLINE (Fipronil)", "LOPERAMIDE (Imodium)",
  "BB WOUNDS / PROJECTILE INJURIES",
  "PREBIOTICS AND PROBIOTICS (Bene-Bac, Primal Defense, LA-200, FortiFlora, Proviable-DC, VSL#3)",
]

def calc(r, weight_g, conc_override=None):
    amt = r["dose_per_kg"] * weight_g / 1000
    conc = conc_override or r["concentration_mg_per_mL"]
    return amt, (amt / conc if conc else None)

if __name__ == "__main__":
    json.dump(dict(regimens=D, text_only=TEXT_ONLY), open(Path(__file__).resolve().parent.parent / "data" / "doses.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(D), "regimens across", len({r['drug'] for r in D}), "drugs;", len(TEXT_ONLY), "text-only entries")
