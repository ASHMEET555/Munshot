"""
dashboard/app.py
----------------
Flask backend for the Luggage Intelligence Dashboard.
Serves all dashboard views and exposes JSON API endpoints for chart data.

Routes:
  GET /                   → Main dashboard overview
  GET /brand/<name>       → Brand drilldown page
  GET /product/<id>       → Product detail page
  GET /api/overview       → Overview stats JSON
  GET /api/brands         → All brand comparison data
  GET /api/charts/<type>  → Plotly chart JSON
  GET /api/insights       → Agent insights JSON
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from functools import lru_cache

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from flask import Flask, render_template, jsonify, request, abort

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from utils.helpers import NumpyEncoder, get_brand_color, get_all_brand_colors, apply_plotly_theme
from analysis.sentiment import (
    analyze_reviews, brand_sentiment_summary, brand_aspect_sentiment, extract_themes
)
from analysis.pricing_analysis import compute_all_pricing, brand_pricing_summary
from analysis.competitor_analysis import (
    build_comparison_matrix, rank_brands, identify_winners, brand_scorecard, get_brand_pros_cons
)
from agent.insight_generator import generate_all_insights

# ── App setup ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.json_encoder = NumpyEncoder

DATA_PATH = ROOT / "data" / "raw" / "amazon_luggage_raw.csv"
PROCESSED_PATH = ROOT / "data" / "processed" / "amazon_luggage_processed.csv"


# ── Data loading & caching ────────────────────────────────────────────────────

def _load_or_generate() -> pd.DataFrame:
    """Load dataset from disk, generating synthetic data if needed."""
    if DATA_PATH.exists():
        return pd.read_csv(DATA_PATH)

    print("[!] Dataset not found. Generating synthetic data...")
    from generate_dataset import generate_dataset, save_dataset
    df = generate_dataset()
    save_dataset(df, str(DATA_PATH), str(PROCESSED_PATH))
    return df


@lru_cache(maxsize=1)
def _get_analysis_cache():
    """
    Run full analysis pipeline once and cache results.
    Returns tuple of DataFrames and dicts used across all routes.
    """
    raw_df = _load_or_generate()
    df = analyze_reviews(raw_df)

    # Sentiment aggregations
    sentiment_df = brand_sentiment_summary(df)
    aspect_df = brand_aspect_sentiment(df)

    # Pricing
    pricing = compute_all_pricing(df, sentiment_df)
    pricing_summary = pricing["brand_pricing"]

    # Merge into comparison matrix
    matrix = build_comparison_matrix(pricing_summary, sentiment_df, aspect_df)
    matrix = rank_brands(matrix)

    # Value scores
    value_df = pricing["value_analysis"]
    if "value_score_pct" in value_df.columns:
        matrix = matrix.merge(
            value_df[["brand", "value_score_pct"]], on="brand", how="left"
        )

    # Scorecard
    scorecard = brand_scorecard(matrix)

    # Winners
    winners = identify_winners(matrix)

    # Themes per brand
    brands = df["brand"].unique()
    themes = {b: extract_themes(df, b) for b in brands}

    # Agent insights
    insights = generate_all_insights(matrix)

    return {
        "raw_df": raw_df,
        "df": df,
        "sentiment_df": sentiment_df,
        "aspect_df": aspect_df,
        "pricing_summary": pricing_summary,
        "pricing": pricing,
        "matrix": matrix,
        "scorecard": scorecard,
        "winners": winners,
        "themes": themes,
        "insights": insights,
    }


def get_data():
    return _get_analysis_cache()


# ── Helper: safe JSON response ─────────────────────────────────────────────────

def safe_jsonify(data):
    return app.response_class(
        json.dumps(data, cls=NumpyEncoder),
        mimetype="application/json"
    )


# ── Page routes ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Main dashboard overview page."""
    d = get_data()
    df = d["df"]
    matrix = d["matrix"]

    overview = {
        "total_brands": int(df["brand"].nunique()),
        "total_products": int(df.drop_duplicates("product_title")["product_title"].count()),
        "total_reviews": int(len(df)),
        "avg_sentiment": float(df["sentiment_score"].mean().round(3)),
        "avg_price": float(df.drop_duplicates("product_title")["price"].mean().round(0)),
        "avg_rating": float(df.drop_duplicates("product_title")["rating"].mean().round(2)),
        "avg_discount": float(df.drop_duplicates("product_title")["discount"].mean().round(1)),
    }

    brands = sorted(df["brand"].unique().tolist())
    return render_template("index.html", overview=overview, brands=brands,
                           winners=d["winners"], insights=d["insights"])


