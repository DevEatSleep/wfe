# Assistant Financier - Équité Couple

**Version:** 0.1  
**Author:** Thierry Verdier  
**Last Updated:** April 9, 2026

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

- **Backend:** Flask 3.0.3 (Python 3.11+) with Blueprint-based modular architecture
- **Frontend:** HTML5, CSS3, JavaScript (Vanilla + Chart.js)
- **Database:** PostgreSQL (via psycopg2) - persistent data with session-based buffering
- **Deployment:** Render.com (free tier with auto-scaling)
- **PWA:** Service Worker + Web Manifest
- **Architecture:** Modular structure with `/src/` package for separation of concerns

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

## Déploiement sur Render

Voir [RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md) pour les instructions complètes.

## PWA Installation

Voir [PWA_SETUP.md](PWA_SETUP.md) pour comment installer et utiliser l'app en tant que PWA.

## Structure du Projet

```
├── app.py                      # Application Flask principale (orchestration)
├── requirements.txt            # Dépendances Python
├── .env                        # Configuration (DATABASE_URL, SECRET_KEY)
├── src/                        # Package principal (modular architecture)
│   ├── __init__.py
│   ├── db.py                  # Logique PostgreSQL + session management
│   ├── intents.py             # Détection d'intents du chatbot
│   ├── state_result.py        # Gestion d'état des réponses FSM
│   ├── utils/
│   │   ├── __init__.py
│   │   └── helpers.py         # Fonctions utilitaires (normalisation, détection d'intents)
│   └── routes/
│       ├── __init__.py        # Exports des blueprints
│       ├── pages.py           # Routes HTML (/, /chatbot, /dashboard)
│       ├── api.py             # Endpoints API (/api/save-to-db, /api/bilan, /api/reset)
│       └── chat.py            # Chatbot message processing blueprint
├── templates/
│   ├── chat.html              # Interface du chatbot
│   └── dashboard.html         # Tableau de bord
├── static/
│   ├── css/                   # Feuilles de style
│   ├── manifest.json          # Configuration PWA
│   ├── service-worker.js      # Service Worker
│   └── *.svg                  # Icônes
├── data/
│   ├── messages.json          # Messages du chatbot
│   └── categories.json        # Catégories de dépenses
└── docs/                       # Documentation
    └── RENDER_DEPLOYMENT.md   # Guide de déploiement
```

## Auteur

**Thierry Verdier** - Développeur Full Stack

## License

MIT

## Support

Pour toute question ou issue, consultez la documentation ou contactez l'auteur.
