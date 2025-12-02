// Firebase Configuration
console.log('firebase-config.js loading...');

const firebaseConfig = {
  apiKey: "AIzaSyBL8j-Hfi4QImpO7RfDVQ2ficbiuIn9bWs",
  authDomain: "mtg-archive-357ca.firebaseapp.com",
  projectId: "mtg-archive-357ca",
  storageBucket: "mtg-archive-357ca.firebasestorage.app",
  messagingSenderId: "137025206900",
  appId: "1:137025206900:web:2ed26329033dec191aaf21"
};

// Wait for Firebase SDK to be available, with timeout
let firebaseInitAttempts = 0;
const MAX_INIT_ATTEMPTS = 50; // 5 seconds with 100ms checks

function tryInitializeFirebase() {
  firebaseInitAttempts++;
  
  // Check if Firebase SDK is available
  if (typeof firebase === 'undefined') {
    if (firebaseInitAttempts < MAX_INIT_ATTEMPTS) {
      console.log(`Firebase SDK not ready, retrying... (attempt ${firebaseInitAttempts}/${MAX_INIT_ATTEMPTS})`);
      setTimeout(tryInitializeFirebase, 100);
    } else {
      console.error('Firebase SDK failed to load after 5 seconds');
      alert('Firebase failed to initialize. Please refresh the page.');
    }
    return;
  }

  console.log('Firebase SDK detected, initializing...');
  
  try {
    // Check if already initialized
    if (firebase.apps && firebase.apps.length > 0) {
      console.log('Firebase already initialized, reusing existing app');
      const app = firebase.apps[0];
      const auth = firebase.auth(app);
      const db = firebase.firestore(app);
      const storage = firebase.storage(app);
      
      window.firebaseServices = { auth, db, storage };
      console.log('✅ Firebase services available (reused app)');
      return;
    }
    
    // Initialize new app
    const app = firebase.initializeApp(firebaseConfig);
    const auth = firebase.auth(app);
    const db = firebase.firestore(app);
    const storage = firebase.storage(app);
    
    window.firebaseServices = { auth, db, storage };
    console.log('✅ Firebase services initialized successfully');
  } catch (error) {
    console.error('Firebase initialization error:', error);
    if (error.code === 'app/duplicate-app') {
      console.log('App already initialized, fetching services...');
      const app = firebase.apps[0];
      window.firebaseServices = {
        auth: firebase.auth(app),
        db: firebase.firestore(app),
        storage: firebase.storage(app)
      };
      console.log('✅ Firebase services recovered');
    }
  }
}

// Start initialization immediately
tryInitializeFirebase();
