# test_nlp_pipeline.py
import sys
import os

root_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, root_dir)
sys.path.insert(0, os.path.join(root_dir, 'scripts'))
sys.path.insert(0, os.path.join(root_dir, 'src'))

from scripts.load_data import load_data
from scripts.generate_series_kb import generate_series_kb
from scripts.build_unique_word_kb import build_unique_word_kb
from scripts.build_bigram_trigram_kb import build_bigram_trigram_kb
from scripts.build_abbrev_alt_kb import build_abbrev_alt_kb
from scripts.build_brand_models_kb import build_brand_models_kb
from src.nlp_pipeline import nlp_pipeline_fuzzy

def main():
    print("Memuat data...")
    laptop_df, min_req_df, _ = load_data()

    print("Membangun series abbreviations...")
    series_abbreviations, series_games, game_list = generate_series_kb(min_req_df)

    print("Membangun unique word KB...")
    unique_word_kb = build_unique_word_kb(min_req_df)

    print("Membangun bigram/trigram KB...")
    bigram_unique_kb = build_bigram_trigram_kb(min_req_df)

    print("Membangun abbreviation & alt title KB...")
    game_abbreviations_kb, game_alt_titles_kb = build_abbrev_alt_kb(game_list, series_abbreviations, series_games)

    print("Membangun laptop & brand lists...")
    laptop_list, laptop_brand_list, _ = build_brand_models_kb(laptop_df)

    queries = [
        "laptop asus ROG dan predator 16gb ram buat spiderman remastered",
        "laptop asus ROG dan acer 16gb ram buat spiderman remastered",
        "laptop asus dan predator 16gb ram buat spiderman remastered",
        "laptop untuk bermain cod mw 2 remastered dengan budget 8 sampai 10 juta",
        "gaming laptop assasin creed 3 remastered murah 5-7 juta",
        "laptop acer dan asus buat main uma musume, valo dan ac shadows hsr sekitar 18-20 juta dengan RAM 16 gb",
        "laptop acer buat main dark souls iii dan delta",
        "gaming laptop Marvel's Spider-Man Remastered sekitar sepuluh juta",
        "gaming laptop hongkai impatc dan genshhin murah sekitar 5,5 sampai 6,7 juta",
        "laptop buat main honkai impatc",
        "laptop untuk game dengan budget lima juta",
        "laptop gaming harga delapan ribu",
        "Laptop Asus seharga 10 juta untuk main hsr",
        "budget dua puluh sampai tiga puluh juta untuk laptop",
        "gaming laptop Marvel's Spider-Man Remastered murah sekitar delapan sampai sepuluh juta"
    ]

    print("\n" + "="*60)
    print("TESTING NLP PIPELINE")
    print("="*60)

    for query in queries:
        result = nlp_pipeline_fuzzy(
            query,
            game_list,
            laptop_list,
            laptop_brand_list,
            unique_word_kb,
            game_abbreviations_kb,
            game_alt_titles_kb,
            series_abbreviations,
            bigram_unique_kb
        )
        print(f"\nQuery: {query}")
        print(f"  Found games  : {result['found_games']}")
        print(f"  Found laptops: {result['found_laptops']}")
        print(f"  Budget       : {result['budget']}")
        print(f"  RAM          : {result['ram']}")
        print("-" * 50)

if __name__ == "__main__":
    main()