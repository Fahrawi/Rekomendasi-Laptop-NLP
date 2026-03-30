import pandas as pd

def categorize_laptops(game_name, df_min, df_rec, df_laptops, ram_weight=1.0, storage_weight=1.0):
    game_req = df_min[df_min['App'].str.lower() == game_name.lower()]
    game_rec = df_rec[df_rec['App'].str.lower() == game_name.lower()]
    if game_req.empty or game_rec.empty:
        print(f"Game '{game_name}' tidak ditemukan.")
        return pd.DataFrame()

    req_row_min = game_req.iloc[0]
    req_row_rec = game_rec.iloc[0]

    # Convert RAM and Storage requirements to numeric, handling potential errors
    ram_req_str_min = req_row_min['RAM']
    storage_req_str_min = req_row_min['File Size']
    ram_req_str_rec = req_row_rec['RAM']
    storage_req_str_rec = req_row_rec['File Size']

    # Extract numeric part and convert to integer
    ram_req_min = int(''.join(filter(str.isdigit, ram_req_str_min))) if any(char.isdigit() for char in ram_req_str_min) else 0
    storage_req_min = int(''.join(filter(str.isdigit, storage_req_str_min))) if any(char.isdigit() for char in storage_req_str_min) else 0
    ram_req_rec = int(''.join(filter(str.isdigit, ram_req_str_rec))) if any(char.isdigit() for char in ram_req_str_rec) else 0
    storage_req_rec = int(''.join(filter(str.isdigit, storage_req_str_rec))) if any(char.isdigit() for char in storage_req_str_rec) else 0

    # --- Vendor detection helper ---
    def get_gpu_vendor(gpu_name):
        gpu_name = gpu_name.lower()
        if any(x in gpu_name for x in ['rtx', 'gtx', 'mx']):
            return 'nvidia'
        elif any(x in gpu_name for x in ['radeon', 'rx', 'vega', 'pro']):
            return 'amd'
        elif any(x in gpu_name for x in ['integrated', 'iris', 'uhd']):
            return 'intel'
        else:
            return 'intel'

    # --- CPU detection helper ---
    def get_cpu_vendor(cpu_name):
        cpu_name = cpu_name.lower()
        if 'intel' in cpu_name:
            return 'intel'
        elif 'amd' in cpu_name:
            return 'amd'
        else:
            return 'intel'

    # --- Ambil score ---
    def get_cpu_score(row, req_row):
        vendor = get_cpu_vendor(row['CPU'])
        if vendor == 'intel':
            return req_row['CPU_Intel_score']
        elif vendor == 'amd':
            return req_row['CPU_AMD_score']
        else:
            return req_row['CPU_Intel_score']

    def get_gpu_score(row, req_row):
        vendor = get_gpu_vendor(row['GPU'])
        if vendor == 'nvidia':
            return req_row['GPU_NVIDIA_score']
        elif vendor == 'amd':
            return req_row['GPU_AMD_score']
        elif vendor == 'intel':
            return req_row['GPU_Intel_score']
        else:
            return req_row['GPU_Intel_score']

    # --- Hitung match score ---
    def calculate_match(row):
        cpu_req = get_cpu_score(row, req_row_min)
        gpu_req = get_gpu_score(row, req_row_min)
        cpu_score = row['CPU_score'] / cpu_req if cpu_req > 0 else 1.0
        gpu_score = row['GPU_score'] / gpu_req if gpu_req > 0 else 1.0
        ram_score = (row['RAM'] / ram_req_min) * ram_weight if ram_req_min > 0 else 1.0
        storage_score = (row['Storage'] / storage_req_min) * storage_weight if storage_req_min > 0 else 1.0
        final_score = (cpu_score + gpu_score + ram_score + storage_score) / (2 + ram_weight + storage_weight)
        return final_score

    # --- Kategorisasi ---
    def categorize(row):
        cpu_min = get_cpu_score(row, req_row_min)
        gpu_min = get_gpu_score(row, req_row_min)
        cpu_rec = get_cpu_score(row, req_row_rec)
        gpu_rec = get_gpu_score(row, req_row_rec)

        # Disqualified if below minimum CPU or GPU
        if row['CPU_score'] < cpu_min or row['GPU_score'] < gpu_min:
            return 'Disqualified'

        # Disqualified if below minimum RAM or Storage
        if row['RAM'] < ram_req_min or row['Storage'] < storage_req_min:
            return 'Disqualified'

        cpu_rec_flag = row['CPU_score'] >= cpu_rec
        gpu_rec_flag = row['GPU_score'] >= gpu_rec
        ram_rec_flag = row['RAM'] >= ram_req_rec
        storage_rec_flag = row['Storage'] >= storage_req_rec

        if cpu_rec_flag and gpu_rec_flag and ram_rec_flag and storage_rec_flag:
            return 'Recommended'
        elif (cpu_rec_flag and gpu_rec_flag) or (cpu_rec_flag and ram_rec_flag) or (gpu_rec_flag and ram_rec_flag) or (cpu_rec_flag and storage_rec_flag) or (gpu_rec_flag and storage_rec_flag) or (ram_rec_flag and storage_rec_flag):
            return 'Mixed'
        else:
            return 'Minimum'

    # --- Filter RAM & Storage ---
    df_filtered = df_laptops.copy()

    # --- Hitung Match_Score ---
    df_filtered['Match_Score'] = df_filtered.apply(calculate_match, axis=1)

    # --- Tentukan Kategori ---
    df_filtered['Category'] = df_filtered.apply(categorize, axis=1)

    # --- Buang yang Disqualified ---
    df_final = df_filtered[df_filtered['Category'] != 'Disqualified'].copy()

    # --- Urutkan ---
    df_final = df_final.sort_values(by='Match_Score', ascending=False).reset_index(drop=True)
    return df_final