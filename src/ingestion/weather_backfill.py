from meteo_fetcher import MeteoFetcher
from supabase_loader import SupabaseLoader

LAT = -34.881066
LONG = -58.68288
START_DATE = "2025-01-01"
END_DATE = "2026-10-01"

print(f"1. Descargando datos de open-meteo...\n")

meteo = MeteoFetcher()
loader = SupabaseLoader()

weather_records = meteo.fetch_historical_weather(LAT,LONG,START_DATE,END_DATE)

print(f"Datos obtenidos: {len(weather_records)}")

print(f"2. Subiendo datos a supabase...\n")
inserted = loader.upsert_weather(weather_records,batch_size=1000)
print(f"Carga completa, total de registros: {inserted}")