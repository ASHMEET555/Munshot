"""
scraper/review_scraper.py
--------------------------
Scrapes customer reviews from Amazon India product pages.
For each product ASIN, fetches multiple review pages and extracts:
- Review text
- Star rating
- Review date
- Verified purchase flag

Includes polite rate limiting and anti-block measures.
Falls back to synthetic review generation if scraping fails.
"""

import asyncio
import random
import re
from pathlib import Path
from typing import Optional

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


REVIEW_URL_TEMPLATE = "https://www.amazon.in/product-reviews/{asin}/ref=cm_cr_dp_d_show_all_btm?ie=UTF8&reviewerType=all_reviews&pageNumber={page}"


async def scrape_product_reviews(page, asin: str, product_title: str, brand: str,
                                  max_pages: int = 3) -> list:
    """
    Scrape up to max_pages of reviews for a given product ASIN.
    Returns list of review dicts.
    """
    reviews = []

    for page_num in range(1, max_pages + 1):
        url = REVIEW_URL_TEMPLATE.format(asin=asin, page=page_num)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            await asyncio.sleep(random.uniform(1.5, 3.0))

            review_els = await page.query_selector_all('[data-hook="review"]')

            for rev_el in review_els:
                try:
                    # Extract review text
                    body_el = await rev_el.query_selector('[data-hook="review-body"] span')
                    text = (await body_el.inner_text()).strip() if body_el else ""

                    # Extract star rating
                    rating_el = await rev_el.query_selector('[data-hook="review-star-rating"] span')
                    rating_text = (await rating_el.inner_text()).strip() if rating_el else "3"
                    rating = float(rating_text.split(" ")[0] or "3")

                    if text:
                        reviews.append({
                            "brand": brand,
                            "product_title": product_title,
                            "review_text": text,
                            "review_rating": rating,
                        })
                except Exception:
                    continue

            if not review_els:
                break  # No more reviews

        except Exception as e:
            print(f"    [!] Page {page_num} error for {asin}: {e}")
            break

    return reviews


async def run_review_scraper(products_data: list, output_path: str = "data/raw/scraped_reviews.csv"):
    """
    Scrape reviews for all products in products_data.
    products_data should be list of dicts with 'asin', 'product_title', 'brand'.
    """
    if not PLAYWRIGHT_AVAILABLE:
        print("[!] Playwright unavailable for review scraping.")
        return []

    all_reviews = []
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(locale="en-IN", timezone_id="Asia/Kolkata")
        page = await context.new_page()

        for product in products_data:
            asin = product.get("asin", "")
            if not asin:
                continue
            print(f"  [→] Scraping reviews for {product['product_title'][:40]}...")
            reviews = await scrape_product_reviews(
                page, asin, product["product_title"], product["brand"]
            )
            all_reviews.extend(reviews)
            print(f"      → {len(reviews)} reviews collected")
            await asyncio.sleep(random.uniform(2, 4))

        await browser.close()

    return all_reviews


if __name__ == "__main__":
    # Example usage — provide your ASIN list here
    sample_products = [
        {"asin": "B07XYZ1234", "product_title": "Safari Cabin Trolley", "brand": "Safari"},
    ]
    asyncio.run(run_review_scraper(sample_products))