# -*- coding: utf-8 -*-
"""
Created on Mon Jun 29 11:42:46 2026

@author: Areeba.Irfan
"""

# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd
import streamlit_authenticator as stauth
import plotly.express as px
import google.generativeai as genai
import mysql.connector  # Make sure this is installed: pip install mysql-connector-python

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(
    page_title="AI Inventory Dashboard",
    layout="wide"
)

# =========================
# LOAD DATA FROM MYSQL (UPDATED)
# =========================
@st.cache_data(ttl=600)  # 10 minutes tak data cache rahega taake performance fast ho
def load_data_from_db():
    try:
        conn = mysql.connector.connect(
            host="S049BWNSDEV.sami.local",
            user="sapdwh_etl",
            password="Sap@1234",
            database="samibiapps_dw"
        )
        
        if conn.is_connected():
            query = "SELECT * FROM samibiapps_dw.Stock_Data;"
            # pd.read_sql use karne se fetchall aur column names ka manual jhanjhat khatam ho jata hai
            data = pd.read_sql(query, conn)
            conn.close()
            
            # Column cleaning (purane code ki tarah)
            data.columns = data.columns.str.strip().str.lower().str.replace(" ", "_")
            return data
    except Exception as e:
        st.error(f"❌ Database Connection Error: {e}")
        st.stop()

# Data load ho raha hai
df = load_data_from_db()

THRESHOLD = 15



# =========================
# CUSTOM CSS
# =========================
st.markdown("""
<style>
.block-container { padding-top: 1rem; padding-left: 1rem; padding-right: 1rem; }
h1 { font-size: 32px !important; }
.kpi-container { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; width: 100%; }
.kpi-card { background: #5F8B94; padding: 15px 10px; border-radius: 12px; text-align: center; box-shadow: 0px 2px 8px rgba(0,0,0,0.08); }
.kpi-title { font-size: 16px; font-weight: 600; color: #CACBCA; white-space: nowrap; }
.kpi-value { font-size: 28px; font-weight: bold; color: #FFFFFF; margin-top: 5px; }
@media (max-width: 768px) {
    .kpi-container { grid-template-columns: repeat(2, 1fr) !important; gap: 8px; }
    .kpi-title { font-size: 13px; }
    .kpi-value { font-size: 22px; }
}
</style>
""", unsafe_allow_html=True)

# =========================
# AUTH CONFIG (FROM SECRETS)
# =========================
try:
    cookie_data = dict(st.secrets["cookie"])
    raw_usernames = st.secrets["credentials"]["usernames"]
    
    credentials_data = {"usernames": {}}

    for username, user_info in raw_usernames.items():
        credentials_data["usernames"][username] = {
            "name": str(user_info["name"]),
            "password": str(user_info["password"])
        }
        
        current_password = credentials_data["usernames"][username]["password"]
        if not current_password.startswith("$2b$"):
            credentials_data["usernames"][username]["password"] = stauth.Hasher().hash(current_password)

    authenticator = stauth.Authenticate(
        credentials_data,
        cookie_data["name"],
        cookie_data["key"],
        int(cookie_data["expiry_days"])
    )

except KeyError as e:
    st.error(f"❌ Streamlit Secrets mein authentication data missing hai: {e}")
    st.stop()
except Exception as e:
    st.error(f"❌ Authentication setup mein error: {e}")
    st.stop()

# =========================
# LOGIN FORM
# =========================
authenticator.login(location="main")

name = st.session_state.get("name")
auth_status = st.session_state.get("authentication_status")

# =========================
# LOGIN HANDLING
# =========================
if auth_status is False:
    st.error("❌ Wrong username or password")

elif auth_status is None:
    st.warning("🔐 Please login first")

