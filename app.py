import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

# ----------------------------------------------------------------------------
# PAGE CONFIG
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="Retail Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_DIR = Path(__file__).parent / "data"

# ----------------------------------------------------------------------------
# DATA LOADING
# ----------------------------------------------------------------------------
@st.cache_data
def load_data():
    products = pd.read_csv(DATA_DIR / "products.csv")
    orders = pd.read_csv(DATA_DIR / "orders.csv", parse_dates=["order_date"])
    customers = pd.read_csv(DATA_DIR / "customers.csv", parse_dates=["signup_date"])
    order_items = pd.read_csv(DATA_DIR / "order_items.csv")

    # Build a fully joined fact table (one row per order item)
    fact = (
        order_items
        .merge(orders, on="order_id", how="left")
        .merge(products, on="product_id", how="left")
        .merge(customers, on="customer_id", how="left")
    )
    fact["gross_amount"] = fact["quantity"] * fact["unit_price"]
    fact["discount_amount"] = fact["gross_amount"] * fact["discount"]
    fact["net_revenue"] = fact["gross_amount"] - fact["discount_amount"]
    fact["order_month"] = fact["order_date"].dt.to_period("M").dt.to_timestamp()
    fact["order_year"] = fact["order_date"].dt.year
    fact["days_since_signup"] = (fact["order_date"] - fact["signup_date"]).dt.days
    return products, orders, customers, order_items, fact

products, orders, customers, order_items, fact_all = load_data()

# ----------------------------------------------------------------------------
# SIDEBAR FILTERS
# ----------------------------------------------------------------------------
st.sidebar.title("🔎 Filters")

min_date, max_date = fact_all["order_date"].min(), fact_all["order_date"].max()
date_range = st.sidebar.date_input(
    "Order date range",
    value=(min_date.date(), max_date.date()),
    min_value=min_date.date(),
    max_value=max_date.date(),
)
if len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_date.date(), max_date.date()

regions = st.sidebar.multiselect(
    "Region", sorted(fact_all["region"].dropna().unique()), default=None
)
categories = st.sidebar.multiselect(
    "Category", sorted(fact_all["category"].dropna().unique()), default=None
)
segments = st.sidebar.multiselect(
    "Customer Segment", sorted(fact_all["segment"].dropna().unique()), default=None
)
statuses = st.sidebar.multiselect(
    "Order Status", sorted(fact_all["order_status"].dropna().unique()), default=None
)

fact = fact_all[
    (fact_all["order_date"].dt.date >= start_date)
    & (fact_all["order_date"].dt.date <= end_date)
].copy()

if regions:
    fact = fact[fact["region"].isin(regions)]
if categories:
    fact = fact[fact["category"].isin(categories)]
if segments:
    fact = fact[fact["segment"].isin(segments)]
if statuses:
    fact = fact[fact["order_status"].isin(statuses)]

st.sidebar.markdown("---")
st.sidebar.caption(f"Rows in view: **{len(fact):,}** of {len(fact_all):,}")
st.sidebar.caption("Data: products.csv · orders.csv · customers.csv · order_items.csv")

if fact.empty:
    st.warning("No data matches the current filters. Please widen your filter selection.")
    st.stop()

# ----------------------------------------------------------------------------
# HEADER + KPIs  (Solution 1)
# ----------------------------------------------------------------------------
st.title("📊 Retail Analytics Dashboard")
st.caption("15 analytical solutions built from products, orders, customers & order-items data")

total_revenue = fact["net_revenue"].sum()
total_orders = fact["order_id"].nunique()
total_customers = fact["customer_id"].nunique()
aov = total_revenue / total_orders if total_orders else 0
total_units = fact["quantity"].sum()
cancel_rate = (
    fact.loc[fact["order_status"] == "Cancelled", "order_id"].nunique() / total_orders * 100
    if total_orders else 0
)

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Net Revenue", f"₹{total_revenue:,.0f}")
k2.metric("Orders", f"{total_orders:,}")
k3.metric("Customers", f"{total_customers:,}")
k4.metric("Avg Order Value", f"₹{aov:,.0f}")
k5.metric("Units Sold", f"{total_units:,}")
k6.metric("Cancellation Rate", f"{cancel_rate:,.1f}%")

st.markdown("---")

