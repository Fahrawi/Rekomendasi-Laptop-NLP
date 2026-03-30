# scripts/generate_series_kb.py
from src.series_abbreviation import create_abbreviations

def generate_series_kb(min_req_df):
    game_list = min_req_df['App'].tolist()
    series_abbreviations, series_games = create_abbreviations(game_list)
    return series_abbreviations, series_games, game_list