import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from supabase import create_client
import time

st.set_page_config(page_title="Gestion Copropriété", page_icon="🏢", layout="wide", initial_sidebar_state="expanded")

@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

st.markdown("""
<style>
    .main-header { font-size: 2.5rem; font-weight: bold; color: #1f77b4; text-align: center; margin-bottom: 2rem; }
    .stat-box { background: #f0f2f6; padding: 1rem; border-radius: 8px; margin: 0.5rem 0; }
</style>
""", unsafe_allow_html=True)

# v20260218_111053 — Fix Alur base = total_bud
# ==================== FONCTIONS DB ====================
def get_budget():
    try:
        return pd.DataFrame(supabase.table('budget').select('*').execute().data)
    except Exception as e:
        st.error(f"❌ Erreur budget: {e}"); return pd.DataFrame()

def get_depenses(date_debut=None, date_fin=None):
    try:
        q = supabase.table('depenses').select('*')
        if date_debut: q = q.gte('date', date_debut.strftime('%Y-%m-%d'))
        if date_fin:   q = q.lte('date', date_fin.strftime('%Y-%m-%d'))
        df = pd.DataFrame(q.execute().data)
        if not df.empty and 'deleted' in df.columns:
            df = df[df['deleted'] != True]
        return df
    except Exception as e:
        st.error(f"❌ Erreur dépenses: {e}"); return pd.DataFrame()

def get_coproprietaires():
    try:
        return pd.DataFrame(supabase.table('coproprietaires').select('*').execute().data)
    except Exception as e:
        st.error(f"❌ Erreur copropriétaires: {e}"); return pd.DataFrame()

def get_plan_comptable():
    try:
        return pd.DataFrame(supabase.table('plan_comptable').select('*').execute().data)
    except Exception as e:
        st.error(f"❌ Erreur plan comptable: {e}"); return pd.DataFrame()

def get_travaux_votes():
    try:
        return pd.DataFrame(supabase.table('travaux_votes').select('*').order('date').execute().data)
    except Exception as e:
        st.error(f"❌ Erreur travaux_votes: {e}"); return pd.DataFrame()

def get_travaux_votes_depense_ids():
    """Retourne les IDs des dépenses transférées en travaux votés."""
    try:
        res = supabase.table('travaux_votes').select('depense_id').not_.is_('depense_id', 'null').execute()
        return [r['depense_id'] for r in res.data if r.get('depense_id')]
    except:
        return []

def get_loi_alur():
    try:
        return pd.DataFrame(supabase.table('loi_alur').select('*').order('date').execute().data)
    except Exception as e:
        st.error(f"❌ Erreur loi_alur: {e}"); return pd.DataFrame()

def get_depenses_alur_ids():
    """Retourne les IDs des dépenses déjà affectées au fonds Alur."""
    try:
        res = supabase.table('loi_alur').select('depense_id').not_.is_('depense_id', 'null').execute()
        return [r['depense_id'] for r in res.data if r.get('depense_id')]
    except:
        return []

# ==================== CONFIGURATION CLÉS DE RÉPARTITION ====================
# Basé sur votre plan comptable réel :
# Classe 1A, 1B, 7 → Charges générales → tantième_general / 10 000
# Classe 2          → Électricité RDC/ss-sols → tantième_rdc_ssols / 928
# Classe 3          → Électricité sous-sols → tantième_ssols / 20
# Classe 4          → Garages/Parkings → tantième_garages / 28
# Classe 5          → Ascenseurs → tantième_ascenseurs / 1 000
# Classe 6          → Monte-voitures → tantième_ssols / 20

MAPPING_CLASSE_TANTIEME = {
    '1A': 'general',
    '1B': 'general',
    '7':  'general',
    '2':  'rdc_ssols',
    '3':  'ssols_elec',
    '4':  'garages',
    '5':  'ascenseurs',
    '6':  'ssols',
}

# ==================== CONFIGURATION SYNDIC ====================
SYNDIC_INFO = {
    "nom": "VILLA TOBIAS (0275)",
    "adresse": "52 RUE SMOLETT",
    "cp_ville": "06300 NICE",
    "ville": "NICE",
}

# Libellés des postes pour les PDFs (correspondance clé CHARGES_CONFIG → libellé officiel)
POSTES_LABELS = {
    'general':    'CHARGES COMMUNES GENERALES',
    'ascenseurs': 'ASCENSEURS',
    'rdc_ssols':  'CHARGES SPECIALES RDC S/SOLS',
    'ssols_elec': 'CHARGES SPECIALES S/SOLS',
    'garages':    'CHARGES GARAGES/PARKINGS',
    'ssols':      'MONTE VOITURES',
}

