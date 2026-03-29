"""
analysis/competitor_analysis.py
--------------------------------
Cross-brand competitive analysis.
Builds a unified comparison matrix and benchmarks all brands
across price, sentiment, discount, rating, and review volume.
Identifies winners and laggards in each dimension.
"""

import pandas as pd
import numpy as np


def build_comparison_matrix(pricing_df: pd.DataFrame, sentiment_df: pd.DataFrame,
                             aspect_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge all brand-level analyses into one comparison matrix.
    Each row = one brand; columns = all KPIs.
    """
    matrix = pricing_df.merge(sentiment_df, on="brand", how="outer")
    matrix = matrix.merge(aspect_df, on="brand", how="left")
    return matrix


def rank_brands(matrix: pd.DataFrame) -> pd.DataFrame:
    """
    Add rank columns for each KPI (1 = best).
    Ranking directions:
      - avg_sentiment: higher = better
      - avg_price: lower = better (more accessible)
      - avg_discount: higher = heavier discounter (neutral)
      - avg_rating: higher = better
      - value_score_pct: higher = better
    """
    df = matrix.copy()
    rank_map = {
        "avg_sentiment": False,   # ascending=False → highest ranked 1
        "avg_rating": False,
        "value_score_pct": False,
        "avg_price": True,        # ascending=True → cheapest ranked 1
        "avg_discount": False,
        "total_review_count": False,
    }
    for col, ascending in rank_map.items():
        if col in df.columns:
            df[f"rank_{col}"] = df[col].rank(ascending=ascending, method="min").astype(int)
    return df


def identify_winners(matrix: pd.DataFrame) -> dict:
    """
    Identify the top brand in each competitive dimension.
    Returns dict mapping dimension → brand name.
    """
    winners = {}
    if "avg_sentiment" in matrix.columns:
        winners["best_sentiment"] = matrix.loc[matrix["avg_sentiment"].idxmax(), "brand"]
    if "avg_rating" in matrix.columns:
        winners["best_rating"] = matrix.loc[matrix["avg_rating"].idxmax(), "brand"]
    if "avg_price" in matrix.columns:
        winners["most_affordable"] = matrix.loc[matrix["avg_price"].idxmin(), "brand"]
        winners["most_premium"] = matrix.loc[matrix["avg_price"].idxmax(), "brand"]
    if "avg_discount" in matrix.columns:
        winners["heaviest_discounter"] = matrix.loc[matrix["avg_discount"].idxmax(), "brand"]
    if "value_score_pct" in matrix.columns:
        winners["best_value"] = matrix.loc[matrix["value_score_pct"].idxmax(), "brand"]
        winners["worst_value"] = matrix.loc[matrix["value_score_pct"].idxmin(), "brand"]
    if "total_review_count" in matrix.columns:
        winners["most_reviews"] = matrix.loc[matrix["total_review_count"].idxmax(), "brand"]

    # Aspect winners
    for aspect in ["wheels", "handle", "material", "zipper", "size", "durability"]:
        if aspect in matrix.columns:
            winners[f"best_{aspect}"] = matrix.loc[matrix[aspect].idxmax(), "brand"]

    return winners


def brand_scorecard(matrix: pd.DataFrame) -> pd.DataFrame:
    """
    Build a normalized 0-100 scorecard for each brand across all KPIs.
    Useful for radar charts.
    """
    df = matrix.copy()
    kpis = {
        "sentiment": "avg_sentiment",
        "rating": "avg_rating",
        "value": "value_score_pct",
        "affordability": "avg_price",    # Will invert
        "review_volume": "total_review_count",
        "durability": "durability",
        "wheel_quality": "wheels",
        "handle_quality": "handle",
    }

    scorecard_rows = []
    for _, row in df.iterrows():
        scores = {"brand": row["brand"]}
        for label, col in kpis.items():
            if col not in df.columns:
                scores[label] = 50
                continue
            col_min = df[col].min()
            col_max = df[col].max()
            val = row[col] if col in row else 50
            if col_max == col_min:
                norm = 50
            else:
                norm = (val - col_min) / (col_max - col_min) * 100
                if label == "affordability":
                    norm = 100 - norm  # Invert: cheaper = higher score
            scores[label] = round(norm, 1)
        scorecard_rows.append(scores)

    return pd.DataFrame(scorecard_rows)


def get_brand_pros_cons(df: pd.DataFrame, brand: str, themes: dict) -> dict:
    """
    Return pros and cons for a specific brand using themes and aspect scores.
    """
    brand_row = df[df["brand"] == brand]
    if brand_row.empty:
        return {"pros": [], "cons": []}

    row = brand_row.iloc[0]

    # Aspect-based pros/cons
    aspect_cols = ["wheels", "handle", "material", "zipper", "size", "durability"]
    aspects = {a: float(row.get(a, 0.5)) for a in aspect_cols if a in row}

    pros = [f"Strong {a} quality" for a, s in sorted(aspects.items(), key=lambda x: -x[1])
            if s >= 0.70][:3]
    cons = [f"Weak {a} quality" for a, s in sorted(aspects.items(), key=lambda x: x[1])
            if s < 0.50][:3]

    # Add theme-based pros/cons
    brand_themes = themes.get(brand, {})
    if brand_themes.get("positive_themes"):
        pros += [f"Customers praise: {', '.join(brand_themes['positive_themes'][:2])}"]
    if brand_themes.get("negative_themes"):
        cons += [f"Common complaints: {', '.join(brand_themes['negative_themes'][:2])}"]

    return {"pros": pros[:4], "cons": cons[:4]}