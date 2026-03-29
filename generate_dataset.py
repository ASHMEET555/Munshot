"""
generate_dataset.py
-------------------
Generates a realistic synthetic dataset of Amazon India luggage products and reviews.
This module is used when live scraping is unavailable (e.g., anti-bot blocks).
The data mimics real Amazon India patterns for 6 brands × 12 products × ~60 reviews.
"""

import json
import random
import pandas as pd
import numpy as np
from pathlib import Path

random.seed(42)
np.random.seed(42)

# ── Brand profiles ────────────────────────────────────────────────────────────
BRAND_PROFILES = {
    "Safari": {
        "tier": "mid-premium",
        "base_price_range": (3500, 9000),
        "avg_discount": 38,
        "avg_rating": 4.1,
        "sentiment_bias": 0.62,
        "strengths": ["durable", "spacious", "good locks", "lightweight"],
        "weaknesses": ["zipper quality", "wheel noise", "handle wobble"],
        "durability_score": 0.72,
        "wheel_score": 0.55,
        "handle_score": 0.60,
        "material_score": 0.75,
        "zipper_score": 0.48,
        "size_score": 0.80,
    },
    "Skybags": {
        "tier": "budget-mid",
        "base_price_range": (2500, 7000),
        "avg_discount": 52,
        "avg_rating": 3.9,
        "sentiment_bias": 0.55,
        "strengths": ["trendy design", "affordable", "lightweight", "color options"],
        "weaknesses": ["durability issues", "cheap zippers", "wheels break easily"],
        "durability_score": 0.45,
        "wheel_score": 0.40,
        "handle_score": 0.58,
        "material_score": 0.50,
        "zipper_score": 0.42,
        "size_score": 0.70,
    },
    "American Tourister": {
        "tier": "premium",
        "base_price_range": (5500, 15000),
        "avg_discount": 42,
        "avg_rating": 4.3,
        "sentiment_bias": 0.72,
        "strengths": ["excellent build quality", "smooth wheels", "warranty", "elegant design"],
        "weaknesses": ["expensive", "heavy", "limited budget options"],
        "durability_score": 0.85,
        "wheel_score": 0.82,
        "handle_score": 0.80,
        "material_score": 0.88,
        "zipper_score": 0.78,
        "size_score": 0.75,
    },
    "VIP": {
        "tier": "budget",
        "base_price_range": (1800, 5500),
        "avg_discount": 45,
        "avg_rating": 3.7,
        "sentiment_bias": 0.48,
        "strengths": ["budget friendly", "lightweight", "widely available"],
        "weaknesses": ["poor durability", "flimsy material", "handle breaks", "wheels poor"],
        "durability_score": 0.38,
        "wheel_score": 0.35,
        "handle_score": 0.40,
        "material_score": 0.42,
        "zipper_score": 0.50,
        "size_score": 0.68,
    },
    "Aristocrat": {
        "tier": "budget-mid",
        "base_price_range": (2200, 6000),
        "avg_discount": 40,
        "avg_rating": 3.8,
        "sentiment_bias": 0.52,
        "strengths": ["affordable", "decent capacity", "okay build"],
        "weaknesses": ["wheel quality poor", "material feels cheap", "zipper issues after use"],
        "durability_score": 0.48,
        "wheel_score": 0.42,
        "handle_score": 0.52,
        "material_score": 0.48,
        "zipper_score": 0.45,
        "size_score": 0.72,
    },
    "Nasher Miles": {
        "tier": "mid-premium",
        "base_price_range": (4000, 11000),
        "avg_discount": 35,
        "avg_rating": 4.2,
        "sentiment_bias": 0.68,
        "strengths": ["360 wheels", "TSA lock", "hard shell", "stylish"],
        "weaknesses": ["price premium", "limited size options", "heavy shell"],
        "durability_score": 0.78,
        "wheel_score": 0.82,
        "handle_score": 0.70,
        "material_score": 0.80,
        "zipper_score": 0.65,
        "size_score": 0.60,
    },
}

