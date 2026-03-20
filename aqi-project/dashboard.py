import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
import socket
import numpy as np
from sklearn.linear_model import LinearRegression
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
query = """
SELECT *
FROM aqi_data
ORDER BY timestamp
"""

df = pd.read_sql(query, conn)
df["timestamp"] = pd.to_datetime(df["timestamp"])

# remove unwanted columns
df = df.drop(columns=["co", "so2", "o3"], errors="ignore")


from sklearn.ensemble import RandomForestRegressor

def create_sliding_window(data, window_size=5):
    X = []
    y = []

    for i in range(len(data) - window_size):
        X.append(data[i:i+window_size])
        y.append(data[i+window_size])

    return np.array(X), np.array(y)

def generate_7day_forecast(df):
    df = df.copy()
    
    # Safety Check: Ensure the source column exists
    if 'overall_aqi' in df.columns:
        df['AQI'] = df['overall_aqi']
    elif 'aqi' in df.columns:
        df['AQI'] = df['aqi']
    else:
        # If neither exists, we can't proceed
        return pd.DataFrame(), 0 

    # Drop missing values and keep only valid AQI numbers
    df = df.dropna(subset=['AQI'])
    df = df[df['AQI'] > 0]
    
    # Rest of your code...
    aqi_values = df['AQI'].values
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split

def generate_7day_forecast(df):
    # 1. Create a local copy to avoid modifying the original dataframe
    df_local = df.copy()

    # 2. Robust Column Mapping: Look for any version of AQI
    if 'overall_aqi' in df_local.columns:
        df_local['AQI'] = df_local['overall_aqi']
    elif 'aqi' in df_local.columns:
        df_local['AQI'] = df_local['aqi']
    else:
        # If no AQI column is found, return empty results instead of crashing
        return pd.DataFrame(), 0.0

    # 3. Data Cleaning
    df_local = df_local.dropna(subset=['AQI'])
    df_local = df_local[df_local['AQI'] > 0]

    aqi_values = df['AQI'].values
    window_size = 5 # Looking back 5 days to predict the 6th
    
    # Create the training features (X) and target (y)
    X, y = create_sliding_window(aqi_values, window_size)
    
    # Train the model
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X, y)

    # --- START OF SLIDING FORECAST ---
    # Get the very last 5 actual days from your data to start the forecast
    current_window = aqi_values[-window_size:].reshape(1, -1)
    
    predictions = []
    for _ in range(7):
        # 1. Predict the next value
        next_val = model.predict(current_window)[0]
        predictions.append(int(next_val))
        
        # 2. Slide the window: 
        # Remove the first element and append the new prediction
        # new_window = [old_2, old_3, old_4, old_5, prediction]
        current_window = np.append(current_window[:, 1:], [[next_val]], axis=1)

    forecast_df = pd.DataFrame({
        'Date': forecast_dates,
        'Predicted AQI': predictions
    })
    
    # Apply your classification function for the 'Status' column
    forecast_df['Status'] = forecast_df['Predicted AQI'].apply(lambda x: classify_aqi(x)[0])

    return forecast_df, mae
# -----------------------------
# AQI Classification
# -----------------------------
def classify_aqi(aqi):
    if aqi <= 50:
        return "Good 🟢", "#2ecc71"
    elif aqi <= 100:
        return "Moderate 🟡", "#f1c40f"
    elif aqi <= 200:
        return "Unhealthy 🟠", "#e67e22"
    else:
        return "Hazardous 🔴", "#e74c3c"

# -----------------------------
# Live AQI Cards
# -----------------------------
st.subheader("Live AQI Status")

latest = df.sort_values("timestamp").groupby("city").tail(1)

cols = st.columns(len(latest))

for i, (_, row) in enumerate(latest.iterrows()):
    category, color = classify_aqi(row["overall_aqi"])

    with cols[i]:
        st.markdown(
            f"""
            <div style="background-color:{color};
            padding:20px;border-radius:10px;
            text-align:center;color:white;">
            <b>{row['city']}</b><br>
            AQI: {row['overall_aqi']}<br>
            {category}
            </div>
            """,
            unsafe_allow_html=True
        )

# -----------------------------
# Table
# -----------------------------
st.subheader("📊 Latest AQI by City")
st.dataframe(latest)

