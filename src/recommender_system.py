# src/recommender_system.py
import pandas as pd
from fuzzywuzzy import process
from src.nlp_pipeline import nlp_pipeline_fuzzy
from src.recommender_core import categorize_laptops_adapted

def recognize_intent_simple(user_query, found_games, found_laptops_entities, extracted_budget):
    query_lower = user_query.lower()
    compare_keywords = ['bandingkan', 'bandingkan dengan', 'versus', 'vs', 'compare']
    if any(keyword in query_lower for keyword in compare_keywords) and len(found_laptops_entities) >= 2:
        return "COMPARE_LAPTOPS"
    expensive_keywords = ['termahal', 'paling mahal', 'harga tinggi']
    if any(keyword in query_lower for keyword in expensive_keywords):
        return "FIND_MOST_EXPENSIVE_LAPTOP"
    cheapest_keywords = ['termurah', 'paling murah', 'harga rendah', 'murah']
    if any(keyword in query_lower for keyword in cheapest_keywords):
        if found_games:
            return "FIND_CHEAPEST_LAPTOP_FOR_GAME"
        if extracted_budget is not None:
            return "FILTER_LAPTOPS"
    filter_keywords = ['brand', 'merek', 'model', 'seri', 'tipe', 'type', 'budget', 'harga', 'ram']
    if (any(keyword in query_lower for keyword in filter_keywords) or found_laptops_entities or extracted_budget is not None) and not found_games:
        return "FILTER_LAPTOPS"
    game_keywords = ['main', 'untuk', 'buat', 'bermain', 'playing', 'cocok', 'game', 'gaming', 'butuh']
    if found_games and any(keyword in query_lower for keyword in game_keywords):
        return "FIND_LAPTOP_FOR_GAME"
    return "QUERY_NOT_PROCESSED"


