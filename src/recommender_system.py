# src/recommender_system.py
import pandas as pd
import traceback
from fuzzywuzzy import process
from src.nlp_pipeline import nlp_pipeline_fuzzy
from src.recommender_core import categorize_laptops_adapted, get_cpu_req_score, get_gpu_req_score

def recognize_intent_simple(user_query, found_games, found_laptops_entities, extracted_budget):
    query_lower = user_query.lower()
    
    # 1. Comparison intent (prioritas tertinggi)
    compare_keywords = ['bandingkan', 'bandingkan dengan', 'versus', 'vs', 'compare']
    if any(keyword in query_lower for keyword in compare_keywords) and len(found_laptops_entities) >= 2:
        return "COMPARE_LAPTOPS"
    
    # 2. Most expensive laptop
    expensive_keywords = ['termahal', 'paling mahal', 'harga tinggi']
    if any(keyword in query_lower for keyword in expensive_keywords):
        return "FIND_MOST_EXPENSIVE_LAPTOP"
    
    # 3. Cheapest laptop (dengan atau tanpa game)
    cheapest_keywords = ['termurah', 'paling murah', 'harga rendah', 'murah']
    if any(keyword in query_lower for keyword in cheapest_keywords):
        if found_games:
            return "FIND_CHEAPEST_LAPTOP_FOR_GAME"
        if extracted_budget is not None:
            return "FILTER_LAPTOPS"
    
    # 4. Filter intent (tanpa game)
    filter_keywords = ['brand', 'merek', 'model', 'seri', 'tipe', 'type', 'budget', 'harga', 'ram']
    if (any(keyword in query_lower for keyword in filter_keywords) or found_laptops_entities or extracted_budget is not None) and not found_games:
        return "FILTER_LAPTOPS"
    
    # 5. Jika ada game terdeteksi, default ke FIND_LAPTOP_FOR_GAME
    if found_games:
        return "FIND_LAPTOP_FOR_GAME"
    
    # 6. Tidak ada game dan tidak ada intent spesifik
    return "QUERY_NOT_PROCESSED"


