from dotenv import load_dotenv
from supabase import create_client, Client
import os

load_dotenv()

supabase_key = os.getenv("SUPABASE_KEY")
supabase_url = os.getenv("SUPABASE_URL")

class SupabaseLoader:
    def __init__(self, key : str = None, url : str = None):
        self.key = key or supabase_key
        self.url = url or supabase_url
        
        if not self.key or not self.url:
            raise ValueError("Credenciales de Supabase no encontradas en el entorno.")
        
        self.client = create_client(self.url, self.key)

    def upsert_sensor_metadata(self, data : dict):
        """Funcion para insertar y/o actualizar datos en la tabla de metadata (info. sensor)."""
        if not data:
            raise ValueError(f"El diccionario de metadata esta vacio.")
        
        self.client.table("sensors").upsert(data, on_conflict="sensor_id").execute()
        
    def upsert_measurements(self, data : list[dict]):
        """Funcion para insertar y/o actualizar datos en la tabla de medidas obtenidas del sensor."""
        if len(data) == 0:
            return 0
        
        else:
            response = self.client.table("measurements").upsert(
            data, 
            on_conflict="sensor_id,datetime_utc"
            ).execute()
            
        return len(response.data) if response.data else len(data)
    
    def upsert_weather(self, data : list[dict], batch_size: int = 1000) -> int:
        """Funcion para insertar datos del clima (open-meteo) a supabase."""
        if not data:
            return 0
        
        total_inserted = 0
        for i in range(0,len(data),batch_size):
            batch = data[i:i+batch_size]
            response = self.client.table('weather_hourly').upsert(batch,
                                                                  on_conflict="latitude,longitude,datetime_utc"
                                                                  ).execute()
            total_inserted += len(response.data) if response.data else len(batch)
        return total_inserted