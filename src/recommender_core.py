import pandas as pd
import numpy as np

def get_gpu_vendor(gpu_name):
    if pd.isna(gpu_name): return 'intel'
    gpu_name = str(gpu_name).lower()
    if any(x in gpu_name for x in ['rtx', 'gtx', 'mx']): return 'nvidia'
    elif any(x in gpu_name for x in ['radeon', 'rx', 'vega', 'pro']): return 'amd'
    elif any(x in gpu_name for x in ['integrated', 'iris', 'uhd', 'hd graphics']): return 'intel'
    else: return 'intel'

def get_cpu_vendor(cpu_name):
    if pd.isna(cpu_name): return 'intel'
    cpu_name = str(cpu_name).lower()
    if 'intel' in cpu_name or any(x in cpu_name for x in ['core', 'pentium', 'celeron', 'xeon', 'evo']): return 'intel'
    elif 'amd' in cpu_name or any(x in cpu_name for x in ['ryzen', 'fx', 'athlon', 'phenom', 'opteron']): return 'amd'
    else: return 'intel'

def get_cpu_req_score(row, req_row):
    vendor = get_cpu_vendor(row['CPU'])
    score_key = 'CPU_Intel_score' if vendor == 'intel' else 'CPU_AMD_score'
    score = req_row.get(score_key, 0)
    return score if pd.notna(score) and isinstance(score, (int, float)) else 0.0

def get_gpu_req_score(row, req_row):
    laptop_gpu_vendor = get_gpu_vendor(row['GPU'])
    if laptop_gpu_vendor == 'nvidia': score_key = 'GPU_NVIDIA_score'
    elif laptop_gpu_vendor == 'amd': score_key = 'GPU_AMD_score'
    else: score_key = 'GPU_Intel_score'
    score = req_row.get(score_key, 0)
    return score if pd.notna(score) and isinstance(score, (int, float)) else 0.0

def get_storage_type_score(storage_type):
    if pd.isna(storage_type): return 0.0
    storage_type_lower = str(storage_type).lower()
    if 'ssd' in storage_type_lower: return 1.0
    elif 'hdd' in storage_type_lower: return 0.5
    elif 'emmc' in storage_type_lower: return 0.3
    else: return 0.0