def generate_game_comments(laptop_row, games, min_req_kb, rec_req_kb, min_req_df, rec_req_df):
    comments = {}
    for game in games:
        try:
            min_req = min_req_kb.get(game)
            rec_req = rec_req_kb.get(game)
            if min_req is None or rec_req is None:
                min_row = min_req_df[min_req_df['App'].str.lower() == game.lower()]
                rec_row = rec_req_df[rec_req_df['App'].str.lower() == game.lower()]
                if min_row.empty:
                    comments[game] = "Persyaratan game tidak ditemukan."
                    continue
                min_req = min_row.iloc[0].to_dict()
                rec_req = rec_row.iloc[0].to_dict() if not rec_row.empty else min_req

            cpu_rec_score = get_cpu_req_score(laptop_row, rec_req)
            gpu_rec_score = get_gpu_req_score(laptop_row, rec_req)

            cpu_meets_rec = laptop_row['CPU_score'] >= cpu_rec_score if cpu_rec_score > 0 else False
            gpu_meets_rec = laptop_row['GPU_score'] >= gpu_rec_score if gpu_rec_score > 0 else False

            if cpu_meets_rec and gpu_meets_rec:
                comment = (
                    f"🟢 Status: Optimal / High Performance\n\n"
                    f"Game {game} dapat dijalankan dengan sangat lancar karena spesifikasi laptop sudah melampaui kebutuhan rekomendasi. "
                    f"Performa stabil pada setting tinggi hingga ultra, termasuk pada skenario berat."
                )
            elif cpu_meets_rec and not gpu_meets_rec:
                comment = (
                    f"🟠 Status: CPU Strong (GPU Bottleneck)\n\n"
                    f"Game {game} dapat berjalan dengan stabil dari sisi pemrosesan karena CPU sudah melampaui spesifikasi rekomendasi, "
                    f"sehingga mampu menangani simulasi, AI, dan banyak objek dengan baik. Namun, GPU masih berada di bawah rekomendasi "
                    f"sehingga menjadi batas utama pada rendering grafis. Setting tinggi berpotensi menyebabkan penurunan FPS, "
                    f"sehingga disarankan menggunakan setting medium hingga medium–high dengan penyesuaian grafis."
                )
            elif not cpu_meets_rec and gpu_meets_rec:
                comment = (
                    f"🟠 Status: GPU Strong (CPU Bottleneck)\n\n"
                    f"Game {game} mampu menampilkan grafis dengan baik karena GPU sudah melampaui spesifikasi rekomendasi, "
                    f"sehingga rendering visual seperti texture, shadow, dan efek dapat berjalan optimal. Namun, CPU masih berada di bawah rekomendasi "
                    f"dan dapat menjadi batas pada proses seperti simulasi, AI, atau jumlah objek, yang berpotensi menyebabkan stuttering "
                    f"atau penurunan performa pada kondisi tertentu. Disarankan menggunakan setting medium hingga medium–high, "
                    f"dengan memperhatikan beban CPU saat bermain."
                )
            else:
                comment = (
                    f"🟡 Status: Playable\n\n"
                    f"Game {game} dapat dijalankan dengan baik karena spesifikasi laptop sudah memenuhi kebutuhan minimum. "
                    f"Namun, karena belum mencapai spesifikasi yang direkomendasikan, performa optimal mungkin belum tercapai "
                    f"terutama pada setting tinggi. Disarankan menggunakan setting low hingga medium dengan penyesuaian untuk menjaga kestabilan performa."
                )
            comments[game] = comment
        except Exception as e:
            print(f"Error generating comment for {game}: {e}")
            comments[game] = f"Error: {str(e)}"
    return comments


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
        bigram_unique_kb,
        brand_models_mapping
    )
    found_games_nlp = pipeline_result['found_games']
    found_laptops_entities = pipeline_result['found_laptops']
    extracted_budget = pipeline_result['budget']
    extracted_ram = pipeline_result['ram']
    budget_span = pipeline_result.get('budget_span')

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

    def apply_filters(df, budget=None, ram=None, entities=None, budget_span=None):
        df_filtered = df.copy()
        if budget is not None:
            if isinstance(budget, tuple):
                df_filtered = df_filtered[(df_filtered['Final Price'] >= budget[0]) & (df_filtered['Final Price'] <= budget[1])]
            elif budget > 0:
                is_above = False
                if budget_span is not None:
                    before_budget = user_query[:budget_span[0]]
                    last_30_before = before_budget[-30:] if len(before_budget) >= 30 else before_budget
                    min_keywords = ['minimal', 'di atas', 'diatas', 'lebih dari']
                    if any(kw in last_30_before.lower() for kw in min_keywords):
                        is_above = True
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
                if ' ' in ent:
                    parts = ent.split(' ', 1)
                    if len(parts) == 2:
                        brand_candidate, model_candidate = parts
                        if brand_candidate in laptop_brand_list and model_candidate in laptop_list:
                            mask |= ((df_filtered['Brand'].str.lower() == brand_candidate.lower()) &
                                     (df_filtered['Model'].str.lower() == model_candidate.lower()))
                            continue
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

        laptops_filtered = apply_filters(laptop_df, budget=extracted_budget, ram=extracted_ram, entities=found_laptops_entities, budget_span=budget_span)
        laptops_filtered = laptops_filtered[
            (laptops_filtered['RAM'] >= agg_min_req['RAM']) &
            (laptops_filtered['Storage'] >= agg_min_req['File Size'])
        ].copy()
        if laptops_filtered.empty:
            return pd.DataFrame({"Status": ["Tidak Ditemukan"], "Pesan": ["Tidak ada laptop yang memenuhi persyaratan minimum untuk game tersebut."]})

        # Pastikan kolom id ada
        if 'id' not in laptops_filtered.columns:
            print("Error: Kolom 'id' tidak ditemukan di laptop_df. Pastikan CSV memiliki kolom 'id'.")
            return pd.DataFrame({"Status": ["Error"], "Pesan": ["Kolom id tidak ditemukan."]})

        # Kategorisasi (categorize_laptops_adapted harus mengembalikan kolom id)
        final_recommendations = categorize_laptops_adapted(
            laptops_filtered,
            agg_min_req,
            agg_rec_req
        )
        if final_recommendations.empty:
            return pd.DataFrame({"Status": ["Tidak Ditemukan"], "Pesan": ["Tidak ada laptop yang memenuhi kriteria."]})

        # Gabungkan dengan laptop_df asli berdasarkan id untuk mendapatkan data yang akurat
        # Sertakan semua kolom yang diperlukan: id, Laptop, Brand, Model, CPU, GPU, RAM, Storage, Storage type, Final Price, CPU_score, GPU_score
        laptop_original = laptop_df[['id', 'Laptop', 'Brand', 'Model', 'CPU', 'GPU', 'RAM', 'Storage', 'Storage type', 'Final Price', 'CPU_score', 'GPU_score']].drop_duplicates(subset='id')
        # Hapus kolom spesifikasi dari final_recommendations (karena akan diganti)
        keep_cols = ['id', 'Category', 'Match_Score']
        if 'Category_Order' in final_recommendations.columns:
            keep_cols.append('Category_Order')
        final_recommendations = final_recommendations[keep_cols]
        final_recommendations = final_recommendations.merge(laptop_original, on='id', how='left')

        # Sorting ulang jika diperlukan
        if detected_intent == "FIND_CHEAPEST_LAPTOP_FOR_GAME":
            final_recommendations['Category_Order'] = final_recommendations['Category'].map({'Recommended': 0, 'Mixed': 1, 'Minimum': 2})
            final_recommendations = final_recommendations.sort_values(by=['Category_Order', 'Final Price', 'Match_Score'], ascending=[True, True, False]).drop(columns='Category_Order')
        else:
            final_recommendations['Category_Order'] = final_recommendations['Category'].map({'Recommended': 0, 'Mixed': 1, 'Minimum': 2})
            final_recommendations = final_recommendations.sort_values(by=['Category_Order', 'Match_Score'], ascending=[True, False]).drop(columns='Category_Order')

        # --- Tambahkan komentar game ---
        if not final_recommendations.empty and found_games_nlp:
            try:
                score_dict = {}
                for _, row in laptop_df[['id', 'CPU_score', 'GPU_score']].iterrows():
                    score_dict[row['id']] = (row['CPU_score'], row['GPU_score'])
                
                comment_list = []
                for idx, row in final_recommendations.iterrows():
                    laptop_id = row['id']
                    cpu_score, gpu_score = score_dict.get(laptop_id, (0, 0))
                    temp_row = row.copy()
                    temp_row['CPU_score'] = cpu_score
                    temp_row['GPU_score'] = gpu_score
                    comments = generate_game_comments(
                        temp_row, found_games_nlp, min_req_kb, rec_req_kb, min_req_df, rec_req_df
                    )
                    comment_text = "<br><br>".join([f"<strong>{game}</strong><br>{text}" for game, text in comments.items()])
                    comment_list.append(comment_text)
                final_recommendations['game_comments'] = comment_list
            except Exception as e:
                print(f"Error adding game comments: {e}")
                traceback.print_exc()

        print("\nHasil Rekomendasi Laptop:")
        print(final_recommendations)
        return final_recommendations

    print("\nQuery tidak dapat diproses. Mohon sebutkan game atau kriteria spesifik (brand, budget, RAM).")
    return pd.DataFrame({"Status": ["Query Tidak Dapat Diproses"], "Pesan": ["Sorry, I could not process your query. Please mention a game or specific criteria (brand, budget, RAM)."]})