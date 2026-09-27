from dotenv import load_dotenv
import os

load_dotenv()

supa_key = os.getenv("SUPABASE_KEY")
supa_url = os.getenv("SUPABASE_URL")

