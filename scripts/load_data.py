# scripts/load_data.py
from pathlib import Path
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'

def load_data():
    laptop_df = pd.read_csv(DATA_DIR / 'cleaned_dataset_v3.csv')
    min_req_df = pd.read_csv(DATA_DIR / 'minimum_requirements_processed.csv')
    rec_req_df = pd.read_csv(DATA_DIR / 'recommended_requirements_processed.csv')
    return laptop_df, min_req_df, rec_req_df