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


def compute_value_score(
    pricing_df: pd.DataFrame,
    sentiment_df: pd.DataFrame,
    aspect_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Value-for-money score using a weighted mix of brand quality + price fairness.
    Higher score = better value.
    
    Args:
        pricing_df: brand-level pricing summary
        sentiment_df: brand-level sentiment summary
    Returns:
        Merged DataFrame with value_score and value_score_pct columns
    """
    merged = pricing_df.merge(sentiment_df[["brand", "avg_sentiment"]], on="brand", how="left")

    # Pull in durability signal if available (from aspect sentiment pipeline).
    if aspect_df is not None and "durability" in aspect_df.columns:
        merged = merged.merge(aspect_df[["brand", "durability"]], on="brand", how="left")
    elif "durability" not in merged.columns:
        merged["durability"] = merged["avg_sentiment"]

    # Normalize price (0=cheapest, 1=most expensive)
    min_p = merged["avg_price"].min()
    max_p = merged["avg_price"].max()
    merged["price_norm"] = (merged["avg_price"] - min_p) / (max_p - min_p + 1)

    # Softer price penalty: 1 / (0.7 + sqrt(price_norm))
    merged["soft_price_component"] = 1 / (0.7 + np.sqrt(merged["price_norm"].clip(lower=0)))
    p_min = merged["soft_price_component"].min()
    p_max = merged["soft_price_component"].max()
    merged["price_score"] = (merged["soft_price_component"] - p_min) / (p_max - p_min + 1e-9)

    # Component scores normalized to 0-1.
    merged["sentiment_score"] = merged["avg_sentiment"].clip(0, 1)
    merged["rating_score"] = ((merged["avg_rating"] - 1) / 4).clip(0, 1)
    merged["durability_score"] = merged["durability"].fillna(merged["sentiment_score"]).clip(0, 1)

    # Weighted value mix: sentiment + rating + durability + price.
    weights = {
        "sentiment_score": 0.35,
        "rating_score": 0.25,
        "durability_score": 0.20,
        "price_score": 0.20,
    }
    merged["value_score"] = (
        merged["sentiment_score"] * weights["sentiment_score"]
        + merged["rating_score"] * weights["rating_score"]
        + merged["durability_score"] * weights["durability_score"]
        + merged["price_score"] * weights["price_score"]
    ).round(3)

    # Percentile rank to 0-100 (more stable than strict min-max on small brand sets).
    merged["value_score_pct"] = (merged["value_score"].rank(pct=True, method="average") * 100).round(1)

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


def compute_all_pricing(
    df: pd.DataFrame,
    sentiment_df: pd.DataFrame,
    aspect_df: pd.DataFrame | None = None,
) -> dict:
    """
    Run all pricing analyses and return dict of DataFrames.
    """
    pricing_summary = brand_pricing_summary(df)
    value_df = compute_value_score(pricing_summary, sentiment_df, aspect_df)
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