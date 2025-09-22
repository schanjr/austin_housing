import argparse
import sys
from pathlib import Path
import logging

ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.append(str(ROOT_DIR))

from scripts.scrapers.zillow_scraper import ZillowScraper
from scripts.scrapers.redfin_scraper import RedfinScraper

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def scrape_zillow(max_rent: int = 2000, max_pages: int = 3):
    """Zillow scraper is currently disabled due to 403 blocking"""
    logger.warning("⚠️  Zillow scraper is disabled - site blocks all requests with 403 errors")
    logger.info("💡 Use 'redfin' command instead for working rental data scraping")
    return False

def scrape_redfin(max_rent: int = 5000, max_pages: int = 10):
    """Run Redfin scraper (WORKING - recommended)"""
    logger.info("🚀 Starting Redfin scraping with working scraper...")
    scraper = RedfinScraper()
    scraper.scrape_all_rentals(max_rent=max_rent, max_pages=max_pages)
    logger.info("✅ Redfin scraping completed successfully!")
    return True

def scrape_all(max_rent: int = 5000, max_pages: int = 10):
    """Run working scrapers (currently only Redfin works)"""
    logger.info("🚀 Starting rental data scraping...")
    
    # Zillow is currently blocked - skip it
    logger.warning("⚠️  Skipping Zillow scraper - site blocks requests with 403 errors")
    
    # Run working Redfin scraper
    success = False
    try:
        success = scrape_redfin(max_rent, max_pages)
    except Exception as e:
        logger.error(f"❌ Redfin scraping failed: {e}")
    
    if success:
        logger.info("✅ Scraping completed successfully!")
    else:
        logger.error("❌ Scraping failed - check logs for details")
    
    return success

def main():
    parser = argparse.ArgumentParser(
        description='Austin Housing Scrapers - Redfin Working, Zillow Blocked',
        epilog='💡 Recommended: Use "redfin" or "all" commands for working data scraping'
    )
    parser.add_argument('command', choices=['zillow', 'redfin', 'all'], 
                       help='Which scraper to run (zillow=disabled, redfin=working, all=redfin only)')
    parser.add_argument('--max-rent', type=int, default=5000,
                       help='Maximum rent to scrape (default: 5000)')
    parser.add_argument('--max-pages', type=int, default=10,
                       help='Maximum pages to scrape (default: 10)')
    
    args = parser.parse_args()
    
    if args.command == 'zillow':
        scrape_zillow(args.max_rent, args.max_pages)
    elif args.command == 'redfin':
        scrape_redfin(args.max_rent, args.max_pages)
    elif args.command == 'all':
        scrape_all(args.max_rent, args.max_pages)

if __name__ == "__main__":
    main()