# alert
if not latest[latest["overall_aqi"] > 200].empty:
    st.error("⚠️ Hazardous air quality detected!")

# -----------------------------
# Trend
# -----------------------------
st.subheader("AQI Trend")
trend = df.groupby("timestamp")["overall_aqi"].mean()
st.line_chart(trend)

# -----------------------------
# City Comparison
# -----------------------------
st.subheader("🏙 City AQI Comparison")

fig = px.bar(latest, x="city", y="overall_aqi", color="city")
st.plotly_chart(fig, width="stretch", key="city_bar")

# -----------------------------
# Historical Trend
# -----------------------------
st.subheader("📈 Historical AQI Trend")

city = st.selectbox("Select City", sorted(df["city"].unique()))

city_data = df[df["city"] == city]

fig = px.line(city_data, x="timestamp", y="overall_aqi")
st.plotly_chart(fig, width="stretch", key="history_chart")

# -----------------------------
# Pollutant Analysis
# -----------------------------
st.subheader("💨 Pollutant Distribution")

pollutant = st.selectbox("Select Pollutant", ["pm25", "pm10", "no2"])

fig = px.box(df, x="city", y=pollutant, color="city")
st.plotly_chart(fig, width="stretch", key="pollutant_chart")

# -----------------------------
# Year-wise Trend
# -----------------------------
st.subheader("📈 Year-wise Trend Analysis")

city2 = st.selectbox("Select City for Analysis", sorted(df["city"].unique()), key="year_city")

filtered = df[df["city"] == city2].copy()
filtered["year"] = filtered["timestamp"].dt.year

yearly = filtered.groupby("year")[["overall_aqi","temperature","humidity"]].mean().reset_index()

fig = px.line(yearly, x="year", y=["overall_aqi","temperature","humidity"], markers=True)
st.plotly_chart(fig, width="stretch", key="yearly_chart")

# -----------------------------
# Temperature vs AQI
# -----------------------------
st.subheader("🌡 Temperature vs AQI")

fig = px.scatter(df, x="temperature", y="overall_aqi", color="city")
st.plotly_chart(fig, width="stretch", key="temp_chart")

# -----------------------------
# Humidity vs AQI
# -----------------------------
st.subheader("💧 Humidity vs AQI")

fig = px.scatter(df, x="humidity", y="overall_aqi", color="city")
st.plotly_chart(fig, width="stretch", key="humidity_chart")

# -----------------------------
# Seasonal Analysis
# -----------------------------
st.subheader("📅 Seasonal AQI Analysis")

df["month"] = df["timestamp"].dt.month
season = df.groupby(["month","city"])["overall_aqi"].mean().reset_index()

fig = px.line(season, x="month", y="overall_aqi", color="city")
st.plotly_chart(fig, width="stretch", key="season_chart")


forecast_city = st.selectbox("Select City for Forecast", sorted(df["city"].unique()))

# 3. DEFINE the input variable HERE (Before the button)
forecast_df_input = df[df["city"] == forecast_city]
if st.button("Generate Forecast"):
    forecast_data, model_mae = generate_7day_forecast(forecast_df_input)

    if not forecast_data.empty:
        # Create a "Dashboard Header" with metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Selected City", forecast_city)
        m2.metric("Model Reliability (MAE)", f"{model_mae:.2f}", help="Average prediction error in AQI units. Lower is better.")
        m3.metric("Algorithm", "Random Forest")

        st.markdown("---")
        
        # Display the table with your custom status labels
        st.subheader("7-Day Outlook")
        st.dataframe(forecast_data, use_container_width=True, hide_index=True)

        # Plotting the trend
        fig = px.line(
            forecast_data, x='Date', y='Predicted AQI',
            title=f"Future Trend: {forecast_city}",
            markers=True, text='Status'
        )
        fig.update_traces(line_color='#FF4B4B', textposition="top center")
        st.plotly_chart(fig)
# -----------------------------
# Metrics
# -----------------------------
st.subheader("📌 AQI Summary")

c1, c2, c3 = st.columns(3)
c1.metric("Average AQI", round(df["overall_aqi"].mean(),2))
c2.metric("Max AQI", df["overall_aqi"].max())
c3.metric("Min AQI", df["overall_aqi"].min())

st.markdown("---")
st.caption("Live + Historical AQI Dashboard")
