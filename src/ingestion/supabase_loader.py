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