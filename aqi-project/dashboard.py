import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
import socket
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split
import datetime

# -----------------------------
# Page config
# -----------------------------
st.set_page_config(page_title="AQI Dashboard", layout="wide")
st.title("🌍 Real-Time AQI Monitoring Dashboard")

# -----------------------------
# DB Connection
# -----------------------------
socket.setdefaulttimeout(30)

@st.cache_resource
def get_connection():
    return psycopg2.connect(
        "postgresql://postgres.oxcycpqjisgegrhewdov:AiS%23u2%29jkfty@aws-1-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require"
    )

conn = get_connection()

# -----------------------------
# Load Data
# -----------------------------
query = "SELECT * FROM aqi_data ORDER BY timestamp"
df = pd.read_sql(query, conn)
df["timestamp"] = pd.to_datetime(df["timestamp"])

# --- DATA SANITIZATION LOGIC (The Outlier Shield) ---
total_rows_before = len(df)

# Filter out corrupted sensor readings (like the 393,000°C Hyderabad glitch)
df = df[(df['temperature'] >= -10) & (df['temperature'] <= 60)]
df = df[(df['humidity'] >= 0) & (df['humidity'] <= 100)]
df = df[df['overall_aqi'] <= 500] # Standard atmospheric limit

total_rows_after = len(df)
rows_removed = total_rows_before - total_rows_after

# remove unwanted columns
df = df.drop(columns=["co", "so2", "o3"], errors="ignore")

# -----------------------------
# ML Helper Functions
# -----------------------------
def create_sliding_window_multivariate(data_array, window_size=5):
    X, y = [], []
    for i in range(len(data_array) - window_size):
        window = data_array[i:i+window_size].flatten() 
        X.append(window)
        y.append(data_array[i+window_size, 0]) 
    return np.array(X), np.array(y)

def generate_7day_forecast(df_input):
    df_f = df_input.copy().sort_values("timestamp")
    cols = ['overall_aqi', 'temperature', 'humidity']
    
    if not all(col in df_f.columns for col in cols) or len(df_f) < 20:
        return pd.DataFrame(), 0.0

    data_values = df_f[cols].values.astype(float)
    window_size = 5
    X, y = create_sliding_window_multivariate(data_values, window_size)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    mae = mean_absolute_error(y_test, model.predict(X_test))

    model.fit(X, y)
    current_window_data = data_values[-window_size:]
    predictions = []
    avg_temp, avg_hum = df_f['temperature'].tail(7).mean(), df_f['humidity'].tail(7).mean()

    for _ in range(7):
        input_row = current_window_data.flatten().reshape(1, -1)
        pred_aqi = model.predict(input_row)[0]
        # Add a tiny bit of variation to prevent flat lines
        variation = np.random.uniform(-1.5, 1.5)
        final_pred = int(pred_aqi + variation)
        predictions.append(final_pred)
        
        next_step_data = np.array([[final_pred, avg_temp, avg_hum]])
        current_window_data = np.vstack([current_window_data[1:], next_step_data])

    last_date = pd.to_datetime(df_f['timestamp'].iloc[-1])
    forecast_df = pd.DataFrame({
        'Date': [last_date + pd.Timedelta(days=i) for i in range(1, 8)],
        'Predicted AQI': predictions
    })
    forecast_df['Status'] = forecast_df['Predicted AQI'].apply(lambda x: classify_aqi(x)[0])
    return forecast_df, mae

def classify_aqi(aqi):
    if aqi <= 50: return "Good 🟢", "#2ecc71"
    elif aqi <= 100: return "Moderate 🟡", "#f1c40f"
    elif aqi <= 200: return "Unhealthy 🟠", "#e67e22"
    else: return "Hazardous 🔴", "#e74c3c"

# -----------------------------
# Main UI - Live Cards
# -----------------------------
st.subheader("Live AQI Status")
latest = df.sort_values("timestamp").groupby("city").tail(1)
cols_cards = st.columns(len(latest))

for i, (_, row) in enumerate(latest.iterrows()):
    category, color = classify_aqi(row["overall_aqi"])
    with cols_cards[i]:
        st.markdown(f"""<div style="background-color:{color};padding:20px;border-radius:10px;text-align:center;color:white;">
            <b>{row['city']}</b><br>AQI: {row['overall_aqi']}<br>{category}</div>""", unsafe_allow_html=True)

# -----------------------------
# Tables & Trends
# -----------------------------
st.subheader("📊 Latest AQI by City")
st.dataframe(latest, use_container_width=True)

st.subheader("AQI Trend (All Cities)")
st.line_chart(df.groupby("timestamp")["overall_aqi"].mean())

# -----------------------------
# City Analysis Section
# -----------------------------
st.subheader("📈 City-Specific Historical Trend")
city_choice = st.selectbox("Select City for History", sorted(df["city"].unique()))
city_data = df[df["city"] == city_choice]
st.plotly_chart(px.line(city_data, x="timestamp", y="overall_aqi", title=f"History: {city_choice}"))

# -----------------------------
# Scientific Analysis (Scatter Plots)
# -----------------------------
st.subheader("📊 Atmospheric Correlation Analysis")
view_option = st.radio("Data Range", ["All Historical Data", "Today Only"], horizontal=True)
plot_df = df[df['timestamp'].dt.date == datetime.date.today()] if view_option == "Today Only" else df

col_p1, col_p2 = st.columns(2)
with col_p1:
    fig_temp = px.scatter(plot_df, x="temperature", y="overall_aqi", color="city", opacity=0.5, trendline="ols", title="Temp vs AQI")
    st.plotly_chart(fig_temp, use_container_width=True)

with col_p2:
    fig_hum = px.scatter(plot_df, x="humidity", y="overall_aqi", color="city", opacity=0.5, trendline="ols", title="Humidity vs AQI")
    st.plotly_chart(fig_hum, use_container_width=True)

# -----------------------------
# Forecasting Section
# -----------------------------
st.markdown("---")
st.subheader("🔮 7-Day Predictive Forecast")
forecast_city = st.selectbox("Select City for Forecast", sorted(df["city"].unique()))
forecast_df_input = df[df["city"] == forecast_city]

if st.button("Generate Forecast"):
    forecast_data, model_mae = generate_7day_forecast(forecast_df_input)
    if not forecast_data.empty:
        m1, m2, m3 = st.columns(3)
        m1.metric("City", forecast_city)
        m2.metric("Model MAE", f"{model_mae:.2f}")
        m3.metric("Model", "Multivariate RF")
        
        st.dataframe(forecast_data, use_container_width=True, hide_index=True)
        fig_f = px.line(forecast_data, x='Date', y='Predicted AQI', markers=True, text='Status', title=f"Forecast Trend: {forecast_city}")
        st.plotly_chart(fig_f, use_container_width=True)

# -----------------------------
# Data Health Report (The Footer)
# -----------------------------
st.markdown("---")
with st.expander("🛠️ Data Pipeline Health Report"):
    c_h1, c_h2, c_h3 = st.columns(3)
    c_h1.metric("Healthy Records", total_rows_after)
    c_h2.metric("Corrupt Data Blocked", rows_removed, delta_color="inverse")
    integrity = (total_rows_after / total_rows_before * 100) if total_rows_before > 0 else 0
    c_h3.metric("Data Integrity Score", f"{integrity:.1f}%")
    if rows_removed > 0:
        st.info(f"Filtered {rows_removed} anomalous readings from corrupted sensors.")

st.caption("Developed by Moravaneni Aiswarya Lakshmi | CSE (Data Science)")
