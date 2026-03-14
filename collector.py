import requests
import psycopg2
from datetime import datetime
import time

# WAQI API TOKEN
TOKEN = "8d611b0f9b105b783d4ecf9d1a253a76c6c3cfe3"

# PostgreSQL connection (Supabase)
conn = psycopg2.connect(
    host="db.oxcycpqjisgegrhewdov.supabase.co",
    database="postgres",
    user="postgres",
    password="AiS#u2)jkfty",
    port=5432,
    sslmode="require"
)

cursor = conn.cursor()

# Stations to monitor
CITIES = {
    "Tirupati": "@9069",
    "Visakhapatnam": "@12443",
    "Amaravati": "@11280",
    "Chennai": "@11279",
    "Hyderabad": "@11284",
    "Bangalore": "@3758",
    "Delhi": "@11266"
}

def get_city_data(city, station):
    try:
        url = f"https://api.waqi.info/feed/{station}/?token={TOKEN}"
        response = requests.get(url, timeout=10)
        data = response.json()

        if data["status"] == "ok":

            d = data["data"]
            pollutants = d.get("iaqi", {})

            record = (
                datetime.now(),
                city,
                d.get("aqi"),
                pollutants.get("pm25", {}).get("v"),
                pollutants.get("pm10", {}).get("v"),
                pollutants.get("no2", {}).get("v"),
                pollutants.get("t", {}).get("v"),
                pollutants.get("h", {}).get("v")
            )

            return record

    except Exception as e:
        print(f"Error fetching {city}: {e}")

    return None


while True:

    print("Starting data collection cycle...")

    for city, station in CITIES.items():

        record = get_city_data(city, station)

        if record:

            query = """
            INSERT INTO aqi_data
            (timestamp, city, overall_aqi, pm25, pm10, no2, temperature, humidity)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """

            cursor.execute(query, record)
            conn.commit()

            print(f"Saved data for {city}")


    print("Data collection complete")
