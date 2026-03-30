# scripts/load_data.py
import pandas as pd

def load_data():
    laptop_df = pd.read_csv('data/cleaned_dataset_v3.csv')
    min_req_df = pd.read_csv('data/minimum_requirements_processed.csv')
    rec_req_df = pd.read_csv('data/recommended_requirements_processed.csv')
    return laptop_df, min_req_df, rec_req_df