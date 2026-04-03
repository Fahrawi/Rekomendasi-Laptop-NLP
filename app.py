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
# Phase 1 & 2 imports for hybrid recommendation
from src.smart_filters_and_ahp import apply_smart_filters, get_intent_based_weights
from src.topsis_engine import run_topsis, get_topsis_summary
from pydantic import BaseModel
from typing import Optional, List

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
        
        # Use NLP pipeline to extract intent, budget, RAM, games, brand from natural language query
        nlp_result = nlp_pipeline_fuzzy(
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
        
        print(f"🔍 NLP Result:")
        print(f"   Budget: {nlp_result.get('budget')}")
        print(f"   Games: {nlp_result.get('found_games', [])}")
        print(f"   Laptops/Brand: {nlp_result.get('found_laptops', [])}")
        print(f"   RAM: {nlp_result.get('ram', [])}")
        
        # Extract data from NLP result using correct keys
        # Determine intent based on whether games or other keywords were found
        games = nlp_result.get('found_games', [])
        budget_max = nlp_result.get('budget')  # Will be None if not detected
        ram_min = nlp_result.get('ram', [None])[0] if nlp_result.get('ram') else None  # Get first RAM if any
        brand = nlp_result.get('found_laptops', [None])[0] if nlp_result.get('found_laptops') else None
        
        # Determine intent based on extracted data
        if games:
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
        
        if filtered_df is None or filtered_df.empty:
            return HybridRecommendResponse(
                status="success",
                intent=intent,
                filtered_count=0,
                ranked_count=0,
                weights_applied={},
                recommendations=[],
                message="Tidak ada laptop yang sesuai dengan kriteria Anda."
            )
        
        filtered_count = len(filtered_df)
        print(f"   ✅ Filtered: {filtered_count} laptop")
        
        # Get AHP weights based on intent
        ahp_weights = get_intent_based_weights(intent)
        print(f"   ✅ Weights applied: {ahp_weights}")
        
        # ========== PHASE 2: TOPSIS RANKING ==========
        
        print(f"\n📊 Phase 2: TOPSIS Ranking")
        
        # For game intents, exclude Storage from criteria since past minimum it doesn't affect gaming performance
        custom_criteria = None
        if "GAME" in intent.upper():
            print(f"   ℹ️  Game intent - using GPU-optimized criteria")
            custom_criteria = {
                'GPU_score': {'type': 'benefit', 'description': 'GPU performance score'},
                'CPU_score': {'type': 'benefit', 'description': 'CPU performance score'},
                'RAM': {'type': 'benefit', 'description': 'RAM in GB'},
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
                    app_requirements.append(SystemRequirements(
                        app_name=f"{game} (Minimum)",
                        cpu=min_row.get('CPU', 'N/A'),
                        gpu=min_row.get('GPU', 'N/A'),
                        ram=str(min_row.get('RAM', 'N/A'))
                    ))
                    print(f"   ✅ {game} - Min: CPU:{min_row.get('CPU', 'N/A')}, GPU:{min_row.get('GPU', 'N/A')}, RAM:{min_row.get('RAM', 'N/A')}")
                
                if not rec_req.empty:
                    rec_row = rec_req.iloc[0]
                    # Recommended uses CPU_Intel and GPU_NVIDIA if available (not separate CPU/GPU columns)
                    cpu_rec = rec_row.get('CPU_Intel', rec_row.get('CPU', 'N/A'))
                    gpu_rec = rec_row.get('GPU_NVIDIA', rec_row.get('GPU', 'N/A'))
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
    return {"status": "ok"}