def get_laptop_recommendations_with_intent(
    user_query,
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
):
    print(f"Query Pengguna: {user_query}")

    pipeline_result = nlp_pipeline_fuzzy(
        user_query,
        min_req_df['App'].tolist(),
        laptop_df['Model'].tolist(),
        laptop_df['Brand'].unique().tolist(),
        unique_word_kb,
        game_abbreviations_kb,
        game_alt_titles_kb,
        series_abbreviations,
        bigram_unique_kb
    )
    found_games_nlp = pipeline_result['found_games']
    found_laptops_entities = pipeline_result['found_laptops']
    extracted_budget = pipeline_result['budget']
    extracted_ram = pipeline_result['ram']
    budget_span = pipeline_result.get('budget_span')  # (start, end) posisi angka budget

    query_lower = user_query.lower()
    sekitar_keywords = ['sekitar', 'kisaran', 'kurang lebih']
    if isinstance(extracted_budget, (int, float)) and not isinstance(extracted_budget, tuple) and any(keyword in query_lower for keyword in sekitar_keywords):
        nominal_budget = extracted_budget
        min_budget = max(0, nominal_budget - 1_000_000)
        max_budget = nominal_budget + 1_000_000
        extracted_budget = (min_budget, max_budget)
        print(f"Detected 'sekitar' budget: Adjusting budget to range {extracted_budget[0]:,} - {extracted_budget[1]:,}")

    detected_intent = recognize_intent_simple(user_query, found_games_nlp, found_laptops_entities, extracted_budget)
    print(f"Hasil NLP Pipeline: Game={found_games_nlp}, Laptop/Entity={found_laptops_entities}, Budget={extracted_budget}, RAM={extracted_ram}")
    print(f"Intent Terdeteksi: {detected_intent}")

    # Helper untuk filtering dengan logika budget yang lebih presisi
    def apply_filters(df, budget=None, ram=None, entities=None, budget_span=None):
        df_filtered = df.copy()
        if budget is not None:
            if isinstance(budget, tuple):
                df_filtered = df_filtered[(df_filtered['Final Price'] >= budget[0]) & (df_filtered['Final Price'] <= budget[1])]
            elif budget > 0:
                # Tentukan apakah budget adalah batas bawah (≥) atau batas atas (≤)
                is_above = False
                if budget_span is not None:
                    # Ambil teks sebelum angka budget (hingga 30 karakter sebelumnya)
                    before_budget = user_query[:budget_span[0]]
                    # Periksa keberadaan kata kunci dalam teks sebelum angka
                    # (cukup periksa 30 karakter terakhir untuk menghindari pencarian jauh)
                    last_30_before = before_budget[-30:] if len(before_budget) >= 30 else before_budget
                    # Kata kunci yang menandakan batas bawah
                    min_keywords = ['minimal', 'di atas', 'diatas', 'lebih dari']
                    if any(kw in last_30_before.lower() for kw in min_keywords):
                        is_above = True
                    # Jika tidak ada keyword, default ke batas atas (≤)
                if is_above:
                    df_filtered = df_filtered[df_filtered['Final Price'] >= budget]
                else:
                    df_filtered = df_filtered[df_filtered['Final Price'] <= budget]
        if ram:
            target_ram = max(ram)
            df_filtered = df_filtered[df_filtered['RAM'] >= target_ram]
        if entities:
            mask = pd.Series(False, index=df_filtered.index)
            for ent in entities:
                mask |= (df_filtered['Brand'].str.lower() == ent.lower()) | (df_filtered['Model'].str.lower() == ent.lower())
            if not mask.any():
                for ent in entities:
                    brand_match = process.extractOne(ent, df_filtered['Brand'].unique().tolist(), score_cutoff=90)
                    model_match = process.extractOne(ent, df_filtered['Model'].tolist(), score_cutoff=90)
                    if brand_match:
                        mask |= (df_filtered['Brand'].str.lower() == brand_match[0].lower())
                    if model_match:
                        mask |= (df_filtered['Model'].str.lower() == model_match[0].lower())
            df_filtered = df_filtered[mask]
        return df_filtered

    # Helper untuk mengambil requirement dari DataFrame jika tidak ada di KB
    def get_req_from_df(game_name):
        min_row = min_req_df[min_req_df['App'].str.lower() == game_name.lower()]
        rec_row = rec_req_df[rec_req_df['App'].str.lower() == game_name.lower()]
        if min_row.empty:
            return None, None
        min_req = min_row.iloc[0].to_dict()
        if rec_row.empty:
            rec_req = min_req.copy()
        else:
            rec_req = rec_row.iloc[0].to_dict()
        return min_req, rec_req

    # ======================== INTENT COMPARE_LAPTOPS ========================
    if detected_intent == "COMPARE_LAPTOPS":
        if len(found_laptops_entities) < 2:
            return pd.DataFrame({"Status": ["Informasi Kurang"], "Pesan": ["Mohon sebutkan minimal dua nama laptop atau brand untuk dibandingkan."]})
        comparison_laptops = laptop_df[
            laptop_df['Model'].str.lower().isin([ent.lower() for ent in found_laptops_entities if ent in laptop_df['Model'].tolist()]) |
            laptop_df['Brand'].str.lower().isin([ent.lower() for ent in found_laptops_entities if ent in laptop_df['Brand'].unique().tolist()])
        ].copy()
        if comparison_laptops.empty:
            return pd.DataFrame({"Status": ["Tidak Ditemukan"], "Pesan": ["Tidak ada laptop yang cocok dengan yang ingin Anda bandingkan."]})
        print("\nHasil Perbandingan Laptop:")
        print(comparison_laptops[['Brand', 'Model', 'CPU', 'GPU', 'RAM', 'Storage', 'Storage type', 'Screen', 'Final Price']])
        return comparison_laptops[['Brand', 'Model', 'CPU', 'GPU', 'RAM', 'Storage', 'Storage type', 'Screen', 'Final Price']]

    # ======================== INTENT FILTER_LAPTOPS ========================
    if detected_intent == "FILTER_LAPTOPS":
        if not found_laptops_entities and extracted_budget is None and not extracted_ram:
            return pd.DataFrame({"Status": ["Informasi Kurang"], "Pesan": ["Mohon sebutkan brand laptop, model, budget, atau RAM yang Anda inginkan."]})
        laptops_filtered = apply_filters(laptop_df, budget=extracted_budget, ram=extracted_ram, entities=found_laptops_entities, budget_span=budget_span)
        if laptops_filtered.empty:
            return pd.DataFrame({"Status": ["Tidak Ditemukan"], "Pesan": ["Tidak ada laptop yang ditemukan berdasarkan kriteria Anda."]})
        laptops_filtered = laptops_filtered.sort_values(by='Final Price', ascending=False).reset_index(drop=True)
        print("\nHasil Laptop yang Difilter:")
        print(laptops_filtered[['Brand', 'Model', 'CPU', 'GPU', 'RAM', 'Storage', 'Storage type', 'Final Price']])
        return laptops_filtered[['Brand', 'Model', 'CPU', 'GPU', 'RAM', 'Storage', 'Storage type', 'Final Price']]

    # ======================== INTENT FIND_MOST_EXPENSIVE_LAPTOP ========================
    if detected_intent == "FIND_MOST_EXPENSIVE_LAPTOP":
        laptops_filtered = apply_filters(laptop_df, budget=extracted_budget, ram=extracted_ram, entities=found_laptops_entities, budget_span=budget_span)
        if laptops_filtered.empty:
            return pd.DataFrame({"Status": ["Tidak Ditemukan"], "Pesan": ["Tidak ada laptop yang ditemukan berdasarkan kriteria Anda."]})
        # Jika ada game yang terdeteksi, filter berdasarkan minimum requirements
        if found_games_nlp:
            agg_min_req = {
                'CPU_Intel_score': 0,
                'CPU_AMD_score': 0,
                'GPU_NVIDIA_score': 0,
                'GPU_AMD_score': 0,
                'GPU_Intel_score': 0,
                'RAM': 0,
                'File Size': 0
            }
            for game in found_games_nlp:
                min_req = min_req_kb.get(game)
                if min_req is None:
                    min_req, _ = get_req_from_df(game)
                if min_req:
                    agg_min_req['CPU_Intel_score'] = max(agg_min_req['CPU_Intel_score'], min_req.get('CPU_Intel_score', 0))
                    agg_min_req['CPU_AMD_score'] = max(agg_min_req['CPU_AMD_score'], min_req.get('CPU_AMD_score', 0))
                    agg_min_req['GPU_NVIDIA_score'] = max(agg_min_req['GPU_NVIDIA_score'], min_req.get('GPU_NVIDIA_score', 0))
                    agg_min_req['GPU_AMD_score'] = max(agg_min_req['GPU_AMD_score'], min_req.get('GPU_AMD_score', 0))
                    agg_min_req['GPU_Intel_score'] = max(agg_min_req['GPU_Intel_score'], min_req.get('GPU_Intel_score', 0))
                    ram_min = int(''.join(filter(str.isdigit, str(min_req.get('RAM', '0'))))) or 0
                    storage_min = int(''.join(filter(str.isdigit, str(min_req.get('File Size', '0'))))) or 0
                    agg_min_req['RAM'] = max(agg_min_req['RAM'], ram_min)
                    agg_min_req['File Size'] = max(agg_min_req['File Size'], storage_min)
            laptops_filtered = laptops_filtered[
                (laptops_filtered['RAM'] >= agg_min_req['RAM']) &
                (laptops_filtered['Storage'] >= agg_min_req['File Size'])
            ].copy()
        if laptops_filtered.empty:
            return pd.DataFrame({"Status": ["Tidak Ditemukan"], "Pesan": ["Tidak ada laptop yang memenuhi kriteria."]})
        most_expensive = laptops_filtered.sort_values(by='Final Price', ascending=False).reset_index(drop=True)
        print("\nLaptop Termahal berdasarkan kriteria:")
        print(most_expensive[['Brand', 'Model', 'CPU', 'GPU', 'RAM', 'Storage', 'Storage type', 'Final Price']])
        return most_expensive[['Brand', 'Model', 'CPU', 'GPU', 'RAM', 'Storage', 'Storage type', 'Final Price']]

    # ======================== INTENT FIND_LAPTOP_FOR_GAME ========================
    if detected_intent in ["FIND_BEST_LAPTOP_FOR_GAME", "FIND_CHEAPEST_LAPTOP_FOR_GAME", "FIND_LAPTOP_FOR_GAME"]:
        if not found_games_nlp:
            return pd.DataFrame({"Status": ["Informasi Kurang"], "Pesan": ["Mohon sebutkan nama game yang ingin dimainkan."]})

        # Agregasi requirement per vendor dengan fallback ke DataFrame
        agg_min_req = {
            'CPU_Intel_score': 0,
            'CPU_AMD_score': 0,
            'GPU_NVIDIA_score': 0,
            'GPU_AMD_score': 0,
            'GPU_Intel_score': 0,
            'RAM': 0,
            'File Size': 0
        }
        agg_rec_req = {
            'CPU_Intel_score': 0,
            'CPU_AMD_score': 0,
            'GPU_NVIDIA_score': 0,
            'GPU_AMD_score': 0,
            'GPU_Intel_score': 0,
            'RAM': 0,
            'File Size': 0
        }
        valid_games = []
        for game in found_games_nlp:
            min_req = min_req_kb.get(game)
            rec_req = rec_req_kb.get(game)
            if min_req is None or rec_req is None:
                min_req, rec_req = get_req_from_df(game)
            if min_req and rec_req:
                valid_games.append(game)
                agg_min_req['CPU_Intel_score'] = max(agg_min_req['CPU_Intel_score'], min_req.get('CPU_Intel_score', 0))
                agg_min_req['CPU_AMD_score'] = max(agg_min_req['CPU_AMD_score'], min_req.get('CPU_AMD_score', 0))
                agg_min_req['GPU_NVIDIA_score'] = max(agg_min_req['GPU_NVIDIA_score'], min_req.get('GPU_NVIDIA_score', 0))
                agg_min_req['GPU_AMD_score'] = max(agg_min_req['GPU_AMD_score'], min_req.get('GPU_AMD_score', 0))
                agg_min_req['GPU_Intel_score'] = max(agg_min_req['GPU_Intel_score'], min_req.get('GPU_Intel_score', 0))
                ram_min = int(''.join(filter(str.isdigit, str(min_req.get('RAM', '0'))))) or 0
                storage_min = int(''.join(filter(str.isdigit, str(min_req.get('File Size', '0'))))) or 0
                agg_min_req['RAM'] = max(agg_min_req['RAM'], ram_min)
                agg_min_req['File Size'] = max(agg_min_req['File Size'], storage_min)

                agg_rec_req['CPU_Intel_score'] = max(agg_rec_req['CPU_Intel_score'], rec_req.get('CPU_Intel_score', 0))
                agg_rec_req['CPU_AMD_score'] = max(agg_rec_req['CPU_AMD_score'], rec_req.get('CPU_AMD_score', 0))
                agg_rec_req['GPU_NVIDIA_score'] = max(agg_rec_req['GPU_NVIDIA_score'], rec_req.get('GPU_NVIDIA_score', 0))
                agg_rec_req['GPU_AMD_score'] = max(agg_rec_req['GPU_AMD_score'], rec_req.get('GPU_AMD_score', 0))
                agg_rec_req['GPU_Intel_score'] = max(agg_rec_req['GPU_Intel_score'], rec_req.get('GPU_Intel_score', 0))
                ram_rec = int(''.join(filter(str.isdigit, str(rec_req.get('RAM', '0'))))) or 0
                storage_rec = int(''.join(filter(str.isdigit, str(rec_req.get('File Size', '0'))))) or 0
                agg_rec_req['RAM'] = max(agg_rec_req['RAM'], ram_rec)
                agg_rec_req['File Size'] = max(agg_rec_req['File Size'], storage_rec)

        if not valid_games:
            return pd.DataFrame({"Status": ["Tidak Ditemukan"], "Pesan": ["Tidak dapat menemukan persyaratan untuk game yang disebutkan."]})

        print(f"\nAgregasi Minimum Requirements (per vendor):")
        print(f"  Intel CPU: {agg_min_req['CPU_Intel_score']}, AMD CPU: {agg_min_req['CPU_AMD_score']}")
        print(f"  NVIDIA GPU: {agg_min_req['GPU_NVIDIA_score']}, AMD GPU: {agg_min_req['GPU_AMD_score']}, Intel GPU: {agg_min_req['GPU_Intel_score']}")
        print(f"  RAM: {agg_min_req['RAM']} GB, Storage: {agg_min_req['File Size']} GB")

        # Filter awal berdasarkan budget, RAM, brand/model
        laptops_filtered = apply_filters(laptop_df, budget=extracted_budget, ram=extracted_ram, entities=found_laptops_entities, budget_span=budget_span)

        # Filter berdasarkan minimum requirements (RAM dan Storage)
        laptops_filtered = laptops_filtered[
            (laptops_filtered['RAM'] >= agg_min_req['RAM']) &
            (laptops_filtered['Storage'] >= agg_min_req['File Size'])
        ].copy()

        if laptops_filtered.empty:
            return pd.DataFrame({"Status": ["Tidak Ditemukan"], "Pesan": ["Tidak ada laptop yang memenuhi persyaratan minimum untuk game tersebut."]})

        final_recommendations = categorize_laptops_adapted(
            laptops_filtered,
            agg_min_req,
            agg_rec_req
        )

        if final_recommendations.empty:
            return pd.DataFrame({"Status": ["Tidak Ditemukan"], "Pesan": ["Tidak ada laptop yang memenuhi kriteria."]})

        # Sorting berdasarkan intent
        if detected_intent == "FIND_CHEAPEST_LAPTOP_FOR_GAME":
            final_recommendations['Category_Order'] = final_recommendations['Category'].map({'Recommended': 0, 'Mixed': 1, 'Minimum': 2})
            final_recommendations = final_recommendations.sort_values(by=['Category_Order', 'Final Price', 'Match_Score'], ascending=[True, True, False]).drop(columns='Category_Order')
        else:
            final_recommendations['Category_Order'] = final_recommendations['Category'].map({'Recommended': 0, 'Mixed': 1, 'Minimum': 2})
            final_recommendations = final_recommendations.sort_values(by=['Category_Order', 'Match_Score'], ascending=[True, False]).drop(columns='Category_Order')

        print("\nHasil Rekomendasi Laptop:")
        print(final_recommendations)
        return final_recommendations

    # Jika intent tidak dikenali
    print("\nQuery tidak dapat diproses. Mohon sebutkan game atau kriteria spesifik (brand, budget, RAM).")
    return pd.DataFrame({"Status": ["Query Tidak Dapat Diproses"], "Pesan": ["Sorry, I could not process your query. Please mention a game or specific criteria (brand, budget, RAM)."]})