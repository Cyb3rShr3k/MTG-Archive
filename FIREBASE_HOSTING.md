# Firebase Hosting Setup Guide

## Local Development & Deployment

### Prerequisites
1. **Firebase CLI** installed globally
   ```powershell
   npm install -g firebase-tools
   ```

2. **Node.js** (comes with npm)
   - Download from https://nodejs.org/

### Initial Setup (One-time)

1. **Login to Firebase**
   ```powershell
   firebase login
   ```
   This will open your browser to authenticate with your Google account.

2. **Verify Project Configuration**
   ```powershell
   firebase projects:list
   ```
   Should show `mtg-archive-357ca` as your project.

### Development Workflow

#### Option A: Local Testing with Firebase Emulator (Recommended)
```powershell
# Start the Firebase emulator
firebase emulators:start
```
This runs your app locally at `http://localhost:5000` and allows you to test before deploying.

#### Option B: Direct Deployment to Firebase Hosting
```powershell
# Deploy to Firebase Hosting
firebase deploy --only hosting
```
Your site will be live at: `https://mtg-archive-357ca.web.app`

### Daily Workflow

1. **Make code changes** in VS Code (in `web/` folder)
2. **Test locally** (optional):
   ```powershell
   firebase emulators:start
   ```
   Visit `http://localhost:5000`

3. **Commit to Git** (all changes tracked)
   ```powershell
   git add .
   git commit -m "Your changes"
   git push origin main
   ```

4. **Deploy to Firebase**
   ```powershell
   firebase deploy --only hosting
   ```

### Important Files

- **`firebase.json`** - Firebase configuration
- **`.firebaserc`** - Project ID and default project
- **`web/`** - Your public hosting folder (what gets deployed)

### Useful Firebase Commands

```powershell
# Check current project
firebase projects:list

# Deploy everything
firebase deploy

# Deploy only hosting
firebase deploy --only hosting

# View deployment history
firebase hosting:channel:list

# Stop the emulator
Ctrl+C
```

### Troubleshooting

**Firebase CLI not found:**
```powershell
npm install -g firebase-tools
firebase --version
```

**Can't login:**
```powershell
firebase logout
firebase login
```

**Want to switch projects:**
```powershell
firebase use mtg-archive-357ca
```

### GitHub Integration (Optional Auto-Deploy)

See `.github/workflows/deploy.yml` for automatic deployment on every push to main branch.

### Security Notes

- ✅ Your Firebase credentials are safe (stored locally in `~/.config/gcloud/`)
- ✅ `.firebaserc` doesn't contain sensitive info
- ✅ Never commit actual database credentials to Git
- ✅ Firebase config in `firebase-config.js` is OK to commit (API key is public)

