"""
Price History Tracker

SQLite-based price archive for tracking supermarket prices over time.
Allows querying price history, finding lowest prices, and detecting good deals.

Usage:
    from price_tracker import PriceTracker

    tracker = PriceTracker()
    tracker.import_from_aggregated('aggregated_data.json')

    # Query price history
    history = tracker.get_price_history('Campina Halfvolle melk')
    lowest = tracker.get_lowest_price('Campina Halfvolle melk')
"""

import sqlite3
import json
from datetime import datetime, date
from pathlib import Path

BASE_PATH = Path("/Users/yaronkra/Jarvis/bespaarwijzer")
DB_PATH = BASE_PATH / "pipeline" / "price_history.db"


class PriceTracker:
    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # Access columns by name
        self._setup_db()

    def _setup_db(self):
        """Create tables and indexes if they don't exist."""
        cursor = self.conn.cursor()

        # Main prices table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL,
                product_id TEXT,
                supermarket TEXT NOT NULL,
                offer_price REAL,
                normal_price REAL,
                discount_text TEXT,
                category TEXT,
                week_number INTEGER NOT NULL,
                week_year INTEGER NOT NULL,
                week_date TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create indexes for fast queries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_product_name ON prices(product_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_supermarket ON prices(supermarket)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_week ON prices(week_year, week_number)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_product_supermarket ON prices(product_name, supermarket)')

        # Unique constraint to prevent duplicate entries for same product/supermarket/week
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_entry
            ON prices(product_id, supermarket, week_year, week_number)
            WHERE product_id IS NOT NULL
        ''')

        self.conn.commit()

    def add_price(self, product_name, supermarket, offer_price, normal_price=None,
                  product_id=None, discount_text=None, category=None, week_date=None):
        """Add a single price entry."""
        if week_date is None:
            week_date = date.today()
        elif isinstance(week_date, str):
            week_date = datetime.strptime(week_date, '%Y-%m-%d').date()

        week_number = week_date.isocalendar()[1]
        week_year = week_date.isocalendar()[0]

        try:
            self.conn.execute('''
                INSERT INTO prices (product_name, product_id, supermarket, offer_price,
                                   normal_price, discount_text, category, week_number,
                                   week_year, week_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (product_name, product_id, supermarket, offer_price, normal_price,
                  discount_text, category, week_number, week_year, week_date.isoformat()))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Duplicate entry - already have this product/supermarket/week
            return False

    def import_from_aggregated(self, json_path=None, week_date=None):
        """Import all products from aggregated_data.json into the archive."""
        if json_path is None:
            json_path = BASE_PATH / "aggregated_data.json"

        with open(json_path, 'r') as f:
            data = json.load(f)

        if week_date is None:
            # Extract week from aggregated_at timestamp
            aggregated_at = data.get('aggregated_at', datetime.now().isoformat())
            week_date = datetime.fromisoformat(aggregated_at).date()

        products = data.get('products', [])
        imported = 0
        skipped = 0

        for p in products:
            if p.get('offer_price'):  # Only import products with prices
                success = self.add_price(
                    product_name=p.get('name', ''),
                    supermarket=p.get('supermarket', ''),
                    offer_price=p.get('offer_price'),
                    normal_price=p.get('normal_price'),
                    product_id=p.get('id'),
                    discount_text=p.get('discount_text'),
                    category=p.get('category'),
                    week_date=week_date
                )
                if success:
                    imported += 1
                else:
                    skipped += 1

        return imported, skipped

    def get_price_history(self, product_name, limit=50):
        """Get price history for a product across all supermarkets and weeks."""
        cursor = self.conn.execute('''
            SELECT product_name, supermarket, offer_price, normal_price,
                   week_date, week_number, week_year
            FROM prices
            WHERE product_name LIKE ?
            ORDER BY week_year DESC, week_number DESC, supermarket
            LIMIT ?
        ''', (f'%{product_name}%', limit))
        return cursor.fetchall()

    def get_lowest_price(self, product_name):
        """Get the lowest price ever recorded for a product."""
        cursor = self.conn.execute('''
            SELECT product_name, supermarket, offer_price, week_date, week_number, week_year
            FROM prices
            WHERE product_name LIKE ? AND offer_price IS NOT NULL
            ORDER BY offer_price ASC
            LIMIT 1
        ''', (f'%{product_name}%',))
        return cursor.fetchone()

    def get_price_stats(self, product_name):
        """Get price statistics for a product."""
        cursor = self.conn.execute('''
            SELECT
                MIN(offer_price) as lowest_price,
                MAX(offer_price) as highest_price,
                AVG(offer_price) as avg_price,
                COUNT(*) as observation_count
            FROM prices
            WHERE product_name LIKE ? AND offer_price IS NOT NULL
        ''', (f'%{product_name}%',))
        return cursor.fetchone()

    def find_good_deals(self, threshold_percent=10):
        """Find products in current week that are at or near their historical low."""
        cursor = self.conn.execute('''
            WITH current_week AS (
                SELECT product_name, supermarket, offer_price, week_year, week_number
                FROM prices
                WHERE (week_year, week_number) = (
                    SELECT week_year, week_number FROM prices
                    ORDER BY week_year DESC, week_number DESC LIMIT 1
                )
            ),
            historical_lows AS (
                SELECT product_name, MIN(offer_price) as lowest_price
                FROM prices
                WHERE offer_price IS NOT NULL
                GROUP BY product_name
            )
            SELECT
                c.product_name,
                c.supermarket,
                c.offer_price as current_price,
                h.lowest_price as historical_low,
                ROUND((c.offer_price - h.lowest_price) / h.lowest_price * 100, 1) as percent_above_low
            FROM current_week c
            JOIN historical_lows h ON c.product_name = h.product_name
            WHERE c.offer_price <= h.lowest_price * (1 + ? / 100.0)
            ORDER BY percent_above_low ASC
        ''', (threshold_percent,))
        return cursor.fetchall()

    def get_all_products(self):
        """Get list of all unique products in the database."""
        cursor = self.conn.execute('''
            SELECT DISTINCT product_name, COUNT(*) as observation_count
            FROM prices
            GROUP BY product_name
            ORDER BY product_name
        ''')
        return cursor.fetchall()

    def get_weeks(self):
        """Get list of all weeks in the database."""
        cursor = self.conn.execute('''
            SELECT DISTINCT week_year, week_number, week_date, COUNT(*) as product_count
            FROM prices
            GROUP BY week_year, week_number
            ORDER BY week_year DESC, week_number DESC
        ''')
        return cursor.fetchall()

    def get_summary(self):
        """Get a summary of the database contents."""
        cursor = self.conn.cursor()

        # Total records
        cursor.execute('SELECT COUNT(*) FROM prices')
        total_records = cursor.fetchone()[0]

        # Unique products
        cursor.execute('SELECT COUNT(DISTINCT product_name) FROM prices')
        unique_products = cursor.fetchone()[0]

        # Number of weeks
        cursor.execute('SELECT COUNT(DISTINCT week_year || "-" || week_number) FROM prices')
        total_weeks = cursor.fetchone()[0]

        # By supermarket
        cursor.execute('''
            SELECT supermarket, COUNT(*) as count
            FROM prices
            GROUP BY supermarket
            ORDER BY count DESC
        ''')
        by_supermarket = cursor.fetchall()

        return {
            'total_records': total_records,
            'unique_products': unique_products,
            'total_weeks': total_weeks,
            'by_supermarket': [(row[0], row[1]) for row in by_supermarket]
        }

    def close(self):
        """Close database connection."""
        self.conn.close()


def main():
    """Import current aggregated data and show summary."""
    print("=" * 60)
    print("Price History Tracker")
    print("=" * 60)

    tracker = PriceTracker()

    # Import from aggregated_data.json
    print("\nImporting from aggregated_data.json...")
    imported, skipped = tracker.import_from_aggregated()
    print(f"  Imported: {imported} products")
    print(f"  Skipped (duplicates or no price): {skipped}")

    # Show summary
    print("\n" + "=" * 60)
    print("DATABASE SUMMARY")
    print("=" * 60)

    summary = tracker.get_summary()
    print(f"\nTotal price records: {summary['total_records']}")
    print(f"Unique products: {summary['unique_products']}")
    print(f"Weeks of data: {summary['total_weeks']}")

    print("\nBy supermarket:")
    for sm, count in summary['by_supermarket']:
        print(f"  {sm}: {count} records")

    # Show weeks
    print("\nWeeks in database:")
    for week in tracker.get_weeks():
        print(f"  Week {week['week_number']}/{week['week_year']}: {week['product_count']} products")

    # Show sample query
    print("\n" + "=" * 60)
    print("SAMPLE QUERY: Price history for 'melk'")
    print("=" * 60)

    history = tracker.get_price_history('melk', limit=10)
    if history:
        print(f"\n{'Product':<35} {'Price':>7} {'Supermarket':<12} {'Week'}")
        print("-" * 70)
        for row in history:
            print(f"{row['product_name'][:33]:<35} €{row['offer_price']:>5.2f} {row['supermarket']:<12} {row['week_number']}/{row['week_year']}")
    else:
        print("No records found for 'melk'")

    tracker.close()
    print(f"\nDatabase saved to: {DB_PATH}")


if __name__ == "__main__":
    main()
