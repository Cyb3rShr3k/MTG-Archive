# Firebase Setup Guide

## Step 1: Create Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com)
2. Click "Create project"
3. Project name: `MTG-Archive`
4. Continue → Disable Google Analytics → Create project
5. Wait for project creation (1-2 minutes)

## Step 2: Enable Authentication

1. In Firebase Console, go to **Build** → **Authentication**
2. Click "Get started"
3. Click "Email/Password" provider
4. Enable it → Save
5. Go to **Settings** (gear icon) → **Project settings**
6. Copy your **Web API Key** (you'll need this)

## Step 3: Create Firestore Database

1. In Firebase Console, go to **Build** → **Firestore Database**
2. Click "Create database"
3. Start in **Test mode** (for now)
4. Select region closest to you
5. Create

## Step 4: Get Firebase Config

1. Go to **Project Settings** (gear icon top-left)
2. Under "Your apps" section, click **Add app** → **Web** (</> icon)
3. App nickname: `MTG-Archive Web`
4. Copy the **firebaseConfig** object
5. You'll paste this into `web/firebase-config.js`

## Step 5: Add Firebase to Your Project

The `web/firebase-config.js` file needs your config. Here's the template:

```javascript
// web/firebase-config.js
const firebaseConfig = {
  apiKey: "YOUR_API_KEY_HERE",
  authDomain: "your-project.firebaseapp.com",
  projectId: "your-project-id",
  storageBucket: "your-project.appspot.com",
  messagingSenderId: "YOUR_SENDER_ID",
  appId: "YOUR_APP_ID"
};

// Initialize Firebase
firebase.initializeApp(firebaseConfig);
```

**Replace with values from Firebase Console!**

## Step 6: Update GitHub Pages Settings

1. Go to your GitHub repo settings
2. **Pages** section
3. Source: **Deploy from a branch**
4. Branch: **main** / **root** folder
5. Save

## Step 7: Test Deployment

Your app will be live at: `https://cyb3rshr3k.github.io/MTG-Archive/`

---

## What Firebase Provides

✅ **Authentication** - User login/register  
✅ **Firestore Database** - Store collections/decks  
✅ **Real-time Sync** - Changes sync instantly  
✅ **Free Tier** - Unlimited for small projects  
✅ **No Backend Server** - Everything in JavaScript  

---

## Firestore Database Structure

```
users/
  {userId}/
    username: string
    email: string
    createdAt: timestamp

collections/
  {userId}/
    {cardId}/
      name: string
      set: string
      quantity: number
      scryfall_id: string
      colors: array
      cmc: number
      type: string
      rarity: string
      image_url: string
      added_at: timestamp

decks/
  {userId}/
    {deckId}/
      name: string
      deckType: string
      commander: string
      cards: array of {cardId, quantity}
      colors: string
      createdAt: timestamp
      updatedAt: timestamp
```

---

## Security Rules (Copy to Firestore)

Go to **Firestore** → **Rules** tab and paste:

```firestore
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Users can only read/write their own data
    match /users/{userId} {
      allow read, write: if request.auth.uid == userId;
    }
    match /collections/{userId}/{document=**} {
      allow read, write: if request.auth.uid == userId;
    }
    match /decks/{userId}/{document=**} {
      allow read, write: if request.auth.uid == userId;
    }
  }
}
```

Then click **Publish**

---

## Next Steps

1. Complete steps 1-5 above
2. Create `web/firebase-config.js` with your config
3. We'll update the HTML files to use Firebase
4. Push to GitHub
5. Your app is live!
