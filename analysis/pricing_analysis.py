"""
analysis/pricing_analysis.py
-----------------------------
Pricing and competitive positioning analysis for luggage brands.
Computes:
  - Average price, discount, price range per brand
  - Premium vs budget positioning
  - Value-for-money score (sentiment adjusted by price)
  - Price band segmentation
  - Rating vs price correlation
  - Discount dependency analysis
"""

import pandas as pd
import numpy as np


PRICE_BANDS = {
    "Budget": (0, 3000),
    "Mid-Range": (3000, 6000),
    "Premium": (6000, 10000),
    "Luxury": (10000, float("inf")),
}


def classify_price_band(price: float) -> str:
    """Classify a price into Budget / Mid-Range / Premium / Luxury band."""
    for band, (lo, hi) in PRICE_BANDS.items():
        if lo <= price < hi:
            return band
    return "Luxury"


def brand_pricing_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute per-brand pricing metrics from product-level data.
    Input df should have columns: brand, price, list_price, discount, rating, review_count.
    Deduplicates to unique products first.
    """
    products = df.drop_duplicates(subset=["brand", "product_title"])

    summary = products.groupby("brand").agg(
        avg_price=("price", "mean"),
        min_price=("price", "min"),
        max_price=("price", "max"),
        price_std=("price", "std"),
        avg_list_price=("list_price", "mean"),
        avg_discount=("discount", "mean"),
        max_discount=("discount", "max"),
        avg_rating=("rating", "mean"),
        total_products=("product_title", "count"),
        total_review_count=("review_count", "sum"),
    ).reset_index()

    summary["price_range"] = summary["max_price"] - summary["min_price"]
    summary["avg_price"] = summary["avg_price"].round(0)
    summary["avg_discount"] = summary["avg_discount"].round(1)
    summary["avg_rating"] = summary["avg_rating"].round(2)
    summary["price_band"] = summary["avg_price"].apply(classify_price_band)

    return summary


def compute_value_score(pricing_df: pd.DataFrame, sentiment_df: pd.DataFrame) -> pd.DataFrame:
    """
    Value-for-money score = sentiment_score / normalized_price.
    Higher score = better value (good sentiment at lower price).
    
    Args:
        pricing_df: brand-level pricing summary
        sentiment_df: brand-level sentiment summary
    Returns:
        Merged DataFrame with value_score column
    """
    merged = pricing_df.merge(sentiment_df[["brand", "avg_sentiment"]], on="brand", how="left")

    # Normalize price (0=cheapest, 1=most expensive)
    min_p = merged["avg_price"].min()
    max_p = merged["avg_price"].max()
    merged["price_norm"] = (merged["avg_price"] - min_p) / (max_p - min_p + 1)

    # Value = sentiment / (0.5 + price_norm)  — avoid div-by-zero
    merged["value_score"] = (merged["avg_sentiment"] / (0.5 + merged["price_norm"])).round(3)

    # Normalize value_score to 0-100
    vs_min = merged["value_score"].min()
    vs_max = merged["value_score"].max()
    merged["value_score_pct"] = (
        (merged["value_score"] - vs_min) / (vs_max - vs_min + 0.001) * 100
    ).round(1)

    return merged


def discount_dependency_score(pricing_df: pd.DataFrame) -> pd.DataFrame:
    """
    Score how heavily each brand relies on discounting.
    High discount + lower organic rating → high dependency.
    """
    df = pricing_df.copy()
    max_disc = df["avg_discount"].max()
    df["discount_dependency"] = (df["avg_discount"] / (max_disc + 1) * 100).round(1)
    df["discount_flag"] = df["avg_discount"].apply(
        lambda d: "Heavy Discounter" if d >= 50 else ("Moderate" if d >= 35 else "Low Discounter")
    )
    return df


def rating_price_correlation(df: pd.DataFrame) -> float:
    """Compute Pearson correlation between price and rating across products."""
    products = df.drop_duplicates(subset=["brand", "product_title"])
    if len(products) < 3:
        return 0.0
    corr = products["price"].corr(products["rating"])
    return round(corr, 3)


def product_pricing_detail(df: pd.DataFrame) -> pd.DataFrame:
    """
    Product-level pricing detail table.
    Deduplicates and adds price band column.
    """
    products = df.drop_duplicates(subset=["brand", "product_title"]).copy()
    products["price_band"] = products["price"].apply(classify_price_band)
    products = products.sort_values(["brand", "price"])
    return products


def compute_all_pricing(df: pd.DataFrame, sentiment_df: pd.DataFrame) -> dict:
    """
    Run all pricing analyses and return dict of DataFrames.
    """
    pricing_summary = brand_pricing_summary(df)
    value_df = compute_value_score(pricing_summary, sentiment_df)
    disc_df = discount_dependency_score(pricing_summary)
    corr = rating_price_correlation(df)
    product_df = product_pricing_detail(df)

    return {
        "brand_pricing": pricing_summary,
        "value_analysis": value_df,
        "discount_analysis": disc_df,
        "rating_price_corr": corr,
        "product_detail": product_df,
    }