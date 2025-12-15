# Weekly Update Guide

## When to Update

Dutch supermarkets release new folders weekly:
- **Sunday/Monday**: New deals become active
- **Update frequency**: Once per week is sufficient

## Quick Update (One Command)

```bash
cd /Users/yaronkra/Jarvis/bespaarwijzer
./update.sh
```

This runs all steps automatically:
1. Scrapes all 5 supermarkets
2. Aggregates into unified dataset
3. Transforms to app-ready JSON
4. Shows results

## Update Options

```bash
# Full update (scrape + aggregate + transform)
./update.sh

# Skip scraping (use existing data)
./update.sh --no-scrape

# Update and deploy to Vercel
./update.sh --deploy
```

## Manual Steps (if needed)

### Step 1: Run Scrapers

```bash
cd /Users/yaronkra/Jarvis/bespaarwijzer/scrapers/ah && python3 extract.py
cd /Users/yaronkra/Jarvis/bespaarwijzer/scrapers/dirk && python3 extract.py
cd /Users/yaronkra/Jarvis/bespaarwijzer/scrapers/hoogvliet && python3 extract.py
cd /Users/yaronkra/Jarvis/bespaarwijzer/scrapers/jumbo && python3 extract.py
cd /Users/yaronkra/Jarvis/bespaarwijzer/scrapers/lidl && python3 extract.py
```

### Step 2: Aggregate

```bash
cd /Users/yaronkra/Jarvis/bespaarwijzer/pipeline
python3 aggregate.py
```

Output: `pipeline/output/aggregated_data.json`

### Step 3: Transform

```bash
python3 transform.py
```

Output:
- `app/products.json` (~1.1 MB)
- `app/folder-validity.json` (~200 B)

### Step 4: Test Locally

```bash
cd /Users/yaronkra/Jarvis/bespaarwijzer/app
python3 -m http.server 8080
open http://localhost:8080
```

### Step 5: Deploy (Optional)

```bash
# Copy to deployment folder
cp app/products.json ~/Desktop/bespaarwijzer/
cp app/folder-validity.json ~/Desktop/bespaarwijzer/

# Push to GitHub (Vercel auto-deploys)
cd ~/Desktop/bespaarwijzer
git add . && git commit -m "Weekly update" && git push
```

## Troubleshooting

### Scraper fails
- Check if supermarket website changed
- See scraper-specific GUIDE.md in each folder

### Products show as empty
- Check `aggregated_data.json` was generated
- Check `products.json` exists in app folder

### App won't load data
- Must use HTTP server (not file://)
- Check browser console for errors

## Checking Product Counts

```bash
cd /Users/yaronkra/Jarvis/bespaarwijzer/pipeline
python3 -c "
import json
data = json.load(open('output/aggregated_data.json'))
for store, count in data['insights']['by_supermarket'].items():
    print(f'{store}: {count}')
print(f'Total: {data[\"total_products\"]}')
"
```
