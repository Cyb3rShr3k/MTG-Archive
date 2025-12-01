#!/bin/bash
# Quick deployment script for Firebase Hosting

echo "🔥 MTG Archive Firebase Deployment"
echo "=================================="
echo ""

# Check if Firebase CLI is installed
if ! command -v firebase &> /dev/null; then
    echo "❌ Firebase CLI not found. Installing..."
    npm install -g firebase-tools
fi

echo "📦 Checking Firebase setup..."
firebase --version

echo ""
echo "Select deployment mode:"
echo "1) Deploy to Firebase (production)"
echo "2) Test locally with emulator"
echo "3) Just show current project"
echo ""
read -p "Enter choice (1-3): " choice

case $choice in
    1)
        echo "🚀 Deploying to Firebase Hosting..."
        firebase deploy --only hosting
        echo ""
        echo "✅ Deployment complete!"
        echo "Visit: https://mtg-archive-357ca.web.app"
        ;;
    2)
        echo "🧪 Starting Firebase emulator..."
        firebase emulators:start
        ;;
    3)
        echo "📋 Current Firebase project:"
        firebase projects:list
        ;;
    *)
        echo "Invalid choice"
        ;;
esac
