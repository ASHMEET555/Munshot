/**
 * dashboard/static/script.js
 * ---------------------------
 * Interactive dashboard logic for LuggageIQ.
 * Handles:
 *   - Plotly chart loading from API endpoints
 *   - Brand comparison table rendering
 *   - Filter state management and application
 *   - Product explorer cards
 *   - Sorting table columns
 *   - Cross-chart brand filtering
 */

"use strict";

/* ── State ───────────────────────────────────────────────────────────────── */
const State = {
  selectedBrands: [],  // empty = all
  filters: {
    minPrice: 0,
    maxPrice: 20000,
    minRating: 0,
    category: "",
    minSentiment: 0,
  },
  sortCol: null,
  sortAsc: true,
  brandData: [],
};

const BRAND_COLORS = {
  "Safari":             "#FF6B35",
  "Skybags":            "#4ECDC4",
  "American Tourister": "#64B5F6",
  "VIP":                "#EF5350",
  "Aristocrat":         "#AB47BC",
  "Nasher Miles":       "#66BB6A",
};

const PLOTLY_CONFIG = {
  responsive: true,
  displayModeBar: false,
};

/* ── Utilities ───────────────────────────────────────────────────────────── */

/**
 * Fetch JSON from an API endpoint.
 * Appends brand query params if selectedBrands is non-empty.
 */
async function fetchJSON(url, brands = []) {
  const params = new URLSearchParams();
  (brands.length ? brands : State.selectedBrands).forEach(b => params.append("brand", b));
  const sep = url.includes("?") ? "&" : "?";
  const fullUrl = (params.toString() ? url + sep + params.toString() : url);
  const res = await fetch(fullUrl);
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
  return res.json();
}

/**
 * Render a Plotly chart from API JSON into a container div.
 */
async function fetchAndRender(apiUrl, containerId, brands) {
  const el = document.getElementById(containerId);
  if (!el) return;

  try {
    el.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:200px;color:rgba(255,255,255,0.3);font-family:\'DM Mono\',monospace;font-size:13px">Loading chart...</div>';
    const fig = await fetchJSON(apiUrl, brands || State.selectedBrands);

    // Apply dark background overrides
    if (fig.layout) {
      fig.layout.paper_bgcolor = "rgba(0,0,0,0)";
      fig.layout.plot_bgcolor  = "rgba(15,15,26,0.8)";
      if (fig.layout.font) fig.layout.font.color = "#EDE8DA";
    }

    el.innerHTML = "";
    Plotly.newPlot(el, fig.data, fig.layout, PLOTLY_CONFIG);
  } catch (e) {
    el.innerHTML = `<div style="color:rgba(255,100,100,0.6);padding:20px;font-size:12px">Chart unavailable: ${e.message}</div>`;
    console.warn("Chart error:", apiUrl, e);
  }
}

/* ── Brand comparison table ─────────────────────────────────────────────── */

/**
 * Render all brands into the comparison table tbody.
 */
function renderComparisonTable(data) {
  const tbody = document.getElementById("comparison-tbody");
  if (!tbody) return;

  if (!data || data.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" class="loading-cell">No data found.</td></tr>';
    return;
  }

  tbody.innerHTML = data.map(row => {
    const brand = row.brand;
    const color = BRAND_COLORS[brand] || "#888";
    const sentPct = ((row.avg_sentiment || 0) * 100).toFixed(0);
    const sentColor = row.avg_sentiment >= 0.65 ? "#00E676"
                    : row.avg_sentiment >= 0.50 ? "#FFAB40" : "#FF6B6B";
    const tier = (row.price_band || "Mid-Range").toLowerCase().replace("-", " ").replace(" range", "");
    const tierClass = tier.includes("budget") ? "budget" : tier.includes("premium") || tier.includes("luxury") ? "premium" : "mid";
    const hasValueScore = row.value_score_pct !== null && row.value_score_pct !== undefined;
    const valueScore = hasValueScore ? row.value_score_pct.toFixed(0) : "—";

    return `
    <tr onclick="window.location='/brand/${encodeURIComponent(brand)}'" title="Click to view ${brand} details">
      <td>
        <div class="brand-cell">
          <span class="brand-dot" style="background:${color}"></span>
          ${brand}
        </div>
      </td>
      <td><span class="tier-badge ${tierClass}">${row.price_band || 'Mid'}</span></td>
      <td>₹${(row.avg_price || 0).toLocaleString("en-IN", {maximumFractionDigits:0})}</td>
      <td>${(row.avg_discount || 0).toFixed(1)}%</td>
      <td>${(row.avg_rating || 0).toFixed(2)}★</td>
      <td>${(row.total_review_count || 0).toLocaleString("en-IN")}</td>
      <td>
        <div class="sentiment-bar-wrap">
          <div class="sentiment-bar">
            <div class="sentiment-fill" style="width:${sentPct}%;background:${sentColor}"></div>
          </div>
          <span style="font-size:13px;color:${sentColor};font-weight:600;min-width:38px">${sentPct}%</span>
        </div>
      </td>
      <td style="font-weight:700;color:${row.value_score_pct >= 60 ? '#00E676' : row.value_score_pct >= 40 ? '#FFAB40' : '#FF6B6B'}">${valueScore}</td>
      <td><a href="/brand/${encodeURIComponent(brand)}" class="detail-btn" onclick="event.stopPropagation()">Drill →</a></td>
    </tr>`;
  }).join("");
}

