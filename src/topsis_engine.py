# src/topsis_engine.py
# =============================================================================
# PHASE 2: TOPSIS RANKING ENGINE
# =============================================================================
# Technique for Order of Preference by Similarity to Ideal Solution
#
# Purpose: Rank filtered laptops using AHP weights and TOPSIS algorithm
# Input:   filtered_df (from Phase 1 RBR), ahp_weights (from Phase 1 AHP)
# Output:  ranked_df with TOPSIS scores and ranking
#
# Workflow:
#   Filtered Data + AHP Weights
#       ↓
#   Normalize Decision Matrix
#       ↓
#   Apply Weighted Normalized Matrix
#       ↓
#   Calculate Ideal Solutions (A+ and A-)
#       ↓
#   Calculate Euclidean Distances (D+ and D-)
#       ↓
#   Calculate Preference Scores (C*)
#       ↓
#   Ranked Results (sorted by C* descending)
# =============================================================================

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Any
import warnings

warnings.filterwarnings('ignore')


# =============================================================================
# MAIN TOPSIS FUNCTION
# =============================================================================

def run_topsis(
    filtered_df: pd.DataFrame,
    ahp_weights: Dict[str, float],
    criteria_columns: Dict[str, Dict[str, Any]] = None
) -> pd.DataFrame:
    """
    Run TOPSIS algorithm on filtered laptop data using AHP weights.
    
    Args:
        filtered_df: DataFrame dengan kolom spesifikasi laptop (from Phase 1)
                    Required columns: CPU_score, GPU_score, RAM, Storage, Final_Price
        
        ahp_weights: Dictionary dengan bobot dari Phase 1
                    Format: {'CPU': 0.20, 'GPU': 0.40, 'RAM': 0.15, 'Storage': 0.10, 'Price': 0.15}
        
        criteria_columns: (Optional) Custom mapping untuk kolom kriteria
                         Default: Auto-detect dari filtered_df
    
    Returns:
        pd.DataFrame dengan kolom tambahan:
        - TOPSIS_Score: Skor preferensi (0-1, semakin tinggi semakin baik)
        - Rank: Urutan ranking
        - D_Plus: Jarak ke solusi ideal positif
        - D_Minus: Jarak ke solusi ideal negatif
        - Diurutkan descending berdasarkan TOPSIS_Score
    
    TOPSIS Steps:
        1. Normalize decision matrix (Vector Normalization)
        2. Calculate weighted normalized matrix (apply AHP weights)
        3. Determine ideal positive (A+) and ideal negative (A-) solutions
        4. Calculate Euclidean distances (D+, D-)
        5. Calculate preference scores (C* = D- / (D+ + D-))
        6. Rank based on scores
    """
    
    print("\n" + "="*80)
    print("PHASE 2: TOPSIS RANKING ENGINE")
    print("="*80)
    
    if filtered_df.empty:
        print("[ERROR] Filtered dataframe is empty")
        return pd.DataFrame()
    
    # Step 1: Prepare data
    print(f"\n[INPUT] {len(filtered_df)} laptops to rank")
    print(f"[WEIGHTS] {ahp_weights}")
    
    df_work = filtered_df.copy()
    
    # Step 2: Define criteria columns and their types (benefit vs cost)
    if criteria_columns is None:
        criteria_columns = define_default_criteria(df_work)
    
    criteria_list = list(criteria_columns.keys())
    print(f"[CRITERIA] {criteria_list}")
    
    # Extract numerical matrix
    decision_matrix = df_work[criteria_list].values.astype(float)
    
    # Handle NaN values
    decision_matrix = np.nan_to_num(decision_matrix, nan=0, posinf=1e10, neginf=0)
    
    print(f"   Matrix shape: {decision_matrix.shape}")
    
    # =========================================================================
    # STEP 1: NORMALISASI MATRIKS KEPUTUSAN (Vector Normalization)
    # =========================================================================
    print(f"\n[STEP 1] Normalize Decision Matrix")
    
    # Hitung norm untuk setiap kolom: sqrt(sum(x^2))
    col_norms = np.sqrt((decision_matrix ** 2).sum(axis=0))
    
    # Hindari pembagian dengan nol
    col_norms[col_norms == 0] = 1
    
    # Normalisasi: r_ij = x_ij / sqrt(sum(x_k^2))
    normalized_matrix = decision_matrix / col_norms
    
    print(f"   [OK] Normalized matrix shape: {normalized_matrix.shape}")
    
    # =========================================================================
    # STEP 2: NORMALISASI TERBOBOT (Weighted Normalized Matrix)
    # =========================================================================
    print(f"\n[STEP 2] Apply Weighted Matrix")
    
    # Buat weight array sesuai urutan criteria
    weights_array = np.array([ahp_weights.get(criteria, 0.2) for criteria in criteria_list])
    
    # Kalikan dengan weights: v_ij = w_i * r_ij
    weighted_matrix = normalized_matrix * weights_array
    
    print(f"   [OK] Weighted matrix shape: {weighted_matrix.shape}")
    print(f"   Weights applied: {dict(zip(criteria_list, weights_array))}")
    
    # =========================================================================
    # STEP 3: SOLUSI IDEAL POSITIF (A+) DAN NEGATIF (A-)
    # =========================================================================
    print(f"\n[STEP 3] Calculate Ideal Solutions")
    
    # A+ (Ideal Positive): Max untuk benefit, Min untuk cost
    # A- (Ideal Negative): Min untuk benefit, Max untuk cost
    
    ideal_positive = np.zeros(len(criteria_list))
    ideal_negative = np.zeros(len(criteria_list))
    
    for i, criteria in enumerate(criteria_list):
        criteria_type = criteria_columns[criteria]['type']
        
        if criteria_type == 'benefit':
            # Benefit: Besar lebih baik
            ideal_positive[i] = weighted_matrix[:, i].max()
            ideal_negative[i] = weighted_matrix[:, i].min()
        else:  # cost
            # Cost: Kecil lebih baik
            ideal_positive[i] = weighted_matrix[:, i].min()
            ideal_negative[i] = weighted_matrix[:, i].max()
    
    print(f"   [OK] Ideal Positive (A+):  {ideal_positive}")
    print(f"   [OK] Ideal Negative (A-):  {ideal_negative}")
    
    # =========================================================================
    # STEP 4: JARAK KE SOLUSI IDEAL (Euclidean Distance)
    # =========================================================================
    print(f"\n[STEP 4] Calculate Euclidean Distances")
    
    # D+ = sqrt(sum((v_ij - A+_j)^2)) -> Jarak ke solusi ideal positif
    d_plus = np.sqrt(((weighted_matrix - ideal_positive) ** 2).sum(axis=1))
    
    # D- = sqrt(sum((v_ij - A-_j)^2)) -> Jarak ke solusi ideal negatif
    d_minus = np.sqrt(((weighted_matrix - ideal_negative) ** 2).sum(axis=1))
    
    print(f"   [OK] D+ (distance to ideal positive):  min={d_plus.min():.4f}, max={d_plus.max():.4f}")
    print(f"   [OK] D- (distance to ideal negative):  min={d_minus.min():.4f}, max={d_minus.max():.4f}")
    
    # =========================================================================
    # STEP 5: SKOR PREFERENSI (Preference Score C*)
    # =========================================================================
    print(f"\n[STEP 5] Calculate Preference Scores")
    
    # C* = D- / (D+ + D-)
    # Penjaga: jika D+ + D- = 0, set C* = 0
    denominator = d_plus + d_minus
    denominator[denominator == 0] = 1  # Hindari pembagian nol
    
    topsis_scores = d_minus / denominator
    
    # Jika semua zero, handle gracefully
    topsis_scores = np.nan_to_num(topsis_scores, nan=0)
    
    print(f"   [OK] TOPSIS Scores: min={topsis_scores.min():.4f}, max={topsis_scores.max():.4f}")
    print(f"   [OK] Mean score: {topsis_scores.mean():.4f}")
    
    # =========================================================================
    # STEP 6: RANKING & OUTPUT
    # =========================================================================
    print(f"\n[STEP 6] Generate Rankings")
    
    # Tambahkan hasil ke dataframe
    df_work['D_Plus'] = d_plus
    df_work['D_Minus'] = d_minus
    df_work['TOPSIS_Score'] = topsis_scores
    
    # Sort by TOPSIS score descending (highest score = best laptop)
    df_ranked = df_work.sort_values('TOPSIS_Score', ascending=False).reset_index(drop=True)
    
    # Add ranking column
    df_ranked['Rank'] = range(1, len(df_ranked) + 1)
    
    # Reorder columns: Rank first, then TOPSIS metrics, then other data
    cols_to_front = ['Rank', 'TOPSIS_Score', 'D_Plus', 'D_Minus']
    cols_remaining = [col for col in df_ranked.columns if col not in cols_to_front]
    df_ranked = df_ranked[cols_to_front + cols_remaining]
    
    print(f"   [OK] Ranked {len(df_ranked)} laptops")
    print(f"\n   Top 3 Ranking:")
    
    # Safe column access with fallback
    if len(df_ranked) >= 3:
        for idx, row in df_ranked.head(3).iterrows():
            brand = row.get('Brand', 'N/A') if 'Brand' in row.index else 'N/A'
            model = row.get('Model', 'N/A') if 'Model' in row.index else 'N/A'
            score = row['TOPSIS_Score']
            print(f"   {int(row['Rank'])}. {brand} {model}: Score={score:.4f}")
    else:
        for idx, row in df_ranked.iterrows():
            brand = row.get('Brand', 'N/A') if 'Brand' in row.index else 'N/A'
            model = row.get('Model', 'N/A') if 'Model' in row.index else 'N/A'
            score = row['TOPSIS_Score']
            print(f"   {int(row['Rank'])}. {brand} {model}: Score={score:.4f}")
    
    print(f"\n[COMPLETE] TOPSIS Ranking Complete!")
    print("="*80 + "\n")
    
    return df_ranked


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def define_default_criteria(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """
    Define criteria columns and their types (benefit vs cost).
    
    Returns:
        Dict dengan struktur:
        {
            'CPU': {'type': 'benefit', 'description': '...'},
            'GPU': {'type': 'benefit', 'description': '...'},
            ...
        }
    """
    
    criteria = {}
    
    # Cek dan tentukan criteria columns yang ada di dataframe
    
    # CPU Score (Higher = Better)
    if 'CPU_score' in df.columns:
        criteria['CPU_score'] = {
            'type': 'benefit',
            'description': 'CPU performance score (higher is better)'
        }
    elif 'CPU' in df.columns:
        criteria['CPU'] = {
            'type': 'benefit',
            'description': 'CPU score (higher is better)'
        }
    
    # GPU Score (Higher = Better)
    if 'GPU_score' in df.columns:
        criteria['GPU_score'] = {
            'type': 'benefit',
            'description': 'GPU performance score (higher is better)'
        }
    elif 'GPU' in df.columns:
        # GPU bisa text, skip jika tidak numeric
        if df['GPU'].dtype in ['int64', 'float64']:
            criteria['GPU'] = {
                'type': 'benefit',
                'description': 'GPU score (higher is better)'
            }
    
    # RAM (Higher = Better)
    if 'RAM' in df.columns:
        criteria['RAM'] = {
            'type': 'benefit',
            'description': 'RAM in GB (higher is better)'
        }
    
    # Storage (Higher = Better)
    if 'Storage' in df.columns:
        criteria['Storage'] = {
            'type': 'benefit',
            'description': 'Storage capacity in GB (higher is better)'
        }
    elif 'Total_Storage_GB' in df.columns:
        criteria['Total_Storage_GB'] = {
            'type': 'benefit',
            'description': 'Total storage in GB (higher is better)'
        }
    
    # Price (Lower = Better) - COST criterion
    if 'Final Price' in df.columns:
        criteria['Final Price'] = {
            'type': 'cost',
            'description': 'Price in IDR (lower is better)'
        }
    elif 'Price' in df.columns:
        criteria['Price'] = {
            'type': 'cost',
            'description': 'Price (lower is better)'
        }
    elif 'Final_Price' in df.columns:
        criteria['Final_Price'] = {
            'type': 'cost',
            'description': 'Final price in IDR (lower is better)'
        }
    
    # Validate at least 4 criteria exist
    if len(criteria) < 4:
        print(f"[WARNING] Only {len(criteria)} criteria found. Expected at least 4.")
        print(f"   Available columns: {df.columns.tolist()}")
    
    return criteria


def get_topsis_summary(ranked_df: pd.DataFrame, top_n: int = 5) -> Dict[str, Any]:
    """
    Get summary of TOPSIS results.
    
    Returns:
        Dictionary dengan statistik dan top-N recommendations
    """
    
    summary = {
        'total_ranked': len(ranked_df),
        'score_min': ranked_df['TOPSIS_Score'].min(),
        'score_max': ranked_df['TOPSIS_Score'].max(),
        'score_mean': ranked_df['TOPSIS_Score'].mean(),
        'score_std': ranked_df['TOPSIS_Score'].std(),
        'top_recommendations': []
    }
    
    # Top N recommendations
    for idx, row in ranked_df.head(top_n).iterrows():
        rec = {
            'rank': int(row['Rank']),
            'brand': row.get('Brand', 'N/A'),
            'model': row.get('Model', 'N/A'),
            'topsis_score': float(row['TOPSIS_Score']),
            'price': row.get('Final Price', row.get('Price', 'N/A')),
            'specs': {
                'ram': int(row['RAM']) if 'RAM' in row and pd.notna(row['RAM']) else None,
                'cpu_score': float(row['CPU_score']) if 'CPU_score' in row and pd.notna(row['CPU_score']) else None,
                'gpu_score': float(row['GPU_score']) if 'GPU_score' in row and pd.notna(row['GPU_score']) else None,
                'storage': int(row['Storage']) if 'Storage' in row and pd.notna(row['Storage']) else None,
            }
        }
        summary['top_recommendations'].append(rec)
    
    return summary


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    """
    Example usage of TOPSIS engine.
    """
    
    print("="*80)
    print("TOPSIS ENGINE - EXAMPLE")
    print("="*80)
    
    # Create dummy filtered data
    dummy_data = {
        'Brand': ['Asus', 'Dell', 'Lenovo', 'MSI', 'HP', 'Acer', 'ROG'],
        'Model': ['Model_1', 'Model_2', 'Model_3', 'Model_4', 'Model_5', 'Model_6', 'Model_7'],
        'CPU_score': [60, 70, 50, 75, 55, 80, 85],
        'GPU_score': [4, 5, 2, 4, 3, 5, 5],
        'RAM': [16, 32, 8, 16, 8, 32, 32],
        'Storage': [512, 1000, 256, 512, 256, 1000, 1500],
        'Final Price': [15_000_000, 28_000_000, 10_000_000, 18_000_000, 8_000_000, 35_000_000, 40_000_000]
    }
    df_filtered = pd.DataFrame(dummy_data)
    
    # AHP weights (from Phase 1)
    weights = {
        'CPU_score': 0.20,
        'GPU_score': 0.40,
        'RAM': 0.15,
        'Storage': 0.10,
        'Final Price': 0.15
    }
    
    print("\nInput data:")
    print(df_filtered)
    
    print("\nAHP Weights:")
    print(weights)
    
    # Run TOPSIS
    ranked_df = run_topsis(df_filtered, weights)
    
    print("\nRanked results:")
    print(ranked_df[['Rank', 'Brand', 'Model', 'TOPSIS_Score', 'Final Price']])
    
    # Get summary
    summary = get_topsis_summary(ranked_df, top_n=3)
    print(f"\nSummary:")
    print(f"  Total laptops: {summary['total_ranked']}")
    print(f"  Score range: {summary['score_min']:.4f} - {summary['score_max']:.4f}")
    print(f"  Mean score: {summary['score_mean']:.4f}")
