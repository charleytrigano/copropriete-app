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

# ==================== CONFIGURATION CLÉS DE RÉPARTITION ====================
# Basé sur votre plan comptable réel :
# Classe 1A, 1B, 7 → Charges générales → tantième_general / 10 000
# Classe 2          → Électricité RDC/ss-sols → tantième_rdc_ssols / 928
# Classe 3          → Électricité sous-sols → tantième_rdc_ssols / 928
# Classe 4          → Garages/Parkings → tantième_garages / 28
# Classe 5          → Ascenseurs → tantième_ascenseurs / 1 000
# Classe 6          → Monte-voitures → tantième_ssols / 20

MAPPING_CLASSE_TANTIEME = {
    '1A': 'general',
    '1B': 'general',
    '7':  'general',
    '2':  'rdc_ssols',
    '3':  'rdc_ssols',
    '4':  'garages',
    '5':  'ascenseurs',
    '6':  'ssols',
}

CHARGES_CONFIG = {
    'general':    {'col': 'tantieme_general',    'total': 10000, 'label': 'Charges générales',        'emoji': '🏢', 'classes': ['1A','1B','7']},
    'ascenseurs': {'col': 'tantieme_ascenseurs',  'total': 1000,  'label': 'Ascenseurs',               'emoji': '🛗', 'classes': ['5']},
    'rdc_ssols':  {'col': 'tantieme_rdc_ssols',   'total': 928,   'label': 'RDC / Sous-sols',          'emoji': '🅿️', 'classes': ['2','3']},
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
    "👥 Copropriétaires", "🔄 Répartition", "📈 Analyses", "📋 Plan Comptable"
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

        col1, col2, col3 = st.columns(3)
        with col1:
            annee_filter = st.selectbox("📅 Année", sorted(depenses_df['annee'].unique(), reverse=True), key="tdb_annee")
        with col2:
            classes_dispo = ['Toutes'] + sorted([str(c) for c in depenses_df['classe'].dropna().unique()]) if 'classe' in depenses_df.columns else ['Toutes']
            classe_filter = st.selectbox("🏷️ Classe", classes_dispo, key="tdb_classe")
        with col3:
            comptes_dispo = ['Tous'] + sorted(depenses_df['compte'].dropna().unique().tolist())
            compte_filter = st.selectbox("🔢 Compte", comptes_dispo, key="tdb_compte")

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

        total_budget = bud_f['montant_budget'].sum()
        total_dep = dep_f['montant_du'].sum()
        ecart = total_budget - total_dep
        pct = (total_dep / total_budget * 100) if total_budget > 0 else 0

        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Budget Total", f"{total_budget:,.0f} €")
        c2.metric("Dépenses réelles", f"{total_dep:,.2f} €", delta=f"{pct:.1f}% du budget")
        c3.metric("Écart budgétaire", f"{ecart:,.2f} €", delta_color="normal" if ecart >= 0 else "inverse")
        c4.metric("Nb Dépenses", len(dep_f))
        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Budget vs Dépenses par Classe")
            if 'classe' in bud_f.columns and 'classe' in dep_f.columns:
                bud_cl = bud_f.groupby('classe')['montant_budget'].sum().reset_index()
                dep_cl = dep_f.groupby('classe')['montant_du'].sum().reset_index()
                comp = bud_cl.merge(dep_cl, on='classe', how='left').fillna(0)
                comp.columns = ['Classe','Budget','Dépenses']
                fig = go.Figure()
                fig.add_trace(go.Bar(name='Budget', x=comp['Classe'], y=comp['Budget'], marker_color='lightblue'))
                fig.add_trace(go.Bar(name='Dépenses', x=comp['Classe'], y=comp['Dépenses'], marker_color='salmon'))
                fig.update_layout(barmode='group', height=400)
                st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.subheader("Répartition du Budget")
            if 'classe' in bud_f.columns and not bud_f.empty:
                bud_cl = bud_f.groupby('classe')['montant_budget'].sum().reset_index()
                fig = px.pie(bud_cl, values='montant_budget', names='classe', title=f'Distribution budget {annee_filter}')
                fig.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)

        st.subheader(f"Évolution Mensuelle - {annee_filter}")
        if not dep_f.empty:
            dep_f['mois'] = dep_f['date'].dt.to_period('M').astype(str)
            ev = dep_f.groupby('mois')['montant_du'].sum().reset_index()
            fig = px.line(ev, x='mois', y='montant_du', markers=True, labels={'montant_du':'Montant (€)','mois':'Mois'})
            fig.update_traces(line_color='#1f77b4', line_width=3)
            st.plotly_chart(fig, use_container_width=True)

        st.subheader(f"Top 10 Dépenses - {annee_filter}")
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
        col1, col2, col3 = st.columns(3)
        with col1:
            annees = sorted(budget_df['annee'].unique(), reverse=True)
            annee_filter = st.selectbox("📅 Année", annees, key="budget_annee")
        with col2:
            classe_filter = st.multiselect("🏷️ Classe", options=sorted(budget_df['classe'].unique()))
        with col3:
            famille_filter = st.multiselect("📂 Famille", options=sorted(budget_df['famille'].unique()))

        filt = budget_df[budget_df['annee'] == annee_filter].copy()
        if classe_filter: filt = filt[filt['classe'].isin(classe_filter)]
        if famille_filter: filt = filt[filt['famille'].isin(famille_filter)]

        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Postes", len(filt))
        c2.metric("Budget total", f"{filt['montant_budget'].sum():,.0f} €")
        c3.metric("Moyenne / poste", f"{filt['montant_budget'].mean():,.0f} €" if len(filt) > 0 else "0 €")
        bud_prec = budget_df[budget_df['annee'] == annee_filter - 1]['montant_budget'].sum()
        bud_act = filt['montant_budget'].sum()
        if bud_prec > 0:
            c4.metric("vs N-1", f"{(bud_act-bud_prec)/bud_prec*100:+.1f}%", delta=f"{bud_act-bud_prec:,.0f} €")
        else:
            c4.metric("vs N-1", "N/A")
        st.divider()

        tab1, tab2, tab3 = st.tabs(["📋 Consulter", "✏️ Modifier / Ajouter / Supprimer", "➕ Créer Budget Année"])

        with tab1:
            st.subheader(f"Budget {annee_filter} — {len(filt)} postes — Total : {filt['montant_budget'].sum():,.0f} €")
            st.dataframe(filt[['compte','libelle_compte','montant_budget','classe','famille']].sort_values('compte'),
                use_container_width=True, hide_index=True,
                column_config={
                    "compte": st.column_config.TextColumn("Compte"),
                    "montant_budget": st.column_config.NumberColumn("Budget (€)", format="%,.0f"),
                })
            col1, col2 = st.columns(2)
            with col1:
                bud_cl = filt.groupby('classe')['montant_budget'].sum().reset_index()
                fig = px.bar(bud_cl, x='classe', y='montant_budget', title="Par Classe",
                    labels={'montant_budget':'Budget (€)','classe':'Classe'}, color='classe')
                fig.update_traces(texttemplate='%{y:,.0f}€', textposition='outside')
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                fig = px.pie(bud_cl, values='montant_budget', names='classe', title="Répartition par Classe")
                fig.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)
            st.download_button("📥 Exporter CSV", filt.to_csv(index=False).encode('utf-8'), f"budget_{annee_filter}.csv", "text/csv")

        with tab2:
            subtab1, subtab2, subtab3 = st.tabs(["✏️ Modifier", "➕ Ajouter", "🗑️ Supprimer"])
            with subtab1:
                edited = st.data_editor(
                    filt[['id','compte','libelle_compte','montant_budget','classe','famille']],
                    use_container_width=True, hide_index=True, disabled=['id'],
                    column_config={
                        "compte": st.column_config.TextColumn("Compte"),
                        "libelle_compte": st.column_config.TextColumn("Libellé"),
                        "montant_budget": st.column_config.NumberColumn("Budget (€)", format="%.0f", min_value=0),
                        "classe": st.column_config.SelectboxColumn("Classe", options=['1A','1B','2','3','4','5','6','7']),
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
        bud_tot = budget_df[budget_df['annee'] == annee_dep]['montant_budget'].sum()
        c1.metric("Nb dépenses", len(dep_f))
        c2.metric("Total", f"{total_dep:,.2f} €")
        c3.metric("Moyenne", f"{dep_f['montant_du'].mean():,.2f} €" if len(dep_f) > 0 else "0 €")
        if bud_tot > 0:
            c4.metric("Réalisé vs Budget", f"{total_dep/bud_tot*100:.1f}%", delta=f"{total_dep-bud_tot:,.0f} €")
        else:
            c4.metric("Réalisé vs Budget", "N/A")
        st.divider()

        tab1, tab2, tab3, tab4 = st.tabs(["📋 Consulter", "✏️ Modifier", "➕ Ajouter", "🗑️ Supprimer"])

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
                # Calcul automatique des montants par type depuis le budget
                total_bud = bud_an['montant_budget'].sum()

                # Montants par type basé sur les classes du budget
                montants_auto = {}
                for key, cfg in CHARGES_CONFIG.items():
                    classes = cfg['classes']
                    montants_auto[key] = float(bud_an[bud_an['classe'].isin(classes)]['montant_budget'].sum())

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
                c1, c2, c3 = st.columns(3)
                c1.metric("Total configuré", f"{total_configure:,.0f} €")
                c2.metric("Budget prévu", f"{total_bud:,.0f} €")
                ecart_cfg = total_configure - total_bud
                c3.metric("Écart", f"{ecart_cfg:+,.0f} €", delta_color="normal" if abs(ecart_cfg) < 100 else "inverse")

                if abs(ecart_cfg) > 500:
                    st.warning(f"⚠️ Différence de {abs(ecart_cfg):,.0f} € entre le total configuré et le budget.")

                st.divider()
                st.subheader(f"📋 Appel {label_trim} {annee_appel} — {100//nb_appels}% du budget annuel")

                # Calcul
                appels_df = calculer_appels(copro_df, montants)
                appels_df[f'🎯 APPEL {label_trim} (€)'] = (appels_df['💰 TOTAL Annuel (€)'] / nb_appels).round(2)

                show_detail = st.checkbox("Afficher le détail par type de charge", value=False, key="show_det")

                detail_cols = [f"{CHARGES_CONFIG[k]['emoji']} {CHARGES_CONFIG[k]['label']}" for k in CHARGES_CONFIG]
                base_cols = ['Lot','Copropriétaire','Étage','Usage']
                if show_detail:
                    display_cols = base_cols + detail_cols + ['💰 TOTAL Annuel (€)', f'🎯 APPEL {label_trim} (€)']
                else:
                    display_cols = base_cols + ['💰 TOTAL Annuel (€)', f'🎯 APPEL {label_trim} (€)']

                display_cols = [c for c in display_cols if c in appels_df.columns]

                st.dataframe(appels_df[display_cols], use_container_width=True, hide_index=True,
                    column_config={
                        f'🎯 APPEL {label_trim} (€)': st.column_config.NumberColumn(format="%.2f"),
                        '💰 TOTAL Annuel (€)': st.column_config.NumberColumn(format="%.2f"),
                    })

                st.divider()
                c1, c2, c3, c4 = st.columns(4)
                total_appel = appels_df[f'🎯 APPEL {label_trim} (€)'].sum()
                c1.metric(f"Total appel {label_trim}", f"{total_appel:,.2f} €")
                c2.metric("Total annuel", f"{appels_df['💰 TOTAL Annuel (€)'].sum():,.2f} €")
                c3.metric("Nb copropriétaires", len(appels_df))
                c4.metric("Appel moyen", f"{appels_df[f'🎯 APPEL {label_trim} (€)'].mean():,.2f} €")

                csv_appel = appels_df.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
                st.download_button(
                    f"📥 Exporter appel {label_trim} {annee_appel} (CSV)",
                    csv_appel, f"appel_{label_trim}_{annee_appel}.csv", "text/csv"
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

    # ==================== ONGLET 2 : RÉGULARISATION ====================
    with tab2:
        st.subheader("5ème appel — Régularisation annuelle")
        st.info("Calcule la différence entre les **dépenses réelles** et les **provisions versées**. Solde positif = à appeler. Négatif = à rembourser.")

        col1, col2 = st.columns(2)
        with col1:
            annee_reg = st.selectbox("📅 Année à régulariser", annees_bud, key="reg_annee")
        with col2:
            nb_appels_reg = st.selectbox("Nb appels provisionnels versés", [4,3,2,1], key="nb_reg")

        if depenses_df.empty:
            st.warning("⚠️ Aucune dépense disponible.")
        else:
            depenses_df['date'] = pd.to_datetime(depenses_df['date'])
            depenses_df['montant_du'] = pd.to_numeric(depenses_df['montant_du'], errors='coerce')
            dep_reg = depenses_df[depenses_df['date'].dt.year == annee_reg].copy()
            total_dep_reel = dep_reg['montant_du'].sum()

            # Dépenses réelles par type de charge (via mapping classe)
            dep_par_type_auto = {}
            for key, cfg in CHARGES_CONFIG.items():
                if 'classe' in dep_reg.columns:
                    dep_par_type_auto[key] = float(dep_reg[dep_reg['classe'].isin(cfg['classes'])]['montant_du'].sum())
                else:
                    dep_par_type_auto[key] = 0

            st.divider()
            st.subheader("💰 Provisions versées vs Dépenses réelles")
            st.caption("Entrez les provisions appelées sur l'année. Les dépenses réelles sont calculées automatiquement depuis vos dépenses.")

            col1, col2, col3 = st.columns(3)
            provisions = {}
            reels_saisis = {}
            items = list(CHARGES_CONFIG.items())
            for i, (key, cfg) in enumerate(items):
                col = [col1, col2, col3][i % 3]
                with col:
                    provisions[key] = st.number_input(
                        f"{cfg['emoji']} Provisions {cfg['label']} (€)",
                        min_value=0.0, step=100.0, key=f"prov_{key}"
                    )
                    reels_saisis[key] = st.number_input(
                        f"Dépenses réelles (€)",
                        min_value=0.0,
                        value=round(dep_par_type_auto.get(key, 0.0), 2),
                        step=100.0, key=f"reel_{key}"
                    )

            total_prov = sum(provisions.values())
            total_reel = sum(reels_saisis.values())
            solde_global = total_reel - total_prov

            st.divider()
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Dépenses réelles totales", f"{total_dep_reel:,.2f} €")
            c2.metric("Provisions totales versées", f"{total_prov:,.2f} €")
            c3.metric("Dépenses réelles saisies", f"{total_reel:,.2f} €")
            c4.metric("Solde à régulariser", f"{solde_global:+,.2f} €",
                delta_color="inverse" if solde_global > 0 else "normal")

            if total_prov == 0:
                st.info("💡 Entrez les provisions versées pour calculer la régularisation.")
            else:
                st.divider()
                st.subheader(f"📋 5ème appel de régularisation {annee_reg}")

                reg_list = []
                for _, cop in copro_df.iterrows():
                    prov_cop = 0
                    reel_cop = 0
                    for key, cfg in CHARGES_CONFIG.items():
                        tant = float(cop.get(cfg['col'], 0) or 0)
                        if cfg['total'] > 0 and tant > 0:
                            prov_cop += (tant / cfg['total']) * provisions[key]
                            reel_cop += (tant / cfg['total']) * reels_saisis[key]
                    reg = reel_cop - prov_cop
                    reg_list.append({
                        'Lot': cop.get('lot',''), 'Copropriétaire': cop.get('nom',''),
                        'Étage': cop.get('etage',''), 'Usage': cop.get('usage',''),
                        'Provisions versées (€)': round(prov_cop, 2),
                        'Dépenses réelles (€)': round(reel_cop, 2),
                        'Régularisation (€)': round(reg, 2),
                        'Sens': '💳 À payer' if reg > 0.01 else ('💚 À rembourser' if reg < -0.01 else '✅ Équilibré')
                    })

                reg_df = pd.DataFrame(reg_list)
                st.dataframe(reg_df, use_container_width=True, hide_index=True,
                    column_config={
                        'Provisions versées (€)': st.column_config.NumberColumn(format="%.2f"),
                        'Dépenses réelles (€)': st.column_config.NumberColumn(format="%.2f"),
                        'Régularisation (€)': st.column_config.NumberColumn(format="%.2f"),
                    })

                st.divider()
                c1, c2, c3, c4 = st.columns(4)
                a_payer = reg_df[reg_df['Régularisation (€)'] > 0.01]['Régularisation (€)'].sum()
                a_rembourser = abs(reg_df[reg_df['Régularisation (€)'] < -0.01]['Régularisation (€)'].sum())
                c1.metric("Total provisions", f"{reg_df['Provisions versées (€)'].sum():,.2f} €")
                c2.metric("Total réel", f"{reg_df['Dépenses réelles (€)'].sum():,.2f} €")
                c3.metric("Montant à appeler", f"{a_payer:,.2f} €")
                c4.metric("Montant à rembourser", f"{a_rembourser:,.2f} €")

                csv_reg = reg_df.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
                st.download_button(f"📥 Exporter régularisation {annee_reg}", csv_reg, f"regularisation_{annee_reg}.csv", "text/csv")

    # ==================== ONGLET 3 : VUE GLOBALE ====================
    with tab3:
        st.subheader("📊 Vue globale annuelle — Charges par copropriétaire")

        col1, col2 = st.columns(2)
        with col1:
            annee_glob = st.selectbox("📅 Année", annees_bud, key="glob_annee")
        with col2:
            nb_appels_glob = st.selectbox("Nb appels / an", [4,3,2,1], key="glob_nb")

        bud_glob = budget_df[budget_df['annee'] == annee_glob] if not budget_df.empty else pd.DataFrame()
        total_bud_glob = bud_glob['montant_budget'].sum() if not bud_glob.empty else 0

        st.info(f"Budget {annee_glob} : **{total_bud_glob:,.0f} €** | {len(copro_df)} copropriétaires")
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

        # Ajouter les colonnes trimestrielles
        for t in ['T1','T2','T3','T4']:
            glob_df[f'{t} (€)'] = (glob_df['💰 TOTAL Annuel (€)'] / nb_appels_glob).round(2)

        c1, c2, c3 = st.columns(3)
        c1.metric("Total configuré", f"{total_glob:,.0f} €")
        c2.metric("Total réparti", f"{glob_df['💰 TOTAL Annuel (€)'].sum():,.2f} €")
        c3.metric("Charge moyenne", f"{glob_df['💰 TOTAL Annuel (€)'].mean():,.2f} €")

        st.divider()
        display_cols = ['Lot','Copropriétaire','Étage','Usage','💰 TOTAL Annuel (€)','T1 (€)','T2 (€)','T3 (€)','T4 (€)']
        display_cols = [c for c in display_cols if c in glob_df.columns]
        st.dataframe(glob_df[display_cols], use_container_width=True, hide_index=True,
            column_config={c: st.column_config.NumberColumn(format="%.2f") for c in display_cols if '€' in c})

        fig = px.bar(
            glob_df.sort_values('💰 TOTAL Annuel (€)', ascending=False),
            x='Copropriétaire', y='💰 TOTAL Annuel (€)',
            color='Usage', title=f"Charges annuelles {annee_glob} par copropriétaire",
            text='💰 TOTAL Annuel (€)'
        )
        fig.update_traces(texttemplate='%{text:.0f}€', textposition='outside')
        fig.update_layout(xaxis_tickangle=45, height=500)
        st.plotly_chart(fig, use_container_width=True)

        csv_glob = glob_df.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
        st.download_button(f"📥 Exporter vue globale {annee_glob}", csv_glob, f"charges_{annee_glob}.csv", "text/csv")

# ==================== ANALYSES ====================
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
