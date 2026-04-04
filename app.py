import sys
import os
import traceback
import re
import importlib
import pandas as pd
import numpy as np
import logging
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s', force=True)
logger = logging.getLogger(__name__)

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
# Phase 1 & 2 imports for hybrid recommendation
from src.smart_filters_and_ahp import apply_smart_filters, get_intent_based_weights
from src.topsis_engine import run_topsis, get_topsis_summary
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Tuple

try:
    # Optional accelerated pipeline plugin.
    # Expected API:
    # - nlp_pipeline_accelerated(...same args as nlp_pipeline_fuzzy...)
    # - is_accelerated_nlp_available() -> bool
    from src.nlp_accelerated import nlp_pipeline_accelerated, is_accelerated_nlp_available
except Exception:
    nlp_pipeline_accelerated = None
    is_accelerated_nlp_available = None

app = FastAPI(title="Laptop Recommendation System API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# PHASE 3: REQUEST & RESPONSE MODELS FOR HYBRID RECOMMENDATION
# ============================================================================

class HybridRecommendRequest(BaseModel):
    """Request model for integrated NLP + Phase 1 + Phase 2 recommendation"""
    query: str  # Natural language query, e.g., "mau main hi3rd dengan budget 20jt"
    top_n: int = 5  # Number of recommendations (default 5, max 10)
    nlp_mode: str = "auto"  # auto | cpu | gpu

class LaptopSpecsResponse(BaseModel):
    """Laptop specifications in response"""
    cpu_name: Optional[str] = None
    cpu_score: Optional[float] = None
    gpu_name: Optional[str] = None
    gpu_score: Optional[float] = None
    ram: Optional[int] = None
    ram_type: Optional[str] = None  # DDR3/DDR4/DDR5
    storage: Optional[int] = None
    final_price: Optional[int] = None

class SystemRequirements(BaseModel):
    """System requirements for a game/app"""
    app_name: str
    cpu: str
    gpu: str
    ram: str

class RecommendedLaptop(BaseModel):
    """Single recommended laptop with TOPSIS score"""
    rank: int
    brand: str
    model: str
    topsis_score: float
    specs: LaptopSpecsResponse
    reasoning: str  # Why this laptop is recommended

class HybridRecommendResponse(BaseModel):
    """Response model for hybrid recommendation"""
    status: str
    intent: str
    filtered_count: int
    ranked_count: int
    weights_applied: dict
    recommendations: List[RecommendedLaptop]
    message: str
    app_requirements: Optional[List[SystemRequirements]] = None  # Minimum & Recommended for detected apps

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


def detect_runtime_acceleration() -> Dict[str, Any]:
    """Detect optional acceleration capabilities with safe fallbacks."""
    info = {
        "torch_installed": False,
        "cuda_available": False,
        "accelerated_plugin_available": False,
    }

    try:
        torch_spec = importlib.util.find_spec("torch")
        if torch_spec is not None:
            info["torch_installed"] = True
            import torch  # type: ignore
            info["cuda_available"] = bool(torch.cuda.is_available())
    except Exception:
        info["torch_installed"] = False
        info["cuda_available"] = False

    try:
        plugin_ok = bool(
            nlp_pipeline_accelerated is not None
            and is_accelerated_nlp_available is not None
            and is_accelerated_nlp_available()
        )
        info["accelerated_plugin_available"] = plugin_ok
    except Exception:
        info["accelerated_plugin_available"] = False

    return info


def resolve_nlp_mode(request_mode: str, accel_info: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """Resolve NLP mode with compatibility fallback."""
    mode = str(request_mode or "auto").strip().lower()
    if mode not in {"auto", "cpu", "gpu"}:
        mode = "auto"

    can_use_gpu = bool(accel_info.get("cuda_available")) and bool(accel_info.get("accelerated_plugin_available"))

    if mode == "cpu":
        return "cpu", None

    if mode == "gpu":
        if can_use_gpu:
            return "gpu", None
        return "cpu", "GPU mode requested but acceleration backend is unavailable. Falling back to CPU NLP."

    # auto mode
    if can_use_gpu:
        return "gpu", None
    return "cpu", None


def run_nlp_with_fallback(
    query: str,
    game_list: List[str],
    model_list: List[str],
    brand_list: List[str],
    unique_keyword_game_map,
    abbreviations_kb,
    alt_titles_kb,
    series_abbrev,
    bigram_kb,
    brand_models_map,
    requested_mode: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Run NLP using selected mode and fallback safely to CPU pipeline."""
    accel_info = detect_runtime_acceleration()
    selected_mode, warning = resolve_nlp_mode(requested_mode, accel_info)

    runtime_meta = {
        "nlp_requested_mode": requested_mode,
        "nlp_selected_mode": selected_mode,
        "nlp_warning": warning,
        "acceleration": accel_info,
    }

    # Default CPU pipeline is always available and remains source of truth.
    if selected_mode == "cpu":
        return nlp_pipeline_fuzzy(
            query,
            game_list,
            model_list,
            brand_list,
            unique_keyword_game_map,
            abbreviations_kb,
            alt_titles_kb,
            series_abbrev,
            bigram_kb,
            brand_models_map,
        ), runtime_meta

    # GPU path: attempt accelerated plugin, then fallback to CPU if it fails.
    try:
        result = nlp_pipeline_accelerated(
            query,
            game_list,
            model_list,
            brand_list,
            unique_keyword_game_map,
            abbreviations_kb,
            alt_titles_kb,
            series_abbrev,
            bigram_kb,
            brand_models_map,
        )
        return result, runtime_meta
    except Exception as ex:
        runtime_meta["nlp_warning"] = f"Accelerated NLP failed ({ex}). Falling back to CPU NLP."
        runtime_meta["nlp_selected_mode"] = "cpu"
        return nlp_pipeline_fuzzy(
            query,
            game_list,
            model_list,
            brand_list,
            unique_keyword_game_map,
            abbreviations_kb,
            alt_titles_kb,
            series_abbrev,
            bigram_kb,
            brand_models_map,
        ), runtime_meta

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


def extract_numeric_value(value):
    digits = re.findall(r'\d+', str(value or ''))
    return int(''.join(digits)) if digits else 0


def get_cpu_vendor(cpu_name):
    cpu_text = str(cpu_name or '').lower()
    if 'amd' in cpu_text or any(keyword in cpu_text for keyword in ['ryzen', 'fx', 'athlon', 'phenom', 'opteron']):
        return 'amd'
    return 'intel'


def get_gpu_vendor(gpu_name):
    gpu_text = str(gpu_name or '').lower()
    if any(keyword in gpu_text for keyword in ['rtx', 'gtx', 'mx', 'geforce']):
        return 'nvidia'
    if any(keyword in gpu_text for keyword in ['radeon', 'rx', 'vega', 'pro']):
        return 'amd'
    if any(keyword in gpu_text for keyword in ['iris', 'uhd', 'hd graphics', 'integrated']):
        return 'intel'
    return 'intel'


def format_budget_for_message(budget):
    if isinstance(budget, tuple):
        return f"Rp {budget[0]:,} - Rp {budget[1]:,}"
    return f"Rp {budget:,}"


def get_intent_label(intent):
    labels = {
        "FIND_LAPTOP_FOR_GAME": "gaming",
        "3D_DESIGN": "3D design/rendering",
        "2D_DESIGN": "2D design",
        "AI_DEVELOPMENT": "AI development",
        "WEB_DEVELOPMENT": "web development",
        "VIDEO_EDITOR": "video editing",
        "MULTITASKING": "multitasking",
        "WORKSTATION": "workstation",
        "ENTERTAINMENT": "entertainment",
        "OLAH_DATA": "olah data",
        "FIND_LAPTOP_GENERAL": "kebutuhan umum",
    }
    return labels.get(intent, intent)


def normalize_requirement_display(game_name, cpu_value, gpu_value):
    cpu_text = str(cpu_value or '').strip()
    gpu_text = str(gpu_value or '').strip()
    game_lower = str(game_name or '').lower()

    # Keep CS naming consistent with the rest of the dataset display style.
    if 'counter-strike: global offensive' in game_lower or 'counter-strike 2' in game_lower:
        if 'intel core i5-750' in cpu_text.lower():
            cpu_text = 'Intel Core i5-750'
        if 'directx 11-compatible' in gpu_text.lower() and '1 gb' in gpu_text.lower():
            gpu_text = 'GeForce GTX 750 Ti'

    return cpu_text or 'N/A', gpu_text or 'N/A'


def build_game_benchmark_thresholds(game_names, min_req_df):
    thresholds = {
        'CPU_Intel_score': 0,
        'CPU_AMD_score': 0,
        'GPU_NVIDIA_score': 0,
        'GPU_AMD_score': 0,
        'GPU_Intel_score': 0,
        'RAM': 0,
        'File Size': 0,
    }
    matched_games = []

    for game in game_names:
        min_row = min_req_df[min_req_df['App'].str.lower() == game.lower()]
        if min_row.empty:
            continue

        matched_games.append(game)
        req = min_row.iloc[0]
        for key in ['CPU_Intel_score', 'CPU_AMD_score', 'GPU_NVIDIA_score', 'GPU_AMD_score', 'GPU_Intel_score']:
            thresholds[key] = max(thresholds[key], to_python_int(req.get(key, 0)) or 0)
        thresholds['RAM'] = max(thresholds['RAM'], extract_numeric_value(req.get('RAM', 0)))
        thresholds['File Size'] = max(thresholds['File Size'], extract_numeric_value(req.get('File Size', 0)))

    return thresholds, matched_games


def laptop_meets_game_benchmark(row, thresholds):
    cpu_vendor = get_cpu_vendor(row.get('CPU'))
    gpu_vendor = get_gpu_vendor(row.get('GPU'))

    if cpu_vendor == 'amd':
        cpu_req = thresholds['CPU_AMD_score']
    else:
        cpu_req = thresholds['CPU_Intel_score']

    if gpu_vendor == 'nvidia':
        gpu_req = thresholds['GPU_NVIDIA_score']
    elif gpu_vendor == 'amd':
        gpu_req = thresholds['GPU_AMD_score']
    else:
        gpu_req = thresholds['GPU_Intel_score']

    row_cpu_score = to_python_int(row.get('CPU_score', 0)) or 0
    row_gpu_score = to_python_int(row.get('GPU_score', 0)) or 0
    row_ram = extract_numeric_value(row.get('RAM', 0))
    row_storage = extract_numeric_value(row.get('Storage', 0))

    return (
        row_cpu_score >= cpu_req and
        row_gpu_score >= gpu_req and
        row_ram >= thresholds['RAM'] and
        row_storage >= thresholds['File Size']
    )


def apply_game_benchmark_filter(df, game_names, min_req_df):
    if df is None or df.empty or not game_names:
        return df

    thresholds, matched_games = build_game_benchmark_thresholds(game_names, min_req_df)
    if not matched_games:
        return pd.DataFrame()

    filtered = df[df.apply(lambda row: laptop_meets_game_benchmark(row, thresholds), axis=1)].copy()
    return filtered


def apply_cheapest_preference_weights(base_weights: Dict[str, float]) -> Dict[str, float]:
    """Re-balance weights so price dominates when user asks for cheapest options."""
    adjusted = dict(base_weights)
    non_bonus_keys = ['CPU', 'GPU', 'RAM', 'Storage', 'Price']
    bonus_weight = float(adjusted.get('Storage_Type_Bonus', 0.0))

    # Keep at least 45% emphasis on price for "termurah" queries.
    target_price = max(0.45, float(adjusted.get('Price', 0.0)))
    available_non_bonus_total = max(1e-9, 1.0 - bonus_weight)
    max_price_allowed = max(0.0, available_non_bonus_total - 1e-6)
    target_price = min(target_price, max_price_allowed)

    other_keys = [k for k in non_bonus_keys if k != 'Price']
    other_sum = sum(float(adjusted.get(k, 0.0)) for k in other_keys)
    remaining = max(0.0, available_non_bonus_total - target_price)

    adjusted['Price'] = target_price
    if other_sum > 0:
        scale = remaining / other_sum
        for k in other_keys:
            adjusted[k] = float(adjusted.get(k, 0.0)) * scale

    return adjusted


def get_laptop_weight_column(df: pd.DataFrame) -> Optional[str]:
    """Return a laptop weight column if the dataset has one, otherwise None."""
    if df is None or df.empty:
        return None

    preferred_names = ['weight', 'bobot', 'berat', 'laptop weight', 'device weight']
    for column in df.columns:
        column_lower = str(column).strip().lower()
        if any(name == column_lower or name in column_lower for name in preferred_names):
            return column
    return None


def apply_lightweight_preference_sorting(df: pd.DataFrame) -> pd.DataFrame:
    """Sort by laptop weight if the dataset has it; otherwise return unchanged."""
    weight_column = get_laptop_weight_column(df)
    if weight_column is None:
        return df

    sorted_df = df.sort_values(
        by=[weight_column, 'Final Price'],
        ascending=[True, True]
    ).reset_index(drop=True)
    sorted_df['Rank'] = range(1, len(sorted_df) + 1)
    return sorted_df

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
        # Untuk Intel CPU dan Intel GPU, kita validasi juga agar tidak menampilkan yang tidak sesuai
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
    col_map = {
        'cpu_intel': 'CPU_Intel',
        'cpu_amd': 'CPU_AMD',
        'gpu_nvidia': 'GPU_NVIDIA',
        'gpu_amd': 'GPU_AMD',
        'gpu_intel': 'GPU_Intel'
    }
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
            bigram_unique_kb,
            brand_models_mapping
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
    accel_info = detect_runtime_acceleration()
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
        "brand_models_mapping_keys": list(brand_models_mapping.keys()) if brand_models_mapping else [],
        "nlp_runtime": {
            "default_mode": os.getenv("NLP_MODE_DEFAULT", "auto"),
            "acceleration": accel_info,
        }
    }

# ============================================================================
# PHASE 3: HYBRID RECOMMENDATION ENDPOINT (Phase 1 + Phase 2)
# ============================================================================

@app.post("/api/recommend-hybrid")
async def recommend_hybrid(request: HybridRecommendRequest):
    """
    Integrated NLP + Phase 1 + Phase 2 Hybrid Recommendation Endpoint
    
    Workflow:
    1. NLP Pipeline: Extract intent, budget, RAM, brand, games from natural language query
    2. Phase 1: Apply smart filters based on extracted data
    3. Phase 1: Get AHP weights based on detected intent
    4. Phase 2: Run TOPSIS algorithm for ranking
    5. Return top-N recommendations with TOPSIS scores
    
    Args:
        request: HybridRecommendRequest with natural language query
    
    Returns:
        HybridRecommendResponse with ranked recommendations and TOPSIS scores
    """
    try:
        # Validate data is loaded
        if any(v is None for v in [laptop_df, min_req_df, rec_req_df, 
                                   laptop_list, laptop_brand_list]):
            raise HTTPException(status_code=503, detail="Data belum siap untuk rekomendasi.")
        
        query = request.query.strip()
        top_n = min(request.top_n or 5, 10)  # Max 10 recommendations
        
        print(f"\n📝 Query: {query}")
        
        # ========== NLP PIPELINE: EXTRACT FROM NATURAL LANGUAGE ==========
        
        requested_nlp_mode = request.nlp_mode or os.getenv("NLP_MODE_DEFAULT", "auto")

        # Run NLP via compatibility router (auto/cpu/gpu with safe fallback).
        nlp_result, nlp_runtime = run_nlp_with_fallback(
            query,
            min_req_df['App'].tolist(),
            laptop_df['Model'].tolist(),
            laptop_df['Brand'].unique().tolist(),
            unique_word_kb,
            game_abbreviations_kb,
            game_alt_titles_kb,
            series_abbreviations,
            bigram_unique_kb,
            brand_models_mapping,
            requested_nlp_mode,
        )
        
        print(f"🔍 NLP Result:")
        print(f"   Budget: {nlp_result.get('budget')}")
        print(f"   Games: {nlp_result.get('found_games', [])}")
        print(f"   Laptops/Brand: {nlp_result.get('found_laptops', [])}")
        print(f"   RAM: {nlp_result.get('ram', [])}")
        print(f"   Game Context: {nlp_result.get('has_game_context', False)}")
        print(f"   Preference Category: {nlp_result.get('preference_category', 'BALANCED')}")
        print(f"   NLP Mode: requested={nlp_runtime.get('nlp_requested_mode')} selected={nlp_runtime.get('nlp_selected_mode')}")
        if nlp_runtime.get('nlp_warning'):
            print(f"   ⚠ NLP Warning: {nlp_runtime.get('nlp_warning')}")
        
        # Extract data from NLP result using correct keys
        # Determine intent based on whether games or other keywords were found
        games = nlp_result.get('found_games', [])
        has_game_context = nlp_result.get('has_game_context', False)
        preference_category = nlp_result.get('preference_category', 'BALANCED')
        prefer_cheapest = preference_category == 'CHEAP'  # For compatibility
        budget_max = nlp_result.get('budget')  # Will be None if not detected
        ram_min = nlp_result.get('ram', [None])[0] if nlp_result.get('ram') else None  # Get first RAM if any
        brand = nlp_result.get('found_laptops', [None])[0] if nlp_result.get('found_laptops') else None
        
        # Determine intent with priority: App Intent > Gaming > General
        app_intent = nlp_result.get('app_intent')  # NEW: Check for design/productivity apps
        if app_intent:
            intent = app_intent  # Use detected app intent (2D_DESIGN, 3D_DESIGN, etc.)
            print(f"   ✓ Application intent detected: {intent}")
        elif games or has_game_context:
            intent = "FIND_LAPTOP_FOR_GAME"
        else:
            intent = "FIND_LAPTOP_GENERAL"

        print(f"   Intent (auto-detected): {intent}")
        
        # Convert brand to uppercase if present
        if brand:
            brand = brand.upper()
        
        # ========== PHASE 1: SMART FILTERS & AHP ==========
        
        print(f"\n🔧 Phase 1: Smart Filters + AHP Weighting")
        
        # Prepare filtering criteria based on NLP extraction
        filter_criteria = {
            'intent': intent,
            'budget': None,
            'ram': ram_min,
            'brand': brand,
            'game_list': games
        }
        
        # Add budget filter if detected
        if budget_max:
            filter_criteria['budget'] = (0, budget_max)
        
        # Apply smart filters based on extracted data
        filtered_df = apply_smart_filters(
            df=laptop_df,
            intent=intent,
            budget=filter_criteria['budget'],
            ram=filter_criteria['ram'],
            brand=filter_criteria['brand'],
            game_list=filter_criteria['game_list']
        )

        if games:
            benchmark_filtered_df = apply_game_benchmark_filter(filtered_df, games, min_req_df)
            if benchmark_filtered_df is not None and not benchmark_filtered_df.empty:
                filtered_df = benchmark_filtered_df
                print(f"   ✓ Game benchmark filter: {len(filtered_df)} laptop memenuhi minimum benchmark")
            else:
                filtered_df = pd.DataFrame()
                print("   ⚠️  Tidak ada laptop yang lolos benchmark minimum game.")
        
        # ========== VALIDATION: NO RESULTS HANDLING ==========
        
        if filtered_df is None or filtered_df.empty:
            # Provide detailed error message based on what was requested
            error_message = "Tidak ada laptop yang sesuai dengan kriteria Anda."

            filtered_without_budget = apply_smart_filters(
                df=laptop_df,
                intent=intent,
                budget=None,
                ram=filter_criteria['ram'],
                brand=filter_criteria['brand'],
                game_list=filter_criteria['game_list']
            )

            if games:
                filtered_without_budget = apply_game_benchmark_filter(filtered_without_budget, games, min_req_df)

            intent_label = get_intent_label(intent)
            
            if budget_max:
                budget_text = format_budget_for_message(budget_max)
                if filtered_without_budget is not None and not filtered_without_budget.empty:
                    min_price_for_intent = filtered_without_budget['Final Price'].min()
                    error_message = (
                        f"⚠️  Budget terlalu kecil ({budget_text}) untuk kebutuhan {intent_label}. "
                        f"Laptop termurah yang memenuhi kriteria ini mulai dari Rp {min_price_for_intent:,.0f}."
                    )
                else:
                    error_message = (
                        f"⚠️  Tidak ada laptop yang memenuhi spesifikasi minimum untuk kebutuhan {intent_label}, "
                        f"meskipun tanpa batas budget."
                    )
            else:
                if filtered_without_budget is not None and not filtered_without_budget.empty:
                    min_price_for_intent = filtered_without_budget['Final Price'].min()
                    error_message = (
                        f"⚠️  Tidak ada laptop yang cocok dengan filter saat ini untuk kebutuhan {intent_label}. "
                        f"Laptop termurah untuk intent ini mulai dari Rp {min_price_for_intent:,.0f}."
                    )
            
            if games:
                # Games were requested - check if any laptop can handle minimum requirements
                app_reqs = min_req_df[min_req_df['App'].str.lower().isin([g.lower() for g in games])]
                if not app_reqs.empty:
                    # Get minimum specs from game requirements
                    error_message += f"\n\n📋 Spesifikasi minimum diperlukan:"
                    for _, req in app_reqs.iterrows():
                        ram_raw = str(req.get('RAM', '')).strip()
                        ram_display = ram_raw if 'gb' in ram_raw.lower() else f"{ram_raw} GB"
                        error_message += f"\n  • {req['App']}: CPU {req['CPU']}, GPU {req['GPU']}, RAM {ram_display}"
                    
                    # Check if ANY laptop in entire dataset meets the requirements
                    min_gpu_req = app_reqs['GPU'].iloc[0] if not app_reqs.empty else None
                    if min_gpu_req:
                        min_gpu_laptops = laptop_df[laptop_df['GPU'].notna()].shape[0]
                        if min_gpu_laptops > 0:
                            error_message += f"\n\n💡 Tips: Tingkatkan budget untuk mendapatkan laptop dengan spesifikasi yang memenuhi kebutuhan game."
            
            return HybridRecommendResponse(
                status="success",
                intent=intent,
                filtered_count=0,
                ranked_count=0,
                weights_applied={},
                recommendations=[],
                message=error_message
            )
        
        filtered_count = len(filtered_df)
        print(f"   ✅ Filtered: {filtered_count} laptop")
        
        # ========== SPECIAL HANDLING: PREFERENCE CATEGORIES WITH DIFFERENT SORTING ==========
        # Different preference categories require different sorting strategies
        
        # Category 1: PERFORMANCE - Sort by CPU+GPU score descending (highest performance first)
        if preference_category == 'PERFORMANCE' and filtered_count > 0:
            print(f"\n📊 PERFORMANCE-PREFERENCE PATH: Sort by CPU+GPU score descending")
            
            # Sort by combined CPU+GPU score, then by price ascending as tiebreaker
            ranked_df = filtered_df.copy()
            ranked_df['combined_score'] = ranked_df['CPU_score'] + ranked_df['GPU_score']
            ranked_df = ranked_df.sort_values(
                by=['combined_score', 'Final Price'],
                ascending=[False, True]  # High performance first, then low price
            ).reset_index(drop=True)
            ranked_df['Rank'] = range(1, len(ranked_df) + 1)
            ranked_df['TOPSIS_Score'] = 1.0  # Dummy score untuk compatibility
            
            print(f"   ✓ Sorted by performance descending (terkencang duluan)")
            summary = get_topsis_summary(ranked_df, top_n=top_n)
            ranked_count = len(ranked_df)
            print(f"   ✅ Ranked: {ranked_count} laptop (by performance)")
            
            # ========== FORMAT RESPONSE ==========
            print(f"\n✨ Top {top_n} Performance Recommendations:")
            
            recommendations = []
            if summary and "top_recommendations" in summary:
                for idx, rec in enumerate(summary["top_recommendations"]):
                    reasoning = f"Rank #{rec['rank']}: Performa tertinggi (CPU+GPU score terkencang)"
                    
                    # Extract specs from summary
                    specs = rec.get('specs', {})
                    
                    recommendation = RecommendedLaptop(
                        rank=rec['rank'],
                        brand=rec.get('brand', 'N/A'),
                        model=rec.get('model', 'N/A'),
                        topsis_score=rec.get('topsis_score', 1.0),
                        specs=LaptopSpecsResponse(
                            cpu_name=specs.get('cpu_name'),
                            cpu_score=specs.get('cpu_score'),
                            gpu_name=specs.get('gpu_name'),
                            gpu_score=specs.get('gpu_score'),
                            ram=specs.get('ram'),
                            ram_type=specs.get('ram_type'),
                            storage=specs.get('storage'),
                            final_price=rec.get('price')
                        ),
                        reasoning=reasoning
                    )
                    recommendations.append(recommendation)
            
            response = HybridRecommendResponse(
                status="success",
                intent=intent,
                filtered_count=filtered_count,
                ranked_count=ranked_count,
                weights_applied={"CPU_Score": 0.5, "GPU_Score": 0.5},
                recommendations=recommendations,
                message=f"Berhasil merekomendasikan {len(recommendations)} laptop berkinerja tinggi dari {ranked_count} laptop yang cocok."
            )
            
            if games and intent == "FIND_LAPTOP_FOR_GAME":
                app_reqs = min_req_df[min_req_df['App'].str.lower().isin([g.lower() for g in games])]
                if not app_reqs.empty:
                    game_reqs = []
                    for _, req in app_reqs.iterrows():
                        ram_raw = str(req.get('RAM', '')).strip()
                        ram_display = ram_raw if 'gb' in ram_raw.lower() else f"{ram_raw} GB"
                        game_reqs.append(SystemRequirements(
                            app_name=req['App'],
                            cpu=req.get('CPU', 'N/A'),
                            gpu=req.get('GPU', 'N/A'),
                            ram=ram_display
                        ))
                    response.app_requirements = game_reqs
            
            return response
        
        # Category 2: CHEAP - Sort by price ascending (cheapest first)
        if preference_category == 'CHEAP' and intent == "FIND_LAPTOP_FOR_GAME" and games and filtered_count > 0:
            print(f"\n📊 CHEAP-PREFERENCE PATH: Sort by price for gaming")
            ranked_df = filtered_df.sort_values(
                by=['Final Price'],
                ascending=[True]
            ).reset_index(drop=True)
            ranked_df['Rank'] = range(1, len(ranked_df) + 1)
            ranked_df['TOPSIS_Score'] = 1.0  # Dummy score untuk compatibility
            
            print(f"   ✓ Sorted by price ascending (termurah duluan)")
            summary = get_topsis_summary(ranked_df, top_n=top_n)
            ranked_count = len(ranked_df)
            print(f"   ✅ Ranked: {ranked_count} laptop (by price)")
            
            # ========== FORMAT RESPONSE ==========
            print(f"\n✨ Top {top_n} Cheapest Recommendations:")
            
            recommendations = []
            if summary and "top_recommendations" in summary:
                for idx, rec in enumerate(summary["top_recommendations"]):
                    reasoning = f"Rank #{rec['rank']}: Termurah yang bisa main {', '.join(games)}"
                    
                    # Extract specs from summary
                    specs = rec.get('specs', {})
                    
                    recommendation = RecommendedLaptop(
                        rank=rec['rank'],
                        brand=rec.get('brand', 'N/A'),
                        model=rec.get('model', 'N/A'),
                        topsis_score=rec.get('topsis_score', 1.0),
                        specs=LaptopSpecsResponse(
                            cpu_name=specs.get('cpu_name'),
                            cpu_score=specs.get('cpu_score'),
                            gpu_name=specs.get('gpu_name'),
                            gpu_score=specs.get('gpu_score'),
                            ram=specs.get('ram'),
                            ram_type=specs.get('ram_type'),
                            storage=specs.get('storage'),
                            final_price=rec.get('price')
                        ),
                        reasoning=reasoning
                    )
                    recommendations.append(recommendation)
            
            response = HybridRecommendResponse(
                status="success",
                intent=intent,
                filtered_count=filtered_count,
                ranked_count=ranked_count,
                weights_applied={"Price": 1.0},
                recommendations=recommendations,
                message=f"Berhasil merekomendasikan {len(recommendations)} laptop termurah dari {ranked_count} laptop yang cocok."
            )
            
            if games and intent == "FIND_LAPTOP_FOR_GAME":
                app_reqs = min_req_df[min_req_df['App'].str.lower().isin([g.lower() for g in games])]
                if not app_reqs.empty:
                    game_reqs = []
                    for _, req in app_reqs.iterrows():
                        ram_raw = str(req.get('RAM', '')).strip()
                        ram_display = ram_raw if 'gb' in ram_raw.lower() else f"{ram_raw} GB"
                        game_reqs.append(SystemRequirements(
                            app_name=req['App'],
                            cpu=req.get('CPU', 'N/A'),
                            gpu=req.get('GPU', 'N/A'),
                            ram=ram_display
                        ))
                    response.app_requirements = game_reqs
            
            return response
        
        # ========== NORMAL PATH: AHP WEIGHTING + TOPSIS RANKING ==========
        # For CHEAP category in non-gaming context, VALUE category, LIGHTWEIGHT, or BALANCED
        
        # Get AHP weights based on intent
        ahp_weights = get_intent_based_weights(intent)
        logger.warning(f"[DEBUG] preference_category = {preference_category}")
        
        if preference_category == 'CHEAP':
            logger.warning(f"[DEBUG] Weights BEFORE: {ahp_weights}")
            ahp_weights = apply_cheapest_preference_weights(ahp_weights)
            logger.warning(f"[DEBUG] Weights AFTER: {ahp_weights}")
            print(f"   ✓ Cheapest preference detected: prioritizing Price weight")
        print(f"   ✅ Weights applied: {ahp_weights}")
        
        # ========== PHASE 2: TOPSIS RANKING ==========
        
        print(f"\n📊 Phase 2: TOPSIS Ranking")
        
        # For game intents, rank by performance-first criteria only.
        # RAM and storage are already enforced by the Phase 1 benchmark/filter step,
        # so they should not overpower GPU differences in the final ranking.
        custom_criteria = None
        if "GAME" in intent.upper():
            print(f"   ℹ️  Game intent - using GPU-optimized criteria")
            custom_criteria = {
                'GPU_score': {'type': 'benefit', 'description': 'GPU performance score'},
                'CPU_score': {'type': 'benefit', 'description': 'CPU performance score'},
                'Final Price': {'type': 'cost', 'description': 'Price in IDR'}
            }
        
        # Run TOPSIS algorithm
        ranked_df = run_topsis(filtered_df, ahp_weights, criteria_columns=custom_criteria)
        
        if ranked_df is None or ranked_df.empty:
            return HybridRecommendResponse(
                status="success",
                intent=intent,
                filtered_count=filtered_count,
                ranked_count=0,
                weights_applied=ahp_weights,
                recommendations=[],
                message="Gagal melakukan ranking dengan TOPSIS."
            )

        # Apply category-specific sorting
        if intent == "FIND_LAPTOP_FOR_GAME" and all(col in ranked_df.columns for col in ['GPU_score', 'CPU_score', 'RAM', 'Final Price', 'TOPSIS_Score']):
            ranked_df = ranked_df.sort_values(
                by=['GPU_score', 'CPU_score', 'RAM', 'TOPSIS_Score', 'Final Price'],
                ascending=[False, False, False, False, True]
            ).reset_index(drop=True)
            ranked_df['Rank'] = range(1, len(ranked_df) + 1)
            print("   ✓ Gaming tie-break applied: GPU > CPU > RAM > TOPSIS > Price")

        if preference_category == 'CHEAP' and 'Final Price' in ranked_df.columns and 'TOPSIS_Score' in ranked_df.columns:
            ranked_df = ranked_df.sort_values(
                by=['Final Price', 'TOPSIS_Score'],
                ascending=[True, False]
            ).reset_index(drop=True)
            ranked_df['Rank'] = range(1, len(ranked_df) + 1)
            print("   ✓ Cheapest preference applied: sorted by lowest Final Price")
        elif preference_category == 'LIGHTWEIGHT':
            weight_column = get_laptop_weight_column(ranked_df)
            if weight_column is None:
                print("   ℹ️  Lightweight preference detected, but dataset has no laptop weight column. Ignoring preference.")
            else:
                ranked_df = apply_lightweight_preference_sorting(ranked_df)
                print(f"   ✓ Lightweight preference applied: sorting by {weight_column}")
        
        # Get top-N recommendations with summary stats
        summary = get_topsis_summary(ranked_df, top_n=top_n)
        
        ranked_count = len(ranked_df)
        print(f"   ✅ Ranked: {ranked_count} laptop")
        
        # ========== FORMAT RESPONSE ==========
        
        print(f"\n✨ Top {top_n} Recommendations:")
        
        recommendations = []
        if summary and "top_recommendations" in summary:
            for idx, rec in enumerate(summary["top_recommendations"]):
                # Build reasoning based on weights and scores
                reasoning = f"Rank #{rec['rank']}: "
                if intent == "FIND_LAPTOP_FOR_GAME":
                    reasoning += f"GPU skor {rec['specs'].get('gpu_score', 0) or 0:.0f} (TOPSIS: {rec['topsis_score']:.4f})"
                elif intent == "AI_DEVELOPMENT":
                    reasoning += f"CPU & GPU optimal (TOPSIS: {rec['topsis_score']:.4f})"
                else:
                    reasoning += f"Cocok untuk use case Anda (TOPSIS: {rec['topsis_score']:.4f})"
                
                recommended = RecommendedLaptop(
                    rank=rec['rank'],
                    brand=rec.get('brand', 'N/A'),
                    model=rec.get('model', 'N/A'),
                    topsis_score=float(rec.get('topsis_score', 0)),
                    specs=LaptopSpecsResponse(
                        cpu_name=rec['specs'].get('cpu_name', None),
                        cpu_score=rec['specs'].get('cpu_score', None),
                        gpu_name=rec['specs'].get('gpu_name', None),
                        gpu_score=rec['specs'].get('gpu_score', None),
                        ram=rec['specs'].get('ram', None),
                        ram_type=rec['specs'].get('ram_type', None),
                        storage=rec['specs'].get('storage', None),
                        final_price=rec.get('price', None)
                    ),
                    reasoning=reasoning
                )
                recommendations.append(recommended)
                print(f"   {idx+1}. {rec.get('Brand')} {rec.get('Model')} (TOPSIS: {rec.get('TOPSIS_Score', 0):.4f})")
        
        # ========== SYSTEM REQUIREMENTS INFO ==========
        
        app_requirements = []
        if games:
            print(f"\n📋 System Requirements untuk game:")
            for game in games:
                # Try to find in both min and rec dataframes
                min_req = min_req_df[min_req_df['App'].str.lower() == game.lower()]
                rec_req = rec_req_df[rec_req_df['App'].str.lower() == game.lower()]
                
                if not min_req.empty:
                    min_row = min_req.iloc[0]
                    cpu_min = min_row.get('CPU_Intel', min_row.get('CPU', 'N/A'))
                    gpu_min = min_row.get('GPU_NVIDIA', min_row.get('GPU', 'N/A'))
                    cpu_min, gpu_min = normalize_requirement_display(game, cpu_min, gpu_min)
                    ram_min = str(min_row.get('RAM', 'N/A'))
                    app_requirements.append(SystemRequirements(
                        app_name=f"{game} (Minimum)",
                        cpu=cpu_min,
                        gpu=gpu_min,
                        ram=ram_min
                    ))
                    print(f"   ✅ {game} - Min: CPU:{cpu_min}, GPU:{gpu_min}, RAM:{ram_min}")
                
                if not rec_req.empty:
                    rec_row = rec_req.iloc[0]
                    # Recommended uses CPU_Intel and GPU_NVIDIA if available (not separate CPU/GPU columns)
                    cpu_rec = rec_row.get('CPU_Intel', rec_row.get('CPU', 'N/A'))
                    gpu_rec = rec_row.get('GPU_NVIDIA', rec_row.get('GPU', 'N/A'))
                    cpu_rec, gpu_rec = normalize_requirement_display(game, cpu_rec, gpu_rec)
                    ram_rec = rec_row.get('RAM', 'N/A')
                    
                    app_requirements.append(SystemRequirements(
                        app_name=f"{game} (Recommended)",
                        cpu=cpu_rec,
                        gpu=gpu_rec,
                        ram=str(ram_rec)
                    ))
                    print(f"   ✅ {game} - Rec: CPU:{cpu_rec}, GPU:{gpu_rec}, RAM:{ram_rec}")
        
        return HybridRecommendResponse(
            status="success",
            intent=intent,
            filtered_count=filtered_count,
            ranked_count=ranked_count,
            weights_applied=ahp_weights,
            recommendations=recommendations,
            message=f"Berhasil merekomendasikan {len(recommendations)} laptop dari {filtered_count} laptop yang cocok.",
            app_requirements=app_requirements if app_requirements else None
        )
    
    except ValueError as ve:
        print(f"❌ ValueError: {ve}")
        raise HTTPException(status_code=400, detail=f"Error: {str(ve)}")
    except Exception as e:
        print(f"❌ Error di /api/recommend-hybrid:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Terjadi kesalahan: {str(e)}")

@app.get("/health")
async def health():
    accel_info = detect_runtime_acceleration()
    selected_mode, _ = resolve_nlp_mode(os.getenv("NLP_MODE_DEFAULT", "auto"), accel_info)
    return {
        "status": "ok",
        "nlp_default_mode": os.getenv("NLP_MODE_DEFAULT", "auto"),
        "nlp_selected_mode": selected_mode,
        "acceleration": accel_info,
    }