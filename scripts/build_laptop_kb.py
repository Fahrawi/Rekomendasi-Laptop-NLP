# scripts/build_laptop_kb.py
from collections import defaultdict

def build_laptop_kb(laptop_df):
    laptop_kb = defaultdict(list)
    for _, row in laptop_df.iterrows():
        model = row['Model']
        specs = {
            'Brand': row['Brand'],
            'CPU_score': row['CPU_score'],
            'GPU_score': row['GPU_score'],
            'RAM': row['RAM'],
            'Final Price': row['Final Price'],
            'Storage': row['Storage'],
            'Storage type': row['Storage type']
        }
        laptop_kb[model].append(specs)
    return laptop_kb