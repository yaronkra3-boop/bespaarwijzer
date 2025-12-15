# BespaarWijzer

Dutch supermarket deals aggregator and comparison app.

## Quick Start

```bash
# Run weekly update (scrape + aggregate + transform)
./update.sh

# Skip scraping, just process existing data
./update.sh --no-scrape

# Update and deploy to Vercel
./update.sh --deploy

# Test locally
cd app && python3 -m http.server 8080
open http://localhost:8080
```

## Folder Structure

```
bespaarwijzer/
├── update.sh              # One-command weekly update
├── scrapers/              # Web scrapers for each supermarket
│   ├── ah/               # Albert Heijn
│   ├── dirk/             # Dirk
│   ├── hoogvliet/        # Hoogvliet
│   ├── jumbo/            # Jumbo
│   ├── lidl/             # Lidl
│   └── data/             # Weekly scraped data
├── pipeline/              # Data processing
│   ├── aggregate.py      # Combine all scrapers
│   ├── transform.py      # Generate app-ready JSON
│   ├── price_tracker.py  # Historical price tracking
│   └── output/           # Generated files
├── app/                   # Deployable application
│   ├── index.html        # Main app
│   ├── products.json     # Product data (weekly)
│   └── folder-validity.json
├── docs/                  # Documentation
└── archive/               # Old versions & mockups
```

## Weekly Update Process

1. **Sunday/Monday**: New supermarket deals are released
2. **Run update.sh**: Scrapes all supermarkets, aggregates data, generates app JSON
3. **Deploy**: Either manually or with `--deploy` flag

See [docs/WEEKLY-UPDATE.md](docs/WEEKLY-UPDATE.md) for detailed instructions.

## Documentation

- [Weekly Update Guide](docs/WEEKLY-UPDATE.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [Architecture Overview](docs/ARCHITECTURE.md)

## Supermarkets Supported

| Supermarket | Products | Method |
|-------------|----------|--------|
| Albert Heijn | ~140 | API |
| Dirk | ~420 | Web scrape |
| Hoogvliet | ~650 | Web scrape |
| Jumbo | ~580 | API |
| Lidl | ~120 | API |

## Live App

- **URL**: [bespaarwijzer.vercel.app](https://bespaarwijzer.vercel.app)
- **Auto-deploys** when GitHub repo is updated
