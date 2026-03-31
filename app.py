# app.py
import sys
import os
import traceback
import pandas as pd
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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # tambahkan domain lain jika perlu
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
        laptop_kb = build_laptop_kb(laptop_df)  # optional

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
    query: str = Query(..., description="Query pengguna dalam bahasa Indonesia", min_length=1),
    limit: int = Query(20, ge=1, le=100, description="Jumlah maksimum rekomendasi yang ditampilkan (1-100)")
):
    try:
        # Cek data sudah siap
        if any(v is None for v in [laptop_df, min_req_df, rec_req_df, min_req_kb, rec_req_kb,
                                   laptop_list, laptop_brand_list, unique_word_kb,
                                   game_abbreviations_kb, game_alt_titles_kb,
                                   series_abbreviations, bigram_unique_kb,
                                   series_games, brand_models_mapping]):
            raise HTTPException(status_code=503, detail="Data belum siap. Silakan coba lagi nanti.")

        # Jalankan pipeline NLP untuk mendapatkan metadata (deteksi entity)
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

        # Dapatkan rekomendasi
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

        # Konversi DataFrame ke list of dict
        if result_df is None or result_df.empty:
            records = []
        else:
            # Rename kolom agar sesuai dengan frontend
            result_df = result_df.rename(columns={
                'Final Price': 'Final_Price',
                'Storage type': 'Storage_type'
            })
            records = result_df.head(limit).to_dict(orient='records')

        # Format budget untuk tampilan (opsional)
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
            "detected_ram": pipeline_meta['ram']
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