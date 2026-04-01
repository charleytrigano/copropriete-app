# 🏢 Gestion de Copropriété — Application Streamlit

Application complète de gestion de copropriété avec Supabase comme base de données.

## 🚀 Démarrage rapide

### 1. Prérequis
- Python 3.9+
- Un compte [Supabase](https://supabase.com) (gratuit)

### 2. Installation
```bash
pip install -r requirements.txt
```

### 3. Configuration Supabase
1. Créez un projet sur [supabase.com](https://supabase.com)
2. Allez dans **Project Settings > API** et copiez l'URL et la clé `anon`
3. Allez dans **SQL Editor** et exécutez le contenu de `setup_supabase.sql`
4. Allez dans **Storage > New Bucket** et créez un bucket nommé `factures` (privé)

### 4. Configuration des secrets
Éditez `.streamlit/secrets.toml` :
```toml
SUPABASE_URL = "https://xxxx.supabase.co"
SUPABASE_KEY = "votre-anon-key"
```

### 5. Import des données (optionnel)
```bash
python import_data.py
```

### 6. Lancement
```bash
streamlit run app.py
```

## 📋 Fonctionnalités

| Module | Description |
|--------|-------------|
| 📊 Tableau de Bord | Vue synthétique budget vs dépenses |
| 💰 Budget | Gestion du budget prévisionnel |
| 📝 Dépenses | Saisie et suivi des dépenses + factures |
| 👥 Copropriétaires | Annuaire et gestion des lots |
| 🔄 Répartition | Calcul des appels de fonds trimestriels |
| 🏛️ Loi Alur | Suivi du fonds de travaux obligatoire |
| 📈 Analyses | Graphiques et statistiques |
| 📋 Plan Comptable | Gestion du plan comptable |
| 🏛 AG | Assemblées générales et procès-verbaux |
| 📒 Grand Livre | Historique comptable |
| 📑 Contrats | Suivi des contrats fournisseurs |
| 📬 Communications | Envoi email / WhatsApp / SMS |
| 🏠 Locataires | Fiches locataires et gestion des BAL |

## ⚙️ Services optionnels

- **Brevo** : envoi d'emails transactionnels (gratuit jusqu'à 300 emails/jour)
- **Twilio** : envoi de SMS
- **SMTP** : alternative à Brevo pour les emails

## 📁 Structure
```
├── app.py                  # Application principale
├── import_data.py          # Script d'import Excel → Supabase
├── setup_supabase.sql      # Schéma de base de données
├── requirements.txt        # Dépendances Python
├── suivi_copropriete_automatise.xlsx  # Données source
└── .streamlit/
    ├── config.toml         # Configuration Streamlit (thème, etc.)
    └── secrets.toml        # Vos credentials (ne pas committer !)
```
