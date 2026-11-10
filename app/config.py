import os
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

def db_path():
    path = Path(os.getenv('DATABASE_PATH', 'data/orders.db'))
    return path if path.is_absolute() else ROOT / path

def raj_url():
    return os.getenv('RAJ_API_URL', 'http://127.0.0.1:8080').rstrip('/')
