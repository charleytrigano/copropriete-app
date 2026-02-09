import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from supabase import create_client, Client
import os

# Configuration de la page
st.set_page_config(
    page_title="Gestion Copropriété",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialisation de Supabase
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# Styles CSS personnalisés
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .stat-box {
        background: #f0f2f6;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Fonctions de base de données
def get_budget():
    response = supabase.table('budget').select('*').execute()
    return pd.DataFrame(response.data)

def get_depenses(date_debut=None, date_fin=None):
    query = supabase.table('depenses').select('*')
    if date_debut:
        query = query.gte('date', date_debut.strftime('%Y-%m-%d'))
    if date_fin:
        query = query.lte('date', date_fin.strftime('%Y-%m-%d'))
    response = query.execute()
    return pd.DataFrame(response.data)

def get_coproprietaires():
    response = supabase.table('coproprietaires').select('*').execute()
    return pd.DataFrame(response.data)

def add_depense(data):
    response = supabase.table('depenses').insert(data).execute()
    return response

def update_budget(compte, nouveau_montant):
    response = supabase.table('budget').update({'montant_budget': nouveau_montant}).eq('compte', compte).execute()
    return response

# Menu latéral
st.sidebar.image("https://img.icons8.com/color/96/000000/office-building.png", width=100)
st.sidebar.title("Navigation")

menu = st.sidebar.radio(
    "Choisir une section",
    ["📊 Tableau de Bord", "💰 Budget", "📝 Dépenses", "👥 Copropriétaires", "🔄 Répartition", "📈 Analyses"]
)

# ==================== TABLEAU DE BORD ====================
if menu == "📊 Tableau de Bord":
    st.markdown("<h1 class='main-header'>📊 Tableau de Bord</h1>", unsafe_allow_html=True)
    
    # Chargement des données
    budget_df = get_budget()
    depenses_df = get_depenses()
    
    if not budget_df.empty and not depenses_df.empty:
        # Conversion des dates
        depenses_df['date'] = pd.to_datetime(depenses_df['date'])
        
        # Filtres de date
        col1, col2 = st.columns(2)
        with col1:
            date_debut = st.date_input("Date de début", datetime(2025, 1, 1))
        with col2:
            date_fin = st.date_input("Date de fin", datetime.now())
        
        # Filtrer les dépenses
        depenses_filtered = depenses_df[
            (depenses_df['date'] >= pd.Timestamp(date_debut)) & 
            (depenses_df['date'] <= pd.Timestamp(date_fin))
        ]
        
        # Calculs
        total_budget = budget_df['montant_budget'].sum()
        total_depenses = depenses_filtered['montant_du'].sum()
        ecart = total_budget - total_depenses
        pourcentage = (total_depenses / total_budget * 100) if total_budget > 0 else 0
        
        # Métriques principales
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Budget Total", f"{total_budget:,.0f} €", delta=None)
        with col2:
            st.metric("Dépenses", f"{total_depenses:,.2f} €", delta=f"{pourcentage:.1f}%")
        with col3:
            st.metric("Écart", f"{ecart:,.2f} €", delta="Disponible")
        with col4:
            st.metric("Nb Dépenses", len(depenses_filtered))
        
        st.divider()
        
        # Graphiques
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Budget vs Dépenses par Famille")
            # Agrégation par famille
            budget_famille = budget_df.groupby('famille')['montant_budget'].sum().reset_index()
            depenses_famille = depenses_filtered.groupby('famille')['montant_du'].sum().reset_index()
            
            comparaison = budget_famille.merge(depenses_famille, on='famille', how='left').fillna(0)
            comparaison.columns = ['Famille', 'Budget', 'Dépenses']
            
            fig = go.Figure()
            fig.add_trace(go.Bar(name='Budget', x=comparaison['Famille'], y=comparaison['Budget'], marker_color='lightblue'))
            fig.add_trace(go.Bar(name='Dépenses', x=comparaison['Famille'], y=comparaison['Dépenses'], marker_color='salmon'))
            fig.update_layout(barmode='group', height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("Répartition du Budget")
            fig = px.pie(budget_famille, values='montant_budget', names='famille', 
                         title='Distribution du budget par famille')
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
        
        # Évolution mensuelle
        st.subheader("Évolution des Dépenses Mensuelles")
        depenses_filtered['mois'] = depenses_filtered['date'].dt.to_period('M').astype(str)
        evolution = depenses_filtered.groupby('mois')['montant_du'].sum().reset_index()
        
        fig = px.line(evolution, x='mois', y='montant_du', markers=True,
                      labels={'montant_du': 'Montant (€)', 'mois': 'Mois'})
        fig.update_traces(line_color='#1f77b4', line_width=3)
        st.plotly_chart(fig, use_container_width=True)
        
        # Top dépenses
        st.subheader("Top 10 des Dépenses")
        top_depenses = depenses_filtered.nlargest(10, 'montant_du')[['date', 'fournisseur', 'montant_du', 'commentaire']]
        top_depenses['date'] = top_depenses['date'].dt.strftime('%d/%m/%Y')
        st.dataframe(top_depenses, use_container_width=True, hide_index=True)

# ==================== BUDGET ====================
elif menu == "💰 Budget":
    st.markdown("<h1 class='main-header'>💰 Gestion du Budget</h1>", unsafe_allow_html=True)
    
    budget_df = get_budget()
    
    if not budget_df.empty:
        # Statistiques
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Nombre de postes", len(budget_df))
        with col2:
            st.metric("Budget total", f"{budget_df['montant_budget'].sum():,.0f} €")
        with col3:
            st.metric("Budget moyen", f"{budget_df['montant_budget'].mean():,.0f} €")
        
        st.divider()
        
        # Filtres
        col1, col2 = st.columns(2)
        with col1:
            classe_filter = st.multiselect("Filtrer par classe", options=sorted(budget_df['classe'].unique()))
        with col2:
            famille_filter = st.multiselect("Filtrer par famille", options=sorted(budget_df['famille'].unique()))
        
        # Application des filtres
        filtered_budget = budget_df.copy()
        if classe_filter:
            filtered_budget = filtered_budget[filtered_budget['classe'].isin(classe_filter)]
        if famille_filter:
            filtered_budget = filtered_budget[filtered_budget['famille'].isin(famille_filter)]
        
        # Affichage du budget
        st.subheader(f"Postes budgétaires ({len(filtered_budget)} postes)")
        
        # Édition du budget
        edited_budget = st.data_editor(
            filtered_budget[['compte', 'libelle_compte', 'montant_budget', 'classe', 'famille', 'annee']],
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            column_config={
                "compte": st.column_config.NumberColumn("Compte", format="%d"),
                "libelle_compte": st.column_config.TextColumn("Libellé"),
                "montant_budget": st.column_config.NumberColumn("Budget (€)", format="%.2f"),
                "classe": st.column_config.TextColumn("Classe"),
                "famille": st.column_config.NumberColumn("Famille", format="%d"),
                "annee": st.column_config.NumberColumn("Année", format="%d")
            }
        )
        
        # Boutons d'action
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("💾 Sauvegarder", type="primary"):
                st.success("Budget mis à jour!")

# ==================== DÉPENSES ====================
elif menu == "📝 Dépenses":
    st.markdown("<h1 class='main-header'>📝 Gestion des Dépenses</h1>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["📋 Liste des dépenses", "➕ Nouvelle dépense"])
    
    with tab1:
        depenses_df = get_depenses()
        budget_df = get_budget()
        
        if not depenses_df.empty:
            # Merge avec le budget pour avoir les libellés
            depenses_df = depenses_df.merge(
                budget_df[['compte', 'libelle_compte']], 
                on='compte', 
                how='left'
            )
            depenses_df['date'] = pd.to_datetime(depenses_df['date'])
            
            # Filtres
            col1, col2, col3 = st.columns(3)
            with col1:
                date_debut = st.date_input("Du", datetime(2025, 1, 1), key="dep_debut")
            with col2:
                date_fin = st.date_input("Au", datetime.now(), key="dep_fin")
            with col3:
                fournisseur_filter = st.multiselect(
                    "Fournisseur", 
                    options=sorted(depenses_df['fournisseur'].unique())
                )
            
            # Application des filtres
            filtered_depenses = depenses_df[
                (depenses_df['date'] >= pd.Timestamp(date_debut)) & 
                (depenses_df['date'] <= pd.Timestamp(date_fin))
            ]
            if fournisseur_filter:
                filtered_depenses = filtered_depenses[filtered_depenses['fournisseur'].isin(fournisseur_filter)]
            
            # Statistiques
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Nombre de dépenses", len(filtered_depenses))
            with col2:
                st.metric("Total", f"{filtered_depenses['montant_du'].sum():,.2f} €")
            with col3:
                st.metric("Moyenne", f"{filtered_depenses['montant_du'].mean():,.2f} €")
            
            # Tableau des dépenses
            st.subheader("Détail des dépenses")
            display_df = filtered_depenses[['date', 'fournisseur', 'montant_du', 'libelle_compte', 'classe', 'commentaire']].copy()
            display_df['date'] = display_df['date'].dt.strftime('%d/%m/%Y')
            display_df = display_df.sort_values('date', ascending=False)
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    with tab2:
        st.subheader("Ajouter une nouvelle dépense")
        
        budget_df = get_budget()
        
        with st.form("nouvelle_depense"):
            col1, col2 = st.columns(2)
            
            with col1:
                date_depense = st.date_input("Date", datetime.now())
                fournisseur = st.text_input("Fournisseur")
                montant = st.number_input("Montant (€)", min_value=0.0, step=0.01)
            
            with col2:
                # Sélection du compte
                comptes_options = budget_df.apply(
                    lambda x: f"{x['compte']} - {x['libelle_compte']}", axis=1
                ).tolist()
                compte_selected = st.selectbox("Compte budgétaire", comptes_options)
                
                commentaire = st.text_area("Commentaire (optionnel)")
            
            submitted = st.form_submit_button("💾 Enregistrer", type="primary")
            
            if submitted and fournisseur and montant > 0:
                compte_num = int(compte_selected.split(' - ')[0])
                compte_info = budget_df[budget_df['compte'] == compte_num].iloc[0]
                
                nouvelle_depense = {
                    'date': date_depense.strftime('%Y-%m-%d'),
                    'fournisseur': fournisseur,
                    'montant_du': montant,
                    'compte': compte_num,
                    'commentaire': commentaire if commentaire else None,
                    'classe': compte_info['classe'],
                    'famille': int(compte_info['famille'])
                }
                
                try:
                    add_depense(nouvelle_depense)
                    st.success("✅ Dépense enregistrée!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur: {str(e)}")

# ==================== COPROPRIÉTAIRES ====================
elif menu == "👥 Copropriétaires":
    st.markdown("<h1 class='main-header'>👥 Copropriétaires</h1>", unsafe_allow_html=True)
    
    copro_df = get_coproprietaires()
    
    if not copro_df.empty:
        total_tantiemes = copro_df['tantieme'].sum()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Nombre de copropriétaires", len(copro_df))
        with col2:
            st.metric("Total tantièmes", total_tantiemes)
        with col3:
            st.metric("Moyenne", f"{copro_df['tantieme'].mean():.1f}")
        
        st.divider()
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("Répartition des tantièmes")
            fig = px.pie(copro_df, values='tantieme', names='nom')
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("Liste des copropriétaires")
            copro_display = copro_df.copy()
            copro_display['pourcentage'] = (copro_display['tantieme'] / total_tantiemes * 100).round(2)
            st.dataframe(copro_display, use_container_width=True, hide_index=True)

# ==================== RÉPARTITION ====================
elif menu == "🔄 Répartition":
    st.markdown("<h1 class='main-header'>🔄 Répartition des Charges</h1>", unsafe_allow_html=True)
    
    copro_df = get_coproprietaires()
    depenses_df = get_depenses()
    
    if not copro_df.empty and not depenses_df.empty:
        col1, col2 = st.columns(2)
        with col1:
            date_debut = st.date_input("Période du", datetime(2025, 1, 1), key="rep_debut")
        with col2:
            date_fin = st.date_input("Au", datetime.now(), key="rep_fin")
        
        depenses_df['date'] = pd.to_datetime(depenses_df['date'])
        depenses_periode = depenses_df[
            (depenses_df['date'] >= pd.Timestamp(date_debut)) & 
            (depenses_df['date'] <= pd.Timestamp(date_fin))
        ]
        
        total_depenses = depenses_periode['montant_du'].sum()
        total_tantiemes = copro_df['tantieme'].sum()
        
        st.info(f"**Total des dépenses** : {total_depenses:,.2f} €")
        
        repartition = []
        for _, copro in copro_df.iterrows():
            part = (copro['tantieme'] / total_tantiemes) * total_depenses
            repartition.append({
                'Copropriétaire': copro['nom'],
                'Lot': copro['lot'],
                'Tantièmes': copro['tantieme'],
                'Part (%)': round(copro['tantieme'] / total_tantiemes * 100, 2),
                'Montant dû (€)': round(part, 2)
            })
        
        repartition_df = pd.DataFrame(repartition)
        
        st.subheader("Répartition par copropriétaire")
        st.dataframe(repartition_df, use_container_width=True, hide_index=True)
        
        fig = px.bar(repartition_df, x='Copropriétaire', y='Montant dû (€)',
                     color='Part (%)', text='Montant dû (€)')
        st.plotly_chart(fig, use_container_width=True)

# ==================== ANALYSES ====================
elif menu == "📈 Analyses":
    st.markdown("<h1 class='main-header'>📈 Analyses Avancées</h1>", unsafe_allow_html=True)
    
    depenses_df = get_depenses()
    budget_df = get_budget()
    
    if not depenses_df.empty:
        depenses_df['date'] = pd.to_datetime(depenses_df['date'])
        depenses_df = depenses_df.merge(budget_df[['compte', 'libelle_compte']], on='compte', how='left')
        
        st.subheader("📊 Top Fournisseurs")
        top_fournisseurs = depenses_df.groupby('fournisseur')['montant_du'].agg(['sum', 'count']).reset_index()
        top_fournisseurs.columns = ['Fournisseur', 'Total (€)', 'Nb factures']
        top_fournisseurs = top_fournisseurs.sort_values('Total (€)', ascending=False).head(10)
        
        fig = px.bar(top_fournisseurs, x='Fournisseur', y='Total (€)', color='Nb factures')
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("💰 Dépenses par Classe")
        depenses_classe = depenses_df.groupby('classe')['montant_du'].sum().reset_index()
        fig = px.pie(depenses_classe, values='montant_du', names='classe')
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("📅 Évolution Mensuelle")
        depenses_df['mois'] = depenses_df['date'].dt.to_period('M').astype(str)
        evolution = depenses_df.groupby('mois')['montant_du'].sum().reset_index()
        fig = px.area(evolution, x='mois', y='montant_du')
        st.plotly_chart(fig, use_container_width=True)

st.divider()
st.markdown("<div style='text-align: center; color: #666;'>🏢 Gestion de Copropriété</div>", unsafe_allow_html=True)

