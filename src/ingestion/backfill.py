from openaq_fetcher import OpenAQFetcher
from supabase_loader import SupabaseLoader
from datetime import datetime, timezone, timedelta
import time

START_DATE = datetime(2025,1,1,tzinfo=timezone.utc)
END_DATE = datetime.now(timezone.utc)
STEPS = timedelta(days=7)

fetcher = OpenAQFetcher()
loader = SupabaseLoader()

def filldb(start : datetime, end : datetime, step,  sensor_id : int, data : str = "hours"):
    current_start = start    
    
    while current_start < end:
        current_end = min(current_start + step, end)
        
        print(f"Descargando rango: {current_start.date()} -> {current_end.date()}...", end=" ")
        
        if current_start >= current_end:
            break
        
        try:
            r = fetcher.fetch_sensor_measurements(sensor_id=sensor_id,
                                                        data=data,
                                                        date_from=current_start,
                                                        date_to=current_end)
            if not r:
                print("Sin mediciones reportadas en este periodo")
            else:
                inserted = loader.upsert_measurements(r)
                print(f"Listo ({inserted} filas procesadas).")

        except Exception as e:
                print(f"\nError en el rango {current_start.date()} - {current_end.date()}: {e}")

        current_start = current_end
        time.sleep(1)
    
    print("Backfill completado!")

def backfill_sensor(sensor_id: int, start: datetime, end: datetime, step: timedelta, data: str = "hours"):
    """Sincroniza la dimensión del sensor y descarga todo su histórico de mediciones."""
    print(f"\n==========================================")
    print(f"Iniciando proceso para sensor: {sensor_id}")
    print(f"==========================================")
    
    # 1. Asegurar integridad (Metadata)
    metadata = fetcher.fetch_sensor_details(sensor_id)
    loader.upsert_sensor_metadata(metadata)
    print(f"Sensor registrado: {metadata.get('parameter')} ({metadata.get('units')})")
    
    # 2. Ingesta de mediciones
    filldb(start=start, end=end, step=step, sensor_id=sensor_id, data=data)

TARGET_SENSORS = [
    7696815, #PM2.5
    8562542, #PM10
    8562534 #PM1
]

if __name__ == '__main__':
    for s_id in TARGET_SENSORS:
        backfill_sensor(sensor_id=s_id,
                        start=START_DATE,
                        end=END_DATE,
                        step=STEPS)