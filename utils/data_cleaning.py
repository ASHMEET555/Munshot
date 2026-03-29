"""
utils/data_cleaning.py
----------------------
Data cleaning and normalization utilities for the luggage intelligence pipeline.
Handles missing values, price normalization, text cleaning, and brand standardization.
"""

import re
import pandas as pd
import numpy as np


BRAND_ALIASES = {
    "american tourister": "American Tourister",
    "americantourister": "American Tourister",
    "at": "American Tourister",
    "safari": "Safari",
    "safaris": "Safari",
    "skybags": "Skybags",
    "sky bags": "Skybags",
    "vip": "VIP",
    "aristocrat": "Aristocrat",
    "nasher miles": "Nasher Miles",
    "nashermiles": "Nasher Miles",
}


def normalize_brand(brand_str: str) -> str:
    """Normalize brand name to canonical form using alias mapping."""
    if pd.isna(brand_str):
        return "Unknown"
    key = str(brand_str).strip().lower()
    return BRAND_ALIASES.get(key, str(brand_str).strip().title())


def clean_price(price_val) -> float:
    """Convert price string/value to float, stripping ₹, commas, spaces."""
    if pd.isna(price_val):
        return np.nan
    price_str = str(price_val).replace("₹", "").replace(",", "").strip()
    try:
        return float(price_str)
    except ValueError:
        return np.nan


def normalize_discount(discount_val) -> float:
    """Ensure discount is a float between 0 and 100."""
    val = pd.to_numeric(discount_val, errors="coerce")
    if pd.isna(val):
        return np.nan
    return float(np.clip(val, 0, 100))


def clean_review_text(text: str) -> str:
    """
    Clean review text:
    - Remove HTML tags
    - Normalize whitespace
    - Strip special characters while keeping punctuation
    """
    if pd.isna(text) or not isinstance(text, str):
        return ""
    text = re.sub(r"<[^>]+>", " ", text)               # Remove HTML
    text = re.sub(r"[^\w\s.,!?'-]", " ", text)          # Keep core chars
    text = re.sub(r"\s+", " ", text).strip()             # Normalize whitespace
    return text


def handle_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fill or drop missing values with sensible defaults:
    - Numeric: fill with brand-level median
    - Text: fill with empty string
    """
    numeric_cols = ["price", "list_price", "discount", "rating", "review_count"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            # Fill missing with brand median, then global median
            df[col] = df.groupby("brand")[col].transform(lambda x: x.fillna(x.median()))
            df[col] = df[col].fillna(df[col].median())

    text_cols = ["review_text", "product_title"]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].fillna("")

    return df


def compute_discount_from_prices(df: pd.DataFrame) -> pd.DataFrame:
    """Recompute discount column if list_price and price both exist."""
    mask = (df["list_price"] > 0) & df["discount"].isna()
    df.loc[mask, "discount"] = (
        (df.loc[mask, "list_price"] - df.loc[mask, "price"]) / df.loc[mask, "list_price"] * 100
    ).round(1)
    return df


def clean_full_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """
    Run the full cleaning pipeline on raw dataset.
    Returns cleaned DataFrame ready for analysis.
    """
    df = df.copy()

    # Brand normalization
    if "brand" in df.columns:
        df["brand"] = df["brand"].apply(normalize_brand)

    # Price cleaning
    for col in ["price", "list_price"]:
        if col in df.columns:
            df[col] = df[col].apply(clean_price)

    # Discount normalization
    if "discount" in df.columns:
        df["discount"] = df["discount"].apply(normalize_discount)

    # Review text cleaning
    if "review_text" in df.columns:
        df["review_text"] = df["review_text"].apply(clean_review_text)

    # Fill missing values
    df = handle_missing_values(df)

    # Recompute discounts if possible
    if "list_price" in df.columns and "price" in df.columns:
        df = compute_discount_from_prices(df)

    # Clip rating to valid range
    if "rating" in df.columns:
        df["rating"] = df["rating"].clip(1.0, 5.0)

    return df