PRODUCT_TYPES = [
    ("Cabin Trolley 55cm", "cabin"),
    ("Check-In Luggage 65cm", "medium"),
    ("Large Trolley 75cm", "large"),
    ("Hard Shell Cabin 55cm", "cabin"),
    ("Soft Side Check-In 65cm", "medium"),
    ("Expandable Trolley 68cm", "medium"),
    ("4-Wheeler Spinner 75cm", "large"),
    ("Business Trolley 56cm", "cabin"),
    ("Travel Set 3pc", "set"),
    ("Hard Top 75cm", "large"),
    ("Dual-Tone Cabin 55cm", "cabin"),
    ("Polycarbonate Shell 65cm", "medium"),
]

POSITIVE_REVIEW_TEMPLATES = [
    "Really impressed with the {strength}. Used it for my {trip} trip and it held up perfectly. The {aspect} is excellent.",
    "Great luggage! The {strength} exceeded my expectations. Would definitely recommend to anyone looking for {tier} options.",
    "Bought this for my {trip} and absolutely love it. {strength} is top notch. The {aspect} works smoothly.",
    "Very happy with this purchase. {strength} is great value for money. Perfect size for {trip}.",
    "Amazing product! The {aspect} quality is superb. {strength} makes travel so much easier. 5 stars!",
    "Best luggage I have owned in years. {strength} is solid and the {aspect} glides smoothly. No complaints at all.",
    "Excellent build quality. The {strength} is premium. {aspect} function is smooth and reliable. Happy customer!",
    "Perfect for my frequent {trip} trips. {strength} has been amazing. The {aspect} is sturdy and well made.",
]

NEGATIVE_REVIEW_TEMPLATES = [
    "Disappointed with the {weakness}. After just {months} months, the {aspect} started giving issues.",
    "The {weakness} is a major problem. I expected better quality at this price point. {aspect} feels cheap.",
    "Not happy with this purchase. The {weakness} is very noticeable. {aspect} quality is poor for the price.",
    "After {months} uses, the {aspect} broke completely. The {weakness} is terrible. Would not recommend.",
    "Looks good in photos but the {weakness} is frustrating. {aspect} made noise from day one. Disappointing.",
    "Bought for {trip} trip but the {weakness} ruined the experience. The {aspect} stopped working mid travel.",
    "Quality has gone downhill. The {weakness} is a deal breaker. {aspect} wobbles badly after light use.",
]

NEUTRAL_REVIEW_TEMPLATES = [
    "Decent luggage for the price. {aspect} is okay, nothing special. The {weakness} is a minor concern.",
    "Average product. {strength} is decent but the {weakness} needs improvement. Okay for occasional use.",
    "Works fine for basic travel. {aspect} is acceptable. Not the best but not the worst either.",
    "Good enough for the price paid. {weakness} is a small issue. {aspect} functions adequately.",
]

TRIP_TYPES = ["Goa", "Delhi", "Mumbai", "international", "business", "family", "weekend", "honeymoon"]
ASPECTS_MAP = ["wheels", "handle", "material", "zipper", "size", "durability"]


def generate_review(brand: str, profile: dict, sentiment: str) -> dict:
    """Generate a single realistic review for a brand based on sentiment polarity."""
    if sentiment == "positive":
        template = random.choice(POSITIVE_REVIEW_TEMPLATES)
        strength = random.choice(profile["strengths"])
        aspect = random.choice(ASPECTS_MAP)
        text = template.format(
            strength=strength, trip=random.choice(TRIP_TYPES),
            aspect=aspect, tier=profile["tier"]
        )
        rating = random.choice([4, 4, 4, 5, 5])
        score = round(random.uniform(0.65, 0.95), 3)
    elif sentiment == "negative":
        template = random.choice(NEGATIVE_REVIEW_TEMPLATES)
        weakness = random.choice(profile["weaknesses"])
        aspect = random.choice(ASPECTS_MAP)
        text = template.format(
            weakness=weakness, aspect=aspect,
            months=random.randint(1, 6), trip=random.choice(TRIP_TYPES)
        )
        rating = random.choice([1, 1, 2, 2, 3])
        score = round(random.uniform(0.05, 0.38), 3)
    else:
        template = random.choice(NEUTRAL_REVIEW_TEMPLATES)
        aspect = random.choice(ASPECTS_MAP)
        text = template.format(
            strength=random.choice(profile["strengths"]),
            weakness=random.choice(profile["weaknesses"]),
            aspect=aspect
        )
        rating = random.choice([3, 3, 4])
        score = round(random.uniform(0.38, 0.65), 3)

    return {"review_text": text, "review_rating": rating, "sentiment_score": score, "sentiment_label": sentiment}


