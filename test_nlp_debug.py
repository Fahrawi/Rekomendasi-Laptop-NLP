import sys
sys.path.insert(0, '.')

from scripts.load_data import load_data
from src.nlp_pipeline import nlp_pipeline_fuzzy

# Basic load
laptop_df, min_req_df, rec_req_df = load_data()
games_list = min_req_df['App'].tolist()
laptop_models = laptop_df['Model'].tolist()
laptop_brands = laptop_df['Brand'].unique().tolist()

# Build KBs (minimal)
unique_word_kb = {}
game_abbreviations_kb = {}
game_alt_titles_kb = {}
series_abbreviations = {}
bigram_unique_kb = {}
brand_models_mapping = {}

query = "laptop untuk bermain black myth wukong termurah"
print(f"Query: {query}\n")

result = nlp_pipeline_fuzzy(
    query,
    games_list,
    laptop_models,
    laptop_brands,
    unique_word_kb,
    game_abbreviations_kb,
    game_alt_titles_kb,
    series_abbreviations,
    bigram_unique_kb,
    brand_models_mapping
)

print(f"\nResults:")
print(f"  prefer_cheapest: {result.get('prefer_cheapest')}")
print(f"  found_games: {result.get('found_games')}")
print(f"  has_game_context: {result.get('has_game_context')}")