/**
 * Sort brand data by column and re-render.
 */
function sortTableBy(col) {
  if (State.sortCol === col) {
    State.sortAsc = !State.sortAsc;
  } else {
    State.sortCol = col;
    State.sortAsc = false;  // Default: high to low
  }
  const sorted = [...State.brandData].sort((a, b) => {
    const va = a[col] ?? 0;
    const vb = b[col] ?? 0;
    return State.sortAsc ? va - vb : vb - va;
  });
  renderComparisonTable(sorted);
}

/* ── Product explorer cards ──────────────────────────────────────────────── */

/**
 * Render product cards in the product grid.
 */
function renderProductCards(products) {
  const grid = document.getElementById("product-grid");
  const countEl = document.getElementById("product-count");
  if (!grid) return;

  if (!products || products.length === 0) {
    grid.innerHTML = '<div class="loading-cell">No products match the current filters.</div>';
    if (countEl) countEl.textContent = "0 products";
    return;
  }

  if (countEl) countEl.textContent = `${products.length} products found`;

  grid.innerHTML = products.map(p => {
    const color = BRAND_COLORS[p.brand] || "#888";
    const slug = (p.product_title || "").replace(/\s+/g, "_");
    const sentPct = p.avg_sentiment ? ((p.avg_sentiment || 0) * 100).toFixed(0) + "%" : "";

    return `
    <a class="product-card" href="/product/${encodeURIComponent(slug)}">
      <div class="product-card-brand" style="color:${color}">${p.brand || ""}</div>
      <div class="product-card-title">${p.product_title || ""}</div>
      <div class="product-card-price">₹${(p.price || 0).toLocaleString("en-IN", {maximumFractionDigits:0})}</div>
      <div class="product-card-meta">
        <span class="cat-badge">${p.category || ""}</span>
        <span class="rating-badge">${(p.rating || 0).toFixed(1)}★</span>
        <span class="discount-badge">${(p.discount || 0).toFixed(0)}% off</span>
        ${sentPct ? `<span style="font-size:12px;color:#aaa;font-family:'DM Mono',monospace">😊 ${sentPct}</span>` : ""}
      </div>
    </a>`;
  }).join("");
}

/* ── Filter logic ────────────────────────────────────────────────────────── */

/**
 * Collect filter values from UI elements.
 */
function collectFilters() {
  return {
    minPrice: parseFloat(document.getElementById("min-price")?.value || 0),
    maxPrice: parseFloat(document.getElementById("max-price")?.value || 999999),
    minRating: parseFloat(document.getElementById("rating-filter")?.value || 0),
    category: document.getElementById("cat-filter")?.value || "",
    minSentiment: parseFloat(document.getElementById("sentiment-filter")?.value || 0),
  };
}

/**
 * Build API URL for filtered products.
 */
function buildFilterURL() {
  const params = new URLSearchParams();
  State.selectedBrands.forEach(b => params.append("brand", b));
  if (State.filters.minPrice > 0) params.set("min_price", State.filters.minPrice);
  if (State.filters.maxPrice < 20000) params.set("max_price", State.filters.maxPrice);
  if (State.filters.minRating > 0) params.set("min_rating", State.filters.minRating);
  if (State.filters.category) params.set("category", State.filters.category);
  if (State.filters.minSentiment > 0) params.set("min_sentiment", State.filters.minSentiment);
  return "/api/filter?" + params.toString();
}

/**
 * Apply all filters and refresh products + charts.
 */
