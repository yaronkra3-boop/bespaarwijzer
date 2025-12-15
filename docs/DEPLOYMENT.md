# Deployment Guide

BespaarWijzer deploys to Vercel via GitHub.

## Architecture

```
[Local Development]          [GitHub]           [Vercel]
     app/                →    repo/          →   bespaarwijzer.vercel.app
     ├── index.html           ├── index.html     (auto-deploy on push)
     ├── products.json        ├── products.json
     └── folder-validity.json └── folder-validity.json
```

## Initial Setup (One-Time)

### 1. Create GitHub Repository

1. Go to [github.com/new](https://github.com/new)
2. Name: `bespaarwijzer`
3. Public (required for free Vercel)
4. Don't initialize with README

### 2. Create Local Deployment Folder

```bash
mkdir -p ~/Desktop/bespaarwijzer

# Copy app files
cp /Users/yaronkra/Jarvis/bespaarwijzer/app/index.html ~/Desktop/bespaarwijzer/
cp /Users/yaronkra/Jarvis/bespaarwijzer/app/products.json ~/Desktop/bespaarwijzer/
cp /Users/yaronkra/Jarvis/bespaarwijzer/app/folder-validity.json ~/Desktop/bespaarwijzer/
```

### 3. Initialize Git

```bash
cd ~/Desktop/bespaarwijzer
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/bespaarwijzer.git
git push -u origin main
```

### 4. Connect to Vercel

1. Go to [vercel.com](https://vercel.com)
2. Sign in with GitHub
3. Click "Add New" → "Project"
4. Import `bespaarwijzer` repository
5. Framework: "Other"
6. Click "Deploy"

Your app is now live at: `bespaarwijzer.vercel.app`

## Weekly Deployment

After running `./update.sh`:

```bash
# Copy updated files
cp /Users/yaronkra/Jarvis/bespaarwijzer/app/products.json ~/Desktop/bespaarwijzer/
cp /Users/yaronkra/Jarvis/bespaarwijzer/app/folder-validity.json ~/Desktop/bespaarwijzer/

# Push to GitHub
cd ~/Desktop/bespaarwijzer
git add .
git commit -m "Weekly update - $(date +%Y-%m-%d)"
git push
```

Vercel auto-deploys within 30 seconds.

## Automated Deployment

Use the `--deploy` flag:

```bash
./update.sh --deploy
```

This automatically:
1. Copies files to deployment folder
2. Commits and pushes to GitHub
3. Vercel auto-deploys

## Useful Links

| Resource | URL |
|----------|-----|
| Live App | [bespaarwijzer.vercel.app](https://bespaarwijzer.vercel.app) |
| Vercel Dashboard | [vercel.com/dashboard](https://vercel.com/dashboard) |
| GitHub Repo | github.com/YOUR_USERNAME/bespaarwijzer |
| Local Folder | ~/Desktop/bespaarwijzer |
