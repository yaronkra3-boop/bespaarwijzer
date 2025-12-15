#!/bin/bash
#
# BespaarWijzer Weekly Update Script
# Run this every week when new supermarket deals are released
#
# Features:
#   - Data validation (each scraper checks minimum product count)
#   - Email alerts on failure
#   - Backup of previous deploy before overwriting
#
# Usage:
#   ./update.sh              # Full update (scrape + aggregate + transform)
#   ./update.sh --no-scrape  # Skip scraping, just aggregate and transform
#   ./update.sh --deploy     # Also push to GitHub after update
#

# Exit on error - but we'll handle errors manually for email alerts
set +e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
BASE_PATH="/Users/yaronkra/Jarvis/bespaarwijzer"
SCRAPERS_PATH="$BASE_PATH/scrapers"
PIPELINE_PATH="$BASE_PATH/pipeline"
APP_PATH="$BASE_PATH/app"
LOG_FILE="$BASE_PATH/logs/update_$(date +%Y%m%d_%H%M%S).log"
ALERT_EMAIL="yaronkra3@gmail.com"

# Create logs directory if needed
mkdir -p "$BASE_PATH/logs"

# Track errors
ERRORS=()
HAD_ERROR=false

# Function to send email alert
send_alert() {
    local subject="$1"
    local body="$2"

    echo -e "${RED}Sending alert email to $ALERT_EMAIL${NC}"

    # Use macOS mail command (or osascript for Mail.app)
    # This uses the built-in mail command which works with configured mail accounts
    echo "$body" | mail -s "$subject" "$ALERT_EMAIL" 2>/dev/null || \
    osascript -e "tell application \"Mail\"
        set newMessage to make new outgoing message with properties {subject:\"$subject\", content:\"$body\", visible:false}
        tell newMessage
            make new to recipient at end of to recipients with properties {address:\"$ALERT_EMAIL\"}
            send
        end tell
    end tell" 2>/dev/null || \
    echo -e "${YELLOW}Warning: Could not send email. Check mail configuration.${NC}"
}

# Function to log and print
log() {
    echo -e "$1"
    echo -e "$1" | sed 's/\x1b\[[0-9;]*m//g' >> "$LOG_FILE"
}

# Parse arguments
SKIP_SCRAPE=false
DEPLOY=false

for arg in "$@"; do
    case $arg in
        --no-scrape)
            SKIP_SCRAPE=true
            shift
            ;;
        --deploy)
            DEPLOY=true
            shift
            ;;
    esac
done

log ""
log "${BLUE}╔══════════════════════════════════════════════════╗${NC}"
log "${BLUE}║           BespaarWijzer Weekly Update            ║${NC}"
log "${BLUE}╚══════════════════════════════════════════════════╝${NC}"
log ""
log "Started at: $(date)"
log "Log file: $LOG_FILE"
log ""

# Step 1: Run scrapers (optional)
if [ "$SKIP_SCRAPE" = false ]; then
    log "${YELLOW}Step 1: Running scrapers...${NC}"
    log ""

    for store in ah dirk hoogvliet jumbo lidl; do
        log "  ${BLUE}→${NC} Scraping $store..."
        cd "$SCRAPERS_PATH/$store"

        # Run scraper and capture output
        output=$(python3 extract.py 2>&1)
        exit_code=$?

        echo "$output" | sed 's/^/    /' | tee -a "$LOG_FILE"

        if [ $exit_code -ne 0 ]; then
            log "  ${RED}✗ $store scraper FAILED${NC}"
            ERRORS+=("$store scraper failed: $(echo "$output" | grep -i 'error\|failed\|exception' | head -1)")
            HAD_ERROR=true
        else
            log "  ${GREEN}✓ $store completed${NC}"
        fi
        log ""
    done

    if [ "$HAD_ERROR" = true ]; then
        log "${RED}Warning: Some scrapers failed. Continuing with available data...${NC}"
    else
        log "${GREEN}  ✓ All scrapers completed successfully${NC}"
    fi
    log ""
else
    log "${YELLOW}Step 1: Skipping scrapers (--no-scrape)${NC}"
    log ""
fi

# Step 2: Run aggregator
log "${YELLOW}Step 2: Running aggregator...${NC}"
cd "$PIPELINE_PATH"
output=$(python3 aggregate.py 2>&1)
exit_code=$?
echo "$output" | sed 's/^/    /' | tee -a "$LOG_FILE"

if [ $exit_code -ne 0 ]; then
    log "${RED}  ✗ Aggregation FAILED${NC}"
    ERRORS+=("Aggregation failed")
    HAD_ERROR=true
else
    log "${GREEN}  ✓ Aggregation complete${NC}"
fi
log ""

# Step 3: Run transformer (includes enrichment with BespaarWijzer categories)
log "${YELLOW}Step 3: Running transformer (with enrichment)...${NC}"
output=$(python3 transform.py 2>&1)
exit_code=$?
echo "$output" | sed 's/^/    /' | tee -a "$LOG_FILE"

