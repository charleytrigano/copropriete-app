import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from supabase import create_client, Client
import os
import time

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
    try:
        response = supabase.table('budget').select('*').execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"❌ Erreur lors de la récupération du budget: {str(e)}")
        return pd.DataFrame()

def get_depenses(date_debut=None, date_fin=None):
    try:
        query = supabase.table('depenses').select('*')
        if date_debut:
            query = query.gte('date', date_debut.strftime('%Y-%m-%d'))
        if date_fin:
            query = query.lte('date', date_fin.strftime('%Y-%m-%d'))
        response = query.execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"❌ Erreur lors de la récupération des dépenses: {str(e)}")
        st.info("💡 Vérifiez que la table 'depenses' existe dans Supabase et que RLS est désactivé.")
        return pd.DataFrame()  # Retourner un DataFrame vide en cas d'erreur

def get_coproprietaires():
    try:
        response = supabase.table('coproprietaires').select('*').execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"❌ Erreur lors de la récupération des copropriétaires: {str(e)}")
        return pd.DataFrame()

def get_plan_comptable():
    try:
        response = supabase.table('plan_comptable').select('*').execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"❌ Erreur lors de la récupération du plan comptable: {str(e)}")
        return pd.DataFrame()

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
    ["📊 Tableau de Bord", "💰 Budget", "📝 Dépenses", "👥 Copropriétaires", "🔄 Répartition", "📈 Analyses", "📋 Plan Comptable"]
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
        # Filtres en haut
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Filtre par année
            annees_disponibles = sorted(budget_df['annee'].unique(), reverse=True)
            annee_filter = st.selectbox("📅 Année", annees_disponibles, key="budget_annee")
        
        with col2:
            # Filtre par classe
            classe_filter = st.multiselect("🏷️ Classe", options=sorted(budget_df['classe'].unique()))
        
        with col3:
            # Filtre par famille
            famille_filter = st.multiselect("📂 Famille", options=sorted(budget_df['famille'].unique()))
        
        # Application des filtres
        filtered_budget = budget_df[budget_df['annee'] == annee_filter].copy()
        
        if classe_filter:
            filtered_budget = filtered_budget[filtered_budget['classe'].isin(classe_filter)]
        if famille_filter:
            filtered_budget = filtered_budget[filtered_budget['famille'].isin(famille_filter)]
        
        # Statistiques FILTRÉES
        st.divider()
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Nombre de postes", len(filtered_budget))
        with col2:
            st.metric("Budget total", f"{filtered_budget['montant_budget'].sum():,.0f} €")
        with col3:
            st.metric("Budget moyen", f"{filtered_budget['montant_budget'].mean():,.0f} €" if len(filtered_budget) > 0 else "0 €")
        with col4:
            # Comparer avec année précédente
            annee_precedente = annee_filter - 1
            budget_precedent = budget_df[budget_df['annee'] == annee_precedente]['montant_budget'].sum()
            budget_actuel = filtered_budget['montant_budget'].sum()
            if budget_precedent > 0:
                variation = ((budget_actuel - budget_precedent) / budget_precedent * 100)
                st.metric("vs année N-1", f"{variation:+.1f}%", delta=f"{budget_actuel - budget_precedent:,.0f} €")
            else:
                st.metric("vs année N-1", "N/A")
        
        st.divider()
        
        # Onglets
        tab1, tab2, tab3 = st.tabs(["📋 Consulter", "✏️ Modifier", "➕ Créer Budget Année"])
        
        # =============== ONGLET 1 : CONSULTER ===============
        with tab1:
            st.subheader(f"Budget {annee_filter} ({len(filtered_budget)} postes)")
            
            # Affichage en lecture seule
            st.dataframe(
                filtered_budget[['compte', 'libelle_compte', 'montant_budget', 'classe', 'famille']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "compte": st.column_config.NumberColumn("Compte", format="%d"),
                    "libelle_compte": st.column_config.TextColumn("Libellé"),
                    "montant_budget": st.column_config.NumberColumn("Budget (€)", format="%,.0f"),
                    "classe": st.column_config.TextColumn("Classe"),
                    "famille": st.column_config.NumberColumn("Famille", format="%d")
                }
            )
            
            # Graphiques
            st.divider()
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Par Famille")
                budget_famille = filtered_budget.groupby('famille')['montant_budget'].sum().reset_index()
                budget_famille.columns = ['Famille', 'Budget']
                fig = px.bar(budget_famille, x='Famille', y='Budget', text='Budget')
                fig.update_traces(texttemplate='%{text:,.0f}€', textposition='outside')
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.subheader("Par Classe")
                budget_classe = filtered_budget.groupby('classe')['montant_budget'].sum().reset_index()
                budget_classe.columns = ['Classe', 'Budget']
                fig = px.pie(budget_classe, values='Budget', names='Classe')
                fig.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)
            
            # Export
            st.divider()
            csv = filtered_budget.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Exporter en CSV",
                data=csv,
                file_name=f"budget_{annee_filter}.csv",
                mime="text/csv"
            )
        
        # =============== ONGLET 2 : MODIFIER ===============
        with tab2:
            st.subheader(f"Gérer le budget {annee_filter}")
            
            # Sous-onglets pour organiser les actions
            subtab1, subtab2, subtab3 = st.tabs(["✏️ Modifier", "➕ Ajouter", "🗑️ Supprimer"])
            
            # ========== SOUS-ONGLET 1 : MODIFIER ==========
            with subtab1:
                st.info("💡 Modifiez les lignes directement dans le tableau. Toutes les colonnes sont éditables.")
                
                # Tableau éditable avec TOUTES les colonnes modifiables
                edited_budget = st.data_editor(
                    filtered_budget[['id', 'compte', 'libelle_compte', 'montant_budget', 'classe', 'famille']],
                    use_container_width=True,
                    hide_index=True,
                    disabled=['id'],  # Seul l'ID est non-éditable
                    column_config={
                        "id": st.column_config.NumberColumn("ID", disabled=True),
                        "compte": st.column_config.NumberColumn("Compte", format="%d", min_value=0),
                        "libelle_compte": st.column_config.TextColumn("Libellé", max_chars=200),
                        "montant_budget": st.column_config.NumberColumn("Budget (€)", format="%.0f", min_value=0),
                        "classe": st.column_config.TextColumn("Classe"),
                        "famille": st.column_config.NumberColumn("Famille", format="%d", min_value=0)
                    },
                    key="budget_editor_modify"
                )
                
                # Boutons d'action
                col1, col2, col3 = st.columns([1, 1, 2])
                
                with col1:
                    if st.button("💾 Enregistrer les modifications", type="primary", key="save_modifications"):
                        try:
                            modifications = 0
                            for idx, row in edited_budget.iterrows():
                                # Trouver la ligne originale
                                original_row = filtered_budget[filtered_budget['id'] == row['id']]
                                if not original_row.empty:
                                    original = original_row.iloc[0]
                                    
                                    # Vérifier s'il y a des changements
                                    changed = False
                                    updates = {}
                                    
                                    if int(row['compte']) != int(original['compte']):
                                        updates['compte'] = int(row['compte'])
                                        changed = True
                                    
                                    if str(row['libelle_compte']) != str(original['libelle_compte']):
                                        updates['libelle_compte'] = str(row['libelle_compte'])
                                        changed = True
                                    
                                    if float(row['montant_budget']) != float(original['montant_budget']):
                                        updates['montant_budget'] = int(row['montant_budget'])
                                        changed = True
                                    
                                    if str(row['classe']) != str(original['classe']):
                                        updates['classe'] = str(row['classe'])
                                        changed = True
                                    
                                    if int(row['famille']) != int(original['famille']):
                                        updates['famille'] = int(row['famille'])
                                        changed = True
                                    
                                    # Si changement, mettre à jour
                                    if changed:
                                        supabase.table('budget').update(updates).eq('id', int(row['id'])).execute()
                                        modifications += 1
                            
                            if modifications > 0:
                                st.success(f"✅ {modifications} ligne(s) mise(s) à jour avec succès!")
                                st.rerun()
                            else:
                                st.info("ℹ️ Aucune modification détectée")
                        except Exception as e:
                            st.error(f"❌ Erreur lors de la sauvegarde: {str(e)}")
                
                with col2:
                    if st.button("🔄 Annuler", key="cancel_modifications"):
                        st.rerun()
            
            # ========== SOUS-ONGLET 2 : AJOUTER ==========
            with subtab2:
                st.subheader(f"Ajouter un nouveau compte au budget {annee_filter}")
                
                st.info("💡 Entrez le numéro de compte. Si le compte existe dans le plan comptable, les informations seront automatiquement remplies.")
                
                # Récupérer le plan comptable
                plan_df = get_plan_comptable()
                
                # Numéro de compte (sans formulaire pour permettre l'auto-remplissage)
                new_compte = st.number_input(
                    "Numéro de compte *",
                    min_value=0,
                    step=1,
                    format="%d",
                    help="Entrez le numéro du compte. Les autres champs se rempliront automatiquement s'il existe dans le plan comptable.",
                    key="new_compte_input"
                )
                
                # Chercher dans le plan comptable
                compte_info = None
                if new_compte > 0 and not plan_df.empty:
                    compte_info = plan_df[plan_df['compte'] == new_compte]
                
                # Afficher un message si trouvé
                if compte_info is not None and not compte_info.empty:
                    st.success(f"✅ Compte trouvé dans le plan comptable : {compte_info.iloc[0]['libelle_compte']}")
                    auto_fill = True
                    default_libelle = compte_info.iloc[0]['libelle_compte']
                    default_classe = compte_info.iloc[0]['classe']
                    default_famille = int(compte_info.iloc[0]['famille'])
                elif new_compte > 0:
                    st.warning(f"⚠️ Le compte {new_compte} n'existe pas dans le plan comptable. Vous devrez saisir toutes les informations manuellement.")
                    auto_fill = False
                    default_libelle = ""
                    default_classe = ""
                    default_famille = 0
                else:
                    auto_fill = False
                    default_libelle = ""
                    default_classe = ""
                    default_famille = 0
                
                st.divider()
                
                # Reste du formulaire
                col1, col2 = st.columns(2)
                
                with col1:
                    new_libelle = st.text_input(
                        "Libellé du compte *",
                        value=default_libelle,
                        max_chars=200,
                        help="Description du compte (auto-rempli si le compte existe dans le plan comptable)",
                        key="new_libelle_input"
                    )
                    
                    new_montant = st.number_input(
                        "Montant du budget (€) *",
                        min_value=0,
                        step=100,
                        format="%d",
                        help="Montant budgété pour ce poste",
                        key="new_montant_input"
                    )
                
                with col2:
                    # Classe
                    if auto_fill and default_classe:
                        new_classe = st.text_input(
                            "Classe *",
                            value=default_classe,
                            help="Classe comptable (auto-rempli)",
                            key="new_classe_input"
                        )
                    else:
                        classes_existantes = sorted(budget_df['classe'].unique())
                        new_classe = st.selectbox(
                            "Classe *",
                            options=[""] + classes_existantes,
                            help="Classe comptable",
                            key="new_classe_select"
                        )
                        
                        if new_classe == "":
                            new_classe = st.text_input("Ou entrer une nouvelle classe *", key="new_classe_manual")
                    
                    # Famille
                    if auto_fill and default_famille > 0:
                        new_famille = st.number_input(
                            "Famille *",
                            value=default_famille,
                            min_value=0,
                            step=1,
                            help="Famille comptable (auto-rempli)",
                            key="new_famille_input"
                        )
                    else:
                        familles_existantes = sorted(budget_df['famille'].unique())
                        famille_choice = st.selectbox(
                            "Famille *",
                            options=["Choisir existante", "Nouvelle famille"],
                            help="Famille comptable",
                            key="famille_choice"
                        )
                        
                        if famille_choice == "Choisir existante":
                            new_famille = st.selectbox("Sélectionner", options=familles_existantes, key="famille_select")
                        else:
                            new_famille = st.number_input("Numéro de famille *", min_value=0, step=1, key="famille_manual")
                
                # Bouton d'ajout
                st.divider()
                
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("✨ Ajouter le compte au budget", type="primary", use_container_width=True, key="add_compte_btn"):
                        # Validation
                        errors = []
                        
                        if new_compte <= 0:
                            errors.append("Le numéro de compte doit être supérieur à 0")
                        
                        if not new_libelle or new_libelle.strip() == "":
                            errors.append("Le libellé est obligatoire")
                        
                        if not new_classe or new_classe.strip() == "":
                            errors.append("La classe est obligatoire")
                        
                        if new_famille <= 0:
                            errors.append("La famille est obligatoire")
                        
                        if errors:
                            for error in errors:
                                st.error(f"❌ {error}")
                        else:
                            # Clé unique pour éviter les doublons
                            insert_key = f"budget_{new_compte}_{annee_filter}_{new_montant}"
                            
                            if 'last_budget_insert' not in st.session_state or st.session_state.last_budget_insert != insert_key:
                                try:
                                    # Vérifier si le compte existe déjà pour cette année
                                    existing = budget_df[
                                        (budget_df['compte'] == new_compte) & 
                                        (budget_df['annee'] == annee_filter)
                                    ]
                                    
                                    if not existing.empty:
                                        st.error(f"❌ Le compte {new_compte} existe déjà dans le budget {annee_filter}")
                                    else:
                                        # Insérer le nouveau compte
                                        new_line = {
                                            'compte': int(new_compte),
                                            'libelle_compte': new_libelle.strip(),
                                            'montant_budget': int(new_montant),
                                            'annee': int(annee_filter),
                                            'classe': new_classe.strip(),
                                            'famille': int(new_famille)
                                        }
                                        
                                        supabase.table('budget').insert(new_line).execute()
                                        
                                        # Marquer comme inséré
                                        st.session_state.last_budget_insert = insert_key
                                        
                                        st.success(f"✅ Compte {new_compte} - {new_libelle} ajouté avec succès au budget {annee_filter}!")
                                        st.balloons()
                                        st.rerun()
                                        
                                except Exception as e:
                                    st.error(f"❌ Erreur lors de l'ajout: {str(e)}")
                            else:
                                st.info("Ce compte a déjà été ajouté. Modifiez les valeurs pour ajouter un nouveau compte.")
                
                with col2:
                    if st.button("🔄 Réinitialiser", use_container_width=True, key="reset_form_btn"):
                        # Réinitialiser le flag
                        if 'last_budget_insert' in st.session_state:
                            del st.session_state.last_budget_insert
                        st.rerun()
                
                # Aide : Aperçu du plan comptable
                st.divider()
                with st.expander("📋 Consulter le plan comptable"):
                    if not plan_df.empty:
                        st.dataframe(
                            plan_df[['compte', 'libelle_compte', 'classe', 'famille']],
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "compte": st.column_config.NumberColumn("Compte", format="%d"),
                                "libelle_compte": "Libellé",
                                "classe": "Classe",
                                "famille": st.column_config.NumberColumn("Famille", format="%d")
                            }
                        )
                    else:
                        st.info("Le plan comptable est vide")
                
                # Aide : Comptes déjà dans le budget
                with st.expander(f"📊 Comptes déjà dans le budget {annee_filter}"):
                    st.dataframe(
                        filtered_budget[['compte', 'libelle_compte', 'classe', 'famille', 'montant_budget']].sort_values('compte'),
                        use_container_width=True,
                        hide_index=True
                    )
            
            # ========== SOUS-ONGLET 3 : SUPPRIMER ==========
            with subtab3:
                st.subheader(f"Supprimer des comptes du budget {annee_filter}")
                
                st.warning("⚠️ La suppression est définitive et ne peut pas être annulée.")
                
                if not filtered_budget.empty:
                    # Sélection par ID
                    st.info("💡 Sélectionnez les comptes à supprimer.")
                    
                    ids_to_delete = st.multiselect(
                        "Sélectionner les comptes à supprimer",
                        options=filtered_budget['id'].tolist(),
                        format_func=lambda x: f"ID {x} - {filtered_budget[filtered_budget['id']==x]['libelle_compte'].values[0]}"
                    )
                    
                    if ids_to_delete:
                        st.warning(f"🗑️ {len(ids_to_delete)} ligne(s) sélectionnée(s) pour suppression")
                        
                        # Afficher les lignes qui seront supprimées
                        lines_to_delete = filtered_budget[filtered_budget['id'].isin(ids_to_delete)]
                        st.dataframe(
                            lines_to_delete[['compte', 'libelle_compte', 'montant_budget']],
                            use_container_width=True,
                            hide_index=True
                        )
                        
                        col1, col2, col3 = st.columns([1, 1, 2])
                        
                        with col1:
                            if st.button("🗑️ Confirmer la suppression", type="secondary", key="confirm_delete"):
                                # Créer une clé unique pour cette suppression
                                delete_key = f"delete_budget_{'-'.join(map(str, sorted(ids_to_delete)))}"
                                
                                # Vérifier si cette suppression n'a pas déjà été faite
                                if 'last_budget_delete' not in st.session_state or st.session_state.last_budget_delete != delete_key:
                                    try:
                                        # Supprimer les lignes sélectionnées
                                        for id_to_del in ids_to_delete:
                                            supabase.table('budget').delete().eq('id', id_to_del).execute()
                                        
                                        # Marquer comme supprimé
                                        st.session_state.last_budget_delete = delete_key
                                        
                                        st.success(f"✅ {len(ids_to_delete)} ligne(s) supprimée(s) avec succès!")
                                        st.rerun()
                                        
                                    except Exception as e:
                                        st.error(f"❌ Erreur lors de la suppression: {str(e)}")
                                else:
                                    st.info("Ces lignes ont déjà été supprimées. Rafraîchissez la page (F5).")
                        
                        with col2:
                            if st.button("❌ Annuler", key="cancel_delete"):
                                # Réinitialiser le flag
                                if 'last_budget_delete' in st.session_state:
                                    del st.session_state.last_budget_delete
                                st.rerun()
                    else:
                        st.info("ℹ️ Sélectionnez au moins un compte pour activer la suppression")
                else:
                    st.info("ℹ️ Aucune ligne à supprimer avec les filtres actuels")
        
        # =============== ONGLET 3 : CRÉER NOUVEAU BUDGET ===============
        with tab3:
            st.subheader("Créer un budget pour une nouvelle année")
            
            col1, col2 = st.columns(2)
            
            with col1:
                nouvelle_annee = st.number_input(
                    "📅 Année du nouveau budget", 
                    min_value=2020, 
                    max_value=2050, 
                    value=annee_filter + 1,
                    step=1
                )
            
            with col2:
                annee_source = st.selectbox(
                    "📋 Copier depuis l'année", 
                    annees_disponibles,
                    index=0
                )
            
            # Vérifier si budget existe déjà
            budget_existe = not budget_df[budget_df['annee'] == nouvelle_annee].empty
            
            if budget_existe:
                st.warning(f"⚠️ Un budget pour l'année {nouvelle_annee} existe déjà ({len(budget_df[budget_df['annee'] == nouvelle_annee])} postes)")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🗑️ Supprimer et recréer", type="secondary"):
                        try:
                            # Supprimer l'ancien budget
                            supabase.table('budget').delete().eq('annee', nouvelle_annee).execute()
                            st.success(f"✅ Budget {nouvelle_annee} supprimé")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erreur: {str(e)}")
            else:
                st.info(f"ℹ️ Aucun budget n'existe pour {nouvelle_annee}")
            
            # Option de coefficient
            st.subheader("Ajustement du budget")
            
            col1, col2 = st.columns(2)
            
            with col1:
                ajustement_type = st.radio(
                    "Type d'ajustement",
                    ["Aucun (copie à l'identique)", "Pourcentage global", "Montant fixe"]
                )
            
            with col2:
                if ajustement_type == "Pourcentage global":
                    coefficient = st.number_input(
                        "Pourcentage d'augmentation/diminution",
                        min_value=-50.0,
                        max_value=100.0,
                        value=3.0,
                        step=0.5,
                        format="%.1f"
                    ) / 100
                elif ajustement_type == "Montant fixe":
                    montant_fixe = st.number_input(
                        "Montant à ajouter/retirer (€)",
                        value=0,
                        step=100
                    )
                else:
                    coefficient = 0
                    montant_fixe = 0
            
            # Aperçu
            st.subheader("Aperçu")
            budget_source = budget_df[budget_df['annee'] == annee_source].copy()
            
            if ajustement_type == "Pourcentage global":
                budget_source['nouveau_montant'] = (budget_source['montant_budget'] * (1 + coefficient)).round(0).astype(int)
            elif ajustement_type == "Montant fixe":
                budget_source['nouveau_montant'] = (budget_source['montant_budget'] + montant_fixe).astype(int)
            else:
                budget_source['nouveau_montant'] = budget_source['montant_budget']
            
            total_ancien = budget_source['montant_budget'].sum()
            total_nouveau = budget_source['nouveau_montant'].sum()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(f"Budget {annee_source}", f"{total_ancien:,.0f} €")
            with col2:
                st.metric(f"Nouveau budget {nouvelle_annee}", f"{total_nouveau:,.0f} €")
            with col3:
                variation = total_nouveau - total_ancien
                st.metric("Différence", f"{variation:+,.0f} €", delta=f"{(variation/total_ancien*100):+.1f}%")
            
            # Afficher aperçu
            with st.expander(f"📋 Voir le détail ({len(budget_source)} postes)"):
                st.dataframe(
                    budget_source[['compte', 'libelle_compte', 'montant_budget', 'nouveau_montant', 'classe']],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "compte": "Compte",
                        "libelle_compte": "Libellé",
                        "montant_budget": st.column_config.NumberColumn(f"Budget {annee_source}", format="%,.0f €"),
                        "nouveau_montant": st.column_config.NumberColumn(f"Budget {nouvelle_annee}", format="%,.0f €"),
                        "classe": "Classe"
                    }
                )
            
         # ==================== DÉPENSES ====================
