// Service Worker pour gérer les badges d'application
const CACHE_NAME = 'bon-intervention-v1';

// Installation du service worker
self.addEventListener('install', (event) => {
    console.log('Service Worker installé');
    self.skipWaiting();
});

// Activation du service worker
self.addEventListener('activate', (event) => {
    console.log('Service Worker activé');
    event.waitUntil(self.clients.claim());
});

// Gestion des messages depuis l'application
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'SET_BADGE') {
        const count = event.data.count || 0;
        
        // Utiliser l'API Badging si disponible (iOS 16.4+)
        if ('setAppBadge' in self.navigator) {
            if (count > 0) {
                self.navigator.setAppBadge(count).catch(err => {
                    console.error('Erreur setAppBadge:', err);
                });
            } else {
                self.navigator.clearAppBadge().catch(err => {
                    console.error('Erreur clearAppBadge:', err);
                });
            }
        }
    }
});

// Gestion des notifications push (pour plus tard)
self.addEventListener('push', (event) => {
    console.log('Push notification reçue:', event);
});