if [ $exit_code -ne 0 ]; then
    log "${RED}  ✗ Transform FAILED${NC}"
    ERRORS+=("Transform failed")
    HAD_ERROR=true
else
    log "${GREEN}  ✓ Transform complete${NC}"
fi
log ""

# Step 4: Run category verification
log "${YELLOW}Step 4: Running category verification...${NC}"
output=$(python3 verify_categories.py 2>&1)
exit_code=$?
echo "$output" | sed 's/^/    /' | tee -a "$LOG_FILE"

if [ $exit_code -ne 0 ]; then
    log "${RED}  ✗ Verification FAILED${NC}"
    ERRORS+=("Verification failed")
    HAD_ERROR=true
else
    log "${GREEN}  ✓ Verification complete${NC}"
fi
log ""

# Show results
log "${YELLOW}Results:${NC}"
if [ -f "$APP_PATH/products.json" ]; then
    log "  ${BLUE}→${NC} products.json: $(du -h "$APP_PATH/products.json" | cut -f1)"
fi
if [ -f "$APP_PATH/folder-validity.json" ]; then
    log "  ${BLUE}→${NC} folder-validity.json: $(du -h "$APP_PATH/folder-validity.json" | cut -f1)"
fi
log ""

# Step 5: Deploy (optional)
if [ "$DEPLOY" = true ]; then
    log "${YELLOW}Step 5: Deploying to GitHub...${NC}"

    DEPLOY_PATH="$HOME/Desktop/bespaarwijzer"
    BACKUP_PATH="$BASE_PATH/backups"

    # Create backup directory
    mkdir -p "$BACKUP_PATH"

    if [ -d "$DEPLOY_PATH" ]; then
        # BACKUP: Save previous deploy files
        log "  ${BLUE}→${NC} Creating backup of previous deploy..."
        BACKUP_TIMESTAMP=$(date +%Y%m%d_%H%M%S)

        if [ -f "$DEPLOY_PATH/products.json" ]; then
            cp "$DEPLOY_PATH/products.json" "$BACKUP_PATH/products_${BACKUP_TIMESTAMP}.json"
            log "    Backed up: products_${BACKUP_TIMESTAMP}.json"
        fi
        if [ -f "$DEPLOY_PATH/folder-validity.json" ]; then
            cp "$DEPLOY_PATH/folder-validity.json" "$BACKUP_PATH/folder-validity_${BACKUP_TIMESTAMP}.json"
            log "    Backed up: folder-validity_${BACKUP_TIMESTAMP}.json"
        fi

        # Keep only last 5 backups
        cd "$BACKUP_PATH"
        ls -t products_*.json 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null
        ls -t folder-validity_*.json 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null
        log "    (Keeping last 5 backups)"

        # Copy new files
        log "  ${BLUE}→${NC} Copying new files..."
        cp "$APP_PATH/products.json" "$DEPLOY_PATH/"
        cp "$APP_PATH/folder-validity.json" "$DEPLOY_PATH/"

        # Git push
        log "  ${BLUE}→${NC} Pushing to GitHub..."
        cd "$DEPLOY_PATH"
        git add .
        git commit -m "Weekly update - $(date +%Y-%m-%d)" 2>&1 | sed 's/^/    /'

        if git push 2>&1 | sed 's/^/    /'; then
            log "${GREEN}  ✓ Deployed to GitHub (Vercel will auto-deploy)${NC}"
        else
            log "${RED}  ✗ Git push FAILED${NC}"
            ERRORS+=("Git push failed")
            HAD_ERROR=true
        fi
    else
        log "${RED}  ✗ Deploy folder not found: $DEPLOY_PATH${NC}"
        log "    Run the Vercel setup first (see docs/DEPLOYMENT.md)"
        ERRORS+=("Deploy folder not found")
        HAD_ERROR=true
    fi
    log ""
fi

# Final status and email alert
log ""
if [ "$HAD_ERROR" = true ]; then
    log "${RED}╔══════════════════════════════════════════════════╗${NC}"
    log "${RED}║          Update Completed with ERRORS            ║${NC}"
    log "${RED}╚══════════════════════════════════════════════════╝${NC}"
    log ""
    log "${RED}Errors encountered:${NC}"
    for error in "${ERRORS[@]}"; do
        log "  - $error"
    done
    log ""

    # Send email alert
    error_list=""
    for error in "${ERRORS[@]}"; do
        error_list="$error_list\n- $error"
    done

    send_alert "BespaarWijzer Pipeline FAILED - $(date +%Y-%m-%d)" \
"BespaarWijzer weekly update encountered errors.

Time: $(date)

Errors:
$error_list

Log file: $LOG_FILE

Please check the pipeline and fix any issues.

---
This is an automated message from BespaarWijzer update.sh"
else
    log "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
    log "${GREEN}║                 Update Complete!                 ║${NC}"
    log "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
fi

log ""
log "Finished at: $(date)"
log ""
log "To test locally:"
log "  cd $APP_PATH && python3 -m http.server 8080"
log "  open http://localhost:8080"
log ""

# Return appropriate exit code
if [ "$HAD_ERROR" = true ]; then
    exit 1
else
    exit 0
fi
