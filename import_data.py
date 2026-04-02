"""
import_data.py — Importe les données depuis le fichier Excel
vers Supabase.

Usage :
    pip install supabase openpyxl pandas
    python import_data.py

Remplissez SUPABASE_URL et SUPABASE_KEY ci-dessous,
ou définissez les variables d'environnement correspondantes.
"""

import os
import pandas as pd
from supabase import create_client

# ── Configuration ────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://xxxxxxxxxxxxxxxxxxxx.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "votre-anon-key")
EXCEL_FILE   = "suivi_copropriete_automatise.xlsx"

# ─────────────────────────────────────────────────────────────

def connect():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def import_coproprietaires(client, df: pd.DataFrame):
    """Importe la feuille Copropriétaires."""
    print(f"  → {len(df)} copropriétaires trouvés")
    records = []
    for _, row in df.iterrows():
        records.append({
            "nom":                      str(row.get("nom", "") or ""),
            "lot":                      int(row["lot"]) if pd.notna(row.get("lot")) else None,
            "N° appartement":           str(row.get("description","") or ""), 
            "etage":                    str(row.get("etage", "") or ""),
            "usage":                    str(row.get("usage", "") or ""),
            "adresse":                  str(row.get("adresse", "") or ""),
            "cp_ville":                 str(row.get("cp_ville", "") or ""),
            "email":                    str(row.get("email", "") or "") or None,
            "telephone":                str(row.get("telephone", "") or "") or None,
            "tantieme_general":         float(row.get("tantieme_general", 0) or 0),
            "tantiemes_ascenseur":      float(row.get("tantiemes_ascenseur", 0) or 0),
            "tantiemes_special_rdc_ss": float(row.get("tantiemes_special_rdc_ss", 0) or 0),
            "tantieme_ssols":           float(row.get("tantieme_ssols", 0) or 0),
            "tantieme_garages":         float(row.get("tantieme_garages", 0) or 0),
            "tantieme_monte_voitures":  float(row.get("tantieme_monte_voitures", 0) or 0),
        })
    # Insertion par lots de 50
    for i in range(0, len(records), 50):
        client.table("coproprietaires").insert(records[i:i+50]).execute()
    print(f"  ✅ {len(records)} copropriétaires importés")

def import_budget(client, df: pd.DataFrame):
    """Importe la feuille Budget."""
    print(f"  → {len(df)} postes budget trouvés")
    records = []
    for _, row in df.iterrows():
        records.append({
            "annee":          int(row.get("annee", 2025)),
            "compte":         str(row.get("compte", "") or ""),
            "libelle_compte": str(row.get("libelle_compte", "") or ""),
            "montant_budget": float(row.get("montant_budget", 0) or 0),
            "classe":         str(row.get("classe", "") or ""),
            "famille":        str(row.get("famille", "") or ""),
        })
    for i in range(0, len(records), 50):
        client.table("budget").insert(records[i:i+50]).execute()
    print(f"  ✅ {len(records)} postes budget importés")

def import_depenses(client, df: pd.DataFrame):
    """Importe la feuille Dépenses."""
    print(f"  → {len(df)} dépenses trouvées")
    records = []
    for _, row in df.iterrows():
        date_val = row.get("date")
        if pd.notna(date_val):
            date_str = pd.Timestamp(date_val).strftime("%Y-%m-%d")
        else:
            continue  # date obligatoire
        records.append({
            "date":        date_str,
            "compte":      str(row.get("compte", "") or ""),
            "fournisseur": str(row.get("fournisseur", "") or ""),
            "montant_du":  float(row.get("montant_du", 0) or 0),
            "commentaire": str(row.get("commentaire", "") or "") or None,
            "classe":      str(row.get("classe", "") or ""),
            "famille":     str(row.get("famille", "") or ""),
        })
    for i in range(0, len(records), 50):
        client.table("depenses").insert(records[i:i+50]).execute()
    print(f"  ✅ {len(records)} dépenses importées")

def import_plan_comptable(client, df: pd.DataFrame):
    """Importe la feuille Plan Comptable."""
    print(f"  → {len(df)} comptes trouvés")
    records = []
    for _, row in df.iterrows():
        records.append({
            "compte":         str(row.get("compte", "") or ""),
            "libelle_compte": str(row.get("libelle_compte", "") or ""),
            "classe":         str(row.get("classe", "") or ""),
            "famille":        str(row.get("famille", "") or ""),
        })
    for i in range(0, len(records), 50):
        client.table("plan_comptable").insert(records[i:i+50]).execute()
    print(f"  ✅ {len(records)} comptes importés")

def main():
    print(f"\n🔌 Connexion à Supabase...")
    client = connect()
    print("✅ Connecté\n")

    try:
        xl = pd.ExcelFile(EXCEL_FILE)
        print(f"📊 Feuilles disponibles dans '{EXCEL_FILE}' : {xl.sheet_names}\n")
    except FileNotFoundError:
        print(f"❌ Fichier '{EXCEL_FILE}' introuvable. Placez-le dans le même dossier.")
        return

    sheet_handlers = {
        "Copropriétaires": import_coproprietaires,
        "coproprietaires": import_coproprietaires,
        "Copropriétaire":  import_coproprietaires,
        "Budget":          import_budget,
        "budget":          import_budget,
        "Dépenses":        import_depenses,
        "Depenses":        import_depenses,
        "depenses":        import_depenses,
        "Plan comptable":  import_plan_comptable,
        "Plan Comptable":  import_plan_comptable,
        "plan_comptable":  import_plan_comptable,
    }

    for sheet in xl.sheet_names:
        if sheet in sheet_handlers:
            print(f"📥 Import feuille : '{sheet}'")
            df = xl.parse(sheet)
            sheet_handlers[sheet](client, df)
            print()
        else:
            print(f"⏭️  Feuille ignorée : '{sheet}'")

    print("\n🎉 Import terminé !")

if __name__ == "__main__":
    main()