def generate_dataset() -> pd.DataFrame:
    """
    Generate complete dataset of products + reviews for all brands.
    Returns a flattened DataFrame suitable for analysis.
    """
    records = []

    for brand, profile in BRAND_PROFILES.items():
        low, high = profile["base_price_range"]

        for i, (product_suffix, category) in enumerate(PRODUCT_TYPES):
            product_title = f"{brand} {product_suffix}"
            list_price = round(random.uniform(low, high), -2)
            discount_pct = profile["avg_discount"] + random.randint(-10, 10)
            discount_pct = max(10, min(70, discount_pct))
            price = round(list_price * (1 - discount_pct / 100), -2)
            rating = round(profile["avg_rating"] + random.uniform(-0.4, 0.4), 1)
            rating = max(1.0, min(5.0, rating))
            review_count = random.randint(180, 2400)

            # Determine sentiment split
            pos_ratio = profile["sentiment_bias"]
            neg_ratio = (1 - pos_ratio) * 0.6
            neu_ratio = (1 - pos_ratio) * 0.4

            num_reviews = random.randint(55, 80)
            sentiments = (
                ["positive"] * int(num_reviews * pos_ratio)
                + ["negative"] * int(num_reviews * neg_ratio)
                + ["neutral"] * int(num_reviews * neu_ratio)
            )
            random.shuffle(sentiments)
            sentiments = sentiments[:num_reviews]

            for sent in sentiments:
                rev = generate_review(brand, profile, sent)
                records.append({
                    "brand": brand,
                    "product_title": product_title,
                    "category": category,
                    "price": price,
                    "list_price": list_price,
                    "discount": discount_pct,
                    "rating": rating,
                    "review_count": review_count,
                    "review_text": rev["review_text"],
                    "review_rating": rev["review_rating"],
                    "sentiment_score": rev["sentiment_score"],
                    "sentiment_label": rev["sentiment_label"],
                    # Aspect scores (product-level, add noise)
                    "wheel_score": round(min(1, max(0, profile["wheel_score"] + random.uniform(-0.1, 0.1))), 3),
                    "handle_score": round(min(1, max(0, profile["handle_score"] + random.uniform(-0.1, 0.1))), 3),
                    "material_score": round(min(1, max(0, profile["material_score"] + random.uniform(-0.1, 0.1))), 3),
                    "zipper_score": round(min(1, max(0, profile["zipper_score"] + random.uniform(-0.1, 0.1))), 3),
                    "size_score": round(min(1, max(0, profile["size_score"] + random.uniform(-0.1, 0.1))), 3),
                    "durability_score": round(min(1, max(0, profile["durability_score"] + random.uniform(-0.1, 0.1))), 3),
                })

    df = pd.DataFrame(records)
    return df


def save_dataset(df: pd.DataFrame, raw_path: str, processed_path: str):
    """Save raw and processed versions of the dataset."""
    Path(raw_path).parent.mkdir(parents=True, exist_ok=True)
    Path(processed_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(raw_path, index=False)
    print(f"[✓] Raw dataset saved: {raw_path} ({len(df)} rows)")

    # Processed: aggregated product-level
    processed = df.groupby(["brand", "product_title", "category", "price", "list_price",
                             "discount", "rating", "review_count"]).agg(
        avg_sentiment=("sentiment_score", "mean"),
        positive_reviews=("sentiment_label", lambda x: (x == "positive").sum()),
        negative_reviews=("sentiment_label", lambda x: (x == "negative").sum()),
        neutral_reviews=("sentiment_label", lambda x: (x == "neutral").sum()),
        avg_wheel_score=("wheel_score", "mean"),
        avg_handle_score=("handle_score", "mean"),
        avg_material_score=("material_score", "mean"),
        avg_zipper_score=("zipper_score", "mean"),
        avg_size_score=("size_score", "mean"),
        avg_durability_score=("durability_score", "mean"),
    ).reset_index()
    processed.to_csv(processed_path, index=False)
    print(f"[✓] Processed dataset saved: {processed_path} ({len(processed)} rows)")
    return processed


if __name__ == "__main__":
    df = generate_dataset()
    save_dataset(df, "data/raw/amazon_luggage_raw.csv", "data/processed/amazon_luggage_processed.csv")
    print(f"\nDataset summary:\n{df.groupby('brand')['product_title'].nunique()}")