# scripts/build_brand_models_kb.py
def build_brand_models_kb(laptop_df):
    laptop_list = laptop_df['Model'].tolist()
    laptop_brand_list = laptop_df['Brand'].unique().tolist()
    brand_models_mapping = {}
    for brand in laptop_brand_list:
        models = laptop_df[laptop_df['Brand'] == brand]['Model'].unique().tolist()
        brand_models_mapping[brand] = models
    return laptop_list, laptop_brand_list, brand_models_mapping