elif auth_status:

    # =========================
    # SIDEBAR
    # =========================
    with st.sidebar:
        st.success(f"Welcome {name}")
        authenticator.logout("Logout")

    # =========================
    # KPI CALCULATIONS
    # =========================
    total_products = df["product_name"].nunique() if "product_name" in df.columns else 0
    total_stock = df["fresh_stock"].sum() if "fresh_stock" in df.columns else 0
    low_stock = df[df["fresh_stock"] <= THRESHOLD].shape[0] if "fresh_stock" in df.columns else 0
    out_stock = df[df["fresh_stock"] == 0].shape[0] if "fresh_stock" in df.columns else 0

    # =========================
    # KPI UI
    # =========================
    st.markdown(f"""
    <div class="kpi-container">
        <div class="kpi-card">
            <div class="kpi-title">📦 Products</div>
            <div class="kpi-value">{total_products:,}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">📊 Total Stock</div>
            <div class="kpi-value">{int(total_stock):,}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">⚠️ Low Stock</div>
            <div class="kpi-value">{low_stock:,}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">🚫 Out Of Stock</div>
            <div class="kpi-value">{out_stock:,}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # =========================
    # EXTENDED LOCAL EXPERT ENGINE (WITHOUT API)
    # =========================
    def local_analytics_assistant(query, data):
        q = query.lower().strip()
        
        # ----------------------------------------------------
        # Q1: PRODUCT COMPARISON (English & Roman English)
        # Keywords: compare, achi hai, behtar hai, vs
        # ----------------------------------------------------
        if any(x in q for x in ["compare", "vs", "achi hai", "behtar hai", "muqabla","kisi bhi do products ka comparison","comparison of two products"]):
            # Filter products mentioned in the query
            matched_products = []
            for _, row in data.iterrows():
                if row['product_name'].lower() in q:
                    matched_products.append(row)
            
            if len(matched_products) >= 2:
                p1, p2 = matched_products[0], matched_products[1]
                s1, s2 = int(p1['fresh_stock']), int(p2['fresh_stock'])
                
                comparison = f"⚖️ **Comparison Between {p1['product_name']} & {p2['product_name']}:**\n\n"
                comparison += f"* **{p1['product_name']}:** Current Stock is **{s1}**\n"
                comparison += f"* **{p2['product_name']}:** Current Stock is **{s2}**\n\n"
                
                if s1 > s2:
                    comparison += f"🏆 **Result:** **{p1['product_name']}** ki inventory position zyada behtar aur stable hai."
                elif s2 > s1:
                    comparison += f"🏆 **Result:** **{p2['product_name']}** ki inventory position zyada behtar aur stable hai."
                else:
                    comparison += "🏆 **Result:** Dono products ka stock barabar hai!"
                return comparison
            else:
                return "🔍 Please type the exact names of at least 2 products to compare. (e.g., *Compare ProductA and ProductB*)"

        # ----------------------------------------------------
        # Q2: SALES PREDICTION / FORECASTING
        # Keywords: next month, next year, sale hogi, demand, future
        # ----------------------------------------------------
        elif any(x in q for x in ["next month", "next year", "sale hogi", "sale hoge", "demand prediction", "future prediction", "aglay mahine"]):
            # Business Logic: Top 3 products with maximum stock are prepared for upcoming high demands
            top_3 = data.sort_values(by="fresh_stock", ascending=False).head(3)
            
            forecast = "🔮 **Future Sale & Demand Forecast:**\n\n"
            forecast += "Based on current inventory data analytics, yeh products next month/year zyada sale hone ke trends dikha rahi hain (due to strong supply and availability):\n\n"
            for idx, row in top_3.iterrows():
                forecast += f"{idx+1}. **{row['product_name']}** (Current Stock: {int(row['fresh_stock'])})\n"
            forecast += "\n💡 *Suggestion:* Maintain aggressive marketing for these items as they have the highest fulfillment rate."
            return forecast

        # ----------------------------------------------------
        # MAZEED ADDED QUESTION: HEALTHY STOCK ITEMS
        # Keywords: safe, healthy, good stock, behtareen stock
        # ----------------------------------------------------
        elif any(x in q for x in ["healthy", "safe", "good stock", "sahi stock", "fit stock"]):
            healthy_df = data[data["fresh_stock"] > THRESHOLD]
            return f"✅ Warehouse mein is waqt **{len(healthy_df)}** products aisi hain jinka stock perfectly healthy aur safe zone mein hai."

        # ----------------------------------------------------
        # MAZEED ADDED QUESTION: CRITICAL SUMMARY
        # Keywords: summary, report, halat, status
        # ----------------------------------------------------
        elif any(x in q for x in ["summary", "report", "halat", "status"]):
            return f"""📋 **Warehouse Status Summary Report:**
* Total Product Varieties: **{total_products}**
* Total Items in Hand: **{int(total_stock):,}**
* Critical Alerts (Out of Stock): **{out_stock}** items are completely empty!
* Reorder Urgent (Low Stock): **{low_stock}** items need restocking immediately."""

        # ----------------------------------------------------
        # PREVIOUS STANDARD QUESTIONS
        # ----------------------------------------------------
        elif any(x in q for x in ["out of stock", "khatam", "zero"]):
            oos_df = data[data["fresh_stock"] == 0]
            if oos_df.empty:
                return "🎉 Koi bhi item out of stock nahi hai! Sab maujood hain."
            items = ", ".join(oos_df["product_name"].tolist())
            return f"🚫 **Out of Stock Items ({len(oos_df)}):**\n\n{items}"
            
        elif any(x in q for x in ["low stock", "kam stock", "warning"]):
            low_df = data[(data["fresh_stock"] <= THRESHOLD) & (data["fresh_stock"] > 0)]
            if low_df.empty:
                return "✅ Sab items ka stock healthy hai. Koi low stock nahi hai."
            response = f"⚠️ **Low Stock Items (Stock ≤ {THRESHOLD}):**\n\n"
            for _, row in low_df.iterrows():
                response += f"* {row['product_name']}: **{int(row['fresh_stock'])}** remaining\n"
            return response

        elif any(x in q for x in ["highest", "sabse zyada", "max"]):
            highest_row = data.sort_values(by="fresh_stock", ascending=False).iloc[0]
            return f"📈 Warehouse mein sabse zyada stock **{highest_row['product_name']}** ka hai. Iska total stock **{int(highest_row['fresh_stock']):,}** hai."

        elif any(x in q for x in ["total stock", "kul stock", "stock kitna hai"]):
            total_sum = data["fresh_stock"].sum()
            return f"📊 Warehouse mein is waqt kul mila kar **{int(total_sum):,}** items ka stock maujood hai."

        elif any(x in q for x in ["stock of", "check", "kitna hai"]):
            found = False
            response = ""
            for _, row in data.iterrows():
                if row['product_name'].lower() in q:
                    response += f"🔍 **{row['product_name']}** ka current stock **{int(row['fresh_stock'])}** hai.\n"
                    found = True
            if found:
                return response

        # Default fallback response if keywords don't match
        return """🤖 **Local Analytics Bot:** Main aapka sawal samajh nahi paya. Aap mujhse yeh cheezain pooch sakte hain:
* *Compare [Product A] and [Product B]* (Dono mein se konsi achi hai)
* *Which product will sell more next month/year?* (Konsi zyada sale hogi)
* *Give me a warehouse summary.* (Poori halat/report batayein)
* *Which items are out of stock / low stock?*
* *What is the stock of [Product Name]?*"""

    # =========================
    # SMART LOCAL CHATBOT UI
    # =========================
    st.subheader("🤖 Smart Analytics Assistant (Local & Free)")

    user_input = st.text_input("Ask anything about your data (e.g., Which items are out of stock? or Compare ItemA and ItemB)")

    if user_input:
        with st.spinner("Analyzing dataset locally..."):
            ai_response = local_analytics_assistant(user_input, df)
            
        st.markdown("### 💬 System Response:")
        st.write(ai_response)

    st.divider()

    # =========================
    # DASHBOARD 
    # =========================
    st.subheader("📊 Dashboard")

    with st.expander("📊 View Dashboard Charts", expanded=False):
        if "fresh_stock" in df.columns and "product_name" in df.columns:
            top_10 = df.sort_values(by="fresh_stock", ascending=False).head(10)

            fig1 = px.bar(
                top_10,
                x="product_name",
                y="fresh_stock",
                color="product_name",
                title="Top 10 Products",
                text="fresh_stock" 
            )
            fig1.update_layout(height=500, xaxis_tickangle=-45, showlegend=False)
            fig1.update_traces(texttemplate='%{text:,}')
            st.plotly_chart(fig1, use_container_width=True)

            bottom_10 = df.sort_values(by="fresh_stock", ascending=True).head(10)

            fig2 = px.bar(
                bottom_10,
                x="product_name",
                y="fresh_stock",
                color="product_name",
                title="Bottom 10 Products",
                text="fresh_stock" 
            )
            fig2.update_traces(texttemplate='%{text:,}')
            fig2.update_layout(height=500, xaxis_tickangle=-45, showlegend=False)
            st.plotly_chart(fig2, use_container_width=True)

            stock_status = pd.DataFrame({
                "Status": ["Low Stock", "Healthy Stock", "Out Of Stock"],
                "Count": [
                    df[df["fresh_stock"] <= THRESHOLD].shape[0],
                    df[df["fresh_stock"] > THRESHOLD].shape[0],
                    df[df["fresh_stock"] == 0].shape[0]
                ]
            })
            
            fig3 = px.pie(stock_status, names="Status", values="Count", title="Stock Distribution")
            fig3.update_traces(texttemplate='%{value:,}', textinfo='label+value+percent')
            st.plotly_chart(fig3, use_container_width=True)

    # =========================
    # RAW DATA
    # =========================
    with st.expander("📄 View Data"):
        st.dataframe(df, use_container_width=True, height=500)