def categorize_laptops_adapted(df_laptops_filtered, req_row_min, req_row_rec, ram_weight=1.0, storage_weight=1.0, storage_type_weight=0.5):
    if df_laptops_filtered.empty:
        return pd.DataFrame()

    ram_min_req = req_row_min.get('RAM', 0)
    if pd.isna(ram_min_req) or not isinstance(ram_min_req, (int, float)): ram_min_req = 0
    storage_min_req = req_row_min.get('File Size', 0)
    if pd.isna(storage_min_req) or not isinstance(storage_min_req, (int, float)): storage_min_req = 0

    def calculate_match(row):
        # Ambil skor recommended sesuai vendor laptop
        cpu_req_rec = get_cpu_req_score(row, req_row_rec)
        gpu_req_rec = get_gpu_req_score(row, req_row_rec)
        row_cpu_score = row['CPU_score'] if pd.notna(row['CPU_score']) else 0.0
        row_gpu_score = row['GPU_score'] if pd.notna(row['GPU_score']) else 0.0
        row_ram = row['RAM'] if pd.notna(row['RAM']) else 0.0
        row_storage = row['Storage'] if pd.notna(row['Storage']) else 0.0

        cpu_score_ratio = row_cpu_score / cpu_req_rec if cpu_req_rec > 0 else (1.0 if cpu_req_rec == 0 else 0.0)
        gpu_score_ratio = row_gpu_score / gpu_req_rec if gpu_req_rec > 0 else (1.0 if gpu_req_rec == 0 else 0.0)
        ram_score_ratio = (row_ram / ram_min_req) * ram_weight if ram_min_req > 0 else (1.0 * ram_weight if ram_min_req == 0 else 0.0)
        storage_score_ratio = (row_storage / storage_min_req) * storage_weight if storage_min_req > 0 else (1.0 * storage_weight if storage_min_req == 0 else 0.0)
        storage_type_score = get_storage_type_score(row['Storage type']) * storage_type_weight

        cpu_score_ratio = min(cpu_score_ratio, 5.0)
        gpu_score_ratio = min(gpu_score_ratio, 5.0)
        ram_score_ratio = min(ram_score_ratio, 5.0)
        storage_score_ratio = min(storage_score_ratio, 5.0)

        total_weight = (1.0 if cpu_req_rec > 0 else 0.0) + (1.0 if gpu_req_rec > 0 else 0.0) + (ram_weight if ram_min_req > 0 else 0.0) + (storage_weight if storage_min_req > 0 else 0.0) + storage_type_weight
        total_weight = max(total_weight, 1.0)
        final_score = (cpu_score_ratio + gpu_score_ratio + ram_score_ratio + storage_score_ratio + storage_type_score) / total_weight
        return final_score

    def categorize(row):
        # Ambil skor minimum dan recommended sesuai vendor laptop
        cpu_min_req_score = get_cpu_req_score(row, req_row_min)
        gpu_min_req_score = get_gpu_req_score(row, req_row_min)
        cpu_rec_req_score = get_cpu_req_score(row, req_row_rec)
        gpu_rec_req_score = get_gpu_req_score(row, req_row_rec)

        row_cpu_score = row['CPU_score'] if pd.notna(row['CPU_score']) else -1
        row_gpu_score = row['GPU_score'] if pd.notna(row['GPU_score']) else -1
        row_ram = row['RAM'] if pd.notna(row['RAM']) else -1
        row_storage = row['Storage'] if pd.notna(row['Storage']) else -1

        ram_min_req_val = req_row_min.get('RAM', 0)
        storage_min_req_val = req_row_min.get('File Size', 0)

        cpu_meets_min = (pd.isna(cpu_min_req_score) or cpu_min_req_score <= 0) or (pd.notna(row_cpu_score) and row_cpu_score >= cpu_min_req_score)
        gpu_meets_min = (pd.isna(gpu_min_req_score) or gpu_min_req_score <= 0) or (pd.notna(row_gpu_score) and row_gpu_score >= gpu_min_req_score)
        ram_meets_min = (pd.isna(ram_min_req_val) or ram_min_req_val <= 0) or (pd.notna(row_ram) and row_ram >= ram_min_req_val)
        storage_meets_min = (pd.isna(storage_min_req_val) or storage_min_req_val <= 0) or (pd.notna(row_storage) and row_storage >= storage_min_req_val)

        if not (cpu_meets_min and gpu_meets_min and ram_meets_min and storage_meets_min):
            return 'Disqualified'

        cpu_meets_rec = (pd.notna(cpu_rec_req_score) and cpu_rec_req_score > 0) and (pd.notna(row_cpu_score) and row_cpu_score >= cpu_rec_req_score)
        gpu_meets_rec = (pd.notna(gpu_rec_req_score) and gpu_rec_req_score > 0) and (pd.notna(row_gpu_score) and row_gpu_score >= gpu_rec_req_score)

        if cpu_meets_rec and gpu_meets_rec:
            return 'Recommended'
        elif cpu_meets_rec or gpu_meets_rec:
            return 'Mixed'
        else:
            return 'Minimum'

    df_categorized = df_laptops_filtered.copy()
    if df_categorized.empty:
        return pd.DataFrame()
    df_categorized['Match_Score'] = df_categorized.apply(calculate_match, axis=1)
    df_categorized['Category'] = df_categorized.apply(categorize, axis=1)
    df_final = df_categorized[df_categorized['Category'] != 'Disqualified'].copy()
    cols = ['Brand', 'Model', 'CPU', 'GPU', 'RAM', 'Storage', 'Storage type', 'Final Price', 'Category', 'Match_Score']
    return df_final[[c for c in cols if c in df_final.columns]]