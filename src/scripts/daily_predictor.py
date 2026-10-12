import os
import sys
import pandas as pd
import numpy as np
import joblib
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

script_dir = os.path.dirname(os.path.abspath(__file__)) # Apunta a src/scripts
src_dir = os.path.abspath(os.path.join(script_dir, '..')) # Sube un nivel a src

# Inyectamos 'src' en el PYTHONPATH
if src_dir not in sys.path:
    sys.path.append(src_dir)

from ingestion.openaq_fetcher import OpenAQFetcher
from ingestion.meteo_fetcher import MeteoFetcher
from ingestion.supabase_loader import SupabaseLoader

load_dotenv()

def extract_data(start_datetime, end_datetime, aq_fetcher : OpenAQFetcher, meteo_fetcher: MeteoFetcher, sensor_id: int, lat: float, long: float):
    """
    Descarga los datos de OpenAQ y Open-Meteo.
    Retorna dos DataFrames crudos.
    """
    aq_raw = aq_fetcher.fetch_sensor_measurements(sensor_id=sensor_id,
                                          data="hours",
                                          date_from=start_datetime,
                                          date_to=end_datetime)
    aq_df = pd.DataFrame(aq_raw)
    
    if aq_df.empty:
        print(f"El sensor {sensor_id} no reportó datos. Abortando ejecución silenciosamente.")
        sys.exit(0)
    if 'value' in aq_df.columns:
        aq_df = aq_df.rename(columns={'value': 'pm25_value'})
    
    meteo_raw = meteo_fetcher.fetch_historical_weather(latitude=lat,
                                                       longitude=long,
                                                       start_date=start_datetime.strftime('%Y-%m-%d'),
                                                       end_date=end_datetime.strftime('%Y-%m-%d'))
    meteo_df = pd.DataFrame(meteo_raw)
    
    if meteo_df.empty:
        print(f"Open meteo no reportó datos. Abortando ejecución silenciosamente.")
        sys.exit(0)
    aq_df['datetime_utc'] = pd.to_datetime(aq_df["datetime_utc"], utc=True)
    meteo_df['datetime_utc'] = pd.to_datetime(meteo_df["datetime_utc"], utc=True)
    
    return aq_df, meteo_df
    
def transform_data(df_aq, df_meteo):
    """
    Une los datos, crea el lag de 48 hs, aplica trigonometría 
    y filtra solo las 24 horas que necesitamos predecir.
    """
    df_merged = pd.merge(df_aq,df_meteo,on=['datetime_utc'], how="left").sort_values(by="datetime_utc")
    
    # Hour transform
    df_merged["datetime_local"] = df_merged["datetime_utc"].dt.tz_convert('America/Argentina/Buenos_Aires')

    df_merged["hour"] = df_merged["datetime_local"].dt.hour
    df_merged["day_of_week"] = df_merged["datetime_local"].dt.day_of_week
    df_merged["month"] = df_merged["datetime_local"].dt.month
    df_merged["year"] = df_merged["datetime_local"].dt.year
    
    df_merged = df_merged.drop(columns=['datetime_utc'])
    
    df_merged.set_index('datetime_local',inplace=True)
    df_merged = df_merged.asfreq('h')
    df_merged['pm25_lag_1'] = df_merged['pm25_value'].shift(1)
    
    df_merged['wind_sin'] = np.sin(np.radians(df_merged['wind_direction_10m']))
    df_merged['wind_cos'] = np.cos(np.radians(df_merged['wind_direction_10m']))  
    df_merged = df_merged.drop(columns=['wind_direction_10m'])
    
    df_merged['hour_sin'] = np.sin(2 * np.pi * df_merged['hour'] / 24)
    df_merged['hour_cos'] = np.cos(2 * np.pi * df_merged['hour'] / 24)

    df_merged['month_sin'] = np.sin(2 * np.pi * df_merged['month'] / 12)
    df_merged['month_cos'] = np.cos(2 * np.pi * df_merged['month'] / 12)
    
    df_merged = df_merged.drop(columns=["pm25_value", "hour", "month"])
        
    # Optional
    trash_cols = [col for col in ['latitude', 'longitude', 'sensor_id'] if col in df_merged.columns]
    df_merged = df_merged.drop(columns=trash_cols)
    
    df_merged = df_merged.ffill(limit=2)
    
    df_merged = df_merged.tail(24)

    df_final = df_merged.dropna().copy()
    
    return df_final

def load_predictions(loader : SupabaseLoader, df_predicciones, sensor_id: int):
    """
    Se conecta a Supabase y hace el upsert de los resultados.
    """
    upserted_records = loader.upsert_predictions(df_predicciones,sensor_id=sensor_id)
    
    return upserted_records

if __name__ == "__main__":
    print("Iniciando pipeline de predicción...")
    
    SENSOR_ID = 7696815 # ID de La Matanza
    LATITUDE = -34.6703
    LONGITUDE = -58.5628
    DAYS_WINDOW = 7

    aq_fetcher = OpenAQFetcher()
    meteo_fetcher = MeteoFetcher()
    supabase_loader = SupabaseLoader()
    
    today_utc = datetime.now(timezone.utc)
    two_days_before = today_utc - timedelta(days=DAYS_WINDOW)    
   
    print("Extrayendo datos de OpenAQ y Open-Meteo...")
    aq_df, meteo_df = extract_data(
        start_datetime=two_days_before,
        end_datetime=today_utc,
        aq_fetcher=aq_fetcher,
        meteo_fetcher=meteo_fetcher,
        sensor_id=SENSOR_ID,
        lat=LATITUDE,
        long=LONGITUDE
    )
    
    print("Actualizando tablas históricas con datos reales recientes...")
    aq_db = aq_df.copy()
    meteo_db = meteo_df.copy()
    
    aq_db['datetime_utc'] = aq_db['datetime_utc'].dt.strftime('%Y-%m-%dT%H:%M:%S%z')
    meteo_db['datetime_utc'] = meteo_db['datetime_utc'].dt.strftime('%Y-%m-%dT%H:%M:%S%z')
    aq_db = aq_db.rename(columns={'pm25_value': 'value'})

    aq_records = aq_db.to_dict(orient='records')
    meteo_records = meteo_db.to_dict(orient='records')
    
    supabase_loader.upsert_measurements(aq_records)
    supabase_loader.upsert_weather(meteo_records)
    
    print("Aplicando ingeniería de características y recortes temporales...")
    df_transformed = transform_data(aq_df, meteo_df)
    
    if df_transformed.empty:
        print("El dataframe resultante está vacío tras la purga de nulos. Abortando ejecución.")
        sys.exit(0)
        
    print("Cargando modelo exportado y generando predicciones...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(script_dir, '..', 'model', 'pipeline_air_quality.pkl')

    print(f"Cargando modelo desde: {model_path}")
    model = joblib.load(model_path)
    
    predictions_array = model.predict(df_transformed)
    df_transformed['predicted_aqi_class'] = predictions_array
    
    print("Enviando predicciones a Supabase...")
    rows = load_predictions(supabase_loader, df_transformed, SENSOR_ID)
    
    print(f"Pipeline finalizado con éxito. {rows} filas procesadas.")