@app.route("/brand/<brand_name>")
def brand_page(brand_name: str):
    """Brand-specific drilldown page."""
    d = get_data()
    df = d["df"]
    brands = df["brand"].unique()

    if brand_name not in brands:
        abort(404)

    brand_df = df[df["brand"] == brand_name]
    matrix = d["matrix"]
    brand_row = matrix[matrix["brand"] == brand_name].iloc[0].to_dict()
    themes = d["themes"].get(brand_name, {})
    pros_cons = get_brand_pros_cons(matrix, brand_name, d["themes"])
    products = brand_df.drop_duplicates("product_title")[
        ["product_title", "price", "list_price", "discount", "rating", "review_count", "category"]
    ].to_dict("records")

    return render_template("brand.html",
                           brand=brand_name,
                           brand_data=brand_row,
                           themes=themes,
                           pros_cons=pros_cons,
                           products=products,
                           all_brands=sorted(brands.tolist()))


@app.route("/product/<path:product_id>")
def product_page(product_id: str):
    """Product-level drilldown page."""
    d = get_data()
    df = d["df"]
    products = df.drop_duplicates("product_title")

    # URL-decode product title
    product_title = product_id.replace("_", " ")
    match = products[products["product_title"].str.lower() == product_title.lower()]

    if match.empty:
        # Try partial match
        match = products[products["product_title"].str.lower().str.contains(product_title.lower()[:15])]

    if match.empty:
        abort(404)

    product = match.iloc[0].to_dict()
    brand = product["brand"]
    product_reviews = df[df["product_title"] == product["product_title"]]
    themes = extract_themes(product_reviews)

    return render_template("product.html",
                           product=product,
                           themes=themes,
                           review_count=len(product_reviews),
                           all_brands=sorted(df["brand"].unique().tolist()))


# ── API: Overview stats ────────────────────────────────────────────────────────

@app.route("/api/overview")
def api_overview():
    d = get_data()
    df = d["df"]
    return safe_jsonify({
        "total_brands": int(df["brand"].nunique()),
        "total_products": int(df.drop_duplicates("product_title")["product_title"].count()),
        "total_reviews": int(len(df)),
        "avg_sentiment": float(df["sentiment_score"].mean()),
        "avg_price": float(df.drop_duplicates("product_title")["price"].mean()),
        "avg_rating": float(df.drop_duplicates("product_title")["rating"].mean()),
        "avg_discount": float(df.drop_duplicates("product_title")["discount"].mean()),
    })


# ── API: Brand comparison data ─────────────────────────────────────────────────

@app.route("/api/brands")
def api_brands():
    d = get_data()
    matrix = d["matrix"]
    cols = [c for c in matrix.columns if not c.startswith("rank_")]
    result = matrix[cols].to_dict("records")
    return safe_jsonify(result)


@app.route("/api/brand/<brand_name>")
def api_brand_detail(brand_name: str):
    d = get_data()
    matrix = d["matrix"]
    themes = d["themes"].get(brand_name, {})
    pros_cons = get_brand_pros_cons(matrix, brand_name, d["themes"])
    row = matrix[matrix["brand"] == brand_name]
    if row.empty:
        return safe_jsonify({"error": "Brand not found"}), 404
    data = row.iloc[0].to_dict()
    data.update({"themes": themes, "pros_cons": pros_cons})
    return safe_jsonify(data)


# ── API: Insights ──────────────────────────────────────────────────────────────

@app.route("/api/insights")
def api_insights():
    d = get_data()
    return safe_jsonify(d["insights"])


# ── API: Chart data ────────────────────────────────────────────────────────────

@app.route("/api/chart/price_rating")
def chart_price_rating():
    """Price vs Rating scatter plot data."""
    d = get_data()
    df = d["df"].drop_duplicates("product_title")
    brands = request.args.getlist("brand") or df["brand"].unique().tolist()
    df = df[df["brand"].isin(brands)]

    fig = go.Figure()
    for brand in brands:
        bdf = df[df["brand"] == brand]
        fig.add_trace(go.Scatter(
            x=bdf["price"].tolist(),
            y=bdf["rating"].tolist(),
            mode="markers",
            name=brand,
            text=bdf["product_title"].tolist(),
            hovertemplate="<b>%{text}</b><br>Price: ₹%{x:,.0f}<br>Rating: %{y}★<extra></extra>",
            marker=dict(
                color=get_brand_color(brand),
                size=12,
                opacity=0.8,
                line=dict(width=1, color="rgba(255,255,255,0.3)")
            ),
        ))

    fig.update_layout(
        title="Price vs Rating — All Products",
        xaxis_title="Selling Price (₹)",
        yaxis_title="Star Rating",
        showlegend=True,
    )
    apply_plotly_theme(fig)
    return safe_jsonify(json.loads(fig.to_json()))