async function applyFilters() {
  State.filters = collectFilters();

  // Refresh products
  try {
    const products = await fetch(buildFilterURL()).then(r => r.json());
    renderProductCards(products);
  } catch (e) {
    console.warn("Product filter error:", e);
  }

  // Reload all charts with current brand filter
  loadAllCharts();
}

/**
 * Reset all filters to defaults.
 */
function resetFilters() {
  document.getElementById("min-price").value = 0;
  document.getElementById("max-price").value = 20000;
  document.getElementById("rating-filter").value = 0;
  document.getElementById("cat-filter").value = "";
  State.filters = { minPrice: 0, maxPrice: 20000, minRating: 0, category: "", minSentiment: 0 };
  State.selectedBrands = [];
  document.querySelectorAll(".brand-pill").forEach(p => {
    p.classList.toggle("active", p.dataset.brand === "all");
  });
  loadAllCharts();
  applyFilters();
}

/* ── Chart loading ───────────────────────────────────────────────────────── */

/**
 * Load all charts (called on init and after filter changes).
 */
function loadAllCharts() {
  const brandParam = State.selectedBrands;
  const charts = [
    ["/api/chart/price_rating",  "plot-price-rating"],
    ["/api/chart/brand_price",   "plot-brand-price"],
    ["/api/chart/discount",      "plot-discount"],
    ["/api/chart/sentiment",     "plot-sentiment"],
    ["/api/chart/review_count",  "plot-reviews"],
    ["/api/chart/value_score",   "plot-value"],
    ["/api/chart/aspect_sentiment", "plot-aspect"],
    ["/api/chart/price_box",     "plot-box"],
  ];

  charts.forEach(([url, id]) => {
    if (document.getElementById(id)) {
      fetchAndRender(url, id, brandParam);
    }
  });
}

/* ── Brand pill toggle ───────────────────────────────────────────────────── */

function setupBrandPills() {
  document.querySelectorAll(".brand-pill").forEach(pill => {
    pill.addEventListener("click", () => {
      const brand = pill.dataset.brand;

      if (brand === "all") {
        State.selectedBrands = [];
        document.querySelectorAll(".brand-pill").forEach(p => {
          p.classList.toggle("active", p.dataset.brand === "all");
        });
      } else {
        // Toggle this brand
        const idx = State.selectedBrands.indexOf(brand);
        if (idx >= 0) {
          State.selectedBrands.splice(idx, 1);
          pill.classList.remove("active");
        } else {
          State.selectedBrands.push(brand);
          pill.classList.add("active");
        }
        // Remove "all" active state
        document.querySelector('.brand-pill[data-brand="all"]')?.classList.remove("active");
        // If nothing selected, re-enable "all"
        if (State.selectedBrands.length === 0) {
          document.querySelector('.brand-pill[data-brand="all"]')?.classList.add("active");
        }
      }

      loadAllCharts();
      applyFilters();
    });
  });
}

/* ── Table sort headers ──────────────────────────────────────────────────── */

function setupTableSort() {
  const headers = document.querySelectorAll(".comparison-table thead th");
  const colMap = {
    "Avg Price ↕": "avg_price",
    "Avg Discount ↕": "avg_discount",
    "Avg Rating ↕": "avg_rating",
    "Reviews ↕": "total_review_count",
    "Sentiment ↕": "avg_sentiment",
    "Value Score ↕": "value_score_pct",
  };
  headers.forEach(th => {
    const col = colMap[th.textContent.trim()];
    if (col) {
      th.addEventListener("click", () => sortTableBy(col));
    }
  });
}

/* ── Initialisation ──────────────────────────────────────────────────────── */

async function init() {
  // Load brand comparison data
  try {
    State.brandData = await fetchJSON("/api/brands");
    renderComparisonTable(State.brandData);
  } catch (e) {
    console.warn("Brand data load error:", e);
  }

  // Load initial product list
  try {
    const products = await fetch("/api/filter").then(r => r.json());
    renderProductCards(products);
  } catch (e) {
    console.warn("Product load error:", e);
  }

  // Load all charts
  loadAllCharts();

  // Wire up controls
  setupBrandPills();
  setupTableSort();

  document.getElementById("apply-filters")?.addEventListener("click", applyFilters);
  document.getElementById("reset-filters")?.addEventListener("click", resetFilters);
}

// DOMContentLoaded guard
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}

// Expose for brand.html usage
window.fetchAndRender = fetchAndRender;