elif menu == "📝 Dépenses":
    st.markdown("<h1 class='main-header'>📝 Gestion des Dépenses</h1>", unsafe_allow_html=True)
    
    depenses_df = get_depenses()
    budget_df = get_budget()
    
    # Préparer le dataframe (même s'il est vide)
    if not depenses_df.empty:
        depenses_df = depenses_df.merge(
            budget_df[['compte', 'libelle_compte', 'classe', 'famille']], 
            on='compte', 
            how='left',
            suffixes=('', '_budget')
        )
        depenses_df['date'] = pd.to_datetime(depenses_df['date'])
        depenses_df['annee'] = depenses_df['date'].dt.year
        depenses_df['montant_du'] = pd.to_numeric(depenses_df['montant_du'], errors='coerce')
    else:
        # Créer un DataFrame vide avec les bonnes colonnes
        depenses_df = pd.DataFrame(columns=['id', 'date', 'compte', 'fournisseur', 'montant_du', 'classe', 'famille', 'commentaire', 'annee', 'libelle_compte'])
    
    # TOUJOURS afficher les filtres et onglets (même si vide)
    # Filtres...
    # (votre code de filtres actuel)
    
    # ONGLETS TOUJOURS VISIBLES
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Consulter", "✏️ Modifier", "➕ Ajouter", "🗑️ Supprimer"])
    
    # ... reste du code
                                    st.success(f"✅ {len(ids_to_delete)} dépense(s) supprimée(s) avec succès!")
                                    st.rerun()
                                    
                                except Exception as e:
                                    st.error(f"❌ Erreur lors de la suppression: {str(e)}")
                            else:
                                st.info("Ces lignes ont déjà été supprimées. Rafraîchissez la page (F5).")
                    
                    with col2:
                        if st.button("❌ Annuler", key="cancel_delete_depenses"):
                            # Réinitialiser le flag de suppression
                            if 'last_delete' in st.session_state:
                                del st.session_state.last_delete
                            st.rerun()
                else:
                    st.info("ℹ️ Sélectionnez au moins une dépense pour activer la suppression")
            else:
                st.info("ℹ️ Aucune dépense à supprimer avec les filtres actuels")
    else:
        st.info("Aucune dépense enregistrée")

