# scripts/build_kb.py
def build_kb(min_req_df, rec_req_df):
    min_req_kb = min_req_df.drop_duplicates(subset=['App']).set_index('App').to_dict('index')
    rec_req_kb = rec_req_df.drop_duplicates(subset=['App']).set_index('App').to_dict('index')
    return min_req_kb, rec_req_kb