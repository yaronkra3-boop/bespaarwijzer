# BespaarWijzer Development Workflow

This document describes how to properly make changes to the BespaarWijzer codebase using Git.

## Quick Reference

```bash
# 1. Start new work: Create ticket + branch
mkdir tickets/XXX-feature-name
git checkout -b feature/XXX-feature-name

# 2. Make changes, commit often
git add <files>
git commit -m "Add: description of change"

# 3. When done: Merge to main
git checkout main
git merge feature/XXX-feature-name
git branch -d feature/XXX-feature-name  # optional cleanup
```

---

## Workflow Steps

### Step 1: Create a Ticket

Before starting any significant work, create a ticket folder:

```bash
mkdir /Users/yaronkra/Jarvis/tickets/XXX-descriptive-name/
```

**Naming convention:**
- Number sequentially: `014-`, `015-`, etc.
- Use kebab-case: `lidl-scraper-improvement`
- Be descriptive: what is the goal?

**Ticket contents:**
- `roadmap.html` - Visual roadmap with phases and tasks
- Supporting files as needed (analysis, notes, etc.)

### Step 2: Create a Feature Branch

```bash
# Make sure you're on main first
git checkout main

# Create and switch to new branch
git checkout -b feature/XXX-feature-name
```

**Branch naming:**
- Prefix with `feature/` for new features
- Prefix with `fix/` for bug fixes
- Include ticket number: `feature/014-lidl-scraper`

### Step 3: Make Changes

Work on your changes. After completing a logical unit of work:

```bash
# See what changed
git status
git diff

# Stage specific files
git add path/to/file.py

# Or stage all changes in a directory
git add bespaarwijzer/scrapers/lidl/

# Commit with clear message
git commit -m "Add: brand extraction from product names"
```

**Commit message prefixes:**
- `Add:` - New feature or file
- `Update:` - Changes to existing feature
- `Fix:` - Bug fix
- `Remove:` - Deleted code/files
- `Docs:` - Documentation changes

### Step 4: Test Your Changes

```bash
# For scraper changes, run the update
cd /Users/yaronkra/Jarvis/bespaarwijzer
./update.sh

# Start local server to test
cd app && python3 -m http.server 8080
```

### Step 5: Merge to Main

When your feature is complete and tested:

```bash
# Switch to main
git checkout main

# Merge your feature branch
git merge feature/XXX-feature-name

# Optionally delete the feature branch
git branch -d feature/XXX-feature-name
```

---

## Example: Lidl Scraper Improvement

Here's a real example of this workflow in action:

```bash
# 1. Created ticket
mkdir tickets/014-lidl-scraper-improvement

# 2. Created roadmap.html in ticket folder

# 3. Created feature branch
git checkout -b feature/014-lidl-scraper

# 4. Made changes:
#    - Created data-quality-analysis.html
#    - (Will modify extract.py)

# 5. Commit changes
git add bespaarwijzer/scrapers/lidl/
git add tickets/014-lidl-scraper-improvement/
git commit -m "Add: Lidl data quality analysis"

# 6. After implementing improvements...
git add bespaarwijzer/scrapers/lidl/extract.py
git commit -m "Update: Lidl scraper with brand extraction"

# 7. Test with ./update.sh

# 8. Merge to main when happy
git checkout main
git merge feature/014-lidl-scraper
```

---

## Weekly Update Workflow

The weekly update (scraping new data) is different from feature development:

```bash
# Weekly update runs on main branch
git checkout main

# Run the update
cd /Users/yaronkra/Jarvis/bespaarwijzer
./update.sh

# After verifying data looks good, commit
git add bespaarwijzer/
git commit -m "Update: Week 51 supermarket data"
```

**What gets updated weekly:**
- `scrapers/*/folder_data.json` - Fresh scraped data
- `scrapers/*/archive/` - Weekly archives
- `pipeline/output/` - Aggregated data
- `app/products.json` - App-ready data
- `pipeline/price_history.db` - Historical prices

---

## Tips

1. **Check status often**: `git status` shows what's changed
2. **See changes before committing**: `git diff`
3. **View branch history**: `git log --oneline -10`
4. **Switch branches safely**: Commit or stash changes first
5. **Small commits**: Commit after each logical change, not all at once

---

## Current Branches

To see all branches:
```bash
git branch -a
```

To see which branch you're on:
```bash
git branch --show-current
```

---

*Last updated: 2025-12-15*
