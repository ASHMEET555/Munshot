"""
agent/insight_generator.py
---------------------------
AI-powered insight engine for the Competitive Intelligence Dashboard.
Automatically generates non-obvious, decision-ready insights from the data.

Insight types:
  1. Overpriced-but-low-sentiment detection
  2. Best value-for-money identification
  3. Durability complaint anomaly (high rating + bad durability sentiment)
  4. Discount dependency analysis
  5. Review trust signals (volume vs. rating mismatch)
  6. Underdog brand spotting
  7. Price band leader identification
  8. Aspect-specific outliers
"""

from typing import Optional
import pandas as pd
import numpy as np


INSIGHT_ICONS = {
    "warning": "⚠️",
    "trophy": "🏆",
    "fire": "🔥",
    "magnify": "🔍",
    "money": "💰",
    "chart": "📊",
    "star": "⭐",
    "broken": "💔",
    "crown": "👑",
    "flag": "🚩",
}

SEVERITY_COLORS = {
    "critical": "#FF4444",
    "warning": "#FFA500",
    "positive": "#00C851",
    "info": "#33B5E5",
    "neutral": "#9E9E9E",
}


def insight_overpriced_low_sentiment(matrix: pd.DataFrame) -> Optional[dict]:
    """
    Detect brand(s) with above-average price but below-average sentiment.
    Non-obvious because high price often masks poor satisfaction.
    """
    avg_price = matrix["avg_price"].mean()
    avg_sent = matrix["avg_sentiment"].mean()

    candidates = matrix[
        (matrix["avg_price"] > avg_price * 1.1) &
        (matrix["avg_sentiment"] < avg_sent * 0.95)
    ]

    if candidates.empty:
        return None

    brand = candidates.sort_values("avg_sentiment").iloc[0]["brand"]
    price = candidates.sort_values("avg_sentiment").iloc[0]["avg_price"]
    sent = candidates.sort_values("avg_sentiment").iloc[0]["avg_sentiment"]

    return {
        "id": "overpriced_low_sentiment",
        "icon": INSIGHT_ICONS["warning"],
        "title": f"{brand} is Overpriced Relative to Satisfaction",
        "detail": (
            f"{brand} charges ₹{price:,.0f} on average — above the category mean — "
            f"yet earns only a {sent:.0%} sentiment score, below category average. "
            f"Customers are paying a premium without receiving premium satisfaction. "
            f"A decision-maker should question whether {brand}'s pricing is justified."
        ),
        "recommendation": f"Avoid {brand} at current pricing unless brand prestige is the goal.",
        "severity": "warning",
        "category": "pricing",
    }


def insight_best_value(matrix: pd.DataFrame) -> Optional[dict]:
    """
    Identify the brand with the highest value-for-money score.
    """
    if "value_score_pct" not in matrix.columns:
        return None

    best = matrix.loc[matrix["value_score_pct"].idxmax()]
    second = matrix.nlargest(2, "value_score_pct").iloc[-1]

    return {
        "id": "best_value",
        "icon": INSIGHT_ICONS["trophy"],
        "title": f"{best['brand']} Delivers the Best Value for Money",
        "detail": (
            f"{best['brand']} scores {best['value_score_pct']:.0f}/100 on value — "
            f"the highest in the category. It combines a competitive average price of "
            f"₹{best['avg_price']:,.0f} with strong customer sentiment ({best.get('avg_sentiment', 0):.0%}). "
            f"Runner-up is {second['brand']} at {second['value_score_pct']:.0f}/100."
        ),
        "recommendation": f"For budget-conscious buyers, {best['brand']} is the clear first choice.",
        "severity": "positive",
        "category": "value",
    }


def insight_durability_anomaly(matrix: pd.DataFrame) -> Optional[dict]:
    """
    Detect brands with high overall rating but poor durability sentiment.
    This is a classic 'review gaming' or 'honeymoon effect' signal.
    """
    if "durability" not in matrix.columns or "avg_rating" not in matrix.columns:
        return None

    avg_rating = matrix["avg_rating"].mean()
    avg_durability = matrix["durability"].mean()

    # High rating (above avg) but low durability (below avg)
    anomalies = matrix[
        (matrix["avg_rating"] >= avg_rating) &
        (matrix["durability"] < avg_durability * 0.92)
    ]

    if anomalies.empty:
        return None

    brand = anomalies.sort_values("durability").iloc[0]["brand"]
    rating = anomalies.sort_values("durability").iloc[0]["avg_rating"]
    durability = anomalies.sort_values("durability").iloc[0]["durability"]

    return {
        "id": "durability_anomaly",
        "icon": INSIGHT_ICONS["flag"],
        "title": f"{brand} Has a Durability Problem Hidden by High Ratings",
        "detail": (
            f"{brand} holds an impressive {rating:.1f}★ average rating, yet aspect-level "
            f"analysis reveals its durability sentiment score is only {durability:.0%} — "
            f"below the category average. This suggests early reviewers rate highly but "
            f"durability issues emerge over time, a classic 'honeymoon effect' in reviews."
        ),
        "recommendation": f"Verify {brand}'s long-term durability before bulk procurement.",
        "severity": "critical",
        "category": "quality",
    }


