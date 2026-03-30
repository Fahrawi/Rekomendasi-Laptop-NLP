# main.py
import sys
import os

# Tambahkan root project ke sys.path
sys.path.insert(0, os.path.dirname(__file__))

# Import dari package scripts (wajib ada __init__.py di folder scripts)
from scripts.load_data import load_data
from scripts.build_kb import build_kb
from scripts.build_laptop_kb import build_laptop_kb
from scripts.generate_series_kb import generate_series_kb
from scripts.build_unique_word_kb import build_unique_word_kb
from scripts.build_bigram_trigram_kb import build_bigram_trigram_kb
from scripts.build_abbrev_alt_kb import build_abbrev_alt_kb
from scripts.build_brand_models_kb import build_brand_models_kb
from src.recommender_system import get_laptop_recommendations_with_intent

if __name__ == "__main__":
    # 1. Load data
    laptop_df, min_req_df, rec_req_df = load_data()
    
    # 2. Build KB min/rec
    min_req_kb, rec_req_kb = build_kb(min_req_df, rec_req_df)
    
    # 3. Build laptop KB (optional, not used later but kept)
    laptop_kb = build_laptop_kb(laptop_df)
    
    # 4. Generate series abbreviations
    series_abbreviations, series_games, game_list = generate_series_kb(min_req_df)
    
    # 5. Build unique word KB
    unique_word_kb = build_unique_word_kb(min_req_df)
    
    # 6. Build bigram/trigram KB
    bigram_unique_kb = build_bigram_trigram_kb(min_req_df)
    
    # 7. Build abbreviation and alt title KB
    game_abbreviations_kb, game_alt_titles_kb = build_abbrev_alt_kb(game_list, series_abbreviations, series_games)
    
    # 8. Build brand models mapping and laptop lists
    laptop_list, laptop_brand_list, brand_models_mapping = build_brand_models_kb(laptop_df)
    
    # Test queries
    queries_to_test = [
        "laptop Acer Predator atau Asus ROG 16gb ram buat spiderman remastered minimal 15 juta",
        "laptop Asus diatas 12 juta untuk bermain cod mw 2 remastered",
        "butuh laptop asus utk hi3rd, cs2, cities 2, hsr, genshin RAM 8GB dengan budget 10 sampai 30 juta",
    ]
    for query in queries_to_test:
        print("="*50)
        print(f"Testing Query: {query}")
        print("="*50)
        recommendations = get_laptop_recommendations_with_intent(
            query,
            laptop_df,
            min_req_df,
            rec_req_df,
            min_req_kb,
            rec_req_kb,
            laptop_list,
            laptop_brand_list,
            unique_word_kb,
            game_abbreviations_kb,
            game_alt_titles_kb,
            series_abbreviations,
            bigram_unique_kb,
            series_games,
            brand_models_mapping
        )
        print("\n")