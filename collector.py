import requests
import psycopg2
import socket
import time
from datetime import datetime

TOKEN = "8d611b0f9b105b783d4ecf9d1a253a76c6c3cfe3"

socket.setdefaulttimeout(30)

conn = psycopg2.connect(
    host="aws-1-ap-south-1.pooler.supabase.com",
    port=6543,
    database="postgres",
    user="postgres.oxcycpqjisgegrhewdov",
    password="AiS#u2)jkfty",
    sslmode="require"
)

cursor = conn.cursor()

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


print("Starting data collection...")

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

    time.sleep(1)

print("Data collection complete")

cursor.close()
conn.close()
