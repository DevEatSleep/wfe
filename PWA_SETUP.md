# PWA Setup - Assistant Financier

## Qu'est-ce qu'une PWA (Progressive Web App)?

Une PWA est une application web qui se comporte comme une application native:
- ✅ Installable sur l'écran d'accueil
- ✅ Fonctionne hors ligne (offline)
- ✅ Chargement rapide et interface fluide
- ✅ Notifications push possibles
- ✅ Accès complet aux données utilisateur

## Installation de l'application PWA

### Sur Desktop (Windows/Mac/Linux):
1. Accéder à l'application: `https://votre-app.azurewebsites.net`
2. Cliquer sur le menu (⋮) ou l'icône d'installation
3. Sélectionner "Installer l'application"
4. L'app apparaît dans votre barre d'applications

### Sur Mobile (iOS/Android):
1. Ouvrir l'app dans le navigateur
2. **Android**: Menu (⋮) → "Installer l'application"
3. **iOS**: Partage (⬆️) → "Ajouter à l'écran d'accueil"

## Fonctionnalités PWA implémentées

### 1. Web Manifest (`manifest.json`)
Définit les métadonnées de l'application:
- Nom et description
- Icônes pour divers appareils
- Couleurs du thème
- Raccourcis (Dashboard, Chat)

### 2. Service Worker (`service-worker.js`)
Active le fonctionnement hors ligne:
- **Cache-first** pour les assets statiques (CSS, JS)
- **Network-first** pour les API (toujours essayer le réseau)
- Réponse de fallback en cas d'erreur réseau

### 3. Métadonnées PWA dans le HTML
Tags meta pour:
- Configuration d'écran d'accueil sur iOS
- Couleur du thème
- Icône tactile

## Comportement hors ligne

### Avec connexion:
- Tout fonctionne normalement
- Le cache se met à jour en arrière-plan

### Sans connexion:
- ✅ Les pages déjà visitées restent accessibles
- ✅ Les données mises en cache sont disponibles
- ❌ Les API retournent une erreur contrôlée
- ❌ Impossible d'ajouter de nouvelles données (sauf caching local)

## Améliorations possibles

### 1. Notification des mises à jour
Ajouter à `service-worker.js`:
```javascript
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
```

### 2. Background Sync
Permettre l'envoi des données une fois la connexion rétablie:
```javascript
registration.sync.register('sync-tag');
```

### 3. Web Storage pour les données offline
Stocker les modifications localement avec IndexedDB:
```javascript
// Dans app.py ou JavaScript
localStorage.setItem('expenses', JSON.stringify(expenses));
```

## Debugging de la PWA

### Afficher le Service Worker:
1. Ouvrir DevTools (F12)
2. Aller à l'onglet "Application"
3. Menu "Service Workers"

### Vérifier le cache:
1. DevTools → Application
2. Cache Storage
3. Voir les fichiers en cache

### Afficher le manifest:
1. DevTools → Application
2. Manifest
3. Vérifier les icônes et couleurs

## Tests de la PWA

```bash
# Sur Azure, vérifier que l'app est en HTTPS
curl -I https://votre-app.azurewebsites.net
# Devrait retourner 200 OK

# Vérifier le manifest
curl https://votre-app.azurewebsites.net/static/manifest.json

# Vérifier le service worker
curl https://votre-app.azurewebsites.net/static/service-worker.js
```

## Performance

- **First Contentful Paint (FCP)**: < 2s
- **Cacheable**: 95% des assets
- **Offline ready**: Oui ✅
- **HTTPS**: Requis ✅

## Ressources

- [MDN: Progressive Web Apps](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps)
- [Google: PWA Guide](https://web.dev/progressive-web-apps/)
- [Web.dev: PWA Checklist](https://web.dev/pwa-checklist/)