# ==================== COPROPRIÉTAIRES ====================
elif menu == "👥 Copropriétaires":
    st.markdown("<h1 class='main-header'>👥 Copropriétaires</h1>", unsafe_allow_html=True)
    
    copro_df = get_coproprietaires()
    
    if not copro_df.empty:
        # Convertir tantieme en numérique
        copro_df['tantieme'] = pd.to_numeric(copro_df['tantieme'], errors='coerce')
        
        total_tantiemes = copro_df['tantieme'].sum()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Nombre de copropriétaires", len(copro_df))
        with col2:
            st.metric("Total tantièmes", int(total_tantiemes))
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
        # Convertir en numérique
        copro_df['tantieme'] = pd.to_numeric(copro_df['tantieme'], errors='coerce')
        depenses_df['montant_du'] = pd.to_numeric(depenses_df['montant_du'], errors='coerce')
        
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

# ==================== PLAN COMPTABLE ====================
elif menu == "📋 Plan Comptable":
    st.markdown("<h1 class='main-header'>📋 Plan Comptable</h1>", unsafe_allow_html=True)
    
    plan_df = get_plan_comptable()
    
    if not plan_df.empty:
        # Statistiques
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Nombre de comptes", len(plan_df))
        with col2:
            if 'classe' in plan_df.columns:
                st.metric("Nombre de classes", plan_df['classe'].nunique())
            else:
                st.metric("Classes", "N/A")
        with col3:
            if 'famille' in plan_df.columns:
                st.metric("Nombre de familles", plan_df['famille'].nunique())
            else:
                st.metric("Familles", "N/A")
        
        st.divider()
        
        # Filtres
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Filtre par classe
            if 'classe' in plan_df.columns:
                classes = ['Toutes'] + sorted(plan_df['classe'].unique().tolist())
                classe_filter = st.selectbox("Filtrer par classe", classes)
            else:
                classe_filter = 'Toutes'
        
        with col2:
            # Filtre par famille
            if 'famille' in plan_df.columns:
                familles = ['Toutes'] + sorted(plan_df['famille'].unique().tolist())
                famille_filter = st.selectbox("Filtrer par famille", familles)
            else:
                famille_filter = 'Toutes'
        
        with col3:
            # Recherche
            search = st.text_input("🔍 Rechercher", placeholder="Compte ou libellé...")
        
        # Application des filtres
        filtered_df = plan_df.copy()
        
        if 'classe' in plan_df.columns and classe_filter != 'Toutes':
            filtered_df = filtered_df[filtered_df['classe'] == classe_filter]
        
        if 'famille' in plan_df.columns and famille_filter != 'Toutes':
            filtered_df = filtered_df[filtered_df['famille'] == famille_filter]
        
        if search:
            # Recherche dans le compte ou le libellé
            mask = False
            if 'compte' in filtered_df.columns:
                mask = mask | filtered_df['compte'].astype(str).str.contains(search, case=False, na=False)
            if 'libelle' in filtered_df.columns:
                mask = mask | filtered_df['libelle'].astype(str).str.contains(search, case=False, na=False)
            if 'libelle_compte' in filtered_df.columns:
                mask = mask | filtered_df['libelle_compte'].astype(str).str.contains(search, case=False, na=False)
            
            if isinstance(mask, pd.Series):
                filtered_df = filtered_df[mask]
        
        # Affichage
        st.subheader(f"Plan comptable ({len(filtered_df)} comptes)")
        
        # Déterminer les colonnes à afficher
        display_cols = []
        if 'compte' in filtered_df.columns:
            display_cols.append('compte')
        if 'libelle_compte' in filtered_df.columns:
            display_cols.append('libelle_compte')
        elif 'libelle' in filtered_df.columns:
            display_cols.append('libelle')
        if 'classe' in filtered_df.columns:
            display_cols.append('classe')
        if 'famille' in filtered_df.columns:
            display_cols.append('famille')
        
        # Configuration des colonnes
        column_config = {}
        if 'compte' in display_cols:
            column_config['compte'] = st.column_config.NumberColumn("Compte", format="%d")
        if 'libelle_compte' in display_cols:
            column_config['libelle_compte'] = st.column_config.TextColumn("Libellé")
        elif 'libelle' in display_cols:
            column_config['libelle'] = st.column_config.TextColumn("Libellé")
        if 'classe' in display_cols:
            column_config['classe'] = st.column_config.TextColumn("Classe")
        if 'famille' in display_cols:
            column_config['famille'] = st.column_config.NumberColumn("Famille", format="%d")
        
        # Affichage du tableau
        st.dataframe(
            filtered_df[display_cols] if display_cols else filtered_df,
            use_container_width=True,
            hide_index=True,
            column_config=column_config
        )
        
        # Graphiques
        st.divider()
        
        col1, col2 = st.columns(2)
        
        with col1:
            if 'famille' in filtered_df.columns:
                st.subheader("Répartition par Famille")
                famille_counts = filtered_df['famille'].value_counts().reset_index()
                famille_counts.columns = ['Famille', 'Nombre de comptes']
                fig = px.bar(famille_counts, x='Famille', y='Nombre de comptes', 
                            text='Nombre de comptes',
                            title='Nombre de comptes par famille')
                fig.update_traces(textposition='outside')
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            if 'classe' in filtered_df.columns:
                st.subheader("Répartition par Classe")
                classe_counts = filtered_df['classe'].value_counts().reset_index()
                classe_counts.columns = ['Classe', 'Nombre de comptes']
                fig = px.pie(classe_counts, values='Nombre de comptes', names='Classe',
                            title='Distribution par classe')
                fig.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)
        
        # Export
        st.divider()
        
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            csv = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Exporter en CSV",
                data=csv,
                file_name=f"plan_comptable_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
    else:
        st.warning("⚠️ Aucune donnée dans le plan comptable. Vérifiez que la table 'plan_comptable' existe dans Supabase.")

st.divider()
st.markdown("<div style='text-align: center; color: #666;'>🏢 Gestion de Copropriété</div>", unsafe_allow_html=True)
