import pandas as pd

laptop_df = pd.read_csv('data/cleaned_dataset_v3.csv')
print("Laptop columns:")
print(laptop_df.columns.tolist())
print("\nFirst HP Omen row:")
hp_omen = laptop_df[(laptop_df['Brand'] == 'HP') & (laptop_df['Model'] == 'Omen')].iloc[0]
print(f"CPU column value: {hp_omen.get('CPU', 'MISSING')}")
print(f"GPU column value: {hp_omen.get('GPU', 'MISSING')}")
print(f"CPU_Name: {hp_omen.get('CPU_Name', 'MISSING')}")
print(f"GPU_Name: {hp_omen.get('GPU_Name', 'MISSING')}")
print(f"CPU_score: {hp_omen.get('CPU_score', 'MISSING')}")
print(f"GPU_score: {hp_omen.get('GPU_score', 'MISSING')}")



