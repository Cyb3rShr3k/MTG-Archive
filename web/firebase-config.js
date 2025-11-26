// Firebase Configuration
// REPLACE THESE VALUES WITH YOUR OWN FROM FIREBASE CONSOLE
// See FIREBASE_SETUP.md for instructions

const firebaseConfig = {
  apiKey: "AIzaSyDEMOKEY_REPLACE_WITH_YOUR_KEY",
  authDomain: "your-project.firebaseapp.com",
  projectId: "your-project-id",
  storageBucket: "your-project.appspot.com",
  messagingSenderId: "123456789",
  appId: "1:123456789:web:abcdef123456"
};

// Initialize Firebase
firebase.initializeApp(firebaseConfig);

// Get references to Firebase services
const auth = firebase.auth();
const db = firebase.firestore();
const storage = firebase.storage();

// Export for use in other scripts
window.firebaseServices = {
  auth,
  db,
  storage
};
