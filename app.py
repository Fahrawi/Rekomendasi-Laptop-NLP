# app.py
import sys
import os
import traceback
import re
import pandas as pd
import numpy as np
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from scripts.load_data import load_data
from scripts.build_kb import build_kb
from scripts.build_laptop_kb import build_laptop_kb
from scripts.generate_series_kb import generate_series_kb
from scripts.build_unique_word_kb import build_unique_word_kb
from scripts.build_bigram_trigram_kb import build_bigram_trigram_kb
from scripts.build_abbrev_alt_kb import build_abbrev_alt_kb
from scripts.build_brand_models_kb import build_brand_models_kb
from src.recommender_system import get_laptop_recommendations_with_intent
from src.nlp_pipeline import nlp_pipeline_fuzzy

app = FastAPI(title="Laptop Recommendation System API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables
laptop_df = None
min_req_df = None
rec_req_df = None
min_req_kb = None
rec_req_kb = None
laptop_list = None
laptop_brand_list = None
unique_word_kb = None
game_abbreviations_kb = None
game_alt_titles_kb = None
series_abbreviations = None
bigram_unique_kb = None
series_games = None
brand_models_mapping = None

# Vendor keyword lists
CPU_VENDOR_KEYWORDS = {
    'intel': ['intel', 'core', 'pentium', 'celeron', 'xeon', 'evo'],
    'amd': ['amd', 'ryzen', 'fx', 'athlon', 'phenom', 'opteron']
}
GPU_VENDOR_KEYWORDS = {
    'nvidia': ['nvidia', 'geforce', 'rtx', 'gtx', 'mx'],
    'amd': ['amd', 'radeon', 'rx', 'vega', 'pro'],
    'intel': ['intel', 'integrated', 'iris', 'uhd', 'hd graphics']
}

def is_valid_spec(value, vendor, spec_type='cpu'):
    if not value or not isinstance(value, str):
        return False
    value_lower = value.strip().lower()
    if spec_type == 'cpu':
        keywords = CPU_VENDOR_KEYWORDS.get(vendor, [])
    else:
        keywords = GPU_VENDOR_KEYWORDS.get(vendor, [])
    return any(kw in value_lower for kw in keywords)

def normalize_name(name: str) -> str:
    return re.sub(r'[^a-z0-9]', '', name.lower())

def to_python_int(val):
    if isinstance(val, (np.integer, np.int64)):
        return int(val)
    return val

def get_game_specs_from_df(game_name, min_df, rec_df):
    min_row = min_df[min_df['App'].str.lower() == game_name.lower()]
    rec_row = rec_df[rec_df['App'].str.lower() == game_name.lower()]
    if min_row.empty:
        return None
    min_req = min_row.iloc[0]
    if rec_row.empty:
        rec_req = min_req
    else:
        rec_req = rec_row.iloc[0]

    def get_spec(value, vendor, spec_type):
        if pd.isna(value) or not isinstance(value, str):
            return ''
        value = value.strip()
        if (vendor == 'intel' and spec_type == 'cpu') or (vendor == 'intel' and spec_type == 'gpu'):
            return value
        if is_valid_spec(value, vendor, spec_type):
            return value
        return ''

    return {
        "min": {
            "cpu_intel": get_spec(min_req.get('CPU_Intel', ''), 'intel', 'cpu'),
            "cpu_amd": get_spec(min_req.get('CPU_AMD', ''), 'amd', 'cpu'),
            "gpu_nvidia": get_spec(min_req.get('GPU_NVIDIA', ''), 'nvidia', 'gpu'),
            "gpu_amd": get_spec(min_req.get('GPU_AMD', ''), 'amd', 'gpu'),
            "gpu_intel": get_spec(min_req.get('GPU_Intel', ''), 'intel', 'gpu'),
            "ram": min_req.get('RAM', ''),
            "storage": min_req.get('File Size', '')
        },
        "rec": {
            "cpu_intel": get_spec(rec_req.get('CPU_Intel', ''), 'intel', 'cpu'),
            "cpu_amd": get_spec(rec_req.get('CPU_AMD', ''), 'amd', 'cpu'),
            "gpu_nvidia": get_spec(rec_req.get('GPU_NVIDIA', ''), 'nvidia', 'gpu'),
            "gpu_amd": get_spec(rec_req.get('GPU_AMD', ''), 'amd', 'gpu'),
            "gpu_intel": get_spec(rec_req.get('GPU_Intel', ''), 'intel', 'gpu'),
            "ram": rec_req.get('RAM', ''),
            "storage": rec_req.get('File Size', '')
        }
    }

def aggregate_selected_specs(games, min_df, rec_df):
    """
    Menghitung spesifikasi tertinggi yang digunakan untuk filtering
    berdasarkan semua game yang terdeteksi (skor tertinggi per komponen)
    """
    result = {
        'min': {
            'cpu_intel': {'name': '', 'score': 0, 'game': ''},
            'cpu_amd': {'name': '', 'score': 0, 'game': ''},
            'gpu_nvidia': {'name': '', 'score': 0, 'game': ''},
            'gpu_amd': {'name': '', 'score': 0, 'game': ''},
            'gpu_intel': {'name': '', 'score': 0, 'game': ''},
            'ram': 0,
            'storage': 0
        },
        'rec': {
            'cpu_intel': {'name': '', 'score': 0, 'game': ''},
            'cpu_amd': {'name': '', 'score': 0, 'game': ''},
            'gpu_nvidia': {'name': '', 'score': 0, 'game': ''},
            'gpu_amd': {'name': '', 'score': 0, 'game': ''},
            'gpu_intel': {'name': '', 'score': 0, 'game': ''},
            'ram': 0,
            'storage': 0
        }
    }
    # Mapping dari internal key ke nama kolom untuk spesifikasi (nama hardware)
    col_map = {
        'cpu_intel': 'CPU_Intel',
        'cpu_amd': 'CPU_AMD',
        'gpu_nvidia': 'GPU_NVIDIA',
        'gpu_amd': 'GPU_AMD',
        'gpu_intel': 'GPU_Intel'
    }
    # Mapping dari internal key ke nama kolom untuk skor
    score_col_map = {
        'cpu_intel': 'CPU_Intel_score',
        'cpu_amd': 'CPU_AMD_score',
        'gpu_nvidia': 'GPU_NVIDIA_score',
        'gpu_amd': 'GPU_AMD_score',
        'gpu_intel': 'GPU_Intel_score'
    }
    for game in games:
        min_row = min_df[min_df['App'].str.lower() == game.lower()]
        rec_row = rec_df[rec_df['App'].str.lower() == game.lower()]
        if min_row.empty:
            continue
        min_req = min_row.iloc[0]
        if rec_row.empty:
            rec_req = min_req
        else:
            rec_req = rec_row.iloc[0]

        # Minimum
        for key in ['cpu_intel', 'cpu_amd', 'gpu_nvidia', 'gpu_amd', 'gpu_intel']:
            score_key = score_col_map[key]
            name_key = col_map[key]
            score = to_python_int(min_req.get(score_key, 0))
            if score > result['min'][key]['score']:
                vendor = key.split('_')[1]
                spec_type = 'cpu' if key.startswith('cpu') else 'gpu'
                name_val = min_req.get(name_key, '')
                # Intel CPU dan Intel GPU: langsung simpan nama (tanpa validasi)
                if key in ['cpu_intel', 'gpu_intel']:
                    if pd.notna(name_val) and isinstance(name_val, str) and name_val.strip():
                        result['min'][key]['name'] = name_val.strip()
                        result['min'][key]['game'] = game
                else:
                    if pd.notna(name_val) and isinstance(name_val, str):
                        name_val = name_val.strip()
                        if is_valid_spec(name_val, vendor, spec_type):
                            result['min'][key]['name'] = name_val
                            result['min'][key]['game'] = game
                result['min'][key]['score'] = score
        ram_val = to_python_int(int(''.join(filter(str.isdigit, str(min_req.get('RAM', '0')))) or 0))
        if ram_val > result['min']['ram']:
            result['min']['ram'] = ram_val
        storage_val = to_python_int(int(''.join(filter(str.isdigit, str(min_req.get('File Size', '0')))) or 0))
        if storage_val > result['min']['storage']:
            result['min']['storage'] = storage_val

        # Recommended
        for key in ['cpu_intel', 'cpu_amd', 'gpu_nvidia', 'gpu_amd', 'gpu_intel']:
            score_key = score_col_map[key]
            name_key = col_map[key]
            score = to_python_int(rec_req.get(score_key, 0))
            if score > result['rec'][key]['score']:
                vendor = key.split('_')[1]
                spec_type = 'cpu' if key.startswith('cpu') else 'gpu'
                name_val = rec_req.get(name_key, '')
                if key in ['cpu_intel', 'gpu_intel']:
                    if pd.notna(name_val) and isinstance(name_val, str) and name_val.strip():
                        result['rec'][key]['name'] = name_val.strip()
                        result['rec'][key]['game'] = game
                else:
                    if pd.notna(name_val) and isinstance(name_val, str):
                        name_val = name_val.strip()
                        if is_valid_spec(name_val, vendor, spec_type):
                            result['rec'][key]['name'] = name_val
                            result['rec'][key]['game'] = game
                result['rec'][key]['score'] = score
        ram_val_rec = to_python_int(int(''.join(filter(str.isdigit, str(rec_req.get('RAM', '0')))) or 0))
        if ram_val_rec > result['rec']['ram']:
            result['rec']['ram'] = ram_val_rec
        storage_val_rec = to_python_int(int(''.join(filter(str.isdigit, str(rec_req.get('File Size', '0')))) or 0))
        if storage_val_rec > result['rec']['storage']:
            result['rec']['storage'] = storage_val_rec

    return result

@app.on_event("startup")
async def startup_event():
    global laptop_df, min_req_df, rec_req_df, min_req_kb, rec_req_kb
    global laptop_list, laptop_brand_list, unique_word_kb, game_abbreviations_kb, game_alt_titles_kb
    global series_abbreviations, bigram_unique_kb, series_games, brand_models_mapping

    try:
        print("Memuat data...")
        laptop_df, min_req_df, rec_req_df = load_data()

        print("Membangun KB...")
        min_req_kb, rec_req_kb = build_kb(min_req_df, rec_req_df)
        laptop_kb = build_laptop_kb(laptop_df)

        series_abbreviations, series_games, _ = generate_series_kb(min_req_df)
        unique_word_kb = build_unique_word_kb(min_req_df)
        bigram_unique_kb = build_bigram_trigram_kb(min_req_df)
        game_abbreviations_kb, game_alt_titles_kb = build_abbrev_alt_kb(
            min_req_df['App'].tolist(), series_abbreviations, series_games
        )
        laptop_list, laptop_brand_list, brand_models_mapping = build_brand_models_kb(laptop_df)

        print("✅ Semua data dan KB berhasil dimuat.")
    except Exception as e:
        print("❌ ERROR saat startup:")
        traceback.print_exc()
        raise e

@app.get("/recommend")
async def recommend(
    query: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100)
):
    try:
        if any(v is None for v in [laptop_df, min_req_df, rec_req_df, min_req_kb, rec_req_kb,
                                   laptop_list, laptop_brand_list, unique_word_kb,
                                   game_abbreviations_kb, game_alt_titles_kb,
                                   series_abbreviations, bigram_unique_kb,
                                   series_games, brand_models_mapping]):
            raise HTTPException(status_code=503, detail="Data belum siap.")

        pipeline_meta = nlp_pipeline_fuzzy(
            query,
            min_req_df['App'].tolist(),
            laptop_df['Model'].tolist(),
            laptop_df['Brand'].unique().tolist(),
            unique_word_kb,
            game_abbreviations_kb,
            game_alt_titles_kb,
            series_abbreviations,
            bigram_unique_kb
        )

        result_df = get_laptop_recommendations_with_intent(
            user_query=query,
            laptop_df=laptop_df,
            min_req_df=min_req_df,
            rec_req_df=rec_req_df,
            min_req_kb=min_req_kb,
            rec_req_kb=rec_req_kb,
            laptop_list=laptop_list,
            laptop_brand_list=laptop_brand_list,
            unique_word_kb=unique_word_kb,
            game_abbreviations_kb=game_abbreviations_kb,
            game_alt_titles_kb=game_alt_titles_kb,
            series_abbreviations=series_abbreviations,
            bigram_unique_kb=bigram_unique_kb,
            series_games=series_games,
            brand_models_mapping=brand_models_mapping
        )

        if result_df is None or result_df.empty:
            records = []
        else:
            result_df = result_df.rename(columns={
                'Final Price': 'Final_Price',
                'Storage type': 'Storage_type'
            })
            records = result_df.head(limit).to_dict(orient='records')

        game_requirements = {}
        for game in pipeline_meta['found_games']:
            specs = get_game_specs_from_df(game, min_req_df, rec_req_df)
            if specs:
                game_requirements[game] = specs

        selected_specs = aggregate_selected_specs(pipeline_meta['found_games'], min_req_df, rec_req_df)

        budget = pipeline_meta['budget']
        budget_display = None
        if budget is not None:
            if isinstance(budget, tuple):
                budget_display = f"{budget[0]:,} - {budget[1]:,}"
            else:
                budget_display = f"{budget:,}"

        return {
            "status": "success",
            "data": records,
            "total_found": len(result_df) if result_df is not None else 0,
            "detected_games": pipeline_meta['found_games'],
            "detected_laptops": pipeline_meta['found_laptops'],
            "detected_budget": budget_display,
            "detected_ram": pipeline_meta['ram'],
            "game_requirements": game_requirements,
            "selected_specs": selected_specs
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error processing query '{query}':")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Terjadi kesalahan internal: {str(e)}")

@app.get("/debug")
async def debug():
    return {
        "laptop_df_loaded": laptop_df is not None,
        "min_req_df_loaded": min_req_df is not None,
        "rec_req_df_loaded": rec_req_df is not None,
        "min_req_kb_size": len(min_req_kb) if min_req_kb else 0,
        "rec_req_kb_size": len(rec_req_kb) if rec_req_kb else 0,
        "laptop_list_size": len(laptop_list) if laptop_list else 0,
        "laptop_brand_list": laptop_brand_list if laptop_brand_list else [],
        "unique_word_kb_size": len(unique_word_kb) if unique_word_kb else 0,
        "game_abbreviations_kb_size": len(game_abbreviations_kb) if game_abbreviations_kb else 0,
        "game_alt_titles_kb_size": len(game_alt_titles_kb) if game_alt_titles_kb else 0,
        "series_abbreviations_size": len(series_abbreviations) if series_abbreviations else 0,
        "bigram_unique_kb_size": len(bigram_unique_kb) if bigram_unique_kb else 0,
        "series_games_size": len(series_games) if series_games else 0,
        "brand_models_mapping_keys": list(brand_models_mapping.keys()) if brand_models_mapping else []
    }

@app.get("/health")
async def health():
    return {"status": "ok"}