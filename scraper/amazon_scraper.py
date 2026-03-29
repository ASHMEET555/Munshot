"""
scraper/amazon_scraper.py
--------------------------
Amazon India product listing scraper using Playwright.
Scrapes product titles, prices, list prices, discounts, ratings, and review counts
for specified luggage brands.

Usage:
    python scraper/amazon_scraper.py

Note: Amazon actively blocks scraping. This scraper includes:
- Random delays between requests
- Rotating user agents
- Stealth mode headers
- Fallback to dataset generator if blocked
"""

import asyncio
import random
import time
import csv
import json
from pathlib import Path
from typing import Optional

try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
]

SEARCH_QUERIES = {
    "Safari": "Safari luggage trolley bag Amazon India",
    "Skybags": "Skybags trolley bag suitcase Amazon India",
    "American Tourister": "American Tourister trolley bag Amazon India",
    "VIP": "VIP luggage bag trolley Amazon India",
    "Aristocrat": "Aristocrat luggage trolley bag Amazon India",
    "Nasher Miles": "Nasher Miles hard luggage trolley Amazon India",
}

AMAZON_BASE = "https://www.amazon.in"


async def scrape_brand_products(page, brand: str, search_query: str, max_products: int = 12) -> list:
    """
    Scrape product listings for a single brand from Amazon India search results.
    Returns list of product dicts with title, price, rating, review_count.
    """
    search_url = f"{AMAZON_BASE}/s?k={search_query.replace(' ', '+')}"
    products = []

    try:
        await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(random.uniform(2, 4))  # Polite delay

        # Extract product cards
        cards = await page.query_selector_all('[data-component-type="s-search-result"]')

        for card in cards[:max_products]:
            try:
                # Title
                title_el = await card.query_selector("h2 a span")
                title = (await title_el.inner_text()).strip() if title_el else ""

                # Current price
                price_el = await card.query_selector(".a-price .a-offscreen")
                price_text = (await price_el.inner_text()).strip() if price_el else "0"

                # Strike-through price (list price)
                list_price_el = await card.query_selector(".a-price.a-text-price .a-offscreen")
                list_price_text = (await list_price_el.inner_text()).strip() if list_price_el else price_text

                # Rating
                rating_el = await card.query_selector(".a-icon-alt")
                rating_text = (await rating_el.inner_text()).strip() if rating_el else "0"

                # Review count
                review_el = await card.query_selector('[aria-label*="ratings"]')
                review_text = (await review_el.get_attribute("aria-label") or "0") if review_el else "0"

                # Parse values
                price = float(price_text.replace("₹", "").replace(",", "").strip() or 0)
                list_price = float(list_price_text.replace("₹", "").replace(",", "").strip() or price)
                rating = float(rating_text.split(" ")[0] if rating_text else 0)
                review_count = int("".join(filter(str.isdigit, review_text)) or 0)
                discount = round((list_price - price) / list_price * 100) if list_price > price else 0

                if title and price > 0:
                    products.append({
                        "brand": brand,
                        "product_title": title,
                        "price": price,
                        "list_price": list_price,
                        "discount": discount,
                        "rating": rating,
                        "review_count": review_count,
                    })
            except Exception:
                continue

        print(f"  [✓] {brand}: {len(products)} products scraped")

    except PlaywrightTimeout:
        print(f"  [!] Timeout for {brand} — Amazon may be blocking. Using synthetic data.")
    except Exception as e:
        print(f"  [!] Error scraping {brand}: {e}")

    return products


async def run_scraper(output_path: str = "data/raw/scraped_products.csv"):
    """
    Main scraper coroutine. Launches Playwright browser and scrapes all brands.
    Falls back gracefully to synthetic dataset if blocked.
    """
    if not PLAYWRIGHT_AVAILABLE:
        print("[!] Playwright not installed. Run: pip install playwright && playwright install chromium")
        print("[→] Falling back to synthetic dataset generator...")
        _fallback_to_synthetic(output_path)
        return

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    all_products = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1280, "height": 800},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
        )
        page = await context.new_page()

        # Override navigator.webdriver to avoid detection
        await page.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")

        for brand, query in SEARCH_QUERIES.items():
            print(f"[→] Scraping {brand}...")
            products = await scrape_brand_products(page, brand, query)
            all_products.extend(products)
            await asyncio.sleep(random.uniform(3, 6))  # Rate limiting

        await browser.close()

    if all_products:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=all_products[0].keys())
            writer.writeheader()
            writer.writerows(all_products)
        print(f"\n[✓] Saved {len(all_products)} products to {output_path}")
    else:
        print("[!] No products scraped. Falling back to synthetic data.")
        _fallback_to_synthetic(output_path)


def _fallback_to_synthetic(output_path: str):
    """Use synthetic data generator as fallback."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from generate_dataset import generate_dataset, save_dataset
    df = generate_dataset()
    save_dataset(df, output_path, output_path.replace("raw", "processed"))


def scrape_products():
    """Entry point for synchronous usage."""
    asyncio.run(run_scraper())


if __name__ == "__main__":
    scrape_products()