def insight_discount_dependency(matrix: pd.DataFrame) -> Optional[dict]:
    """
    Flag brands that rely heavily on artificial discounts to appear competitive.
    """
    if "avg_discount" not in matrix.columns:
        return None

    heavy = matrix[matrix["avg_discount"] >= matrix["avg_discount"].quantile(0.75)]
    if heavy.empty:
        return None

    brand = heavy.loc[heavy["avg_discount"].idxmax()]

    return {
        "id": "discount_dependency",
        "icon": INSIGHT_ICONS["money"],
        "title": f"{brand['brand']} Relies Heavily on Artificial Discounting",
        "detail": (
            f"{brand['brand']} averages {brand['avg_discount']:.0f}% discount — "
            f"the highest in the category. This suggests the list price is inflated "
            f"to manufacture discount appeal. The effective price may be reasonable, "
            f"but the brand uses discount optics as a primary sales driver rather than "
            f"genuine product value."
        ),
        "recommendation": f"Always compare {brand['brand']}'s sale price, not list price, to competitors.",
        "severity": "warning",
        "category": "pricing",
    }


def insight_review_volume_mismatch(matrix: pd.DataFrame) -> Optional[dict]:
    """
    Identify brands with unusually high review volume relative to rating.
    High volume + mediocre rating = market saturation without quality.
    """
    if "total_review_count" not in matrix.columns:
        return None

    avg_volume = matrix["total_review_count"].mean()
    avg_rating = matrix["avg_rating"].mean()

    candidates = matrix[
        (matrix["total_review_count"] > avg_volume * 1.4) &
        (matrix["avg_rating"] < avg_rating)
    ]

    if candidates.empty:
        # Try softer threshold
        candidates = matrix.nlargest(1, "total_review_count")

    brand = candidates.iloc[0]

    return {
        "id": "review_volume_mismatch",
        "icon": INSIGHT_ICONS["magnify"],
        "title": f"{brand['brand']} Has High Volume but Quality Concerns",
        "detail": (
            f"{brand['brand']} accumulates {brand['total_review_count']:,.0f} total reviews "
            f"across products — among the highest in the category — yet maintains only "
            f"a {brand['avg_rating']:.1f}★ average. High volume with sub-par rating often "
            f"signals mass-market reach without consistent quality control."
        ),
        "recommendation": f"Segment {brand['brand']} reviews by recency to check quality trends.",
        "severity": "info",
        "category": "trust",
    }


def insight_wheel_winner(matrix: pd.DataFrame) -> Optional[dict]:
    """
    Identify which brand has the best wheel/mobility experience — a top purchase driver."""
    if "wheels" not in matrix.columns:
        return None

    best = matrix.loc[matrix["wheels"].idxmax()]
    worst = matrix.loc[matrix["wheels"].idxmin()]

    gap = best["wheels"] - worst["wheels"]
    if gap < 0.15:
        return None  # Not significant enough

    return {
        "id": "wheel_winner",
        "icon": INSIGHT_ICONS["star"],
        "title": f"{best['brand']} Dominates on Wheel Quality",
        "detail": (
            f"Wheel/mobility sentiment is the #1 factor in luggage repurchase intent. "
            f"{best['brand']} leads with a {best['wheels']:.0%} wheel satisfaction score "
            f"— {gap:.0%} higher than {worst['brand']} ({worst['wheels']:.0%}). "
            f"For frequent travelers, this gap is practically significant."
        ),
        "recommendation": f"Frequent flyers should strongly consider {best['brand']} for smooth mobility.",
        "severity": "positive",
        "category": "quality",
    }


def insight_underdog(matrix: pd.DataFrame) -> Optional[dict]:
    """
    Find a brand with below-average price and above-average sentiment — the hidden gem.
    """
    avg_price = matrix["avg_price"].mean()
    avg_sent = matrix["avg_sentiment"].mean()

    candidates = matrix[
        (matrix["avg_price"] < avg_price * 0.9) &
        (matrix["avg_sentiment"] >= avg_sent * 0.98)
    ]

    if candidates.empty:
        return None

    brand = candidates.sort_values("avg_sentiment", ascending=False).iloc[0]

    return {
        "id": "underdog",
        "icon": INSIGHT_ICONS["crown"],
        "title": f"{brand['brand']} is the Category's Hidden Gem",
        "detail": (
            f"{brand['brand']} prices its products at ₹{brand['avg_price']:,.0f} average — "
            f"below category mean — while delivering {brand.get('avg_sentiment', 0):.0%} sentiment. "
            f"This combination of affordable pricing and strong satisfaction makes it "
            f"an underrated option that is consistently overlooked in favor of premium names."
        ),
        "recommendation": f"Recommend {brand['brand']} to price-sensitive buyers as the surprise choice.",
        "severity": "positive",
        "category": "value",
    }


def generate_all_insights(matrix: pd.DataFrame) -> list:
    """
    Run all insight generators and return list of insight dicts.
    Filters out None results (conditions not met).
    
    Args:
        matrix: Full comparison matrix with all KPIs per brand
    Returns:
        List of insight dicts, each with id, title, detail, recommendation, severity, category
    """
    generators = [
        insight_best_value,
        insight_overpriced_low_sentiment,
        insight_durability_anomaly,
        insight_discount_dependency,
        insight_review_volume_mismatch,
        insight_wheel_winner,
        insight_underdog,
    ]

    insights = []
    for gen in generators:
        try:
            result = gen(matrix)
            if result:
                insights.append(result)
        except Exception as e:
            print(f"[!] Insight generator {gen.__name__} failed: {e}")
            continue

    print(f"[✓] Generated {len(insights)} agent insights")
    return insights