@app.route("/api/chart/brand_price")
def chart_brand_price():
    """Brand average price comparison bar chart."""
    d = get_data()
    matrix = d["matrix"].sort_values("avg_price", ascending=False)
    brands = request.args.getlist("brand") or matrix["brand"].tolist()
    matrix = matrix[matrix["brand"].isin(brands)]

    fig = go.Figure(go.Bar(
        x=matrix["brand"].tolist(),
        y=matrix["avg_price"].tolist(),
        marker_color=[get_brand_color(b) for b in matrix["brand"]],
        text=[f"₹{p:,.0f}" for p in matrix["avg_price"]],
        textposition="auto",
        hovertemplate="<b>%{x}</b><br>Avg Price: ₹%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(title="Average Price by Brand", xaxis_title="Brand", yaxis_title="Price (₹)")
    apply_plotly_theme(fig)
    return safe_jsonify(json.loads(fig.to_json()))


@app.route("/api/chart/discount")
def chart_discount():
    """Average discount comparison."""
    d = get_data()
    matrix = d["matrix"].sort_values("avg_discount", ascending=False)
    brands = request.args.getlist("brand") or matrix["brand"].tolist()
    matrix = matrix[matrix["brand"].isin(brands)]

    fig = go.Figure(go.Bar(
        x=matrix["brand"].tolist(),
        y=matrix["avg_discount"].tolist(),
        marker_color=[get_brand_color(b) for b in matrix["brand"]],
        text=[f"{d:.0f}%" for d in matrix["avg_discount"]],
        textposition="auto",
        hovertemplate="<b>%{x}</b><br>Avg Discount: %{y:.1f}%<extra></extra>",
    ))
    fig.update_layout(title="Average Discount by Brand", xaxis_title="Brand", yaxis_title="Discount (%)")
    apply_plotly_theme(fig)
    return safe_jsonify(json.loads(fig.to_json()))


@app.route("/api/chart/sentiment")
def chart_sentiment():
    """Sentiment comparison chart."""
    d = get_data()
    matrix = d["matrix"].sort_values("avg_sentiment", ascending=False)
    brands = request.args.getlist("brand") or matrix["brand"].tolist()
    matrix = matrix[matrix["brand"].isin(brands)]

    # Stacked bar: positive/neutral/negative percentages
    fig = go.Figure()
    for col, label, color in [
        ("positive_pct", "Positive", "#00C851"),
        ("neutral_pct", "Neutral", "#FFA500"),
        ("negative_pct", "Negative", "#FF4444"),
    ]:
        if col in matrix.columns:
            fig.add_trace(go.Bar(
                name=label,
                x=matrix["brand"].tolist(),
                y=matrix[col].tolist(),
                marker_color=color,
                hovertemplate=f"<b>%{{x}}</b><br>{label}: %{{y:.1f}}%<extra></extra>",
            ))

    fig.update_layout(
        barmode="stack",
        title="Sentiment Distribution by Brand",
        xaxis_title="Brand",
        yaxis_title="Sentiment (%)",
    )
    apply_plotly_theme(fig)
    return safe_jsonify(json.loads(fig.to_json()))


@app.route("/api/chart/review_count")
def chart_review_count():
    """Review count comparison."""
    d = get_data()
    matrix = d["matrix"].sort_values("total_review_count", ascending=False)
    brands = request.args.getlist("brand") or matrix["brand"].tolist()
    matrix = matrix[matrix["brand"].isin(brands)]

    fig = go.Figure(go.Bar(
        x=matrix["brand"].tolist(),
        y=matrix["total_review_count"].tolist(),
        marker_color=[get_brand_color(b) for b in matrix["brand"]],
        text=[f"{int(r):,}" for r in matrix["total_review_count"]],
        textposition="auto",
    ))
    fig.update_layout(title="Total Review Volume by Brand", xaxis_title="Brand", yaxis_title="Reviews")
    apply_plotly_theme(fig)
    return safe_jsonify(json.loads(fig.to_json()))


@app.route("/api/chart/aspect_sentiment")
def chart_aspect_sentiment():
    """Aspect sentiment radar/bar chart."""
    d = get_data()
    aspect_df = d["aspect_df"]
    brands = request.args.getlist("brand") or aspect_df["brand"].unique().tolist()
    aspect_df = aspect_df[aspect_df["brand"].isin(brands)]
    aspects = ["wheels", "handle", "material", "zipper", "size", "durability"]

    fig = go.Figure()
    for _, row in aspect_df.iterrows():
        brand = row["brand"]
        scores = [float(row.get(a, 0.5)) * 100 for a in aspects]
        fig.add_trace(go.Bar(
            name=brand,
            x=aspects,
            y=scores,
            marker_color=get_brand_color(brand),
        ))

    fig.update_layout(
        barmode="group",
        title="Aspect-Level Sentiment by Brand",
        xaxis_title="Aspect",
        yaxis_title="Sentiment Score (%)",
    )
    apply_plotly_theme(fig)
    return safe_jsonify(json.loads(fig.to_json()))


@app.route("/api/chart/price_box")
def chart_price_box():
    """Price distribution box plot."""
    d = get_data()
    df = d["df"].drop_duplicates("product_title")
    brands = request.args.getlist("brand") or df["brand"].unique().tolist()
    df = df[df["brand"].isin(brands)]

    fig = go.Figure()
    for brand in brands:
        bdf = df[df["brand"] == brand]
        fig.add_trace(go.Box(
            y=bdf["price"].tolist(),
            name=brand,
            marker_color=get_brand_color(brand),
            boxpoints="all",
            jitter=0.3,
            pointpos=-1.8,
        ))

    fig.update_layout(title="Price Distribution by Brand", yaxis_title="Price (₹)")
    apply_plotly_theme(fig)
    return safe_jsonify(json.loads(fig.to_json()))


@app.route("/api/chart/value_score")
def chart_value_score():
    """Value-for-money comparison."""
    d = get_data()
    matrix = d["matrix"]
    if "value_score_pct" not in matrix.columns:
        return safe_jsonify({"error": "No value scores"}), 400

    matrix = matrix.sort_values("value_score_pct", ascending=False)
    brands = request.args.getlist("brand") or matrix["brand"].tolist()
    matrix = matrix[matrix["brand"].isin(brands)]

    colors = ["#00C851" if v >= 60 else "#FFA500" if v >= 40 else "#FF4444"
              for v in matrix["value_score_pct"]]

    fig = go.Figure(go.Bar(
        x=matrix["brand"].tolist(),
        y=matrix["value_score_pct"].tolist(),
        marker_color=colors,
        text=[f"{v:.0f}" for v in matrix["value_score_pct"]],
        textposition="auto",
    ))
    fig.update_layout(
        title="Value-for-Money Score (0–100)",
        xaxis_title="Brand",
        yaxis_title="Value Score",
    )
    apply_plotly_theme(fig)
    return safe_jsonify(json.loads(fig.to_json()))


@app.route("/api/chart/radar/<brand_name>")
def chart_radar(brand_name: str):
    """Radar chart for a single brand's scorecard."""
    d = get_data()
    scorecard = d["scorecard"]
    row = scorecard[scorecard["brand"] == brand_name]
    if row.empty:
        return safe_jsonify({"error": "Brand not found"}), 404

    row = row.iloc[0]
    categories = ["sentiment", "rating", "value", "affordability", "review_volume", "durability", "wheel_quality", "handle_quality"]
    values = [float(row.get(c, 50)) for c in categories]
    values.append(values[0])  # Close the radar
    categories.append(categories[0])

    fig = go.Figure(go.Scatterpolar(
        r=values,
        theta=categories,
        fill="toself",
        fillcolor=f"{get_brand_color(brand_name)}44",
        line_color=get_brand_color(brand_name),
        name=brand_name,
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        title=f"{brand_name} — Brand Scorecard",
    )
    apply_plotly_theme(fig)
    return safe_jsonify(json.loads(fig.to_json()))


# ── API: Filtered data ────────────────────────────────────────────────────────

@app.route("/api/filter")
def api_filter():
    """Filter products by brand, price range, rating, sentiment."""
    d = get_data()
    df = d["df"].drop_duplicates("product_title").copy()

    brands = request.args.getlist("brand")
    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)
    min_rating = request.args.get("min_rating", type=float)
    categories = request.args.getlist("category")
    min_sentiment = request.args.get("min_sentiment", type=float)

    if brands:
        df = df[df["brand"].isin(brands)]
    if min_price is not None:
        df = df[df["price"] >= min_price]
    if max_price is not None:
        df = df[df["price"] <= max_price]
    if min_rating is not None:
        df = df[df["rating"] >= min_rating]
    if categories:
        df = df[df["category"].isin(categories)]

    # Add avg sentiment per product
    if "sentiment_score" in d["df"].columns:
        product_sent = d["df"].groupby("product_title")["sentiment_score"].mean().reset_index()
        product_sent.columns = ["product_title", "avg_sentiment"]
        df = df.merge(product_sent, on="product_title", how="left")
        if min_sentiment is not None:
            df = df[df["avg_sentiment"] >= min_sentiment]

    return safe_jsonify(df.head(100).to_dict("records"))


# ── Run ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🚀 Starting Luggage Intelligence Dashboard...")
    print("   → Pre-loading analysis pipeline...")
    get_data()  # Warm cache
    print("   → Dashboard ready at http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)