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
# Convert to numeric
df["temperature"] = pd.to_numeric(df["temperature"], errors="coerce")
df["humidity"] = pd.to_numeric(df["humidity"], errors="coerce")
df["overall_aqi"] = pd.to_numeric(df["overall_aqi"], errors="coerce")

# Keep only valid AQI
df = df[df["overall_aqi"].between(0, 500)]

# Fill missing values instead of deleting rows
df["temperature"] = df.groupby("city")["temperature"].transform(lambda x: x.fillna(x.median()))
df["humidity"] = df.groupby("city")["humidity"].transform(lambda x: x.fillna(x.median()))
df = df.drop(columns=["co", "so2", "o3"], errors="ignore")


from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split

# 1. Update the Sliding Window to accept extra features

def create_sliding_window_multivariate(data_array, window_size=5):

    X = []

    y = []

    # data_array will be a 2D array: [AQI, Temp, Humidity]

    for i in range(len(data_array) - window_size):

        # Flatten the last 5 days of ALL 3 variables into one long row

        window = data_array[i:i+window_size].flatten() 

        X.append(window)

        y.append(data_array[i+window_size, 0]) # We are still only predicting AQI (index 0)

    return np.array(X), np.array(y)

# 2. Update the Forecast function to use Time Features

def generate_7day_forecast(df_input):

    df = df_input.copy().sort_values("timestamp")

    

    # Ensure all required columns exist

    cols = ['overall_aqi', 'temperature', 'humidity']

    if not all(col in df.columns for col in cols):

        return pd.DataFrame(), 0.0

    # Clean data
    df = df.dropna(subset=cols)
    df = df[df['overall_aqi'] > 0]

    if len(df) < 20: return pd.DataFrame(), 0.0

    # Prepare the 2D array for the sliding window
    # Column 0: AQI, Column 1: Temp, Column 2: Humidity
    data_values = df[cols].values.astype(float)
    window_size = 5

    X, y = create_sliding_window_multivariate(data_values, window_size)

    # Train/Test Split & MAE
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    mae = mean_absolute_error(y_test, model.predict(X_test))

    # Recursive Forecast
    model.fit(X, y)
    current_window_data = data_values[-window_size:] # Get last 5 days of all 3 variables
    
    predictions = []
    # We'll use the average Temp/Humidity of the last week to fill the "future" weather
    avg_temp = df['temperature'].tail(7).mean()
    avg_hum = df['humidity'].tail(7).mean()

    for _ in range(7):
        # Predict next AQI
        input_row = current_window_data.flatten().reshape(1, -1)
        pred_aqi = model.predict(input_row)[0]
        predictions.append(int(pred_aqi))
        
        # SLIDE: Create the next step's row [Predicted AQI, Future Temp, Future Hum]
        next_step_data = np.array([[pred_aqi, avg_temp, avg_hum]])
        current_window_data = np.vstack([current_window_data[1:], next_step_data])

    # Format Output
    last_date = pd.to_datetime(df['timestamp'].iloc[-1])
    forecast_df = pd.DataFrame({
        'Date': [last_date + pd.Timedelta(days=i) for i in range(1, 8)],
        'Predicted AQI': predictions
    })
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



st.subheader("📊 Atmospheric Correlation Analysis")

view_option = st.radio(
    "Data Range",
    ["All Historical Data", "Today Only"],
    horizontal=True,
    key="correlation_radio"
)

plot_df = df[df['timestamp'].dt.date == datetime.date.today()] if view_option == "Today Only" else df

# Remove extreme outliers
plot_df = plot_df[plot_df["overall_aqi"] < 300]

# 🌡 Temperature vs AQI
fig_temp = px.scatter(
    plot_df,
    x="temperature",
    y="overall_aqi",
    color="city",
    opacity=0.6,
    trendline="ols",
    trendline_scope="trace",
    title="Impact of Temperature on AQI"
)

fig_temp.update_traces(marker=dict(size=6))
fig_temp.update_layout(
    xaxis_title="Temperature (°C)",
    yaxis_title="AQI"
)

st.plotly_chart(fig_temp, use_container_width=True)


# 💧 Humidity vs AQI
fig_hum = px.scatter(
    plot_df,
    x="humidity",
    y="overall_aqi",
    color="city",
    opacity=0.6,
    trendline="ols",
    trendline_scope="trace",
    title="Impact of Atmospheric Humidity on AQI"
)

fig_hum.update_traces(marker=dict(size=6))
fig_hum.update_layout(
    xaxis_title="Humidity (%)",
    yaxis_title="AQI"
)

st.plotly_chart(fig_hum, use_container_width=True)
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
