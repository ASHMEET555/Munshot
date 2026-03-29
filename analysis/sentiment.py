"""
analysis/sentiment.py
---------------------
Sentiment analysis for luggage brand reviews.
Uses VADER (fast, no GPU needed) with optional HuggingFace transformer upgrade.
Computes:
  - Per-review sentiment score (0-1 scale)
  - Brand-level aggregated sentiment
  - Sentiment distribution (positive/neutral/negative ratios)
  - Top positive and negative themes via keyword extraction
"""

import re
from collections import Counter
from typing import Optional

import pandas as pd
import numpy as np

# VADER is the primary engine (lightweight, no model download needed)
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    VADER_AVAILABLE = True
except ImportError:
    VADER_AVAILABLE = False

# Luggage-domain keyword lists for theme extraction
POSITIVE_KEYWORDS = [
    "smooth", "durable", "sturdy", "spacious", "lightweight", "quality",
    "excellent", "great", "amazing", "perfect", "love", "solid", "strong",
    "easy", "good", "nice", "recommend", "happy", "satisfied", "best",
    "value", "worth", "premium", "elegant", "stylish", "secure"
]

NEGATIVE_KEYWORDS = [
    "broke", "broken", "cheap", "flimsy", "poor", "bad", "terrible",
    "worst", "waste", "disappointed", "damaged", "defective", "issue",
    "problem", "weak", "noisy", "stuck", "difficult", "overpriced",
    "refund", "return", "complaint", "awful", "pathetic", "rubbish"
]

ASPECT_KEYWORDS = {
    "wheels": ["wheel", "wheels", "rolling", "spinner", "roller", "caster", "roll"],
    "handle": ["handle", "handles", "grip", "telescopic", "pull", "extend", "retract"],
    "material": ["material", "shell", "hard", "soft", "fabric", "polycarbonate", "abs", "build"],
    "zipper": ["zipper", "zip", "zippers", "closure", "latch", "lock"],
    "size": ["size", "space", "capacity", "fit", "cabin", "check-in", "large", "small", "spacious"],
    "durability": ["durable", "durability", "long-lasting", "sturdy", "strong", "tough", "last"]
}


def _vader_score(text: str, analyzer) -> float:
    """
    Compute VADER compound score normalized from [-1,1] to [0,1].
    Returns 0.5 if text is empty.
    """
    if not text or not isinstance(text, str):
        return 0.5
    score = analyzer.polarity_scores(text)["compound"]
    return round((score + 1) / 2, 4)  # normalize to [0,1]


def _rule_based_score(text: str) -> float:
    """
    Fallback rule-based scorer using keyword counting.
    Used when VADER is unavailable.
    """
    if not text:
        return 0.5
    text_lower = text.lower()
    pos = sum(1 for kw in POSITIVE_KEYWORDS if kw in text_lower)
    neg = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text_lower)
    total = pos + neg + 1
    return round(0.5 + (pos - neg) / (2 * total), 4)


def score_to_label(score: float) -> str:
    """Convert numeric sentiment score to categorical label."""
    if score >= 0.65:
        return "positive"
    elif score >= 0.40:
        return "neutral"
    return "negative"


def analyze_reviews(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add sentiment_score and sentiment_label columns to review-level DataFrame.
    Uses VADER if available, else rule-based fallback.
    
    Args:
        df: DataFrame with 'review_text' column
    Returns:
        df with added 'sentiment_score' and 'sentiment_label' columns
    """
    if "sentiment_score" in df.columns and df["sentiment_score"].notna().all():
        # Already computed (synthetic data)
        df["sentiment_label"] = df["sentiment_score"].apply(score_to_label)
        return df

    if VADER_AVAILABLE:
        analyzer = SentimentIntensityAnalyzer()
        score_fn = lambda text: _vader_score(text, analyzer)
        print("[✓] Using VADER for sentiment analysis")
    else:
        score_fn = _rule_based_score
        print("[!] VADER not available. Using rule-based scorer.")

    df = df.copy()
    df["sentiment_score"] = df["review_text"].apply(score_fn)
    df["sentiment_label"] = df["sentiment_score"].apply(score_to_label)
    return df


def brand_sentiment_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate sentiment to brand level.
    Returns DataFrame with brand-level metrics.
    """
    summary = df.groupby("brand").agg(
        avg_sentiment=("sentiment_score", "mean"),
        positive_pct=("sentiment_label", lambda x: (x == "positive").mean() * 100),
        neutral_pct=("sentiment_label", lambda x: (x == "neutral").mean() * 100),
        negative_pct=("sentiment_label", lambda x: (x == "negative").mean() * 100),
        total_reviews=("sentiment_score", "count"),
    ).reset_index()
    summary["avg_sentiment"] = summary["avg_sentiment"].round(3)
    return summary


def extract_themes(df: pd.DataFrame, brand: Optional[str] = None, top_n: int = 6) -> dict:
    """
    Extract top positive and negative themes from review texts.
    
    Args:
        df: Review-level DataFrame
        brand: If specified, filter to that brand only
        top_n: Number of themes to return
    Returns:
        Dict with 'positive_themes' and 'negative_themes' lists
    """
    if brand:
        df = df[df["brand"] == brand]

    pos_reviews = df[df["sentiment_label"] == "positive"]["review_text"]
    neg_reviews = df[df["sentiment_label"] == "negative"]["review_text"]

    def count_keywords(texts, keywords):
        counts = Counter()
        for text in texts:
            if not isinstance(text, str):
                continue
            text_lower = text.lower()
            for kw in keywords:
                if kw in text_lower:
                    counts[kw] += 1
        return [kw for kw, _ in counts.most_common(top_n)]

    return {
        "positive_themes": count_keywords(pos_reviews, POSITIVE_KEYWORDS),
        "negative_themes": count_keywords(neg_reviews, NEGATIVE_KEYWORDS),
        "recurring_complaints": count_keywords(neg_reviews, NEGATIVE_KEYWORDS + list(ASPECT_KEYWORDS["durability"])),
        "recurring_praise": count_keywords(pos_reviews, POSITIVE_KEYWORDS + list(ASPECT_KEYWORDS["durability"])),
    }


def aspect_sentiment(df: pd.DataFrame, brand: Optional[str] = None) -> dict:
    """
    Compute sentiment scores for each luggage aspect (wheels, handle, etc.).
    Filters reviews that mention each aspect, computes avg sentiment.
    
    Returns dict: {aspect: avg_score}
    """
    if brand:
        df = df[df["brand"] == brand]

    results = {}
    for aspect, keywords in ASPECT_KEYWORDS.items():
        # Filter reviews mentioning this aspect
        mask = df["review_text"].str.lower().apply(
            lambda t: any(kw in str(t) for kw in keywords)
        )
        aspect_df = df[mask]
        if len(aspect_df) > 0:
            results[aspect] = round(aspect_df["sentiment_score"].mean(), 3)
        else:
            # Fall back to overall score if no aspect mentions
            results[aspect] = round(df["sentiment_score"].mean(), 3) if len(df) > 0 else 0.5

    return results


def brand_aspect_sentiment(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute aspect-level sentiment for every brand.
    Returns DataFrame: brand × aspects matrix.
    """
    brands = df["brand"].unique()
    rows = []
    for brand in brands:
        scores = aspect_sentiment(df, brand)
        rows.append({"brand": brand, **scores})
    return pd.DataFrame(rows)