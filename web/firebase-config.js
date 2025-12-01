// Firebase Configuration
// REPLACE THESE VALUES WITH YOUR OWN FROM FIREBASE CONSOLE
// See FIREBASE_SETUP.md for instructions

console.log('firebase-config.js loading...');

const firebaseConfig = {
  apiKey: "AIzaSyBL8j-Hfi4QImpO7RfDVQ2ficbiuIn9bWs",
  authDomain: "mtg-archive-357ca.firebaseapp.com",
  projectId: "mtg-archive-357ca",
  storageBucket: "mtg-archive-357ca.firebasestorage.app",
  messagingSenderId: "137025206900",
  appId: "1:137025206900:web:2ed26329033dec191aaf21"
};

async function initializeFirebaseConfig() {
  try {
    // Wait for SDK loading promise if it exists
    if (window.firebaseSDKLoading) {
      console.log('Waiting for Firebase SDK to load...');
      await window.firebaseSDKLoading;
    }

    // Check if Firebase is available
    if (typeof firebase === 'undefined') {
      throw new Error('Firebase SDK not loaded - check script tags');
    }

    console.log('Firebase SDK available, initializing app...');
    
    // Check if already initialized
    if (firebase.apps && firebase.apps.length > 0) {
      console.log('Firebase already initialized, reusing existing app');
      const app = firebase.apps[0];
      const auth = firebase.auth(app);
      const db = firebase.firestore(app);
      const storage = firebase.storage(app);
      
      window.firebaseServices = {
        auth,
        db,
        storage
      };
      console.log('window.firebaseServices set successfully (reused app)');
      return;
    }
    
    // Initialize Firebase
    const app = firebase.initializeApp(firebaseConfig);
    console.log('Firebase app initialized');

    // Get references to Firebase services
    const auth = firebase.auth(app);
    const db = firebase.firestore(app);
    const storage = firebase.storage(app);

    console.log('Firebase services loaded:', { auth, db, storage });

    // Export for use in other scripts
    window.firebaseServices = {
      auth,
      db,
      storage
    };

    console.log('window.firebaseServices set successfully');
  } catch (error) {
    console.error('Firebase initialization failed:', error);
    console.error('Stack:', error.stack);
  }
}

// Start initialization immediately
initializeFirebaseConfig();

