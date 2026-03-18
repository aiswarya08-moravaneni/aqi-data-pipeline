# 🌍 AQI Monitoring Dashboard

[![Live Dashboard](https://img.shields.io/badge/Live%20Dashboard-Click%20Here-brightgreen)](https://aqi-data-pipeline-bvgjncknlbz6medlpegyo2.streamlit.app/)

---

## 📌 Project Overview
This project collects real-time air quality data (AQI) from multiple cities using an API, stores it in a cloud database, and visualizes it through an interactive dashboard.

---

## 🚀 Features
- 🌍 Real-time AQI monitoring
- 📊 Historical data analysis
- 📈 Trend visualization (AQI, temperature, humidity)
- 🗺 Interactive map view
- 🔄 Automated data collection using GitHub Actions

---

## 🛠 Tech Stack
- Python
- Streamlit
- Supabase (PostgreSQL)
- Plotly
- GitHub Actions

---

## ⚙️ How It Works
1. Data is fetched from WAQI API
2. Stored in Supabase database
3. GitHub Actions runs every few minutes
4. Streamlit dashboard displays live + historical data

---

## 📊 Insights You Can Get
- Compare pollution levels across cities
- Identify trends over time
- Analyze relationship between AQI, temperature, and humidity

---

## 🌟 Future Improvements
- AQI prediction using Machine Learning
- More cities integration
- Alert system for hazardous AQI
