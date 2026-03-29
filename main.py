"""
main.py
--------
Entry point for the Luggage Intelligence Dashboard.
Handles:
  1. Dataset generation (if no data exists)
  2. Analysis pipeline execution
  3. Dashboard server startup

Usage:
  python main.py               → Run dashboard (generates data if needed)
  python main.py --generate    → Only generate dataset
  python main.py --analyze     → Only run analysis
  python main.py --scrape      → Run scraper (requires Playwright)
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


def generate_data():
    """Generate synthetic dataset if no real scraped data exists."""
    from generate_dataset import generate_dataset, save_dataset
    print("🔄 Generating synthetic dataset...")
    df = generate_dataset()
    save_dataset(df, "data/raw/amazon_luggage_raw.csv", "data/processed/amazon_luggage_processed.csv")
    print(f"✅ Dataset ready: {len(df)} records across {df['brand'].nunique()} brands")
    return df


def run_scraper():
    """Attempt to run live Amazon scraper."""
    print("🔄 Starting Amazon India scraper...")
    print("   Note: Amazon actively blocks scrapers. Will fall back to synthetic data if blocked.")
    from scraper.amazon_scraper import scrape_products
    scrape_products()


def run_analysis():
    """Run full analysis pipeline and print summary."""
    import pandas as pd
    from analysis.sentiment import analyze_reviews, brand_sentiment_summary, brand_aspect_sentiment
    from analysis.pricing_analysis import compute_all_pricing
    from analysis.competitor_analysis import build_comparison_matrix, identify_winners
    from agent.insight_generator import generate_all_insights

    data_path = ROOT / "data" / "raw" / "amazon_luggage_raw.csv"
    if not data_path.exists():
        generate_data()

    df = pd.read_csv(data_path)
    print(f"\n📊 Loaded {len(df)} rows, {df['brand'].nunique()} brands")

    df = analyze_reviews(df)
    sentiment_df = brand_sentiment_summary(df)
    aspect_df = brand_aspect_sentiment(df)
    pricing = compute_all_pricing(df, sentiment_df)
    matrix = build_comparison_matrix(pricing["brand_pricing"], sentiment_df, aspect_df)

    print("\n── Brand Sentiment Summary ──")
    print(sentiment_df[["brand", "avg_sentiment", "positive_pct", "negative_pct"]].to_string(index=False))

    print("\n── Brand Pricing Summary ──")
    print(pricing["brand_pricing"][["brand", "avg_price", "avg_discount", "avg_rating"]].to_string(index=False))

    insights = generate_all_insights(matrix)
    print(f"\n── {len(insights)} Agent Insights Generated ──")
    for ins in insights:
        print(f"  {ins['icon']} [{ins['severity'].upper()}] {ins['title']}")

    print("\n✅ Analysis complete.")


def run_dashboard():
    """Start the Flask dashboard server."""
    import os
    data_path = ROOT / "data" / "raw" / "amazon_luggage_raw.csv"
    if not data_path.exists():
        generate_data()

    print("\n🚀 Starting LuggageIQ Dashboard...")
    print("   → http://localhost:5000")
    print("   → Ctrl+C to stop\n")

    os.chdir(ROOT / "dashboard")
    from dashboard.app import app, get_data
    print("   → Pre-loading analysis pipeline (first load takes ~5s)...")
    get_data()
    print("   → Ready!\n")
    app.run(debug=False, host="0.0.0.0", port=5000)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LuggageIQ — Competitive Intelligence Dashboard")
    parser.add_argument("--generate", action="store_true", help="Generate synthetic dataset only")
    parser.add_argument("--scrape",   action="store_true", help="Run Amazon scraper")
    parser.add_argument("--analyze",  action="store_true", help="Run analysis pipeline and print summary")
    args = parser.parse_args()

    if args.generate:
        generate_data()
    elif args.scrape:
        run_scraper()
    elif args.analyze:
        run_analysis()
    else:
        run_dashboard()