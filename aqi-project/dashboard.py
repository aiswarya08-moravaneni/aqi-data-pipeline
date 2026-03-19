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


def generate_7day_forecast(df):
    df = df.copy()

    # Map correct columns
    df['Date'] = pd.to_datetime(df['timestamp'])
    df['AQI'] = df['overall_aqi']

    # 🚨 REMOVE NULL VALUES (IMPORTANT FIX)
    df = df.dropna(subset=['Date', 'AQI'])

    # 🚨 ALSO REMOVE INVALID VALUES
    df = df[df['AQI'] > 0]

    # If not enough data → stop
    if len(df) < 5:
        st.warning("Not enough data to generate forecast")
        return pd.DataFrame()

    # Convert to ordinal
    df['Date_Ordinal'] = df['Date'].map(datetime.datetime.toordinal)

    X = df[['Date_Ordinal']].values
    y = df['AQI'].values

    # Train model
    model = LinearRegression()
    model.fit(X, y)

    # Future dates
    last_date = df['Date_Ordinal'].max()
    future_dates = np.array([last_date + i for i in range(1, 8)]).reshape(-1, 1)

    predictions = model.predict(future_dates)

    # Convert back to normal dates
    forecast_dates = [datetime.date.fromordinal(int(d)) for d in future_dates.flatten()]

    forecast_df = pd.DataFrame({
        'Date': forecast_dates,
        'Predicted AQI': predictions.astype(int)
    })

    return forecast_df
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

st.header("🔮 7-Day AQI Forecast")

forecast_city = st.selectbox("Select City for Forecast", sorted(df["city"].unique()))

forecast_df_input = df[df["city"] == forecast_city]

if st.button("Generate Forecast"):
    forecast_data = generate_7day_forecast(forecast_df_input)

    if forecast_data.empty:
        st.error("❌ Not enough clean data for prediction")
    else:
        st.dataframe(forecast_data, use_container_width=True)

        fig = px.line(
            forecast_data,
            x='Date',
            y='Predicted AQI',
            title=f"Predicted AQI Trend - {forecast_city}",
            markers=True
        )

        fig.update_traces(line_color='#FF4B4B')
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