tabs = st.tabs(
    ["📈 Sales & Trends", "🛒 Products", "🌍 Regions & Fulfillment", "👥 Customers", "🧮 Deep Dives"]
)

# ----------------------------------------------------------------------------
# TAB 1: SALES & TRENDS
# ----------------------------------------------------------------------------
with tabs[0]:

    # Solution 2: Monthly revenue trend
    st.subheader("1. Monthly Revenue & Order Trend")
    monthly = fact.groupby("order_month").agg(
        revenue=("net_revenue", "sum"), orders=("order_id", "nunique")
    ).reset_index()
    fig = go.Figure()
    fig.add_bar(x=monthly["order_month"], y=monthly["revenue"], name="Revenue (₹)", marker_color="#4C78A8")
    fig.add_trace(go.Scatter(x=monthly["order_month"], y=monthly["orders"], name="Orders",
                              yaxis="y2", mode="lines+markers", line=dict(color="#F58518")))
    fig.update_layout(
        yaxis=dict(title="Revenue (₹)"),
        yaxis2=dict(title="Orders", overlaying="y", side="right"),
        legend=dict(orientation="h", y=1.1), height=420,
    )
    st.plotly_chart(fig, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        # Solution 3: Average order value trend
        st.subheader("2. Average Order Value Over Time")
        aov_trend = fact.groupby("order_month").apply(
            lambda d: d["net_revenue"].sum() / d["order_id"].nunique()
        ).reset_index(name="aov")
        fig2 = px.line(aov_trend, x="order_month", y="aov", markers=True,
                        labels={"order_month": "Month", "aov": "AOV (₹)"})
        fig2.update_traces(line_color="#54A24B")
        st.plotly_chart(fig2, use_container_width=True)

    with c2:
        # Solution 4: Order status breakdown
        st.subheader("3. Order Status Breakdown")
        status_counts = fact.drop_duplicates("order_id")["order_status"].value_counts().reset_index()
        status_counts.columns = ["order_status", "count"]
        fig3 = px.pie(status_counts, names="order_status", values="count", hole=0.5,
                       color="order_status",
                       color_discrete_map={"Delivered": "#54A24B", "Processing": "#F58518",
                                           "Shipped": "#4C78A8", "Cancelled": "#E45756"})
        st.plotly_chart(fig3, use_container_width=True)

    # Solution 5: Weekday sales pattern
    st.subheader("4. Sales Pattern by Day of Week")
    dow = fact.copy()
    dow["weekday"] = dow["order_date"].dt.day_name()
    order_dow = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    dow_rev = dow.groupby("weekday")["net_revenue"].sum().reindex(order_dow).reset_index()
    fig4 = px.bar(dow_rev, x="weekday", y="net_revenue", color="net_revenue",
                   color_continuous_scale="Blues", labels={"net_revenue": "Revenue (₹)", "weekday": ""})
    st.plotly_chart(fig4, use_container_width=True)

# ----------------------------------------------------------------------------
# TAB 2: PRODUCTS
# ----------------------------------------------------------------------------
with tabs[1]:

    c1, c2 = st.columns(2)
    with c1:
        # Solution 6: Revenue by category
        st.subheader("5. Revenue by Category")
        cat_rev = fact.groupby("category")["net_revenue"].sum().sort_values(ascending=False).reset_index()
        fig5 = px.bar(cat_rev, x="net_revenue", y="category", orientation="h", color="net_revenue",
                       color_continuous_scale="Teal", labels={"net_revenue": "Revenue (₹)", "category": ""})
        fig5.update_layout(yaxis=dict(categoryorder="total ascending"))
        st.plotly_chart(fig5, use_container_width=True)

    with c2:
        # Solution 7: Top 10 sub-categories
        st.subheader("6. Top 10 Sub-Categories by Revenue")
        subcat_rev = fact.groupby("sub_category")["net_revenue"].sum().sort_values(ascending=False).head(10).reset_index()
        fig6 = px.bar(subcat_rev, x="net_revenue", y="sub_category", orientation="h", color="net_revenue",
                       color_continuous_scale="Purples", labels={"net_revenue": "Revenue (₹)", "sub_category": ""})
        fig6.update_layout(yaxis=dict(categoryorder="total ascending"))
        st.plotly_chart(fig6, use_container_width=True)

    # Solution 8: Top-selling products table
    st.subheader("7. Top 10 Best-Selling Products")
    prod_perf = fact.groupby(["product_id", "product_name", "category"]).agg(
        units_sold=("quantity", "sum"),
        revenue=("net_revenue", "sum"),
        orders=("order_id", "nunique"),
    ).sort_values("revenue", ascending=False).head(10).reset_index()
    prod_perf["revenue"] = prod_perf["revenue"].round(0)
    st.dataframe(prod_perf, use_container_width=True, hide_index=True)

    c3, c4 = st.columns(2)
    with c3:
        # Solution 9: Discount vs revenue impact
        st.subheader("8. Discount Level vs Revenue")
        fact["discount_band"] = pd.cut(
            fact["discount"], bins=[-0.01, 0, 0.1, 0.2, 0.3, 1],
            labels=["0%", "1-10%", "11-20%", "21-30%", "30%+"]
        )
        disc_band = fact.groupby("discount_band", observed=True).agg(
            revenue=("net_revenue", "sum"), units=("quantity", "sum")
        ).reset_index()
        fig7 = px.bar(disc_band, x="discount_band", y="revenue", color="units",
                       color_continuous_scale="Oranges",
                       labels={"discount_band": "Discount Band", "revenue": "Revenue (₹)"})
        st.plotly_chart(fig7, use_container_width=True)

    with c4:
        # Solution 10: Category x Region heatmap
        st.subheader("9. Category × Region Revenue Heatmap")
        heat = fact.pivot_table(index="category", columns="region", values="net_revenue", aggfunc="sum", fill_value=0)
        fig8 = px.imshow(heat, text_auto=".0f", aspect="auto", color_continuous_scale="Blues",
                          labels=dict(color="Revenue (₹)"))
        st.plotly_chart(fig8, use_container_width=True)

# ----------------------------------------------------------------------------
# TAB 3: REGIONS & FULFILLMENT
# ----------------------------------------------------------------------------
with tabs[2]:

    c1, c2 = st.columns(2)
    with c1:
        # Solution 11: Revenue by region
        st.subheader("10. Revenue & Orders by Region")
        reg = fact.groupby("region").agg(
            revenue=("net_revenue", "sum"), orders=("order_id", "nunique")
        ).reset_index().sort_values("revenue", ascending=False)
        fig9 = px.bar(reg, x="region", y="revenue", color="orders", text_auto=".2s",
                       color_continuous_scale="Viridis", labels={"revenue": "Revenue (₹)"})
        st.plotly_chart(fig9, use_container_width=True)

    with c2:
        # Solution 12: Ship mode distribution & performance
        st.subheader("11. Ship Mode Usage & Revenue")
        ship = fact.groupby("ship_mode").agg(
            revenue=("net_revenue", "sum"), orders=("order_id", "nunique")
        ).reset_index()
        fig10 = px.bar(ship, x="ship_mode", y="orders", color="ship_mode",
                        labels={"ship_mode": "Ship Mode", "orders": "Orders"})
        st.plotly_chart(fig10, use_container_width=True)

    # Solution 13: State-wise revenue (top 10 states)
    st.subheader("12. Top 10 States by Revenue")
    state_rev = fact.groupby("state")["net_revenue"].sum().sort_values(ascending=False).head(10).reset_index()
    fig11 = px.bar(state_rev, x="state", y="net_revenue", color="net_revenue",
                    color_continuous_scale="Sunset", labels={"net_revenue": "Revenue (₹)", "state": ""})
    st.plotly_chart(fig11, use_container_width=True)

    # Solution 14: Order status by region (stacked)
    st.subheader("13. Order Status Composition by Region")
    status_region = fact.drop_duplicates("order_id").groupby(["region", "order_status"]).size().reset_index(name="count")
    fig12 = px.bar(status_region, x="region", y="count", color="order_status", barmode="stack",
                    color_discrete_map={"Delivered": "#54A24B", "Processing": "#F58518",
                                        "Shipped": "#4C78A8", "Cancelled": "#E45756"})
    st.plotly_chart(fig12, use_container_width=True)

# ----------------------------------------------------------------------------
# TAB 4: CUSTOMERS
# ----------------------------------------------------------------------------
with tabs[3]:

    c1, c2 = st.columns(2)
    with c1:
        # Solution 15: Revenue by segment
        st.subheader("14. Revenue by Customer Segment")
        seg_rev = fact.groupby("segment")["net_revenue"].sum().reset_index()
        fig13 = px.pie(seg_rev, names="segment", values="net_revenue", hole=0.4)
        st.plotly_chart(fig13, use_container_width=True)

    with c2:
        # Solution 16: New customer signups over time
        st.subheader("15. New Customer Signups Over Time")
        cust_signup = customers.copy()
        cust_signup["signup_month"] = cust_signup["signup_date"].dt.to_period("M").dt.to_timestamp()
        signup_trend = cust_signup.groupby("signup_month").size().reset_index(name="new_customers")
        fig14 = px.area(signup_trend, x="signup_month", y="new_customers",
                         labels={"signup_month": "Month", "new_customers": "New Customers"})
        st.plotly_chart(fig14, use_container_width=True)

    # Solution 17: Top 10 customers by revenue
    st.subheader("16. Top 10 Customers by Revenue")
    top_cust = fact.groupby(["customer_id", "customer_name", "segment"]).agg(
        revenue=("net_revenue", "sum"), orders=("order_id", "nunique")
    ).sort_values("revenue", ascending=False).head(10).reset_index()
    top_cust["revenue"] = top_cust["revenue"].round(0)
    st.dataframe(top_cust, use_container_width=True, hide_index=True)

    # Solution 18: Repeat vs one-time customers
    st.subheader("17. Repeat vs One-Time Customers")
    orders_per_cust = fact.groupby("customer_id")["order_id"].nunique()
    repeat_flag = (orders_per_cust > 1).map({True: "Repeat (2+ orders)", False: "One-time"})
    repeat_summary = repeat_flag.value_counts().reset_index()
    repeat_summary.columns = ["type", "customers"]
    fig15 = px.pie(repeat_summary, names="type", values="customers", hole=0.4,
                    color_discrete_sequence=["#4C78A8", "#F58518"])
    st.plotly_chart(fig15, use_container_width=True)

# ----------------------------------------------------------------------------
# TAB 5: DEEP DIVES
# ----------------------------------------------------------------------------
with tabs[4]:

    # Solution 19: Product price vs units-sold scatter
    st.subheader("18. Unit Price vs Units Sold (by Product)")
    price_qty = fact.groupby(["product_name", "category"]).agg(
        unit_price=("unit_price", "mean"), units_sold=("quantity", "sum"),
        revenue=("net_revenue", "sum")
    ).reset_index()
    fig16 = px.scatter(price_qty, x="unit_price", y="units_sold", size="revenue", color="category",
                        hover_name="product_name",
                        labels={"unit_price": "Unit Price (₹)", "units_sold": "Units Sold"})
    st.plotly_chart(fig16, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        # Solution 20: Discount rate by category
        st.subheader("19. Average Discount Rate by Category")
        disc_cat = fact.groupby("category")["discount"].mean().sort_values(ascending=False).reset_index()
        disc_cat["discount"] = (disc_cat["discount"] * 100).round(1)
        fig17 = px.bar(disc_cat, x="category", y="discount", color="discount",
                        color_continuous_scale="Reds", labels={"discount": "Avg Discount (%)"})
        st.plotly_chart(fig17, use_container_width=True)

    with c2:
        # Solution 21: Days-to-first-purchase distribution (signup to order)
        st.subheader("20. Days from Signup to Order")
        gap = fact.loc[fact["days_since_signup"] >= 0, "days_since_signup"]
        fig18 = px.histogram(gap, nbins=30, labels={"value": "Days since signup"})
        fig18.update_layout(showlegend=False)
        st.plotly_chart(fig18, use_container_width=True)

    # Explorable raw fact table
    st.subheader("21. Explore the Filtered Data")
    st.dataframe(
        fact[["order_id", "order_date", "customer_name", "segment", "region", "product_name",
              "category", "quantity", "unit_price", "discount", "net_revenue", "order_status"]]
        .sort_values("order_date", ascending=False),
        use_container_width=True, hide_index=True, height=350
    )

st.markdown("---")
st.caption("Built with Streamlit · Data covers " + f"{min_date.date()} to {max_date.date()}")
