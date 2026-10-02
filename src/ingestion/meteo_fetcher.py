import openmeteo_requests
import pandas as pd
import requests_cache
from retry_requests import retry
from datetime import datetime

class MeteoFetcher:
    def __init__(self, cache_dir : str = ".cache"):
        cache_session = requests_cache.CachedSession(cache_dir, expire_after = -1)
        retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
        self.client = openmeteo_requests.Client(session = retry_session)
        self.url = "https://archive-api.open-meteo.com/v1/archive"
        
    def fetch_historical_weather(self, latitude:float, longitude:float, start_date:str, end_date:str) -> list[dict]:
        """
        Descarga datos meteorológicos horarios históricos y los devuelve
        como una lista de diccionarios lista para Supabase.
        
        start_date y end_date esperan strings formato 'YYYY-MM-DD'.
        """
        
        variables = [
            "temperature_2m",
            "relative_humidity_2m",
            "rain",
            "wind_speed_10m",
            "wind_direction_10m",
            "shortwave_radiation"
        ]
        
        params = {
            "latitude": round(latitude, 6),
            "longitude": round(longitude, 6),
            "start_date": start_date,
            "end_date": end_date,
            "hourly": variables,
            "timezone": "UTC",  # Directo en UTC para alinear con OpenAQ
        }

        responses = self.client.weather_api(self.url, params = params)
        response = responses[0]
        hourly = response.Hourly()
        
        timestamps = pd.date_range(
            start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
            end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=hourly.Interval()),
            inclusive="left"
        )
        
        df = pd.DataFrame({
            "datetime_utc": [ts.isoformat() for ts in timestamps],
            "latitude": round(latitude, 6),
            "longitude": round(longitude, 6),
            "temperature_2m": hourly.Variables(0).ValuesAsNumpy(),
            "relative_humidity_2m": hourly.Variables(1).ValuesAsNumpy(),
            "precipitation": hourly.Variables(2).ValuesAsNumpy(),  # Mapeado a 'precipitation'
            "wind_speed_10m": hourly.Variables(3).ValuesAsNumpy(),
            "wind_direction_10m": hourly.Variables(4).ValuesAsNumpy(),
            "shortwave_radiation": hourly.Variables(5).ValuesAsNumpy(),
        })

        # Reemplazar posibles NaNs de NumPy por None para que JSON/Supabase lo acepte
        df = df.where(pd.notnull(df), None)
        
        return df.to_dict(orient="records")