def generate_appel_pdf_bytes(syndic, cop_row, periode, label_trim, annee,
                              montants, alur_par_appel, nb_appels):
    """Génère le PDF d'appel de fonds pour un copropriétaire. Retourne bytes."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER
    from io import BytesIO

    JAUNE      = colors.HexColor('#FFD700')
    JAUNE_CLAIR= colors.HexColor('#FFFACD')
    BLEU       = colors.HexColor('#4472C4')
    GRIS_CLAIR = colors.HexColor('#D9D9D9')

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=12*mm, bottomMargin=15*mm)

    def sty(size=9, bold=False, align='LEFT', color=colors.black):
        from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
        al = {'LEFT': TA_LEFT, 'RIGHT': TA_RIGHT, 'CENTER': TA_CENTER}[align]
        fn = 'Helvetica-Bold' if bold else 'Helvetica'
        return ParagraphStyle('s', fontSize=size, fontName=fn, textColor=color,
                              alignment=al, leading=size*1.3)

    story = []

    # --- EN-TÊTE ---
    from datetime import date
    date_str = date.today().strftime('%d/%m/%Y')
    header = Table([[
        [Paragraph("<u><b>Appel de Fonds</b></u>", sty(20, True)),
         Paragraph(f"Période du {periode}", sty(9))],
        [Paragraph(f"A {syndic['ville']}, le {date_str}", sty(9, align='RIGHT')),
         Paragraph(f"<b>{syndic['nom']}</b>", sty(9, True, 'RIGHT')),
         Paragraph(syndic['adresse'], sty(9, align='RIGHT')),
         Paragraph(syndic['cp_ville'], sty(9, align='RIGHT'))]
    ]], colWidths=[95*mm, 85*mm])
    header.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP')]))
    story.append(header)
    story.append(Spacer(1, 6*mm))

    # --- BLOC RÉF / DESTINATAIRE ---
    nom_cop  = str(cop_row.get('nom', ''))
    ref_cop  = f"0275-{str(cop_row.get('lot','')).zfill(4)}"
    login    = str(cop_row.get('login', '') or '')
    adresse  = str(cop_row.get('adresse', '') or '')
    cp_ville = str(cop_row.get('cp_ville', '') or '')

    ref_tbl = Table([[
        [Paragraph(f"<b>APPEL DE FONDS TRIMESTRIELS {annee}</b>", sty(9, True)),
         Paragraph(f"Réf : {ref_cop} / {nom_cop}", sty(9)),
         Paragraph(f"Internet Login : {login}  Mot de Passe :", sty(9))],
        [],
        [Paragraph(f"<b>{nom_cop}</b>", sty(9, True)),
         Paragraph(adresse, sty(9)),
         Paragraph(cp_ville, sty(9))]
    ]], colWidths=[80*mm, 20*mm, 80*mm])
    ref_tbl.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP')]))
    story.append(ref_tbl)
    story.append(Spacer(1, 8*mm))

    # --- TABLEAU DES POSTES ---
    col_widths = [14*mm, 82*mm, 22*mm, 22*mm, 22*mm, 22*mm]
    thead = [['', Paragraph('Postes à répartir', sty(9, True, 'CENTER', colors.white)),
              Paragraph('Total', sty(9, True, 'CENTER', colors.white)),
              Paragraph('Base', sty(9, True, 'CENTER', colors.white)),
              Paragraph('Tantièmes', sty(9, True, 'CENTER', colors.white)),
              Paragraph('Quote-part', sty(9, True, 'CENTER', colors.white))]]

    lot   = str(cop_row.get('lot',''))
    usage = str(cop_row.get('usage',''))
    rows  = [[Paragraph(f"<b>{lot}</b>", sty(9, True)),
              Paragraph(f"<b>{usage}</b>", sty(9, True)),
              '', '', '', '']]

    total_lot = 0
    for key, cfg in CHARGES_CONFIG.items():
        tant  = float(cop_row.get(cfg['col'], 0) or 0)
        if cfg['total'] == 0 or tant == 0:
            continue
        montant_annuel = montants.get(key, 0)
        quote_part = round((tant / cfg['total']) * (montant_annuel / nb_appels), 2)
        if quote_part == 0:
            continue
        total_lot += quote_part
        rows.append(['',
            Paragraph(POSTES_LABELS.get(key, cfg['label']), sty(8.5)),
            Paragraph(f"{montant_annuel/nb_appels:,.2f}", sty(8.5, align='RIGHT')),
            Paragraph(str(cfg['total']), sty(8.5, align='CENTER')),
            Paragraph(str(int(tant)), sty(8.5, align='CENTER')),
            Paragraph(f"{quote_part:,.2f}", sty(8.5, align='RIGHT'))])

    # Ligne Alur
    tant_gen = float(cop_row.get('tantieme_general', 0) or 0)
    if tant_gen > 0 and alur_par_appel > 0:
        alur_cop = round(tant_gen / 10000 * alur_par_appel, 2)
        total_lot += alur_cop
        rows.append(['',
            Paragraph('FONDS TRAVAUX ALUR', sty(8.5)),
            Paragraph(f"{alur_par_appel:,.2f}", sty(8.5, align='RIGHT')),
            Paragraph('10000', sty(8.5, align='CENTER')),
            Paragraph(str(int(tant_gen)), sty(8.5, align='CENTER')),
            Paragraph(f"{alur_cop:,.2f}", sty(8.5, align='RIGHT'))])

    dont_tva = round(total_lot * 20 / 120, 2)

    rows.append(['', Paragraph('<b>TOTAL DU LOT</b>', sty(9, True, 'RIGHT')),
                 '', '', '',
                 Paragraph(f"<b>{total_lot:,.2f}</b>", sty(9, True, 'RIGHT'))])
    rows.append(['', Paragraph('<b>DONT TVA</b>', sty(9, True, 'RIGHT')),
                 '', '', '',
                 Paragraph(f"<b>{dont_tva:,.2f}</b>", sty(9, True, 'RIGHT'))])

    table_data = thead + rows
    n = len(table_data)
    n_lot = 1; n_ds = 2; n_de = n - 3; n_tot = n - 2; n_tva = n - 1

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    style_rules = [
        ('BACKGROUND', (0,0), (-1,0), BLEU),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('TOPPADDING', (0,0), (-1,0), 5), ('BOTTOMPADDING', (0,0), (-1,0), 5),
        ('BACKGROUND', (0,n_lot), (-1,n_lot), GRIS_CLAIR),
        ('BACKGROUND', (5,n_ds), (5,n_de), GRIS_CLAIR),
        ('BACKGROUND', (0,n_tot), (-1,n_tot), JAUNE),
        ('BACKGROUND', (0,n_tva), (-1,n_tva), JAUNE_CLAIR),
        ('GRID', (0,0), (-1,-1), 0.4, colors.HexColor('#CCCCCC')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#999999')),
        ('ALIGN', (2,1), (2,-1), 'RIGHT'),
        ('ALIGN', (3,1), (3,-1), 'CENTER'),
        ('ALIGN', (4,1), (4,-1), 'CENTER'),
        ('ALIGN', (5,1), (5,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,1), (-1,-1), 3), ('BOTTOMPADDING', (0,1), (-1,-1), 3),
        ('LEFTPADDING', (1,0), (1,-1), 6),
    ]
    for i in range(n_ds, n_tot):
        bg = colors.white if i % 2 == 0 else colors.HexColor('#F5F5F5')
        style_rules.append(('BACKGROUND', (0,i), (4,i), bg))
    tbl.setStyle(TableStyle(style_rules))
    story.append(tbl)

    # --- MONTANT TOTAL ---
    story.append(Spacer(1, 6*mm))
    mt = Table([[
        Paragraph("Montant de l'appel de fonds", sty(11, True)),
        Paragraph(f"<b>{total_lot:,.2f} €</b>", sty(14, True, 'RIGHT'))
    ]], colWidths=[130*mm, 50*mm])
    mt.setStyle(TableStyle([
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('LINEABOVE',(0,0),(-1,0),1.5,colors.black),
        ('TOPPADDING',(0,0),(-1,0),6),
    ]))
    story.append(mt)

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()

CHARGES_CONFIG = {
    'general':    {'col': 'tantieme_general',    'total': 10000, 'label': 'Charges générales',        'emoji': '🏢', 'classes': ['1A','1B','7']},
    'ascenseurs': {'col': 'tantieme_ascenseurs',  'total': 1000,  'label': 'Ascenseurs',               'emoji': '🛗', 'classes': ['5']},
    'rdc_ssols':  {'col': 'tantieme_rdc_ssols',   'total': 928,   'label': 'Charges spéc. RDC S/Sols', 'emoji': '🅿️', 'classes': ['2']},
    'ssols_elec': {'col': 'tantieme_ssols',       'total': 20,    'label': 'Charges spéc. S/Sols',     'emoji': '⬇️', 'classes': ['3']},
    'garages':    {'col': 'tantieme_garages',     'total': 28,    'label': 'Garages / Parkings',       'emoji': '🔑', 'classes': ['4']},
    'ssols':      {'col': 'tantieme_ssols',       'total': 20,    'label': 'Monte-voitures',           'emoji': '🚗', 'classes': ['6']},
}

def prepare_copro(copro_df):
    """Convertit toutes les colonnes tantièmes en numérique."""
    for col in ['tantieme_general','tantieme_ascenseurs','tantieme_rdc_ssols','tantieme_garages','tantieme_ssols','tantieme_monte_voitures','tantieme']:
        if col in copro_df.columns:
            copro_df[col] = pd.to_numeric(copro_df[col], errors='coerce').fillna(0)
    # Fallback si les colonnes spécifiques ne sont pas remplies
    if 'tantieme_general' not in copro_df.columns or copro_df['tantieme_general'].sum() == 0:
        if 'tantieme' in copro_df.columns:
            copro_df['tantieme_general'] = copro_df['tantieme']
    return copro_df

def calculer_appels(copro_df, montants_par_type):
    """Calcule la part de chaque copropriétaire selon les montants par type de charge."""
    rows = []
    for _, cop in copro_df.iterrows():
        total_annuel = 0
        detail = {}
        for key, cfg in CHARGES_CONFIG.items():
            col = cfg['col']
            tant = float(cop.get(col, 0) or 0)
            montant = montants_par_type.get(key, 0)
            part = (tant / cfg['total'] * montant) if cfg['total'] > 0 and tant > 0 else 0
            detail[key] = round(part, 2)
            total_annuel += part
        row = {
            'Lot': cop.get('lot',''), 'Copropriétaire': cop.get('nom',''),
            'Étage': cop.get('etage',''), 'Usage': cop.get('usage',''),
            '_tantieme_general': float(cop.get('tantieme_general', 0) or 0),  # pour calcul Alur
        }
        row.update({f"{CHARGES_CONFIG[k]['emoji']} {CHARGES_CONFIG[k]['label']}": v for k, v in detail.items()})
        row['💰 TOTAL Annuel (€)'] = round(total_annuel, 2)
        rows.append(row)
    return pd.DataFrame(rows)

# ==================== MENU ====================
st.sidebar.image("https://img.icons8.com/color/96/000000/office-building.png", width=100)
st.sidebar.title("Navigation")
menu = st.sidebar.radio("Choisir une section", [
    "📊 Tableau de Bord", "💰 Budget", "📝 Dépenses",
    "👥 Copropriétaires", "🔄 Répartition", "🏛️ Loi Alur", "📈 Analyses", "📋 Plan Comptable"
])

# ==================== TABLEAU DE BORD ====================
if menu == "📊 Tableau de Bord":
    st.markdown("<h1 class='main-header'>📊 Tableau de Bord</h1>", unsafe_allow_html=True)
    budget_df = get_budget()
    depenses_df = get_depenses()

    if not budget_df.empty and not depenses_df.empty:
        depenses_df['date'] = pd.to_datetime(depenses_df['date'])
        depenses_df['annee'] = depenses_df['date'].dt.year
        depenses_df['montant_du'] = pd.to_numeric(depenses_df['montant_du'], errors='coerce')

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            annee_filter = st.selectbox("📅 Année", sorted(depenses_df['annee'].unique(), reverse=True), key="tdb_annee")
        with col2:
            classes_dispo = ['Toutes'] + sorted([str(c) for c in depenses_df['classe'].dropna().unique()]) if 'classe' in depenses_df.columns else ['Toutes']
            classe_filter = st.selectbox("🏷️ Classe", classes_dispo, key="tdb_classe")
        with col3:
            comptes_dispo = ['Tous'] + sorted(depenses_df['compte'].dropna().unique().tolist())
            compte_filter = st.selectbox("🔢 Compte", comptes_dispo, key="tdb_compte")
        with col4:
            alur_taux_tdb = st.number_input("🏛️ Taux Alur (%)", min_value=5.0, max_value=20.0,
                value=5.0, step=0.5, key="alur_taux_tdb")

        dep_f = depenses_df[depenses_df['annee'] == annee_filter].copy()
        if classe_filter != 'Toutes' and 'classe' in dep_f.columns:
            dep_f = dep_f[dep_f['classe'] == classe_filter]
        if compte_filter != 'Tous':
            dep_f = dep_f[dep_f['compte'] == compte_filter]

        bud_f = budget_df[budget_df['annee'] == annee_filter].copy()
        if classe_filter != 'Toutes' and 'classe' in bud_f.columns:
            bud_f = bud_f[bud_f['classe'] == classe_filter]
        if compte_filter != 'Tous':
            bud_f = bud_f[bud_f['compte'] == compte_filter]

        # Alur toujours calculé sur le budget TOTAL de l'année (pas filtré)
        bud_total_annee_tdb = float(budget_df[budget_df['annee'] == annee_filter]['montant_budget'].sum())
        alur_tdb = round(bud_total_annee_tdb * alur_taux_tdb / 100, 2)

        total_budget = float(bud_f['montant_budget'].sum())
        total_dep = float(dep_f['montant_du'].sum())
        total_a_appeler = bud_total_annee_tdb + alur_tdb
        ecart = total_a_appeler - total_dep
        pct = (total_dep / total_a_appeler * 100) if total_a_appeler > 0 else 0

        st.divider()
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Budget charges", f"{bud_total_annee_tdb:,.0f} €")
        c2.metric(f"🏛️ Alur ({alur_taux_tdb:.0f}%)", f"{alur_tdb:,.0f} €")
        c3.metric("💰 Total à appeler", f"{total_a_appeler:,.0f} €")
        c4.metric("Dépenses réelles", f"{total_dep:,.2f} €")
        c5.metric("Écart", f"{ecart:,.2f} €",
            delta_color="normal" if ecart >= 0 else "inverse",
            help="Total à appeler − Dépenses réelles")
        c6.metric("% Réalisé", f"{pct:.1f}%")

        st.info(f"🏛️ **Loi Alur** — {alur_tdb:,.0f} € /an "
                f"({alur_taux_tdb:.0f}% × {bud_total_annee_tdb:,.0f} €) "
                f"— soit **{alur_tdb/4:,.2f} €** par appel trimestriel")
        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Budget + Alur vs Dépenses par Classe")
            if 'classe' in bud_f.columns and 'classe' in dep_f.columns:
                bud_cl = bud_f.groupby('classe')['montant_budget'].sum().reset_index()
                # Ajouter Alur comme classe distincte
                alur_bar = pd.DataFrame([{'classe': f'Alur ({alur_taux_tdb:.0f}%)', 'montant_budget': alur_tdb}])
                bud_cl_total = pd.concat([bud_cl, alur_bar], ignore_index=True)
                dep_cl = dep_f.groupby('classe')['montant_du'].sum().reset_index()
                comp = bud_cl_total.merge(dep_cl, on='classe', how='left').fillna(0)
                comp.columns = ['Classe', 'Budget', 'Dépenses']
                fig = go.Figure()
                fig.add_trace(go.Bar(name='Budget + Alur', x=comp['Classe'], y=comp['Budget'], marker_color='lightblue'))
                fig.add_trace(go.Bar(name='Dépenses réelles', x=comp['Classe'], y=comp['Dépenses'], marker_color='salmon'))
                fig.update_layout(barmode='group', height=400)
                st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.subheader("Répartition Budget + Alur")
            if 'classe' in bud_f.columns and not bud_f.empty:
                bud_cl = bud_f.groupby('classe')['montant_budget'].sum().reset_index()
                bud_cl_pie = pd.concat([bud_cl, pd.DataFrame([{
                    'classe': f'Alur ({alur_taux_tdb:.0f}%)', 'montant_budget': alur_tdb
                }])], ignore_index=True)
                fig = px.pie(bud_cl_pie, values='montant_budget', names='classe',
                    title=f'Distribution budget + Alur {annee_filter}')
                fig.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)

        st.subheader(f"Évolution Mensuelle — {annee_filter}")
        if not dep_f.empty:
            dep_f['mois'] = dep_f['date'].dt.to_period('M').astype(str)
            ev = dep_f.groupby('mois')['montant_du'].sum().reset_index()
            # Ajouter ligne budget mensuel moyen
            bud_mensuel = total_a_appeler / 12
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=ev['mois'], y=ev['montant_du'], mode='lines+markers',
                name='Dépenses réelles', line=dict(color='#1f77b4', width=3)))
            fig.add_hline(y=bud_mensuel, line_dash='dash', line_color='orange',
                annotation_text=f"Moy. budget+Alur/mois ({bud_mensuel:,.0f} €)")
            fig.update_layout(xaxis_title='Mois', yaxis_title='Montant (€)')
            st.plotly_chart(fig, use_container_width=True)

        st.subheader(f"Top 10 Dépenses — {annee_filter}")
        if not dep_f.empty:
            top = dep_f.nlargest(10, 'montant_du')[['date','fournisseur','montant_du','commentaire']].copy()
            top['date'] = top['date'].dt.strftime('%d/%m/%Y')
            st.dataframe(top, use_container_width=True, hide_index=True,
                column_config={"montant_du": st.column_config.NumberColumn("Montant (€)", format="%,.2f")})
    else:
        st.warning("⚠️ Données insuffisantes")

# ==================== BUDGET ====================
elif menu == "💰 Budget":
    st.markdown("<h1 class='main-header'>💰 Gestion du Budget</h1>", unsafe_allow_html=True)
    budget_df = get_budget()

    if not budget_df.empty:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            annees = sorted(budget_df['annee'].unique(), reverse=True)
            annee_filter = st.selectbox("📅 Année", annees, key="budget_annee")
        with col2:
            classe_filter = st.multiselect("🏷️ Classe", options=sorted(budget_df['classe'].unique()))
        with col3:
            famille_filter = st.multiselect("📂 Famille", options=sorted(budget_df['famille'].unique()))
        with col4:
            alur_taux_bud = st.number_input("🏛️ Taux Alur (%)", min_value=5.0, max_value=20.0,
                value=5.0, step=0.5, key="alur_taux_bud",
                help="Minimum légal = 5% du budget voté en AG (loi Alur art. 14-2)")

        filt = budget_df[budget_df['annee'] == annee_filter].copy()
        if classe_filter: filt = filt[filt['classe'].isin(classe_filter)]
        if famille_filter: filt = filt[filt['famille'].isin(famille_filter)]
        bud_total_annee = float(budget_df[budget_df['annee'] == annee_filter]['montant_budget'].sum())
        alur_annuel_bud = round(bud_total_annee * alur_taux_bud / 100, 2)

        st.divider()
        bud_prec = float(budget_df[budget_df['annee'] == annee_filter - 1]['montant_budget'].sum())
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Postes budgétaires", len(filt))
        c2.metric("Budget charges", f"{bud_total_annee:,.0f} €")
        c3.metric(f"🏛️ Alur ({alur_taux_bud:.0f}%)", f"{alur_annuel_bud:,.0f} €",
            help=f"{alur_taux_bud}% × {bud_total_annee:,.0f} € = fonds de travaux obligatoire")
        c4.metric("💰 TOTAL à appeler", f"{bud_total_annee + alur_annuel_bud:,.0f} €")
        if bud_prec > 0:
            c5.metric("vs N-1", f"{(bud_total_annee - bud_prec) / bud_prec * 100:+.1f}%",
                delta=f"{bud_total_annee - bud_prec:+,.0f} €")
        else:
            c5.metric("vs N-1", "N/A")

        # Bloc Alur détaillé
        st.info(f"🏛️ **Loi Alur** — Fonds de travaux : **{alur_annuel_bud:,.0f} €/an** "
                f"({alur_taux_bud:.0f}% × {bud_total_annee:,.0f} €) "
                f"— soit **{alur_annuel_bud/4:,.2f} €/trimestre** par appel de fonds")
        st.divider()

        tab1, tab2, tab3 = st.tabs(["📋 Consulter", "✏️ Modifier / Ajouter / Supprimer", "➕ Créer Budget Année"])

        with tab1:
            st.subheader(f"Budget {annee_filter} — {len(filt)} postes")

            # Tableau avec ligne Alur et total — utilise alur_annuel_bud/bud_total_annee déjà calculés
            filt_display = filt[['compte','libelle_compte','montant_budget','classe','famille']].sort_values('compte').copy()
            filt_display = pd.concat([filt_display, pd.DataFrame([
                {'compte': 'ALUR', 'libelle_compte': f'🏛️ FONDS DE TRAVAUX — Loi Alur ({alur_taux_bud:.0f}%)',
                 'montant_budget': alur_annuel_bud, 'classe': '—', 'famille': '—'},
                {'compte': 'TOTAL', 'libelle_compte': '💰 TOTAL BUDGET + ALUR',
                 'montant_budget': bud_total_annee + alur_annuel_bud, 'classe': '—', 'famille': '—'}
            ])], ignore_index=True)

            st.dataframe(filt_display, use_container_width=True, hide_index=True,
                column_config={
                    "compte": st.column_config.TextColumn("Compte"),
                    "libelle_compte": st.column_config.TextColumn("Libellé"),
                    "montant_budget": st.column_config.NumberColumn("Budget (€)", format="%,.0f"),
                    "classe": st.column_config.TextColumn("Classe"),
                    "famille": st.column_config.TextColumn("Famille"),
                })

            col1, col2 = st.columns(2)
            with col1:
                bud_cl = filt.groupby('classe')['montant_budget'].sum().reset_index()
                bud_cl_graph = pd.concat([bud_cl, pd.DataFrame([
                    {'classe': f'Alur ({alur_taux_bud:.0f}%)', 'montant_budget': alur_annuel_bud}
                ])], ignore_index=True)
                fig = px.bar(bud_cl_graph, x='classe', y='montant_budget',
                    title=f"Budget {annee_filter} par Classe + Alur",
                    labels={'montant_budget':'Budget (€)','classe':'Classe'}, color='classe')
                fig.update_traces(texttemplate='%{y:,.0f}€', textposition='outside')
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                fig = px.pie(bud_cl_graph, values='montant_budget', names='classe',
                    title=f"Répartition Budget + Alur {annee_filter}")
                fig.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)

            st.download_button("📥 Exporter CSV (avec Alur)",
                filt_display.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig'),
                f"budget_{annee_filter}.csv", "text/csv")

        with tab2:
            subtab1, subtab2, subtab3 = st.tabs(["✏️ Modifier", "➕ Ajouter", "🗑️ Supprimer"])
            with subtab1:
                bud_edit_df = filt[['id','compte','libelle_compte','montant_budget','classe','famille']].copy()
                bud_edit_df['compte'] = bud_edit_df['compte'].astype(str).fillna('')
                bud_edit_df['libelle_compte'] = bud_edit_df['libelle_compte'].astype(str).fillna('')
                bud_edit_df['montant_budget'] = pd.to_numeric(bud_edit_df['montant_budget'], errors='coerce').fillna(0.0)
                bud_edit_df['classe'] = bud_edit_df['classe'].astype(str).fillna('')
                bud_edit_df['famille'] = bud_edit_df['famille'].astype(str).fillna('')
                edited = st.data_editor(
                    bud_edit_df,
                    use_container_width=True, hide_index=True, disabled=['id'],
                    column_config={
                        "compte": st.column_config.TextColumn("Compte"),
                        "libelle_compte": st.column_config.TextColumn("Libellé"),
                        "montant_budget": st.column_config.NumberColumn("Budget (€)", format="%.0f", min_value=0),
                        "classe": st.column_config.SelectboxColumn("Classe", options=['1A','1B','2','3','4','5','6','7']),
                        "famille": st.column_config.TextColumn("Famille"),
                    }, key="budget_editor"
                )
                if st.button("💾 Enregistrer", type="primary", key="save_bud"):
                    try:
                        mods = 0
                        for _, row in edited.iterrows():
                            orig = filt[filt['id'] == row['id']]
                            if orig.empty: continue
                            o = orig.iloc[0]; updates = {}
                            if str(row['compte']) != str(o['compte']): updates['compte'] = str(row['compte'])
                            if str(row['libelle_compte']) != str(o['libelle_compte']): updates['libelle_compte'] = str(row['libelle_compte'])
                            if float(row['montant_budget']) != float(o['montant_budget']): updates['montant_budget'] = int(row['montant_budget'])
                            if str(row['classe']) != str(o['classe']): updates['classe'] = str(row['classe'])
                            if str(row['famille']) != str(o['famille']): updates['famille'] = str(row['famille'])
                            if updates:
                                supabase.table('budget').update(updates).eq('id', int(row['id'])).execute()
                                mods += 1
                        st.success(f"✅ {mods} ligne(s) mise(s) à jour!") if mods > 0 else st.info("Aucune modification")
                        if mods > 0: st.rerun()
                    except Exception as e:
                        st.error(f"❌ {e}")

            with subtab2:
                plan_df = get_plan_comptable()
                new_compte = st.text_input("Numéro de compte *", key="new_compte_in")
                compte_info = plan_df[plan_df['compte'].astype(str) == str(new_compte)] if new_compte and not plan_df.empty else pd.DataFrame()
                if not compte_info.empty:
                    st.success(f"✅ {compte_info.iloc[0]['libelle_compte']}")
                    def_lib = compte_info.iloc[0]['libelle_compte']
                    def_cl = compte_info.iloc[0]['classe']
                    def_fam = str(compte_info.iloc[0]['famille'])
                elif new_compte:
                    st.warning("⚠️ Compte non trouvé dans le plan comptable")
                    def_lib = ""; def_cl = "1A"; def_fam = ""
                else:
                    def_lib = ""; def_cl = "1A"; def_fam = ""

                col1, col2 = st.columns(2)
                with col1:
                    new_lib = st.text_input("Libellé *", value=def_lib, key="new_lib_in")
                    new_montant = st.number_input("Montant (€) *", min_value=0, step=100, key="new_montant_in")
                with col2:
                    new_classe = st.selectbox("Classe *", ['1A','1B','2','3','4','5','6','7'],
                        index=['1A','1B','2','3','4','5','6','7'].index(def_cl) if def_cl in ['1A','1B','2','3','4','5','6','7'] else 0,
                        key="new_classe_in")
                    new_famille = st.text_input("Famille *", value=def_fam, key="new_fam_in")

                if st.button("✨ Ajouter", type="primary", key="add_bud"):
                    if new_compte and new_lib and new_famille:
                        try:
                            supabase.table('budget').insert({
                                'compte': new_compte, 'libelle_compte': new_lib,
                                'montant_budget': int(new_montant), 'annee': int(annee_filter),
                                'classe': new_classe, 'famille': new_famille
                            }).execute()
                            st.success("✅ Compte ajouté!"); st.rerun()
                        except Exception as e:
                            st.error(f"❌ {e}")
                    else:
                        st.error("❌ Remplissez tous les champs obligatoires")

            with subtab3:
                st.warning("⚠️ La suppression est définitive.")
                ids_del = st.multiselect("Sélectionner les postes à supprimer", options=filt['id'].tolist(),
                    format_func=lambda x: f"{filt[filt['id']==x]['compte'].values[0]} — {filt[filt['id']==x]['libelle_compte'].values[0]}")
                if ids_del:
                    if st.button("🗑️ Confirmer la suppression", type="secondary"):
                        for i in ids_del: supabase.table('budget').delete().eq('id', i).execute()
                        st.success(f"✅ {len(ids_del)} poste(s) supprimé(s)"); st.rerun()

        with tab3:
            st.subheader("Créer un budget pour une nouvelle année")
            c1, c2 = st.columns(2)
            with c1:
                nouvelle_annee = st.number_input("📅 Nouvelle année", min_value=2020, max_value=2050, value=annee_filter+1, step=1)
            with c2:
                annee_src = st.selectbox("Copier depuis", annees)
            src = budget_df[budget_df['annee'] == annee_src].copy()
            ajust = st.radio("Ajustement", ["Aucun", "Pourcentage"])
            if ajust == "Pourcentage":
                coeff = st.number_input("% +/-", min_value=-50.0, max_value=100.0, value=3.0, step=0.5) / 100
                src['nouveau_montant'] = (src['montant_budget'] * (1+coeff)).round(0).astype(int)
            else:
                src['nouveau_montant'] = src['montant_budget']
            st.metric(f"Budget {nouvelle_annee}", f"{src['nouveau_montant'].sum():,.0f} €")
            existe = not budget_df[budget_df['annee'] == nouvelle_annee].empty
            if existe:
                st.warning(f"⚠️ Budget {nouvelle_annee} existe déjà.")
            else:
                if st.button(f"✨ Créer le budget {nouvelle_annee}", type="primary"):
                    try:
                        postes = [{'compte': r['compte'], 'libelle_compte': r['libelle_compte'],
                                   'montant_budget': int(r['nouveau_montant']), 'annee': int(nouvelle_annee),
                                   'classe': r['classe'], 'famille': r['famille']} for _, r in src.iterrows()]
                        for i in range(0, len(postes), 50):
                            supabase.table('budget').insert(postes[i:i+50]).execute()
                        st.success(f"✅ Budget {nouvelle_annee} créé ({len(postes)} postes)!"); st.rerun()
                    except Exception as e:
                        st.error(f"❌ {e}")

# ==================== DÉPENSES ====================
elif menu == "📝 Dépenses":
    st.markdown("<h1 class='main-header'>📝 Gestion des Dépenses</h1>", unsafe_allow_html=True)
    depenses_df = get_depenses()
    budget_df = get_budget()

    if not depenses_df.empty:
        depenses_df['date'] = pd.to_datetime(depenses_df['date'])
        depenses_df['annee'] = depenses_df['date'].dt.year
        depenses_df['montant_du'] = pd.to_numeric(depenses_df['montant_du'], errors='coerce')

        if not budget_df.empty:
            bud_uniq = budget_df.drop_duplicates(subset=['compte'], keep='first')[['compte','libelle_compte','classe','famille']]
            depenses_df = depenses_df.merge(bud_uniq, on='compte', how='left', suffixes=('','_bud'))

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            annee_dep = st.selectbox("📅 Année", sorted(depenses_df['annee'].unique(), reverse=True), key="dep_annee")
        with col2:
            cpt_filter = st.multiselect("🔢 Compte", options=sorted(depenses_df['compte'].dropna().unique()))
        with col3:
            cl_filter = st.multiselect("🏷️ Classe", options=sorted([c for c in depenses_df['classe'].dropna().unique() if c]))
        with col4:
            four_filter = st.multiselect("🏢 Fournisseur", options=sorted(depenses_df['fournisseur'].dropna().unique()))

        dep_f = depenses_df[depenses_df['annee'] == annee_dep].copy()
        if cpt_filter: dep_f = dep_f[dep_f['compte'].isin(cpt_filter)]
        if cl_filter: dep_f = dep_f[dep_f['classe'].isin(cl_filter)]
        if four_filter: dep_f = dep_f[dep_f['fournisseur'].isin(four_filter)]

        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        total_dep = dep_f['montant_du'].sum()
        bud_tot = budget_df[budget_df['annee'] == annee_dep]['montant_budget'].sum() if not budget_df.empty and 'annee' in budget_df.columns else 0
        c1.metric("Nb dépenses", len(dep_f))
        c2.metric("Total", f"{total_dep:,.2f} €")
        c3.metric("Moyenne", f"{dep_f['montant_du'].mean():,.2f} €" if len(dep_f) > 0 else "0 €")
        if bud_tot > 0:
            c4.metric("Réalisé vs Budget", f"{total_dep/bud_tot*100:.1f}%", delta=f"{total_dep-bud_tot:,.0f} €")
        else:
            c4.metric("Réalisé vs Budget", "N/A")
        st.divider()

        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 Consulter", "✏️ Modifier", "➕ Ajouter", "🗑️ Supprimer", "🏗️ Travaux Votés"])

        with tab1:
            disp = dep_f[['date','compte','libelle_compte','fournisseur','montant_du','classe','commentaire']].copy().sort_values('date', ascending=False)
            disp['date'] = disp['date'].dt.strftime('%d/%m/%Y')
            st.dataframe(disp, use_container_width=True, hide_index=True,
                column_config={"montant_du": st.column_config.NumberColumn("Montant (€)", format="%,.2f")})
            st.download_button("📥 Exporter CSV", dep_f.to_csv(index=False).encode('utf-8'), f"depenses_{annee_dep}.csv", "text/csv")

        with tab2:
            dep_edit_df = dep_f[['id','date','compte','fournisseur','montant_du','commentaire']].copy()
            dep_edit_df['compte'] = dep_edit_df['compte'].astype(str).fillna('')
            dep_edit_df['fournisseur'] = dep_edit_df['fournisseur'].astype(str).fillna('')
            dep_edit_df['commentaire'] = dep_edit_df['commentaire'].astype(str).fillna('')
            dep_edit_df['montant_du'] = pd.to_numeric(dep_edit_df['montant_du'], errors='coerce').fillna(0.0)
            edited_dep = st.data_editor(
                dep_edit_df,
                use_container_width=True, hide_index=True, disabled=['id'],
                column_config={
                    "date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                    "compte": st.column_config.TextColumn("Compte"),
                    "fournisseur": st.column_config.TextColumn("Fournisseur"),
                    "montant_du": st.column_config.NumberColumn("Montant (€)", format="%.2f"),
                    "commentaire": st.column_config.TextColumn("Commentaire"),
                }, key="dep_editor"
            )
            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Enregistrer", type="primary", key="save_dep"):
                    try:
                        mods = 0
                        for _, row in edited_dep.iterrows():
                            orig = dep_f[dep_f['id'] == row['id']]
                            if orig.empty: continue
                            o = orig.iloc[0]; updates = {}
                            date_new = pd.Timestamp(row['date']).strftime('%Y-%m-%d')
                            if date_new != o['date'].strftime('%Y-%m-%d'): updates['date'] = date_new
                            if str(row['compte']) != str(o['compte']): updates['compte'] = str(row['compte'])
                            if str(row['fournisseur']) != str(o['fournisseur']): updates['fournisseur'] = str(row['fournisseur'])
                            if float(row['montant_du']) != float(o['montant_du']): updates['montant_du'] = float(row['montant_du'])
                            if updates:
                                supabase.table('depenses').update(updates).eq('id', int(row['id'])).execute(); mods += 1
                        st.success(f"✅ {mods} ligne(s) mise(s) à jour!") if mods > 0 else st.info("Aucune modification")
                        if mods > 0: st.rerun()
                    except Exception as e:
                        st.error(f"❌ {e}")
            with col2:
                if st.button("🔄 Annuler", key="cancel_dep"): st.rerun()

        with tab3:
            new_cpt = st.text_input("Numéro de compte *", key="new_dep_cpt")
            cpt_bud = budget_df[budget_df['compte'].astype(str) == str(new_cpt)] if new_cpt and not budget_df.empty else pd.DataFrame()
            if not cpt_bud.empty:
                st.success(f"✅ {cpt_bud.iloc[0]['libelle_compte']} — Classe {cpt_bud.iloc[0]['classe']}")
                auto_classe = cpt_bud.iloc[0]['classe']
                auto_famille = cpt_bud.iloc[0]['famille']
            else:
                auto_classe = None; auto_famille = None
                if new_cpt: st.warning("⚠️ Compte non trouvé dans le budget")
            with st.form("form_dep"):
                c1, c2 = st.columns(2)
                with c1:
                    dep_date = st.date_input("Date *", value=datetime.now())
                    dep_four = st.text_input("Fournisseur *")
                with c2:
                    dep_mont = st.number_input("Montant (€) *", step=0.01, format="%.2f")
                    dep_comm = st.text_area("Commentaire")
                if st.form_submit_button("✨ Ajouter la dépense", type="primary", use_container_width=True):
                    if new_cpt and auto_classe and dep_four and dep_mont != 0:
                        try:
                            supabase.table('depenses').insert({
                                'date': dep_date.strftime('%Y-%m-%d'), 'compte': new_cpt,
                                'fournisseur': dep_four.strip(), 'montant_du': float(dep_mont),
                                'classe': auto_classe, 'famille': auto_famille,
                                'commentaire': dep_comm.strip() if dep_comm else None
                            }).execute()
                            st.success("✅ Dépense ajoutée!"); st.rerun()
                        except Exception as e:
                            st.error(f"❌ {e}")
                    else:
                        st.error("❌ Remplissez tous les champs obligatoires (compte valide, fournisseur, montant ≠ 0)")

        with tab4:
            st.warning("⚠️ La suppression est définitive.")
            ids_del = st.multiselect("Sélectionner les dépenses",
                options=dep_f['id'].tolist(),
                format_func=lambda x: f"ID {x} — {dep_f[dep_f['id']==x]['fournisseur'].values[0]} — {dep_f[dep_f['id']==x]['montant_du'].values[0]:.2f} €")
            if ids_del:
                if st.button("🗑️ Confirmer la suppression", type="secondary"):
                    for i in ids_del: supabase.table('depenses').delete().eq('id', i).execute()
                    st.success(f"✅ {len(ids_del)} dépense(s) supprimée(s)"); st.rerun()
        with tab5:
            st.subheader("🏗️ Travaux Votés en Assemblée Générale")
            st.info("""
            Les **travaux votés en AG** sont financés par appel de fonds spécifique et ne font pas partie
            des charges courantes. Les factures affectées ici sont **déduites des dépenses courantes**
            et n'entrent pas dans le calcul du 5ème appel de charges.
            """)

            tv_df = get_travaux_votes()
            tv_dep_ids = get_travaux_votes_depense_ids()

            # Métriques
            if not tv_df.empty:
                tv_df['date'] = pd.to_datetime(tv_df['date'])
                tv_df['montant'] = pd.to_numeric(tv_df['montant'], errors='coerce').fillna(0)
                tv_df['commentaire'] = tv_df['commentaire'].fillna('').astype(str).replace('None','')

            total_tv = tv_df['montant'].sum() if not tv_df.empty else 0
            nb_tv = len(tv_df) if not tv_df.empty else 0
            nb_dep_transferees = len([x for x in tv_dep_ids if x])

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Nb travaux", nb_tv)
            c2.metric("Montant total", f"{total_tv:,.2f} €")
            c3.metric("Factures transférées", nb_dep_transferees)
            # Nb dépenses courantes de l'année filtrées par les transferts
            dep_tv_annee = dep_f[dep_f['id'].isin(tv_dep_ids)]
            c4.metric("Déduit des charges", f"{dep_tv_annee['montant_du'].sum():,.2f} €",
                help="Montant des factures de cette année transférées en travaux votés")

            st.divider()

            subtab1, subtab2, subtab3, subtab4 = st.tabs([
                "📋 Liste", "➕ Nouveau chantier", "🔗 Transférer factures", "🗑️ Gérer"
            ])

            # ---- LISTE ----
            with subtab1:
                if tv_df.empty:
                    st.info("💡 Aucun travail voté enregistré.")
                else:
                    # Grouper par objet/chantier si la colonne existe
                    disp_tv = tv_df.copy().sort_values('date', ascending=False)
                    disp_tv['date_fmt'] = disp_tv['date'].dt.strftime('%d/%m/%Y')
                    disp_tv['Source'] = disp_tv['depense_id'].apply(
                        lambda x: '🔗 Transférée' if pd.notna(x) and x else '✏️ Saisie manuelle')

                    cols_show = ['date_fmt','objet','fournisseur','montant','commentaire','Source']
                    cols_show = [c for c in cols_show if c in disp_tv.columns]
                    st.dataframe(
                        disp_tv[cols_show].rename(columns={
                            'date_fmt':'Date','objet':'Objet / Chantier',
                            'fournisseur':'Fournisseur','montant':'Montant (€)','commentaire':'Commentaire'
                        }),
                        use_container_width=True, hide_index=True,
                        column_config={"Montant (€)": st.column_config.NumberColumn(format="%,.2f")}
                    )

                    # Résumé par chantier
                    if 'objet' in tv_df.columns and tv_df['objet'].notna().any():
                        st.subheader("Résumé par chantier")
                        by_obj = tv_df.groupby('objet')['montant'].agg(['sum','count']).reset_index()
                        by_obj.columns = ['Chantier','Total (€)','Nb factures']
                        by_obj = by_obj.sort_values('Total (€)', ascending=False)
                        col1, col2 = st.columns(2)
                        with col1:
                            st.dataframe(by_obj, use_container_width=True, hide_index=True,
                                column_config={"Total (€)": st.column_config.NumberColumn(format="%,.2f")})
                        with col2:
                            fig = px.pie(by_obj, values='Total (€)', names='Chantier',
                                title="Répartition par chantier")
                            st.plotly_chart(fig, use_container_width=True)

                    csv_tv = tv_df.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
                    st.download_button("📥 Exporter CSV", csv_tv, "travaux_votes.csv", "text/csv")

            # ---- NOUVEAU CHANTIER / SAISIE MANUELLE ----
            with subtab2:
                st.subheader("Ajouter une dépense de travaux votés")
                with st.form("form_tv"):
                    col1, col2 = st.columns(2)
                    with col1:
                        tv_date = st.date_input("Date de la facture *", value=datetime.now())
                        tv_objet = st.text_input("Objet / Chantier *",
                            placeholder="Ex: Ravalement façade, Remplacement ascenseur...")
                        tv_fournisseur = st.text_input("Fournisseur *")
                    with col2:
                        tv_montant = st.number_input("Montant (€) *", min_value=0.0, step=0.01, format="%.2f")
                        tv_ag = st.text_input("AG de vote", placeholder="Ex: AG du 15/03/2024")
                        tv_comment = st.text_area("Commentaire")

                    if st.form_submit_button("✨ Enregistrer", type="primary", use_container_width=True):
                        if tv_objet and tv_fournisseur and tv_montant > 0:
                            try:
                                supabase.table('travaux_votes').insert({
                                    'date': tv_date.strftime('%Y-%m-%d'),
                                    'objet': tv_objet.strip(),
                                    'fournisseur': tv_fournisseur.strip(),
                                    'montant': float(tv_montant),
                                    'ag_vote': tv_ag.strip() if tv_ag else None,
                                    'commentaire': tv_comment.strip() if tv_comment else None,
                                    'depense_id': None
                                }).execute()
                                st.success("✅ Travaux enregistrés!"); st.rerun()
                            except Exception as e:
                                st.error(f"❌ {e}")
                        else:
                            st.error("❌ Remplissez tous les champs obligatoires")

            # ---- TRANSFÉRER FACTURES ----
            with subtab3:
                st.subheader("🔗 Transférer des factures depuis les Dépenses courantes")
                st.caption("Les factures transférées restent dans la table Dépenses mais sont marquées comme "
                           "travaux votés et **exclues des charges courantes** (5ème appel).")

                # Filtrer les dépenses non encore transférées
                dep_non_tv = dep_f[~dep_f['id'].isin(tv_dep_ids)].copy()
                dep_deja_tv = dep_f[dep_f['id'].isin(tv_dep_ids)].copy()

                col1, col2 = st.columns(2)
                col1.metric("Dépenses transférables", len(dep_non_tv))
                col2.metric("Déjà transférées (cette année)", len(dep_deja_tv),
                    delta=f"{dep_deja_tv['montant_du'].sum():,.2f} €")

                if dep_non_tv.empty:
                    st.info("Toutes les dépenses de cette année sont déjà transférées.")
                else:
                    # Champ objet / AG en haut
                    col1, col2 = st.columns(2)
                    with col1:
                        tv_objet_tr = st.text_input("Objet / Chantier *",
                            placeholder="Ex: Ravalement façade 2025", key="tv_objet_tr")
                    with col2:
                        tv_ag_tr = st.text_input("AG de vote",
                            placeholder="Ex: AG du 15/03/2024", key="tv_ag_tr")

                    st.caption("✅ Cochez les factures à transférer puis cliquez sur le bouton.")

                    # Tableau éditable avec case à cocher — c'est la SEULE façon d'avoir des cases interactives
                    dep_editor = dep_non_tv[['id','date','fournisseur','montant_du','classe','commentaire']].copy()
                    dep_editor['date'] = dep_editor['date'].dt.strftime('%d/%m/%Y')
                    dep_editor['compte'] = dep_non_tv['compte'].astype(str).fillna('') if 'compte' in dep_non_tv.columns else ''
                    dep_editor['fournisseur'] = dep_editor['fournisseur'].astype(str).fillna('')
                    dep_editor['commentaire'] = dep_editor['commentaire'].astype(str).fillna('').replace('None','')
                    dep_editor['montant_du'] = pd.to_numeric(dep_editor['montant_du'], errors='coerce').fillna(0.0)
                    dep_editor['✓ Transférer'] = False  # case à cocher initiale

                    edited_tv = st.data_editor(
                        dep_editor[['✓ Transférer','date','fournisseur','compte','montant_du','classe','commentaire']],
                        use_container_width=True, hide_index=True,
                        disabled=['date','fournisseur','compte','montant_du','classe','commentaire'],
                        column_config={
                            '✓ Transférer': st.column_config.CheckboxColumn("✓", help="Cocher pour transférer"),
                            'montant_du': st.column_config.NumberColumn("Montant (€)", format="%,.2f"),
                            'date': st.column_config.TextColumn("Date"),
                            'fournisseur': st.column_config.TextColumn("Fournisseur"),
                            'compte': st.column_config.TextColumn("Compte"),
                            'classe': st.column_config.TextColumn("Classe"),
                            'commentaire': st.column_config.TextColumn("Commentaire"),
                        }, key="tv_dep_editor"
                    )

                    # Récupérer les IDs cochés
                    ids_tv_sel = dep_non_tv['id'].values[edited_tv['✓ Transférer'].values]

                    if len(ids_tv_sel) > 0:
                        total_sel_tv = dep_non_tv[dep_non_tv['id'].isin(ids_tv_sel)]['montant_du'].sum()
                        st.info(f"**{len(ids_tv_sel)}** facture(s) sélectionnée(s) — **{total_sel_tv:,.2f} €**")

                    if st.button("🔗 Transférer en Travaux Votés", type="primary",
                                 disabled=(len(ids_tv_sel) == 0)):
                        if not tv_objet_tr:
                            st.error("❌ Saisissez l'objet du chantier")
                        else:
                            try:
                                for dep_id in ids_tv_sel:
                                    dep_row = dep_non_tv[dep_non_tv['id'] == dep_id].iloc[0]
                                    supabase.table('travaux_votes').insert({
                                        'date': dep_row['date'].strftime('%Y-%m-%d'),
                                        'objet': tv_objet_tr.strip(),
                                        'fournisseur': dep_row['fournisseur'],
                                        'montant': float(dep_row['montant_du']),
                                        'ag_vote': tv_ag_tr.strip() if tv_ag_tr else None,
                                        'commentaire': str(dep_row.get('commentaire','') or ''),
                                        'depense_id': int(dep_id)
                                    }).execute()
                                st.success(f"✅ {len(ids_tv_sel)} facture(s) transférée(s)!"); st.rerun()
                            except Exception as e:
                                st.error(f"❌ {e}")

                # Retransférer (annuler un transfert)
                if not dep_deja_tv.empty:
                    st.divider()
                    st.subheader("↩️ Annuler un transfert")
                    ids_annul = st.multiselect(
                        "Factures à ré-intégrer dans les charges courantes",
                        options=dep_deja_tv['id'].tolist(),
                        format_func=lambda x: (
                            f"{dep_deja_tv[dep_deja_tv['id']==x]['date'].dt.strftime('%d/%m/%Y').values[0]} — "
                            f"{dep_deja_tv[dep_deja_tv['id']==x]['fournisseur'].values[0]} — "
                            f"{dep_deja_tv[dep_deja_tv['id']==x]['montant_du'].values[0]:,.2f} €"
                        ), key="tv_annul"
                    )
                    if ids_annul and st.button("↩️ Annuler le transfert", type="secondary"):
                        try:
                            for dep_id in ids_annul:
                                supabase.table('travaux_votes').delete().eq('depense_id', dep_id).execute()
                            st.success(f"✅ {len(ids_annul)} transfert(s) annulé(s)"); st.rerun()
                        except Exception as e:
                            st.error(f"❌ {e}")

            # ---- GÉRER ----
            with subtab4:
                st.warning("⚠️ La suppression est définitive.")
                if tv_df.empty:
                    st.info("Aucun travail voté enregistré.")
                else:
                    tv_manuels = tv_df[tv_df['depense_id'].isna()] if 'depense_id' in tv_df.columns else tv_df
                    if not tv_manuels.empty:
                        ids_tv_del = st.multiselect("Supprimer des entrées manuelles",
                            options=tv_manuels['id'].tolist(),
                            format_func=lambda x: (
                                f"{tv_manuels[tv_manuels['id']==x]['date'].dt.strftime('%d/%m/%Y').values[0]} — "
                                f"{tv_manuels[tv_manuels['id']==x]['objet'].values[0]} — "
                                f"{tv_manuels[tv_manuels['id']==x]['montant'].values[0]:,.2f} €"
                            ))
                        if ids_tv_del and st.button("🗑️ Supprimer", type="secondary", key="del_tv"):
                            for i in ids_tv_del:
                                supabase.table('travaux_votes').delete().eq('id', i).execute()
                            st.success(f"✅ {len(ids_tv_del)} supprimé(s)"); st.rerun()
                    else:
                        st.info("Toutes les entrées sont des transferts (à annuler via l'onglet 🔗).")

    else:
        st.info("💡 Aucune dépense. Utilisez l'onglet ➕ Ajouter.")

# ==================== COPROPRIÉTAIRES ====================
elif menu == "👥 Copropriétaires":
    st.markdown("<h1 class='main-header'>👥 Copropriétaires</h1>", unsafe_allow_html=True)
    copro_df = get_coproprietaires()

    if not copro_df.empty:
        copro_df = prepare_copro(copro_df)
        tantieme_cols = ['tantieme_general','tantieme_ascenseurs','tantieme_rdc_ssols','tantieme_garages','tantieme_ssols','tantieme_monte_voitures']

        c1, c2, c3 = st.columns(3)
        c1.metric("Copropriétaires", len(copro_df))
        c2.metric("Total tantièmes généraux", int(copro_df['tantieme_general'].sum()))
        c3.metric("Lots parkings", len(copro_df[copro_df['usage']=='parking']) if 'usage' in copro_df.columns else "—")

        st.divider()
        # Vérifier si les tantièmes spécifiques sont remplis
        remplis = {col: int(copro_df[col].sum()) for col in tantieme_cols if col in copro_df.columns}
        st.subheader("🔑 État des clés de répartition")
        cols = st.columns(len(remplis))
        for i, (col, total) in enumerate(remplis.items()):
            label = col.replace('tantieme_','').replace('_',' ').title()
            status = "✅" if total > 0 else "⚠️ À remplir"
            cols[i].metric(f"{status} {label}", f"{total:,}")

        if any(v == 0 for v in remplis.values()):
            st.warning("⚠️ Certains tantièmes sont à 0. Exécutez **UPDATE_TANTIEMES.sql** dans Supabase pour les remplir.")

        st.divider()
        col1, col2 = st.columns([1, 1])
        with col1:
            st.subheader("Répartition des tantièmes généraux")
            fig = px.pie(copro_df, values='tantieme_general', names='nom')
            fig.update_traces(textposition='inside', textinfo='percent')
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.subheader("Liste des copropriétaires")
            disp_cols = ['lot','nom','etage','usage','tantieme_general'] + [c for c in tantieme_cols[1:] if c in copro_df.columns]
            st.dataframe(copro_df[disp_cols].sort_values('lot' if 'lot' in copro_df.columns else 'nom'),
                use_container_width=True, hide_index=True)

# ==================== RÉPARTITION ====================
elif menu == "🔄 Répartition":
    st.markdown("<h1 class='main-header'>🔄 Appels de Fonds & Répartition</h1>", unsafe_allow_html=True)

    copro_df = get_coproprietaires()
    budget_df = get_budget()
    depenses_df = get_depenses()

    if copro_df.empty:
        st.error("❌ Impossible de charger les copropriétaires"); st.stop()

    copro_df = prepare_copro(copro_df)

    # Vérifier état des tantièmes
    tantieme_ok = copro_df['tantieme_general'].sum() > 0
    autres_ok = any(copro_df.get(CHARGES_CONFIG[k]['col'], pd.Series([0])).sum() > 0 for k in ['ascenseurs','rdc_ssols','garages','ssols'])

    if not autres_ok:
        st.warning("⚠️ Les tantièmes spécifiques (ascenseurs, garages, etc.) sont à 0. Exécutez **UPDATE_TANTIEMES.sql** dans Supabase. En attendant, tout est réparti sur les tantièmes généraux.")
        # Fallback temporaire
        for key in ['ascenseurs','rdc_ssols','garages','ssols']:
            col = CHARGES_CONFIG[key]['col']
            if col not in copro_df.columns or copro_df[col].sum() == 0:
                copro_df[col] = copro_df['tantieme_general']

    tab1, tab2, tab3 = st.tabs([
        "📅 Appels provisionnels (T1/T2/T3/T4)",
        "🔄 5ème appel — Régularisation",
        "📊 Vue globale annuelle"
    ])

    # ---- Budget sélectionné ----
    if not budget_df.empty:
        annees_bud = sorted(budget_df['annee'].unique(), reverse=True)
    else:
        annees_bud = [datetime.now().year]

    # ==================== ONGLET 1 : APPELS PROVISIONNELS ====================
    with tab1:
        st.subheader("Calcul des appels de fonds provisionnels")
        st.info("Les appels sont calculés sur le **budget prévisionnel**, réparti selon les clés de tantièmes de votre règlement de copropriété.")

        col1, col2, col3 = st.columns(3)
        with col1:
            annee_appel = st.selectbox("📅 Année", annees_bud, key="appel_annee")
        with col2:
            trimestre = st.selectbox("📆 Appel", ["T1 — Janvier","T2 — Avril","T3 — Juillet","T4 — Octobre"], key="appel_trim")
        with col3:
            nb_appels = st.selectbox("Nb appels / an", [4, 3, 2, 1], index=0, key="nb_appels")

        label_trim = trimestre.split(" ")[0]

        if budget_df.empty:
            st.warning("⚠️ Aucun budget. Créez-en un dans 💰 Budget.")
        else:
            bud_an = budget_df[budget_df['annee'] == annee_appel]
            if bud_an.empty:
                st.warning(f"⚠️ Aucun budget pour {annee_appel}.")
            else:
                # Budget TOTAL voté en AG — sert de base pour le calcul Alur
                total_bud = float(bud_an['montant_budget'].sum())

                # Montants par type basé sur les classes du budget
                montants_auto = {}
                for key, cfg in CHARGES_CONFIG.items():
                    montants_auto[key] = float(bud_an[bud_an['classe'].isin(cfg['classes'])]['montant_budget'].sum())
                # Classes non mappées → ajoutées aux charges générales
                total_mappe = sum(montants_auto.values())
                if total_bud - total_mappe > 0.01:
                    montants_auto['general'] = montants_auto.get('general', 0) + (total_bud - total_mappe)

                st.divider()
                st.subheader(f"⚙️ Montants annuels par type de charge — Budget {annee_appel}")
                st.caption("Calculés automatiquement depuis votre budget. Vous pouvez les ajuster.")

                col1, col2, col3 = st.columns(3)
                montants = {}
                items = list(CHARGES_CONFIG.items())
                for i, (key, cfg) in enumerate(items):
                    col = [col1, col2, col3][i % 3]
                    with col:
                        montants[key] = st.number_input(
                            f"{cfg['emoji']} {cfg['label']} (€/an)",
                            min_value=0, value=int(montants_auto.get(key, 0)),
                            step=100, key=f"mont_{key}",
                            help=f"Réparti sur {cfg['total']:,} tantièmes — Classes : {', '.join(cfg['classes'])}"
                        )

                total_configure = sum(montants.values())

                st.divider()

                # ---- LOI ALUR ----
                st.subheader("🏛️ Loi Alur — Fonds de travaux")
                st.caption("Cotisation obligatoire = 5% minimum du budget prévisionnel, répartie sur les tantièmes généraux.")
                col1, col2, col3 = st.columns(3)
                with col1:
                    alur_taux = st.number_input("Taux Alur (%)", min_value=5.0, max_value=20.0,
                        value=5.0, step=0.5, key="alur_taux",
                        help="Minimum légal = 5% du budget prévisionnel voté en AG (loi Alur art. 14-2)")
                with col2:
                    # BASE CORRECTE : budget total voté (total_bud), pas les montants configurés
                    alur_annuel = round(total_bud * alur_taux / 100, 2)
                    st.metric("Fonds de travaux annuel", f"{alur_annuel:,.2f} €",
                        help=f"{alur_taux}% × {total_bud:,.0f} € (budget voté en AG)")
                with col3:
                    alur_par_appel = round(alur_annuel / nb_appels, 2)
                    st.metric(f"Alur par appel ({label_trim})", f"{alur_par_appel:,.2f} €")

                st.divider()
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Budget charges", f"{total_configure:,.0f} €")
                c2.metric("Fonds de travaux (Alur)", f"{alur_annuel:,.2f} €")
                total_avec_alur = total_configure + alur_annuel
                c3.metric("Total appel annuel", f"{total_avec_alur:,.2f} €")
                ecart_cfg = total_configure - total_bud
                c4.metric("Écart vs budget", f"{ecart_cfg:+,.0f} €",
                    delta_color="normal" if abs(ecart_cfg) < 100 else "inverse")

                if abs(ecart_cfg) > 500:
                    st.warning(f"⚠️ Différence de {abs(ecart_cfg):,.0f} € entre le total configuré et le budget.")

                st.divider()
                st.subheader(f"📋 Appel {label_trim} {annee_appel} — {100//nb_appels}% du budget annuel + Alur")

                # Calcul charges + Alur
                appels_df = calculer_appels(copro_df, montants)
                appels_df[f'🎯 APPEL {label_trim} (€)'] = (appels_df['💰 TOTAL Annuel (€)'] / nb_appels).round(2)

                # Ajouter la cotisation Alur (répartie sur tantièmes généraux /10000)
                # Utilise _tantieme_general stocké directement dans appels_df (évite le lookup par nom bugué)
                appels_df['🏛️ Alur (€)'] = (appels_df['_tantieme_general'] / 10000 * alur_par_appel).round(2)
                appels_df[f'🎯 TOTAL {label_trim} avec Alur (€)'] = (
                    appels_df[f'🎯 APPEL {label_trim} (€)'] + appels_df['🏛️ Alur (€)']
                ).round(2)

                show_detail = st.checkbox("Afficher le détail par type de charge", value=False, key="show_det")

                # Supprimer la colonne technique avant affichage
                if '_tantieme_general' in appels_df.columns:
                    appels_df = appels_df.drop(columns=['_tantieme_general'])
                detail_cols = [f"{CHARGES_CONFIG[k]['emoji']} {CHARGES_CONFIG[k]['label']}" for k in CHARGES_CONFIG]
                base_cols = ['Lot','Copropriétaire','Étage','Usage']
                alur_cols = ['🏛️ Alur (€)', f'🎯 TOTAL {label_trim} avec Alur (€)']
                if show_detail:
                    display_cols = base_cols + detail_cols + ['💰 TOTAL Annuel (€)', f'🎯 APPEL {label_trim} (€)'] + alur_cols
                else:
                    display_cols = base_cols + ['💰 TOTAL Annuel (€)', f'🎯 APPEL {label_trim} (€)'] + alur_cols

                display_cols = [c for c in display_cols if c in appels_df.columns]

                st.dataframe(appels_df[display_cols], use_container_width=True, hide_index=True,
                    column_config={
                        f'🎯 APPEL {label_trim} (€)': st.column_config.NumberColumn("Charges (€)", format="%.2f"),
                        '🏛️ Alur (€)': st.column_config.NumberColumn("Alur (€)", format="%.2f"),
                        f'🎯 TOTAL {label_trim} avec Alur (€)': st.column_config.NumberColumn(f"🎯 TOTAL {label_trim} (€)", format="%.2f"),
                        '💰 TOTAL Annuel (€)': st.column_config.NumberColumn("Total Annuel (€)", format="%.2f"),
                    })

                st.divider()
                c1, c2, c3, c4 = st.columns(4)
                total_charges = appels_df[f'🎯 APPEL {label_trim} (€)'].sum()
                total_alur_appel = appels_df['🏛️ Alur (€)'].sum()
                total_avec_alur = appels_df[f'🎯 TOTAL {label_trim} avec Alur (€)'].sum()
                c1.metric(f"Charges {label_trim}", f"{total_charges:,.2f} €")
                c2.metric("Fonds Alur", f"{total_alur_appel:,.2f} €")
                c3.metric(f"🎯 TOTAL {label_trim}", f"{total_avec_alur:,.2f} €")
                c4.metric("Appel moyen / copro", f"{total_avec_alur/len(appels_df):,.2f} €")

                csv_appel = appels_df.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')

                # ---- EXPORT CSV + PDF ----
                col_exp1, col_exp2, col_exp3 = st.columns(3)
                with col_exp1:
                    st.download_button(
                        f"📥 CSV — Appel {label_trim} {annee_appel}",
                        csv_appel, f"appel_{label_trim}_{annee_appel}.csv", "text/csv"
                    )

                with col_exp2:
                    # PDF individuel : sélection d'un copropriétaire
                    noms_copros = appels_df['Copropriétaire'].tolist()
                    copro_sel_pdf = st.selectbox(
                        "📄 PDF individuel — Copropriétaire",
                        options=noms_copros,
                        key="pdf_copro_sel"
                    )
                    if st.button("📄 Générer PDF individuel", key="btn_pdf_indiv"):
                        cop_row_pdf = copro_df[copro_df['nom'] == copro_sel_pdf].iloc[0] if len(copro_df[copro_df['nom'] == copro_sel_pdf]) > 0 else None
                        if cop_row_pdf is not None:
                            mois_debut = {'T1':'01/01','T2':'01/04','T3':'01/07','T4':'01/10'}[label_trim]
                            mois_fin   = {'T1':'31/03','T2':'30/06','T3':'30/09','T4':'31/12'}[label_trim]
                            periode_pdf = f"{mois_debut}/{annee_appel} au {mois_fin}/{annee_appel}"
                            pdf_bytes = generate_appel_pdf_bytes(
                                SYNDIC_INFO, cop_row_pdf.to_dict(), periode_pdf,
                                label_trim, annee_appel, montants, alur_par_appel, nb_appels
                            )
                            st.download_button(
                                f"⬇️ Télécharger PDF — {copro_sel_pdf}",
                                pdf_bytes,
                                f"appel_{label_trim}_{annee_appel}_{cop_row_pdf.get('lot','')}.pdf",
                                "application/pdf",
                                key="dl_pdf_indiv"
                            )
                        else:
                            st.error("Copropriétaire non trouvé")

                with col_exp3:
                    # PDF tous les copropriétaires (fusionné)
                    if st.button("📦 Générer tous les PDFs (ZIP)", key="btn_pdf_all"):
                        import zipfile, io as _io
                        mois_debut = {'T1':'01/01','T2':'01/04','T3':'01/07','T4':'01/10'}[label_trim]
                        mois_fin   = {'T1':'31/03','T2':'30/06','T3':'30/09','T4':'31/12'}[label_trim]
                        periode_pdf = f"{mois_debut}/{annee_appel} au {mois_fin}/{annee_appel}"

                        zip_buf = _io.BytesIO()
                        nb_gen = 0
                        with st.spinner(f"Génération des PDFs en cours..."):
                            with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                                for _, cop_row_pdf in copro_df.iterrows():
                                    try:
                                        pdf_b = generate_appel_pdf_bytes(
                                            SYNDIC_INFO, cop_row_pdf.to_dict(), periode_pdf,
                                            label_trim, annee_appel, montants, alur_par_appel, nb_appels
                                        )
                                        fname = f"appel_{label_trim}_{annee_appel}_lot{str(cop_row_pdf.get('lot','')).zfill(4)}.pdf"
                                        zf.writestr(fname, pdf_b)
                                        nb_gen += 1
                                    except Exception as e_pdf:
                                        st.warning(f"⚠️ Erreur lot {cop_row_pdf.get('lot','?')}: {e_pdf}")
                        zip_buf.seek(0)
                        st.success(f"✅ {nb_gen} PDFs générés")
                        st.download_button(
                            f"⬇️ Télécharger ZIP ({nb_gen} PDFs)",
                            zip_buf.getvalue(),
                            f"appels_{label_trim}_{annee_appel}.zip",
                            "application/zip",
                            key="dl_zip_all"
                        )

                st.divider()
                col1, col2 = st.columns(2)
                with col1:
                    top15 = appels_df.nlargest(15, f'🎯 APPEL {label_trim} (€)')
                    fig = px.bar(top15, x='Copropriétaire', y=f'🎯 APPEL {label_trim} (€)',
                        color='Usage', title=f"Top 15 — Appel {label_trim} {annee_appel}",
                        text=f'🎯 APPEL {label_trim} (€)')
                    fig.update_traces(texttemplate='%{text:.0f}€', textposition='outside')
                    fig.update_layout(xaxis_tickangle=45)
                    st.plotly_chart(fig, use_container_width=True)
                with col2:
                    type_data = pd.DataFrame([
                        {'Type': f"{cfg['emoji']} {cfg['label']}", 'Montant': montants[k]}
                        for k, cfg in CHARGES_CONFIG.items() if montants[k] > 0
                    ])
                    if not type_data.empty:
                        fig = px.pie(type_data, values='Montant', names='Type', title="Répartition par type de charge")
                        st.plotly_chart(fig, use_container_width=True)

    # ==================== ONGLET 2 : 5ÈME APPEL RÉGULARISATION ====================
    with tab2:
        st.subheader("5ème appel — Régularisation sur dépenses réelles")
        st.info("""
        **Principe :** Les 4 appels provisionnels sont basés sur le budget prévisionnel.  
        Le 5ème appel régularise la différence entre les **dépenses réelles** et les **provisions versées**.  
        → Solde **positif** = complément à appeler | Solde **négatif** = remboursement aux copropriétaires
        """)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            annee_reg = st.selectbox("📅 Année à régulariser", annees_bud, key="reg_annee")
        with col2:
            nb_appels_reg = st.selectbox("Nb appels provisionnels versés", [4,3,2,1], key="nb_reg",
                help="Nombre d'appels provisionnels déjà appelés dans l'année")
        with col3:
            alur_taux_reg = st.number_input("🏛️ Taux Alur (%)", min_value=5.0, max_value=20.0,
                value=5.0, step=0.5, key="alur_taux_reg",
                help="Taux Alur appliqué lors des appels provisionnels (5% minimum légal)")
        with col4:
            source_prov = st.radio("Base des provisions", ["Budget prévisionnel", "Saisie manuelle"], key="src_prov",
                help="Budget = les provisions sont calculées depuis le budget. Manuelle = vous saisissez les montants exacts appelés.")

        if depenses_df.empty:
            st.warning("⚠️ Aucune dépense disponible.")
        else:
            # Préparer les dépenses réelles de l'année
            depenses_df_reg = depenses_df.copy()
            depenses_df_reg['date'] = pd.to_datetime(depenses_df_reg['date'])
            depenses_df_reg['montant_du'] = pd.to_numeric(depenses_df_reg['montant_du'], errors='coerce')
            dep_reg = depenses_df_reg[depenses_df_reg['date'].dt.year == annee_reg].copy()

            # Exclure les dépenses affectées au fonds Alur
            alur_ids_reg = get_depenses_alur_ids()
            dep_reg_alur = dep_reg[dep_reg['id'].isin(alur_ids_reg)]
            nb_alur_exclus = len(dep_reg_alur)
            montant_alur_exclus = dep_reg_alur['montant_du'].sum()

            # Exclure les dépenses transférées en Travaux Votés
            tv_ids_reg = get_travaux_votes_depense_ids()
            dep_reg_tv = dep_reg[dep_reg['id'].isin(tv_ids_reg)]
            nb_tv_exclus = len(dep_reg_tv)
            montant_tv_exclus = dep_reg_tv['montant_du'].sum()

            # Dépenses courantes = hors Alur ET hors Travaux Votés
            ids_exclus = set(alur_ids_reg) | set(tv_ids_reg)
            dep_reg_hors_alur = dep_reg[~dep_reg['id'].isin(ids_exclus)]

            # Bandeau récap des exclusions
            if nb_alur_exclus > 0 or nb_tv_exclus > 0:
                msg_parts = []
                if nb_alur_exclus > 0:
                    msg_parts.append(f"🏛️ **{nb_alur_exclus} dép. Alur** ({montant_alur_exclus:,.2f} €)")
                if nb_tv_exclus > 0:
                    msg_parts.append(f"🏗️ **{nb_tv_exclus} dép. Travaux Votés** ({montant_tv_exclus:,.2f} €)")
                total_exclus = montant_alur_exclus + montant_tv_exclus
                st.info(f"Dépenses exclues des charges courantes : {' + '.join(msg_parts)} "
                        f"= **{total_exclus:,.2f} €** déduits du 5ème appel")

            # Dépenses réelles HORS Alur et HORS Travaux Votés par type
            reel_auto = {}
            for key, cfg in CHARGES_CONFIG.items():
                if 'classe' in dep_reg_hors_alur.columns:
                    reel_auto[key] = float(dep_reg_hors_alur[dep_reg_hors_alur['classe'].isin(cfg['classes'])]['montant_du'].sum())
                else:
                    reel_auto[key] = 0
            total_reel_auto = sum(reel_auto.values())

            # Budget de l'année pour les provisions auto
            # Provisions versées = budget annuel / 4 appels × nb_appels_reg versés + Alur versé
            bud_reg = budget_df[budget_df['annee'] == annee_reg] if not budget_df.empty else pd.DataFrame()
            nb_appels_annee = 4  # appels provisionnels par an (standard)
            total_bud_reg = float(bud_reg['montant_budget'].sum()) if not bud_reg.empty else 0

            # Calcul Alur versé sur la période
            alur_annuel_reg = round(total_bud_reg * alur_taux_reg / 100, 2)
            alur_par_appel_reg = round(alur_annuel_reg / nb_appels_annee, 2)
            alur_verse_reg = round(alur_par_appel_reg * nb_appels_reg, 2)  # total Alur versé sur nb_appels_reg

            prov_auto = {}
            for key, cfg in CHARGES_CONFIG.items():
                if not bud_reg.empty:
                    budget_annuel_type = float(bud_reg[bud_reg['classe'].isin(cfg['classes'])]['montant_budget'].sum())
                    prov_auto[key] = round(budget_annuel_type / nb_appels_annee * nb_appels_reg, 2)
                else:
                    prov_auto[key] = 0

            st.divider()

            # ---- TABLEAU RÉCAP AUTOMATIQUE ----
            st.subheader(f"📊 Dépenses réelles {annee_reg} par type de charge")

            # Calcul des totaux bruts (toutes dépenses de l'année)
            reel_brut = {}
            for key, cfg in CHARGES_CONFIG.items():
                if 'classe' in dep_reg.columns:
                    reel_brut[key] = float(dep_reg[dep_reg['classe'].isin(cfg['classes'])]['montant_du'].sum())
                else:
                    reel_brut[key] = 0
            total_reel_brut = sum(reel_brut.values())

            # Déduction Alur par type
            alur_ded = {}
            for key, cfg in CHARGES_CONFIG.items():
                if 'classe' in dep_reg_alur.columns:
                    alur_ded[key] = float(dep_reg_alur[dep_reg_alur['classe'].isin(cfg['classes'])]['montant_du'].sum())
                else:
                    alur_ded[key] = 0

            # Déduction Travaux Votés par type
            tv_ded = {}
            for key, cfg in CHARGES_CONFIG.items():
                if 'classe' in dep_reg_tv.columns:
                    tv_ded[key] = float(dep_reg_tv[dep_reg_tv['classe'].isin(cfg['classes'])]['montant_du'].sum())
                else:
                    tv_ded[key] = 0

            recap_data = []
            for key, cfg in CHARGES_CONFIG.items():
                recap_data.append({
                    'Type': f"{cfg['emoji']} {cfg['label']}",
                    'Classes': ', '.join(cfg['classes']),
                    'Budget (€)': round(prov_auto.get(key, 0), 2),
                    'Dépenses brutes (€)': round(reel_brut.get(key, 0), 2),
                    '— Alur (€)': round(-alur_ded.get(key, 0), 2) if alur_ded.get(key, 0) > 0 else None,
                    '— Trav. Votés (€)': round(-tv_ded.get(key, 0), 2) if tv_ded.get(key, 0) > 0 else None,
                    'Dépenses nettes (€)': round(reel_auto.get(key, 0), 2),
                    'Écart (€)': round(reel_auto.get(key, 0) - prov_auto.get(key, 0), 2),
                })

            # Ligne TOTAL
            recap_data.append({
                'Type': '💰 TOTAL',
                'Classes': '',
                'Budget (€)': sum(r['Budget (€)'] for r in recap_data),
                'Dépenses brutes (€)': round(total_reel_brut, 2),
                '— Alur (€)': round(-montant_alur_exclus, 2) if montant_alur_exclus > 0 else None,
                '— Trav. Votés (€)': round(-montant_tv_exclus, 2) if montant_tv_exclus > 0 else None,
                'Dépenses nettes (€)': round(total_reel_auto, 2),
                'Écart (€)': round(total_reel_auto - sum(r['Budget (€)'] for r in recap_data[:-1]), 2),
            })

            recap_df = pd.DataFrame(recap_data)
            st.dataframe(recap_df, use_container_width=True, hide_index=True,
                column_config={
                    'Budget (€)': st.column_config.NumberColumn(format="%,.2f"),
                    'Dépenses brutes (€)': st.column_config.NumberColumn(format="%,.2f"),
                    '— Alur (€)': st.column_config.NumberColumn(format="%,.2f"),
                    '— Trav. Votés (€)': st.column_config.NumberColumn(format="%,.2f"),
                    'Dépenses nettes (€)': st.column_config.NumberColumn(format="%,.2f"),
                    'Écart (€)': st.column_config.NumberColumn(format="%+,.2f"),
                })

            # Bandeau récap déductions si applicable
            if montant_alur_exclus > 0 or montant_tv_exclus > 0:
                cols_ded = st.columns(4)
                cols_ded[0].metric("Dépenses brutes", f"{total_reel_brut:,.2f} €")
                if montant_alur_exclus > 0:
                    cols_ded[1].metric("— Fonds Alur", f"{montant_alur_exclus:,.2f} €")
                if montant_tv_exclus > 0:
                    cols_ded[2].metric("— Travaux Votés", f"{montant_tv_exclus:,.2f} €")
                cols_ded[3].metric("= Dépenses nettes", f"{total_reel_auto:,.2f} €",
                    delta=f"-{montant_alur_exclus + montant_tv_exclus:,.2f} €",
                    delta_color="off")

            st.divider()

            # ---- SAISIE DES PROVISIONS ----
            st.subheader("💰 Montants des provisions versées")

            if source_prov == "Budget prévisionnel":
                st.caption(f"✅ Budget {annee_reg} ÷ 4 × {nb_appels_reg} appels + Alur ({alur_taux_reg:.0f}% × {nb_appels_reg} appels = {alur_verse_reg:,.2f} €)")
                provisions = {k: v for k, v in prov_auto.items()}
                # Affichage en lecture seule
                prov_display = pd.DataFrame([
                    {'Type': f"{CHARGES_CONFIG[k]['emoji']} {CHARGES_CONFIG[k]['label']}",
                     'Provisions versées (€)': round(v, 2)}
                    for k, v in provisions.items()
                ])
                prov_display.loc[len(prov_display)] = {
                    'Type': '🏛️ Fonds Alur', 'Provisions versées (€)': alur_verse_reg}
                prov_display.loc[len(prov_display)] = {
                    'Type': '💰 TOTAL (charges + Alur)', 'Provisions versées (€)': sum(provisions.values()) + alur_verse_reg}
                st.dataframe(prov_display, use_container_width=True, hide_index=True,
                    column_config={"Provisions versées (€)": st.column_config.NumberColumn(format="%,.2f")})
            else:
                st.caption("Saisissez les montants **exacts** appelés pour chaque type de charge sur l'année.")
                col1, col2, col3 = st.columns(3)
                provisions = {}
                for i, (key, cfg) in enumerate(CHARGES_CONFIG.items()):
                    with [col1, col2, col3][i % 3]:
                        provisions[key] = st.number_input(
                            f"{cfg['emoji']} {cfg['label']} (€)",
                            min_value=0.0,
                            value=round(prov_auto.get(key, 0.0), 2),  # déjà × nb_appels_reg/4
                            step=100.0, key=f"prov_man_{key}"
                        )

            total_prov = sum(provisions.values()) + alur_verse_reg

            st.divider()

            # ---- MÉTRIQUES GLOBALES ----
            c1, c2, c3, c4 = st.columns(4)
            solde_global = total_reel_auto - total_prov
            c1.metric("Dépenses nettes", f"{total_reel_auto:,.2f} €",
                help=f"Brut {total_reel_brut:,.2f} € − déductions {montant_alur_exclus+montant_tv_exclus:,.2f} €")
            c2.metric("Provisions versées", f"{total_prov:,.2f} €")
            c3.metric("5ème appel global", f"{solde_global:+,.2f} €",
                delta_color="inverse" if solde_global > 0 else "normal")
            c4.metric("Dépenses exclues", f"{montant_alur_exclus+montant_tv_exclus:,.2f} €",
                help=f"Alur: {montant_alur_exclus:,.2f} € | Travaux votés: {montant_tv_exclus:,.2f} €")

            if total_prov == 0:
                st.info("💡 Configurez les provisions pour calculer la régularisation.")
            else:
                st.divider()
                st.subheader(f"📋 5ème appel de régularisation — {annee_reg}")

                # ---- CALCUL PAR COPROPRIÉTAIRE ----
                reg_list = []
                for _, cop in copro_df.iterrows():
                    prov_cop = 0
                    reel_cop = 0
                    detail_prov = {}
                    detail_reel = {}

                    for key, cfg in CHARGES_CONFIG.items():
                        tant = float(cop.get(cfg['col'], 0) or 0)
                        if cfg['total'] > 0 and tant > 0:
                            part_prov = (tant / cfg['total']) * provisions[key]
                            part_reel = (tant / cfg['total']) * reel_auto[key]
                        else:
                            part_prov = 0
                            part_reel = 0
                        prov_cop += part_prov
                        reel_cop += part_reel
                        detail_prov[key] = round(part_prov, 2)
                        detail_reel[key] = round(part_reel, 2)

                    # Ajouter Alur versé par ce copropriétaire (sur tantièmes généraux)
                    tant_gen = float(cop.get('tantieme_general', 0) or 0)
                    alur_cop_verse = round(tant_gen / 10000 * alur_verse_reg, 2) if tant_gen > 0 else 0
                    prov_cop += alur_cop_verse

                    reg = reel_cop - prov_cop

                    row = {
                        'Lot': cop.get('lot', ''),
                        'Copropriétaire': cop.get('nom', ''),
                        'Étage': cop.get('etage', ''),
                        'Usage': cop.get('usage', ''),
                        'Provisions charges (€)': round(prov_cop - alur_cop_verse, 2),
                        '🏛️ Alur versé (€)': round(alur_cop_verse, 2),
                        'Provisions versées (€)': round(prov_cop, 2),
                        'Dépenses réelles (€)': round(reel_cop, 2),
                        '5ème appel (€)': round(reg, 2),
                        'Sens': '💳 À payer' if reg > 0.01 else ('💚 À rembourser' if reg < -0.01 else '✅ Soldé'),
                    }
                    reg_list.append(row)

                reg_df = pd.DataFrame(reg_list).sort_values('Lot')

                # Options d'affichage
                col1, col2 = st.columns(2)
                with col1:
                    show_zeros = st.checkbox("Afficher les lots soldés", value=True, key="show_zeros_reg")
                with col2:
                    filtre_sens = st.selectbox("Filtrer par sens", ["Tous","💳 À payer","💚 À rembourser","✅ Soldé"], key="filtre_sens")

                reg_display = reg_df.copy()
                if not show_zeros:
                    reg_display = reg_display[reg_display['5ème appel (€)'].abs() > 0.01]
                if filtre_sens != "Tous":
                    reg_display = reg_display[reg_display['Sens'] == filtre_sens]

                st.dataframe(reg_display, use_container_width=True, hide_index=True,
                    column_config={
                        'Provisions versées (€)': st.column_config.NumberColumn(format="%.2f"),
                        'Dépenses réelles (€)': st.column_config.NumberColumn(format="%.2f"),
                        '5ème appel (€)': st.column_config.NumberColumn("🎯 5ème appel (€)", format="%+.2f"),
                    })

                st.divider()

                # ---- MÉTRIQUES FINALES ----
                c1, c2, c3, c4 = st.columns(4)
                a_payer_df = reg_df[reg_df['5ème appel (€)'] > 0.01]
                a_rembourser_df = reg_df[reg_df['5ème appel (€)'] < -0.01]
                c1.metric("Provisions versées", f"{reg_df['Provisions versées (€)'].sum():,.2f} €")
                c2.metric("Dépenses réelles", f"{reg_df['Dépenses réelles (€)'].sum():,.2f} €")
                c3.metric(f"💳 Montant à appeler ({len(a_payer_df)} lots)", f"{a_payer_df['5ème appel (€)'].sum():,.2f} €")
                c4.metric(f"💚 À rembourser ({len(a_rembourser_df)} lots)", f"{abs(a_rembourser_df['5ème appel (€)'].sum()):,.2f} €")

                # ---- GRAPHIQUE ----
                st.divider()
                col1, col2 = st.columns(2)
                with col1:
                    fig = px.bar(
                        reg_df.sort_values('5ème appel (€)', ascending=False),
                        x='Copropriétaire', y='5ème appel (€)',
                        color='Sens', title=f"5ème appel par copropriétaire — {annee_reg}",
                        color_discrete_map={'💳 À payer':'#e74c3c','💚 À rembourser':'#2ecc71','✅ Soldé':'#95a5a6'},
                        text='5ème appel (€)'
                    )
                    fig.update_traces(texttemplate='%{text:+.0f}€', textposition='outside')
                    fig.update_layout(xaxis_tickangle=45, height=450)
                    st.plotly_chart(fig, use_container_width=True)
                with col2:
                    # Répartition provisions vs réel par type
                    comp_types = pd.DataFrame([
                        {'Type': f"{CHARGES_CONFIG[k]['emoji']} {CHARGES_CONFIG[k]['label']}",
                         'Provisions (€)': round(provisions[k], 2),
                         'Réel (€)': round(reel_auto[k], 2)}
                        for k in CHARGES_CONFIG
                    ])
                    fig2 = go.Figure()
                    fig2.add_trace(go.Bar(name='Provisions', x=comp_types['Type'], y=comp_types['Provisions (€)'], marker_color='lightblue'))
                    fig2.add_trace(go.Bar(name='Réel', x=comp_types['Type'], y=comp_types['Réel (€)'], marker_color='salmon'))
                    fig2.update_layout(barmode='group', title='Provisions vs Réel par type', xaxis_tickangle=20)
                    st.plotly_chart(fig2, use_container_width=True)

                # ---- EXPORT ----
                st.divider()
                col1, col2 = st.columns(2)
                with col1:
                    csv_reg = reg_df.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
                    st.download_button(
                        f"📥 Exporter 5ème appel {annee_reg} (CSV)",
                        csv_reg, f"5eme_appel_{annee_reg}.csv", "text/csv"
                    )
                with col2:
                    # Export uniquement les lots à régulariser
                    reg_actif = reg_df[reg_df['5ème appel (€)'].abs() > 0.01]
                    csv_actif = reg_actif.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
                    st.download_button(
                        f"📥 Exporter uniquement lots à régulariser ({len(reg_actif)})",
                        csv_actif, f"5eme_appel_{annee_reg}_actif.csv", "text/csv"
                    )

    # ==================== ONGLET 3 : VUE GLOBALE ====================
    with tab3:
        st.subheader("📊 Vue globale annuelle — Charges + Alur par copropriétaire")

        col1, col2, col3 = st.columns(3)
        with col1:
            annee_glob = st.selectbox("📅 Année", annees_bud, key="glob_annee")
        with col2:
            nb_appels_glob = st.selectbox("Nb appels / an", [4,3,2,1], key="glob_nb")
        with col3:
            alur_taux_glob = st.number_input("🏛️ Taux Alur (%)", min_value=5.0, max_value=20.0,
                value=5.0, step=0.5, key="alur_taux_glob")

        bud_glob = budget_df[budget_df['annee'] == annee_glob] if not budget_df.empty else pd.DataFrame()
        total_bud_glob = float(bud_glob['montant_budget'].sum()) if not bud_glob.empty else 0
        alur_glob_annuel = round(total_bud_glob * alur_taux_glob / 100, 2)
        alur_glob_appel = round(alur_glob_annuel / nb_appels_glob, 2)

        st.info(f"Budget {annee_glob} : **{total_bud_glob:,.0f} €** "
                f"+ 🏛️ Alur ({alur_taux_glob:.0f}%) : **{alur_glob_annuel:,.0f} €/an** "
                f"= **{total_bud_glob + alur_glob_annuel:,.0f} €** total | {len(copro_df)} copropriétaires")
        st.divider()

        # Montants auto depuis budget
        montants_glob_auto = {}
        for key, cfg in CHARGES_CONFIG.items():
            if not bud_glob.empty:
                montants_glob_auto[key] = float(bud_glob[bud_glob['classe'].isin(cfg['classes'])]['montant_budget'].sum())
            else:
                montants_glob_auto[key] = 0

        st.subheader("⚙️ Ventilation du budget par type de charge")
        col1, col2, col3 = st.columns(3)
        montants_glob = {}
        for i, (key, cfg) in enumerate(CHARGES_CONFIG.items()):
            col = [col1, col2, col3][i % 3]
            with col:
                montants_glob[key] = st.number_input(
                    f"{cfg['emoji']} {cfg['label']} (€)",
                    min_value=0, value=int(montants_glob_auto.get(key, 0)),
                    step=100, key=f"glob_{key}"
                )

        total_glob = sum(montants_glob.values())
        st.divider()

        glob_df = calculer_appels(copro_df, montants_glob)

        # Alur par copropriétaire via tantième général
        glob_df['🏛️ Alur Annuel (€)'] = (glob_df['_tantieme_general'] / 10000 * alur_glob_annuel).round(2)
        glob_df['💰 TOTAL + Alur Annuel (€)'] = (glob_df['💰 TOTAL Annuel (€)'] + glob_df['🏛️ Alur Annuel (€)']).round(2)

        # Colonnes par appel
        for t in ['T1','T2','T3','T4']:
            glob_df[f'Charges {t} (€)'] = (glob_df['💰 TOTAL Annuel (€)'] / nb_appels_glob).round(2)
            glob_df[f'Alur {t} (€)'] = (glob_df['_tantieme_general'] / 10000 * alur_glob_appel).round(2)
            glob_df[f'🎯 TOTAL {t} (€)'] = (glob_df[f'Charges {t} (€)'] + glob_df[f'Alur {t} (€)']).round(2)

        # Supprimer colonne technique
        if '_tantieme_general' in glob_df.columns:
            glob_df = glob_df.drop(columns=['_tantieme_general'])

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Budget charges", f"{total_glob:,.0f} €")
        c2.metric(f"🏛️ Alur ({alur_taux_glob:.0f}%)", f"{alur_glob_annuel:,.0f} €")
        c3.metric("💰 TOTAL annuel + Alur", f"{glob_df['💰 TOTAL + Alur Annuel (€)'].sum():,.2f} €")
        c4.metric("Appel moyen / copro", f"{glob_df['💰 TOTAL + Alur Annuel (€)'].mean():,.2f} €")

        st.divider()

        # Choix de vue
        vue = st.radio("Affichage", ["Vue annuelle", "Vue par appel (T1/T2/T3/T4)"], horizontal=True, key="glob_vue")

        if vue == "Vue annuelle":
            display_cols = ['Lot','Copropriétaire','Étage','Usage',
                            '💰 TOTAL Annuel (€)','🏛️ Alur Annuel (€)','💰 TOTAL + Alur Annuel (€)']
        else:
            display_cols = ['Lot','Copropriétaire','Étage','Usage']
            for t in ['T1','T2','T3','T4']:
                display_cols += [f'Charges {t} (€)', f'Alur {t} (€)', f'🎯 TOTAL {t} (€)']

        display_cols = [c for c in display_cols if c in glob_df.columns]
        st.dataframe(glob_df[display_cols], use_container_width=True, hide_index=True,
            column_config={c: st.column_config.NumberColumn(format="%.2f") for c in display_cols if '€' in c})

        fig = px.bar(
            glob_df.sort_values('💰 TOTAL + Alur Annuel (€)', ascending=False),
            x='Copropriétaire', y=['💰 TOTAL Annuel (€)', '🏛️ Alur Annuel (€)'],
            title=f"Charges annuelles + Alur {annee_glob} par copropriétaire",
            labels={'value': 'Montant (€)', 'variable': 'Type'},
            color_discrete_map={'💰 TOTAL Annuel (€)': '#1f77b4', '🏛️ Alur Annuel (€)': '#ff7f0e'},
            barmode='stack'
        )
        fig.update_layout(xaxis_tickangle=45, height=500)
        st.plotly_chart(fig, use_container_width=True)

        csv_glob = glob_df.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
        st.download_button(f"📥 Exporter vue globale {annee_glob} (avec Alur)",
            csv_glob, f"charges_{annee_glob}.csv", "text/csv")

# ==================== ANALYSES ====================
elif menu == "🏛️ Loi Alur":
    st.markdown("<h1 class='main-header'>🏛️ Suivi Loi Alur — Fonds de Travaux</h1>", unsafe_allow_html=True)

    alur_df = get_loi_alur()
    depenses_df_alur = get_depenses()

    # Préparer les dépenses
    if not depenses_df_alur.empty:
        depenses_df_alur['date'] = pd.to_datetime(depenses_df_alur['date'])
        depenses_df_alur['montant_du'] = pd.to_numeric(depenses_df_alur['montant_du'], errors='coerce').fillna(0)

    # IDs dépenses déjà affectées Alur
    alur_depense_ids = get_depenses_alur_ids()

    # ---- MÉTRIQUES GLOBALES ----
    if not alur_df.empty:
        alur_df['date'] = pd.to_datetime(alur_df['date'])
        alur_df['appels_fonds'] = pd.to_numeric(alur_df['appels_fonds'], errors='coerce').fillna(0)
        alur_df['utilisation'] = pd.to_numeric(alur_df['utilisation'], errors='coerce').fillna(0)
        if 'commentaire' in alur_df.columns:
            alur_df['commentaire'] = alur_df['commentaire'].fillna('').astype(str).replace('None', '')
        total_appels = alur_df['appels_fonds'].sum()
        total_util = alur_df['utilisation'].sum()
        solde = total_appels - total_util
    else:
        total_appels = total_util = solde = 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Total appelé", f"{total_appels:,.2f} €")
    c2.metric("🔧 Total utilisé", f"{total_util:,.2f} €")
    c3.metric("📊 Solde disponible", f"{solde:,.2f} €",
        delta_color="normal" if solde >= 0 else "inverse")
    c4.metric("Nb opérations", len(alur_df) if not alur_df.empty else 0)

    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Grand Livre", "➕ Ajouter opération", "🔗 Affecter dépenses", "📊 Analyse"
    ])

    # ---- ONGLET 1 : GRAND LIVRE ----
    with tab1:
        st.subheader("Grand Livre du Fonds de Travaux")
        if alur_df.empty:
            st.info("💡 Aucune opération. Commencez par ajouter un 'À nouveau' ou un appel de fonds.")
        else:
            # Calcul du solde cumulé
            alur_display = alur_df.copy().sort_values('date')
            alur_display['Solde cumulé (€)'] = (alur_display['appels_fonds'] - alur_display['utilisation']).cumsum().round(2)
            alur_display['date_fmt'] = alur_display['date'].dt.strftime('%d/%m/%Y')
            # Masquer les 0 : afficher vide si valeur = 0
            alur_display['Appels (€)'] = alur_display['appels_fonds'].apply(
                lambda x: x if x > 0 else None)
            alur_display['Utilisation (€)'] = alur_display['utilisation'].apply(
                lambda x: x if x > 0 else None)
            alur_display['Commentaire'] = alur_display.get('commentaire', pd.Series(['']*len(alur_display))).fillna('').replace('None','')

            cols_display = ['date_fmt','designation','Appels (€)','Utilisation (€)','Commentaire','Solde cumulé (€)']
            cols_display = [c for c in cols_display if c in alur_display.columns]
            st.dataframe(
                alur_display[cols_display].rename(columns={'date_fmt': 'Date', 'designation': 'Désignation'}),
                use_container_width=True, hide_index=True,
                column_config={
                    'Appels (€)': st.column_config.NumberColumn(format="%,.2f"),
                    'Utilisation (€)': st.column_config.NumberColumn(format="%,.2f"),
                    'Solde cumulé (€)': st.column_config.NumberColumn(format="%,.2f"),
                }
            )

            # Graphique solde cumulé
            fig = go.Figure()
            fig.add_trace(go.Bar(name='Appels', x=alur_display['date_fmt'],
                y=alur_display['appels_fonds'], marker_color='#2ecc71'))
            fig.add_trace(go.Bar(name='Utilisation', x=alur_display['date_fmt'],
                y=-alur_display['utilisation'], marker_color='#e74c3c'))
            fig.add_trace(go.Scatter(name='Solde cumulé', x=alur_display['date_fmt'],
                y=alur_display['Solde cumulé (€)'], mode='lines+markers',
                line=dict(color='orange', width=3), yaxis='y'))
            fig.update_layout(barmode='relative', title="Évolution du fonds de travaux",
                yaxis_title='Montant (€)', height=400)
            st.plotly_chart(fig, use_container_width=True)

            csv_alur = alur_display.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
            st.download_button("📥 Exporter Grand Livre CSV", csv_alur, "grand_livre_alur.csv", "text/csv")

    # ---- ONGLET 2 : AJOUTER OPÉRATION ----
    with tab2:
        st.subheader("Ajouter une opération au fonds")
        type_op = st.radio("Type d'opération",
            ["💰 Appel de fonds", "🔧 Utilisation / Dépense", "📋 À nouveau"],
            horizontal=True, key="alur_type_op")

        with st.form("form_alur"):
            col1, col2 = st.columns(2)
            with col1:
                op_date = st.date_input("Date *", value=datetime.now())
                op_desig = st.text_input("Désignation *",
                    placeholder="Ex: Appel de fonds T1 2026, Travaux toiture...")
            with col2:
                if type_op == "💰 Appel de fonds":
                    op_appel = st.number_input("Montant appelé (€) *", min_value=0.0, step=100.0, format="%.2f")
                    op_util = 0.0
                elif type_op == "🔧 Utilisation / Dépense":
                    op_appel = 0.0
                    op_util = st.number_input("Montant utilisé (€) *", min_value=0.0, step=100.0, format="%.2f")
                else:  # À nouveau
                    op_appel = st.number_input("Solde reporté (€) *", min_value=0.0, step=100.0, format="%.2f")
                    op_util = 0.0
                op_comment = st.text_area("Commentaire")

            if st.form_submit_button("✨ Enregistrer", type="primary", use_container_width=True):
                if op_desig and (op_appel > 0 or op_util > 0):
                    try:
                        supabase.table('loi_alur').insert({
                            'date': op_date.strftime('%Y-%m-%d'),
                            'designation': op_desig.strip(),
                            'appels_fonds': float(op_appel) if op_appel > 0 else None,
                            'utilisation': float(op_util) if op_util > 0 else None,
                            'commentaire': op_comment.strip() if op_comment else None,
                            'depense_id': None
                        }).execute()
                        st.success("✅ Opération enregistrée!"); st.rerun()
                    except Exception as e:
                        st.error(f"❌ {e}")
                else:
                    st.error("❌ Remplissez tous les champs obligatoires")

        # Suppression
        st.divider()
        st.subheader("🗑️ Supprimer une opération")
        if not alur_df.empty:
            alur_no_dep = alur_df[alur_df.get('depense_id', pd.Series([None]*len(alur_df))).isna()]
            if not alur_no_dep.empty:
                ids_del = st.multiselect("Sélectionner",
                    options=alur_no_dep['id'].tolist(),
                    format_func=lambda x: f"{alur_no_dep[alur_no_dep['id']==x]['date'].dt.strftime('%d/%m/%Y').values[0]} — {alur_no_dep[alur_no_dep['id']==x]['designation'].values[0]}")
                if ids_del and st.button("🗑️ Supprimer", type="secondary"):
                    for i in ids_del: supabase.table('loi_alur').delete().eq('id', i).execute()
                    st.success(f"✅ {len(ids_del)} supprimé(s)"); st.rerun()

    # ---- ONGLET 3 : AFFECTER DÉPENSES ----
    with tab3:
        st.subheader("🔗 Affecter des dépenses au fonds Alur")
        st.info("""
        Certaines dépenses de la table **Dépenses** peuvent être financées par le fonds de travaux Alur.
        En les affectant ici, elles seront **exclues du 5ème appel de charges courantes**
        et comptabilisées dans le fonds Alur.
        """)

        if depenses_df_alur.empty:
            st.warning("⚠️ Aucune dépense disponible.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                annee_aff = st.selectbox("📅 Année", sorted(depenses_df_alur['date'].dt.year.unique(), reverse=True), key="alur_aff_annee")
            with col2:
                show_already = st.checkbox("Afficher les dépenses déjà affectées", value=False)

            dep_annee = depenses_df_alur[depenses_df_alur['date'].dt.year == annee_aff].copy()

            # Marquer les dépenses déjà affectées
            dep_annee['alur'] = dep_annee['id'].isin(alur_depense_ids)

            if not show_already:
                dep_non_affectees = dep_annee[~dep_annee['alur']]
            else:
                dep_non_affectees = dep_annee

            st.write(f"**{len(dep_annee[~dep_annee['alur']])}** dépenses non affectées | "
                     f"**{len(dep_annee[dep_annee['alur']])}** déjà affectées au fonds Alur")

            if not dep_non_affectees.empty:
                ids_select = st.multiselect(
                    "Sélectionner les dépenses à affecter au fonds Alur",
                    options=dep_non_affectees[~dep_non_affectees['alur']]['id'].tolist() if not show_already else [],
                    format_func=lambda x: (
                        f"{dep_non_affectees[dep_non_affectees['id']==x]['date'].dt.strftime('%d/%m/%Y').values[0]} — "
                        f"{dep_non_affectees[dep_non_affectees['id']==x]['fournisseur'].values[0]} — "
                        f"{dep_non_affectees[dep_non_affectees['id']==x]['montant_du'].values[0]:,.2f} €"
                    ),
                    key="alur_dep_select"
                )

                # Tableau récapitulatif
                disp_dep = dep_non_affectees[['date','compte','fournisseur','montant_du','classe','commentaire']].copy()
                disp_dep['date'] = disp_dep['date'].dt.strftime('%d/%m/%Y')
                disp_dep['Alur'] = dep_non_affectees['alur'].map({True: '✅ Affectée', False: '—'})
                st.dataframe(disp_dep, use_container_width=True, hide_index=True,
                    column_config={"montant_du": st.column_config.NumberColumn("Montant (€)", format="%,.2f")})

                if ids_select:
                    total_sel = dep_non_affectees[dep_non_affectees['id'].isin(ids_select)]['montant_du'].sum()
                    st.info(f"**{len(ids_select)}** dépense(s) sélectionnée(s) — Total : **{total_sel:,.2f} €**")

                    col1, col2 = st.columns(2)
                    with col1:
                        desig_alur = st.text_input("Désignation dans le fonds Alur",
                            value=f"Dépenses affectées Alur {annee_aff}", key="alur_desig_aff")
                    with col2:
                        comment_alur = st.text_area("Commentaire", key="alur_comment_aff")

                    if st.button("🔗 Affecter au fonds Alur", type="primary"):
                        try:
                            for dep_id in ids_select:
                                dep_row = dep_non_affectees[dep_non_affectees['id'] == dep_id].iloc[0]
                                supabase.table('loi_alur').insert({
                                    'date': dep_row['date'].strftime('%Y-%m-%d') if hasattr(dep_row['date'], 'strftime') else str(dep_row['date']),
                                    'designation': f"{dep_row['fournisseur']} — {dep_row.get('commentaire','') or desig_alur}",
                                    'appels_fonds': None,
                                    'utilisation': float(dep_row['montant_du']),
                                    'commentaire': comment_alur.strip() if comment_alur else None,
                                    'depense_id': int(dep_id)
                                }).execute()
                            st.success(f"✅ {len(ids_select)} dépense(s) affectée(s) au fonds Alur!"); st.rerun()
                        except Exception as e:
                            st.error(f"❌ {e}")

            # Désaffecter
            st.divider()
            st.subheader("↩️ Désaffecter des dépenses")
            dep_affectees = dep_annee[dep_annee['alur']]
            if not dep_affectees.empty:
                ids_desaff = st.multiselect("Dépenses à désaffecter",
                    options=dep_affectees['id'].tolist(),
                    format_func=lambda x: (
                        f"{dep_affectees[dep_affectees['id']==x]['date'].dt.strftime('%d/%m/%Y').values[0]} — "
                        f"{dep_affectees[dep_affectees['id']==x]['fournisseur'].values[0]} — "
                        f"{dep_affectees[dep_affectees['id']==x]['montant_du'].values[0]:,.2f} €"
                    ), key="alur_desaff")
                if ids_desaff and st.button("↩️ Désaffecter", type="secondary"):
                    try:
                        for dep_id in ids_desaff:
                            supabase.table('loi_alur').delete().eq('depense_id', dep_id).execute()
                        st.success(f"✅ {len(ids_desaff)} dépense(s) désaffectée(s)"); st.rerun()
                    except Exception as e:
                        st.error(f"❌ {e}")
            else:
                st.info("Aucune dépense affectée pour cette année.")

    # ---- ONGLET 4 : ANALYSE ----
    with tab4:
        st.subheader("📊 Analyse du fonds de travaux")
        if alur_df.empty:
            st.info("Aucune donnée disponible.")
        else:
            alur_an = alur_df.copy()
            alur_an['annee'] = alur_an['date'].dt.year
            by_year = alur_an.groupby('annee').agg(
                appels=('appels_fonds','sum'), util=('utilisation','sum')
            ).reset_index()
            by_year['solde'] = by_year['appels'] - by_year['util']

            col1, col2 = st.columns(2)
            with col1:
                fig = go.Figure()
                fig.add_trace(go.Bar(name='Appels', x=by_year['annee'].astype(str), y=by_year['appels'], marker_color='#2ecc71'))
                fig.add_trace(go.Bar(name='Utilisation', x=by_year['annee'].astype(str), y=by_year['util'], marker_color='#e74c3c'))
                fig.update_layout(barmode='group', title='Appels vs Utilisation par année')
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                fig = px.bar(by_year, x='annee', y='solde', title='Solde net par année',
                    color='solde', color_continuous_scale=['red','green'],
                    text='solde', labels={'solde':'Solde (€)', 'annee':'Année'})
                fig.update_traces(texttemplate='%{text:,.0f}€', textposition='outside')
                st.plotly_chart(fig, use_container_width=True)

            st.subheader("Impact sur le 5ème appel")
            total_dep_alur = alur_df[alur_df.get('depense_id', pd.Series([None]*len(alur_df))).notna()]['utilisation'].sum()
            if total_dep_alur > 0:
                st.success(f"✅ **{total_dep_alur:,.2f} €** de dépenses affectées au fonds Alur "
                           f"sont exclues du 5ème appel de charges courantes.")
            else:
                st.info("Aucune dépense n'est encore affectée au fonds Alur.")

elif menu == "📈 Analyses":
    st.markdown("<h1 class='main-header'>📈 Analyses Avancées</h1>", unsafe_allow_html=True)
    depenses_df = get_depenses()
    budget_df = get_budget()

    if not depenses_df.empty and not budget_df.empty:
        depenses_df['date'] = pd.to_datetime(depenses_df['date'])
        depenses_df['annee'] = depenses_df['date'].dt.year
        depenses_df['montant_du'] = pd.to_numeric(depenses_df['montant_du'], errors='coerce')

        annees = sorted(depenses_df['annee'].unique(), reverse=True)
        annee_a = st.selectbox("📅 Année", annees, key="anal_annee")
        dep_a = depenses_df[depenses_df['annee'] == annee_a].copy()
        bud_a = budget_df[budget_df['annee'] == annee_a].copy()

        st.divider()
        st.subheader(f"📊 Analyse Budget vs Réalisé par Classe — {annee_a}")

        classes_labels = {
            '1A':'Charges courantes', '1B':'Entretien courant', '2':'Élec. RDC/ss-sols',
            '3':'Élec. sous-sols', '4':'Garages/Parkings', '5':'Ascenseurs',
            '6':'Monte-voitures', '7':'Travaux/Divers'
        }
        rows = []
        tot_bud = 0; tot_dep = 0
        for cl, lib in classes_labels.items():
            b = float(bud_a[bud_a['classe']==cl]['montant_budget'].sum()) if 'classe' in bud_a.columns else 0
            d = float(dep_a[dep_a['classe']==cl]['montant_du'].sum()) if 'classe' in dep_a.columns else 0
            rows.append({'Classe': cl, 'Libellé': lib, 'Budget (€)': b, 'Dépenses (€)': d,
                         'Écart (€)': b-d, '% Réalisé': round(d/b*100,1) if b > 0 else 0})
            tot_bud += b; tot_dep += d
        rows.append({'Classe':'TOTAL','Libellé':'','Budget (€)':tot_bud,'Dépenses (€)':tot_dep,
                     'Écart (€)':tot_bud-tot_dep,'% Réalisé':round(tot_dep/tot_bud*100,1) if tot_bud>0 else 0})

        anal_df = pd.DataFrame(rows)
        st.dataframe(anal_df, use_container_width=True, hide_index=True,
            column_config={
                "Budget (€)": st.column_config.NumberColumn(format="%,.0f"),
                "Dépenses (€)": st.column_config.NumberColumn(format="%,.2f"),
                "Écart (€)": st.column_config.NumberColumn(format="%,.2f"),
                "% Réalisé": st.column_config.NumberColumn(format="%.1f%%"),
            })

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Budget vs Dépenses par Classe")
            fig = go.Figure()
            df_no_total = anal_df[anal_df['Classe'] != 'TOTAL']
            fig.add_trace(go.Bar(name='Budget', x=df_no_total['Classe'], y=df_no_total['Budget (€)'], marker_color='lightblue'))
            fig.add_trace(go.Bar(name='Dépenses', x=df_no_total['Classe'], y=df_no_total['Dépenses (€)'], marker_color='salmon'))
            fig.update_layout(barmode='group')
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.subheader("Top Fournisseurs")
            if not dep_a.empty and 'fournisseur' in dep_a.columns:
                top_f = dep_a.groupby('fournisseur')['montant_du'].agg(['sum','count']).reset_index()
                top_f.columns = ['Fournisseur','Total (€)','Nb factures']
                top_f = top_f.sort_values('Total (€)', ascending=False).head(10)
                fig = px.bar(top_f, x='Fournisseur', y='Total (€)', color='Nb factures', text='Total (€)')
                fig.update_traces(texttemplate='%{text:,.0f}€', textposition='outside')
                fig.update_layout(xaxis_tickangle=45)
                st.plotly_chart(fig, use_container_width=True)

        st.subheader(f"📅 Évolution Mensuelle — {annee_a}")
        if not dep_a.empty:
            dep_a['mois'] = dep_a['date'].dt.to_period('M').astype(str)
            ev = dep_a.groupby('mois')['montant_du'].sum().reset_index()
            fig = px.area(ev, x='mois', y='montant_du', labels={'montant_du':'Montant (€)','mois':'Mois'},
                title=f"Évolution mensuelle {annee_a}")
            st.plotly_chart(fig, use_container_width=True)

        st.download_button("📥 Exporter l'analyse CSV",
            anal_df.to_csv(index=False).encode('utf-8'), f"analyse_{annee_a}.csv", "text/csv")
    else:
        st.warning("⚠️ Données insuffisantes pour les analyses")

# ==================== PLAN COMPTABLE ====================
elif menu == "📋 Plan Comptable":
    st.markdown("<h1 class='main-header'>📋 Plan Comptable</h1>", unsafe_allow_html=True)
    plan_df = get_plan_comptable()

    if not plan_df.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Comptes", len(plan_df))
        c2.metric("Classes", plan_df['classe'].nunique() if 'classe' in plan_df.columns else "N/A")
        c3.metric("Familles", plan_df['famille'].nunique() if 'famille' in plan_df.columns else "N/A")
        st.divider()

        col1, col2, col3 = st.columns(3)
        with col1:
            cl_f = st.selectbox("Classe", ['Toutes'] + sorted(plan_df['classe'].unique().tolist()))
        with col2:
            fam_f = st.selectbox("Famille", ['Toutes'] + sorted(plan_df['famille'].unique().tolist()))
        with col3:
            search = st.text_input("🔍 Recherche")

        filt = plan_df.copy()
        if cl_f != 'Toutes': filt = filt[filt['classe'] == cl_f]
        if fam_f != 'Toutes': filt = filt[filt['famille'] == fam_f]
        if search:
            mask = filt['compte'].astype(str).str.contains(search, case=False, na=False)
            if 'libelle_compte' in filt.columns:
                mask |= filt['libelle_compte'].astype(str).str.contains(search, case=False, na=False)
            filt = filt[mask]

        disp_cols = [c for c in ['compte','libelle_compte','classe','famille'] if c in filt.columns]
        st.dataframe(filt[disp_cols].sort_values('compte' if 'compte' in filt.columns else disp_cols[0]),
            use_container_width=True, hide_index=True)
        st.download_button("📥 Exporter CSV",
            filt.to_csv(index=False).encode('utf-8'),
            f"plan_comptable_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")

        col1, col2 = st.columns(2)
        with col1:
            if 'classe' in filt.columns:
                cl_cnt = filt['classe'].value_counts().reset_index()
                cl_cnt.columns = ['Classe','Nb comptes']
                fig = px.bar(cl_cnt, x='Classe', y='Nb comptes', title='Comptes par classe', text='Nb comptes')
                st.plotly_chart(fig, use_container_width=True)
        with col2:
            if 'famille' in filt.columns:
                fam_cnt = filt['famille'].value_counts().reset_index()
                fam_cnt.columns = ['Famille','Nb comptes']
                fig = px.pie(fam_cnt, values='Nb comptes', names='Famille', title='Comptes par famille')
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("⚠️ Aucune donnée dans le plan comptable.")

st.divider()
st.markdown("<div style='text-align: center; color: #666;'>🏢 Gestion de Copropriété — v2.0</div>", unsafe_allow_html=True)
