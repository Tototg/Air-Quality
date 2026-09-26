import os
from datetime import datetime
from openaq import OpenAQ
from dotenv import load_dotenv

load_dotenv()

OPENAQ_API_KEY = os.getenv("OPENAQ_API_KEY")

class OpenAQFetcher:
    def __init__(self, openaq_apikey: str = None):
      self.api_key = openaq_apikey or OPENAQ_API_KEY
      self.client = OpenAQ(api_key=self.api_key)

    def fetch_sensor_measurements(self, sensor_id: int, data : str, date_from : datetime, date_to : datetime, limit=1000) -> list[dict]:
        """Descarga mediciones de un sensor dentro de un rago de timepo especificado."""
        
        datetime_from = datetime.fromisoformat(date_from)
        datetime_to = datetime.fromisoformat(date_to)
        
        response = self.client.measurements.list(
            sensors_id=sensor_id,
            data=data,
            datetime_from=datetime_from,
            datetime_to=datetime_to,
            limit=limit
            )
        
        results = []
        for item in response.results:
            results.append({
                "sensor_id" : sensor_id,
                "datetime_utc": item.period.datetime_to.utc,
                "value" : item.value
            })

        return results
    
    def fetch_sensor_details(self, sensor_id,):
        int