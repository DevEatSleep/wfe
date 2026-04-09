# Assistant Financier - Équité Couple

**Version:** 0.1  
**Author:** Thierry Verdier  
**Last Updated:** April 8, 2026

## Description

Un assistant financier innovant qui analyse l'équité financière et domestique dans les couples. L'application aide les couples à mieux comprendre le partage des responsabilités (financières et domestiques) et à identifier les déséquilibres potentiels.

## Features

✅ **Chatbot intelligent** - Collecte les informations de manière conversationnelle  
✅ **Calcul d'équité** - Analyse le score d'équité basé sur:
  - Revenu de chaque partenaire
  - Dépenses payées par chaque partenaire
  - Heures de travail domestique

✅ **Tableau de bord** - Visualisation des données et des statistiques  
✅ **PWA** - Application web progressive (installable sur mobile/desktop)  
✅ **Fonctionnement hors ligne** - Service Worker pour accès offline  
✅ **Données INSEE** - Basées sur les statistiques de travail domestique françaises

## Stack Technique

- **Backend:** Flask (Python 3.11+)
- **Frontend:** HTML5, CSS3, JavaScript (Vanilla + Chart.js)
- **Database:** SQLite (local) / Azure SQL Database (production)
- **Deployment:** Azure App Service / Docker
- **PWA:** Service Worker + Web Manifest

## Installation Locale

```bash
# 1. Cloner le repo
cd wfe

# 2. Créer l'environnement virtuel
python -m venv .venv

# 3. Activer l'environnement
.venv\Scripts\Activate.ps1  # Windows
source .venv/bin/activate   # macOS/Linux

# 4. Installer les dépendances
pip install -r requirements.txt

# 5. Lancer l'app
python app.py

# L'app est accessible à http://localhost:5000
```

## Déploiement sur Azure

Voir [AZURE_DEPLOYMENT.md](AZURE_DEPLOYMENT.md) pour les instructions complètes.

## PWA Installation

Voir [PWA_SETUP.md](PWA_SETUP.md) pour comment installer et utiliser l'app en tant que PWA.

## Structure du Projet

```
├── app.py                  # Application Flask principale
├── db.py                   # Logique de base de données
├── intents.py              # Détection d'intents du chatbot
├── state_result.py         # Gestion d'état des réponses
├── requirements.txt        # Dépendances Python
├── templates/
│   ├── chat.html          # Interface du chatbot
│   └── dashboard.html     # Tableau de bord
├── static/
│   ├── css/               # Feuilles de style
│   ├── manifest.json      # Configuration PWA
│   ├── service-worker.js  # Service Worker
│   └── *.svg              # Icônes
├── data/
│   ├── messages.json      # Messages du chatbot
│   └── categories.json    # Catégories de dépenses
└── .github/workflows/     # GitHub Actions CI/CD
```

## Auteur

**Thierry Verdier** - Développeur Full Stack

## License

MIT

## Support

Pour toute question ou issue, consultez la documentation ou contactez l'auteur.
