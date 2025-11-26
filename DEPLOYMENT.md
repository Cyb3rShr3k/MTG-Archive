# MTG Archive - Web Deployment Guide

## Running Locally

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Flask server:**
   ```bash
   python main.py
   ```

3. **Open in browser:**
   ```
   http://localhost:5000
   ```

## Deploying to Render

1. **Push to GitHub:**
   ```bash
   git add .
   git commit -m "Convert to web application"
   git push origin main
   ```

2. **Create Render account:**
   - Go to https://render.com
   - Sign up with GitHub

3. **Create New Web Service:**
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Render will auto-detect the `render.yaml` configuration

4. **Configure (if needed):**
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn main:app`
   - Python Version: 3.11

5. **Deploy:**
   - Click "Create Web Service"
   - Render will automatically deploy your app
   - Your app will be live at: `https://your-app-name.onrender.com`

## Deploying to Railway

1. **Install Railway CLI (optional):**
   ```bash
   npm install -g @railway/cli
   ```

2. **Deploy via GitHub:**
   - Go to https://railway.app
   - Click "New Project" → "Deploy from GitHub repo"
   - Select your repository
   - Railway will auto-detect Flask and deploy

3. **Or deploy via CLI:**
   ```bash
   railway login
   railway init
   railway up
   ```

## Deploying to Heroku

1. **Install Heroku CLI:**
   ```bash
   # Download from https://devcenter.heroku.com/articles/heroku-cli
   ```

2. **Login and create app:**
   ```bash
   heroku login
   heroku create your-app-name
   ```

3. **Deploy:**
   ```bash
   git push heroku main
   ```

4. **Open your app:**
   ```bash
   heroku open
   ```

## Environment Variables

For production, you may want to set:
- `PORT` - Server port (usually auto-set by hosting platform)
- `FLASK_ENV` - Set to `production`

## Notes

- **Free Tier Limitations:**
  - Render: 750 hours/month, spins down after inactivity
  - Railway: $5 free credit/month
  - Heroku: No longer has free tier (requires paid plan)

- **Database:** Currently uses SQLite (single-user). For multi-user, you'll need to:
  - Migrate to PostgreSQL
  - Add user authentication
  - Add user-specific data isolation

- **File Storage:** Uploaded files are temporary. For persistent storage, use:
  - AWS S3
  - Cloudinary
  - Or hosting platform's persistent disk

## Recommended: Render Free Tier

Render is recommended because:
- ✅ Free tier available
- ✅ Auto-deploys from GitHub
- ✅ Supports Python 3.11
- ✅ Easy configuration with `render.yaml`
- ✅ Automatic HTTPS
