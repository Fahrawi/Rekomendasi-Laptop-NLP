# src/smart_filters_and_ahp.py
# =============================================================================
# HYBRID RECOMMENDER SYSTEM - Phase 1: Smart Filters + Dynamic AHP Weights
# =============================================================================
# Functionality:
#   1. apply_smart_filters() - Rule-Based Reasoning untuk 10 intent
#   2. get_intent_based_weights() - Dynamic AHP weights per intent
# 
# Architecture: NLP -> RBR (Smart Pre-filter) -> Dynamic AHP -> TOPSIS
# =============================================================================

import pandas as pd
import numpy as np
from typing import Dict, Tuple


# =============================================================================
# FUNGSI 1: RULE-BASED REASONING (RBR) - SMART FILTERS
# =============================================================================

def apply_smart_filters(
    df: pd.DataFrame,
    intent: str,
    budget: Tuple[int, int] = None,
    ram: int = None,
    brand: str = None,
    game_list: list = None
) -> pd.DataFrame:
    """
    Apply Rule-Based Reasoning (RBR) untuk filter laptop berdasarkan intent pengguna.
    
    Args:
        df: Dataframe laptop dengan kolom: RAM, CPU, GPU, Storage, Price, Brand, etc.
        intent: Salah satu dari 10 intent yang tersedia
        budget: Tuple (min, max) range harga dalam IDR, atau single value untuk max budget
        ram: Minimum RAM yang diinginkan dalam GB
        brand: Brand preference (optional filter tambahan)
        game_list: List game requirements (optional untuk gaming intent)
    
    Returns:
        pd.DataFrame yang sudah tersaring sesuai RBR rules
    
    Logic:
        - Setiap intent memiliki spec minimum yang harus dipenuhi
        - RBR rules mempertimbangkan vendor CPU/GPU untuk scoring akurat
        - Budget & RAM dari NLP di-gabung dengan intent rules
    """
    
    # Copy dataframe untuk menghindari mutasi data original
    df_filtered = df.copy()
    
    # =========================================================================
    # INTENT-BASED SPECIFICATION RULES (RBR Rules)
    # =========================================================================
    
    rbr_rules = {
        # =====================================================================
        # 1. GAMING
        # =====================================================================
        # Alasan: Gaming membutuhkan GPU dedicated yang kuat, CPU multi-core untuk
        # rendering 3D, RAM cukup untuk smooth gameplay tanpa lag.
        # CPU harus Intel i7/Ryzen 7 atau lebih tinggi, GPU RTX/RX dedicated.
        "FIND_LAPTOP_FOR_GAME": {
            "min_ram_gb": 8,
            "recommended_ram_gb": 16,
            "min_cpu_score": 60,  # i5/Ryzen 5 equivalent score
            "min_gpu_score": 3,   # GTX 1050 equivalent (3 = mid-range dedicated)
            "min_storage_gb": 512,  # SSD untuk fast loading
            "preferred_storage_type": "SSD",
            "cpu_preference": ["intel", "amd"],  # Both OK untuk gaming
            "gpu_preference": "dedicated",  # Must be dedicated, not integrated
            "description": "High-end GPU + multi-core CPU + fast storage"
        },
        
        # =====================================================================
        # 2. 3D DESIGN (CAD, VRAY, Blender)
        # =====================================================================
        # Alasan: 3D rendering sangat compute-intensive dan memory-hungry.
        # Membutuhkan GPU CUDA/HIP capable (NVIDIA RTX/Pro atau AMD Pro).
        # CPU harus banyak core (Ryzen 9 / i9 / Xeon).
        # RAM sangat kritis (32GB+) untuk handle project besar.
        # Storage besar untuk cache & temporary files.
        "3D_DESIGN": {
            "min_ram_gb": 32,
            "recommended_ram_gb": 64,
            "min_cpu_score": 80,  # High-end workstation CPU
            "min_gpu_score": 4,   # RTX 2060 or better (CUDA capable)
            "min_storage_gb": 1000,  # 1TB minimum untuk cache
            "preferred_storage_type": "SSD",
            "cpu_preference": ["intel", "amd"],  # High-core count preferred
            "gpu_preference": "dedicated_professional",  # RTX/RTX A series preferred
            "description": "Workstation-grade: 32GB+ RAM, high-core CPU, CUDA GPU"
        },
        
        # =====================================================================
        # 3. 2D DESIGN (Photoshop, Illustrator)
        # =====================================================================
        # Alasan: 2D design less compute-intensive than 3D, tapi butuh responsive UI.
        # GPU untuk UI acceleration appreciated, tapi integrated GPU OK.
        # RAM moderate (16GB) untuk handle large canvas + plugins.
        # Storage untuk caching & library assets.
        "2D_DESIGN": {
            "min_ram_gb": 16,
            "recommended_ram_gb": 32,
            "min_cpu_score": 50,  # i5/Ryzen 5 sufficient
            "min_gpu_score": 1,   # Integrated GPU OK, dedicated nicer
            "min_storage_gb": 512,  # SSD untuk responsiveness
            "preferred_storage_type": "SSD",
            "cpu_preference": ["intel", "amd"],
            "gpu_preference": "any",  # Integrated GPU acceptable
            "description": "Moderate specs: 16GB RAM, responsive CPU, SSD priority"
        },
        
        # =====================================================================
        # 4. OLAH DATA (Data Analysis, Statistics, Database)
        # =====================================================================
        # Alasan: Data processing butuh CPU multi-core & RAM besar untuk in-memory analytics.
        # GPU optional tapi berguna untuk parallel processing (NVIDIA).
        # Storage large untuk dataset & database files.
        # Networking performance important (tidak tercover dalam laptop spec tho).
        "OLAH_DATA": {
            "min_ram_gb": 16,
            "recommended_ram_gb": 32,
            "min_cpu_score": 60,  # Multi-core important
            "min_gpu_score": 0,   # GPU optional, tapi good-to-have
            "min_storage_gb": 512,  # For datasets & processing cache
            "preferred_storage_type": "SSD",
            "cpu_preference": ["intel", "amd"],  # High clock-speed preferred
            "gpu_preference": "optional_dedicated",  # Better with NVIDIA CUDA
            "description": "CPU-intensive: 16GB+ RAM, multi-core, large storage"
        },
        
        # =====================================================================
        # 5. AI DEVELOPMENT (ML/DL: TensorFlow, PyTorch)
        # =====================================================================
        # Alasan: AI/DL adalah yang paling demanding - training model butuh GPU dedicated
        # dengan compute capability tinggi (RTX, A series, RTX A100+).
        # RAM besar untuk batch processing, CPU high-core untuk data pipeline.
        # Storage large untuk datasets, models, checkpoints.
        "AI_DEVELOPMENT": {
            "min_ram_gb": 32,
            "recommended_ram_gb": 64,
            "min_cpu_score": 70,  # Decent CPU untuk data preprocessing
            "min_gpu_score": 4,   # RTX 2060 or better (CUDA compute capability 7.0+)
            "min_storage_gb": 1000,  # 1TB+ untuk datasets & models
            "preferred_storage_type": "SSD",
            "cpu_preference": ["intel", "amd"],
            "gpu_preference": "dedicated_cuda",  # NVIDIA CUDA essential
            "description": "Most demanding: 32GB+ RAM, NVIDIA GPU CUDA, large storage"
        },
        
        # =====================================================================
        # 6. WEB DEVELOPMENT (React, Node.js, Django, etc.)
        # =====================================================================
        # Alasan: Web dev relatively light-weight. Mostly I/O bound (compilation, bundling).
        # CPU untuk fast build times, RAM moderate untuk editor + browser + localhost apps.
        # GPU not important.
        # Storage untuk codebase, node_modules, docker images (can get large).
        "WEB_DEVELOPMENT": {
            "min_ram_gb": 8,
            "recommended_ram_gb": 16,
            "min_cpu_score": 40,  # i5/Ryzen 5 sufficient, fast clock important
            "min_gpu_score": 0,   # GPU not needed
            "min_storage_gb": 512,  # SSD untuk fast compilation & build times
            "preferred_storage_type": "SSD",
            "cpu_preference": ["intel", "amd"],
            "gpu_preference": "not_needed",
            "description": "Lightweight: 8-16GB RAM, fast CPU, SSD priority"
        },
        
        # =====================================================================
        # 7. MULTITASKING (Power user: many tabs, many apps)
        # =====================================================================
        # Alasan: Multitasking resource-heavy dalam context-switching & memory pressure.
        # RAM critical (32GB+), decent CPU untuk responsiveness.
        # GPU tidak penting tapi appreciated untuk UI smoothness.
        # Storage moderate.
        "MULTITASKING": {
            "min_ram_gb": 32,
            "recommended_ram_gb": 64,
            "min_cpu_score": 60,  # Good CPU untuk context switching
            "min_gpu_score": 1,   # Integrated OK but dedicated nicer
            "min_storage_gb": 512,
            "preferred_storage_type": "SSD",
            "cpu_preference": ["intel", "amd"],
            "gpu_preference": "any",
            "description": "Heavy RAM user: 32GB+, responsive CPU, fast storage"
        },
        
        # =====================================================================
        # 8. WORKSTATION (General/Office)
        # =====================================================================
        # Alasan: Office use case is balance antara cost & performance.
        # Modest specs cukup untuk productivity apps (Word, Excel, Zoom).
        # RAM 8GB OK, CPU moderate-to-good untuk smooth operation.
        # GPU not needed. Storage for documents & media files.
        "WORKSTATION": {
            "min_ram_gb": 8,
            "recommended_ram_gb": 16,
            "min_cpu_score": 30,  # i5/Ryzen 5 sufficient, even i3 OK
            "min_gpu_score": 0,   # GPU not needed
            "min_storage_gb": 256,  # Even 256GB OK for office work
            "preferred_storage_type": "SSD",
            "cpu_preference": ["intel", "amd"],
            "gpu_preference": "not_needed",
            "description": "Budget-friendly: 8GB RAM, modest CPU, basic storage"
        },
        
        # =====================================================================
        # 9. ENTERTAINMENT (Video & Music Consumption)
        # =====================================================================
        # Alasan: Media consumption is light-weight, GPU untuk video decoding & UI.
        # RAM modest 8GB, CPU moderate.
        # Storage untuk local media library (500GB+ recommended).
        # Prioritas: good display, good speakers, long battery.
        "ENTERTAINMENT": {
            "min_ram_gb": 8,
            "recommended_ram_gb": 16,
            "min_cpu_score": 35,  # Lower requirement
            "min_gpu_score": 1,   # For video decoding h.264/h.265
            "min_storage_gb": 512,  # For media library
            "preferred_storage_type": "any",  # HDD OK for media storage
            "cpu_preference": ["intel", "amd"],
            "gpu_preference": "any",  # GPU for decoding (integrated OK)
            "description": "Media consumption: 8GB RAM, good display, enough storage"
        },
        
        # =====================================================================
        # 10. VIDEO EDITOR (DaVinci Resolve, Premiere Pro, Vegas)
        # =====================================================================
        # Alasan: Video editing sangat demanding dalam compute & I/O.
        # GPU critical untuk real-time preview & effects rendering.
        # RAM besar (32GB+) untuk cache video frames.
        # CPU high-core untuk timeline responsiveness.
        # Storage SANGAT penting - besar dan FAST (NVMe SSD wajib).
        "VIDEO_EDITOR": {
            "min_ram_gb": 32,
            "recommended_ram_gb": 64,
            "min_cpu_score": 70,  # High-end CPU untuk timeline
            "min_gpu_score": 4,   # RTX 2060 or better (CUDA for preview)
            "min_storage_gb": 1000,  # 1TB+ for video files cache
            "preferred_storage_type": "SSD",  # NVMe SSD essential
            "cpu_preference": ["intel", "amd"],
            "gpu_preference": "dedicated_cuda",  # NVIDIA CUDA preferred for effects
            "description": "Most I/O intensive: 32GB+ RAM, high-end GPU, NVMe SSD"
        },
    }
    
    # Get RBR rules untuk intent yang diminta
    if intent not in rbr_rules:
        print(f"Warning: Intent '{intent}' tidak dikenali. Return unfiltered data.")
        return df_filtered
    
    rules = rbr_rules[intent]
    print(f"\n📋 Applying RBR Rules for intent: {intent}")
    print(f"   {rules['description']}")
    
    # =========================================================================
    # APPLY RBR RULES - FILTERING LOGIC
    # =========================================================================
    
    # 1. Filter by Budget (if provided)
    if budget is not None:
        if isinstance(budget, tuple):
            df_filtered = df_filtered[
                (df_filtered['Final Price'] >= budget[0]) & 
                (df_filtered['Final Price'] <= budget[1])
            ]
            print(f"   ✓ Budget filter: Rp {budget[0]:,} - Rp {budget[1]:,}")
        else:
            # Single value = maximum budget
            df_filtered = df_filtered[df_filtered['Final Price'] <= budget]
            print(f"   ✓ Budget filter: ≤ Rp {budget:,}")
    
    # 2. Filter by RAM (use NLP value if provided, else use intent minimum)
    min_ram = ram if ram is not None else rules['min_ram_gb']
    df_filtered = df_filtered[df_filtered['RAM'] >= min_ram]
    print(f"   ✓ RAM filter: ≥ {min_ram}GB")
    
    # 3. Filter by CPU Score (if CPU_score column exists)
    if 'CPU_score' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['CPU_score'] >= rules['min_cpu_score']]
        print(f"   ✓ CPU filter: score ≥ {rules['min_cpu_score']}")
    
    # 4. Filter by GPU Score (if GPU_score column exists)
    if 'GPU_score' in df_filtered.columns:
        gpu_min = rules['min_gpu_score']
        if gpu_min > 0:
            df_filtered = df_filtered[df_filtered['GPU_score'] >= gpu_min]
            print(f"   ✓ GPU filter: score ≥ {gpu_min}")
    
    # 5. Filter by GPU Type (dedicated vs integrated) - if applicable
    if rules['gpu_preference'] == 'dedicated' and 'GPU' in df_filtered.columns:
        # Filter untuk dedicated GPU only
        integrated_keywords = ['integrated', 'uhd', 'hd graphics', 'iris', 'intel']
        mask = ~df_filtered['GPU'].astype(str).str.lower().str.contains(
            '|'.join(integrated_keywords), 
            na=False
        )
        df_filtered = df_filtered[mask]
        print(f"   ✓ GPU type filter: dedicated GPU required")
    
    # 6. Filter by Storage (SSD preference)
    if 'Storage' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Storage'] >= rules['min_storage_gb']]
        if rules['preferred_storage_type'] == 'SSD' and 'Storage type' in df_filtered.columns:
            # Prioritize SSD but don't exclude HDD
            print(f"   ✓ Storage filter: ≥ {rules['min_storage_gb']}GB (SSD preferred)")
    
    # 7. Filter by Brand (if preferred brand provided by NLP)
    if brand is not None and 'Brand' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['Brand'].str.lower() == brand.lower()]
        print(f"   ✓ Brand filter: {brand}")
    
    # 8. Special filter untuk gaming with game requirements
    if intent == "FIND_LAPTOP_FOR_GAME" and game_list:
        print(f"   ✓ Game compatibility check: {', '.join(game_list[:3])}...")
        # This would use game_requirements minimum/recommended specs
        # More details in recommender_system.py
    
    # =========================================================================
    # VALIDATION & RETURN
    # =========================================================================
    
    remaining_count = len(df_filtered)
    original_count = len(df)
    print(f"\n   📊 Filtering Result: {remaining_count} / {original_count} laptops match criteria\n")
    
    if remaining_count == 0:
        print("   ⚠️ Warning: No laptops match all criteria. Returning all data.")
        return df.copy()
    
    return df_filtered.reset_index(drop=True)


# =============================================================================
# FUNGSI 2: GET INTENT-BASED AHP WEIGHTS (DYNAMIC)
# =============================================================================

def get_intent_based_weights(intent: str) -> Dict[str, float]:
    """
    Generate AHP weight matrix berdasarkan intent pengguna.
    
    Setiap intent memiliki bobot prioritas yang berbeda untuk 5 kriteria:
    - CPU Score
    - GPU Score
    - RAM
    - Storage (Capacity & Type)
    - Price
    
    Args:
        intent: Intent yang diinginkan (10 pilihan)
    
    Returns:
        Dictionary dengan struktur:
        {
            'CPU': float,
            'GPU': float,
            'RAM': float,
            'Storage': float,
            'Price': float,
            'Storage_Type_Bonus': float  # Optional weight untuk SSD priority
        }
        Total semua weight = 1.0
    
    Methodology:
        - Weight mencerminkan pentingnya criteria untuk intent tersebut
        - Lebih strict intent (AI/3D) → GPU weight lebih tinggi
        - Budget-conscious → Price weight lebih tinggi
        - Multitasking → RAM weight lebih tinggi
    """
    
    # AHP Weight Templates untuk 10 intent
    # Format: (CPU, GPU, RAM, Storage, Price) - HARUS TOTAL = 1.0
    weight_templates = {
        # =====================================================================
        # 1. GAMING
        # =====================================================================
        # Alasan: GPU paling penting untuk frame rate & visual quality.
        # CPU secondary (untuk physics, AI). RAM moderate (16GB enough).
        # Storage for loading times. Price adalah tradeoff.
        "FIND_LAPTOP_FOR_GAME": {
            'CPU': 0.15,           # Secondary - mostly for physics/AI
            'GPU': 0.55,           # PRIMARY - determines FPS & visual quality (INCREASED for better ranking)
            'RAM': 0.10,           # Tertiary - 16GB minimum already filtered by Phase 1
            'Storage': 0.05,       # Minimum 512GB already ensured by Phase 1
            'Price': 0.10,         # Budget constraint tradeoff (reduced for GPU priority)
            'Storage_Type_Bonus': 0.05  # SSD worth extra
        },
        
        # =====================================================================
        # 2. 3D DESIGN (CAD, Blender, VRAY)
        # =====================================================================
        # Alasan: GPU untuk CUDA rendering, CPU untuk modeling,
        # RAM SANGAT penting untuk project besar, Storage untuk cache.
        "3D_DESIGN": {
            'CPU': 0.25,           # Important for modeling & baking
            'GPU': 0.30,           # Essential - CUDA rendering
            'RAM': 0.25,           # CRITICAL - 32GB+ for large projects
            'Storage': 0.10,       # Cache & temporary files
            'Price': 0.10,         # Professional users less price-sensitive
            'Storage_Type_Bonus': 0.05
        },
        
        # =====================================================================
        # 3. 2D DESIGN (Photoshop, Illustrator)
        # =====================================================================
        # Alasan: UI responsiveness dari CPU paling penting.
        # GPU untuk UI acceleration (less critical).
        # RAM moderate untuk layer stacking.
        "2D_DESIGN": {
            'CPU': 0.30,           # PRIMARY - UI responsiveness
            'GPU': 0.15,           # Nice to have for UI acceleration
            'RAM': 0.25,           # Moderate - layer handling
            'Storage': 0.12,       # Brushes, fonts, library
            'Price': 0.18,         # Freelancers price-sensitive
            'Storage_Type_Bonus': 0.03
        },
        
        # =====================================================================
        # 4. OLAH DATA (Data Analysis, Statistics)
        # =====================================================================
        # Alasan: CPU-intensive untuk calculation & pandas operations.
        # RAM SANGAT penting untuk in-memory analytics.
        # GPU optional (good-to-have untuk parallel processing).
        "OLAH_DATA": {
            'CPU': 0.30,           # Data processing load
            'GPU': 0.10,           # Optional - for parallel compute
            'RAM': 0.35,           # CRITICAL - in-memory analytics
            'Storage': 0.10,       # Dataset & cache
            'Price': 0.15,         # Academic/enterprise budget
            'Storage_Type_Bonus': 0.03
        },
        
        # =====================================================================
        # 5. AI DEVELOPMENT (Machine Learning, Deep Learning)
        # =====================================================================
        # Alasan: GPU MANDATORY untuk training (CUDA cores).
        # RAM sangat penting untuk batch processing.
        # CPU untuk data preprocessing.
        # Storage untuk datasets & model checkpoints.
        "AI_DEVELOPMENT": {
            'CPU': 0.15,           # Data preprocessing
            'GPU': 0.40,           # PRIMARY - CUDA training
            'RAM': 0.30,           # CRITICAL - batch processing
            'Storage': 0.10,       # Datasets & models
            'Price': 0.05,         # Willing to invest in hardware
            'Storage_Type_Bonus': 0.05
        },
        
        # =====================================================================
        # 6. WEB DEVELOPMENT (React, Node, Django, etc)
        # =====================================================================
        # Alasan: CPU untuk build times & local server.
        # RAM untuk editor + browser + localhost.
        # GPU tidak relevan. Storage moderate untuk codebase.
        "WEB_DEVELOPMENT": {
            'CPU': 0.35,           # Build times & compilation speed
            'GPU': 0.05,           # Not needed
            'RAM': 0.25,           # Dev environment + browser + apps
            'Storage': 0.20,       # node_modules, docker images
            'Price': 0.15,         # Young developers, price-sensitive
            'Storage_Type_Bonus': 0.08
        },
        
        # =====================================================================
        # 7. MULTITASKING (Power users)
        # =====================================================================
        # Alasan: RAM PALING PENTING untuk context-switching.
        # CPU untuk responsiveness saat multitask.
        # GPU untuk UI smoothness. Storage untuk various apps.
        "MULTITASKING": {
            'CPU': 0.25,           # Responsiveness when multitasking
            'GPU': 0.10,           # UI smoothness (nice to have)
            'RAM': 0.40,           # CRITICAL - running many apps
            'Storage': 0.15,       # Multiple large applications
            'Price': 0.10,         # Professional, willing to invest
            'Storage_Type_Bonus': 0.05
        },
        
        # =====================================================================
        # 8. WORKSTATION (General/Office)
        # =====================================================================
        # Alasan: Balanced, budget-conscious.
        # CPU moderate, RAM moderate, GPU unnecessary.
        # Price adalah faktor penting.
        "WORKSTATION": {
            'CPU': 0.20,           # Moderate performance needed
            'GPU': 0.05,           # Not needed for office
            'RAM': 0.20,           # 8GB usually enough
            'Storage': 0.15,       # Documents, media
            'Price': 0.40,         # Budget is PRIMARY concern
            'Storage_Type_Bonus': 0.03
        },
        
        # =====================================================================
        # 9. ENTERTAINMENT (Video & Music)
        # =====================================================================
        # Alasan: GPU untuk video decoding (can save CPU power).
        # CPU moderate. RAM untuk smooth playback.
        # Storage besar untuk media library.
        "ENTERTAINMENT": {
            'CPU': 0.15,           # Modest requirements
            'GPU': 0.15,           # For video decoding efficiency
            'RAM': 0.15,           # Smooth streaming/playback
            'Storage': 0.25,       # Large media library
            'Price': 0.30,         # Consumer price-sensitive
            'Storage_Type_Bonus': 0.02
        },
        
        # =====================================================================
        # 10. VIDEO EDITOR (DaVinci, Premiere, Vegas)
        # =====================================================================
        # Alasan: Storage CRITICAL untuk I/O performance.
        # GPU untuk CUDA rendering & preview.
        # RAM untuk timeline caching.
        # CPU untuk codec encoding.
        "VIDEO_EDITOR": {
            'CPU': 0.20,           # Codec encoding
            'GPU': 0.30,           # CUDA rendering & preview
            'RAM': 0.25,           # Timeline cache & effects
            'Storage': 0.20,       # CRITICAL - fast storage for video I/O
            'Price': 0.05,         # Professional, not price-sensitive
            'Storage_Type_Bonus': 0.08  # NVMe SSD essential
        },
    }
    
    # Get template untuk intent
    if intent not in weight_templates:
        print(f"Warning: Intent '{intent}' tidak dikenali. Return default weights.")
        # Fallback ke balanced weights
        return {
            'CPU': 0.20,
            'GPU': 0.20,
            'RAM': 0.25,
            'Storage': 0.15,
            'Price': 0.20,
            'Storage_Type_Bonus': 0.03
        }
    
    template = weight_templates[intent]
    
    # Validation: Pastikan total = 1.0
    total_weight = sum([v for k, v in template.items() if k != 'Storage_Type_Bonus'])
    if abs(total_weight - 1.0) > 0.001:
        print(f"Warning: Weight total untuk {intent} = {total_weight}, should be 1.0")
        # Auto-normalize
        for key in ['CPU', 'GPU', 'RAM', 'Storage', 'Price']:
            template[key] = template[key] / total_weight
    
    print(f"\n⚖️  AHP Weights untuk intent '{intent}':")
    print(f"   CPU:      {template['CPU']:.1%}")
    print(f"   GPU:      {template['GPU']:.1%}")
    print(f"   RAM:      {template['RAM']:.1%}")
    print(f"   Storage:  {template['Storage']:.1%}")
    print(f"   Price:    {template['Price']:.1%}")
    if 'Storage_Type_Bonus' in template and template['Storage_Type_Bonus'] > 0:
        print(f"   SSD Bonus: {template['Storage_Type_Bonus']:.1%}\n")
    
    return template


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_all_intents() -> list:
    """Return list semua intent yang tersupported."""
    return [
        "FIND_LAPTOP_FOR_GAME",
        "3D_DESIGN",
        "2D_DESIGN",
        "OLAH_DATA",
        "AI_DEVELOPMENT",
        "WEB_DEVELOPMENT",
        "MULTITASKING",
        "WORKSTATION",
        "ENTERTAINMENT",
        "VIDEO_EDITOR",
    ]


def validate_intent(intent: str) -> bool:
    """Check apakah intent valid."""
    return intent in get_all_intents()


def get_intent_description(intent: str) -> str:
    """Get deskripsi singkat untuk intent."""
    descriptions = {
        "FIND_LAPTOP_FOR_GAME": "Gaming - High-end GPU untuk smooth gameplay",
        "3D_DESIGN": "3D Design - Workstation-grade untuk rendering",
        "2D_DESIGN": "2D Design - Responsive CPU + moderate specs",
        "OLAH_DATA": "Data Analysis - High RAM untuk in-memory computing",
        "AI_DEVELOPMENT": "AI/ML Development - NVIDIA CUDA untuk training",
        "WEB_DEVELOPMENT": "Web Development - Fast CPU untuk build times",
        "MULTITASKING": "Multitasking - 32GB+ RAM untuk context switching",
        "WORKSTATION": "Office/General - Budget-friendly balanced specs",
        "ENTERTAINMENT": "Media Consumption - Good display + large storage",
        "VIDEO_EDITOR": "Video Editing - High-speed I/O + CUDA GPU",
    }
    return descriptions.get(intent, "Unknown intent")


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    """
    Example penggunaan fungsi-fungsi ini.
    """
    
    # Contoh 1: Get weights untuk gaming
    print("=" * 70)
    print("CONTOH 1: Get AHP Weights untuk Gaming")
    print("=" * 70)
    gaming_weights = get_intent_based_weights("FIND_LAPTOP_FOR_GAME")
    print(f"Result: {gaming_weights}\n")
    
    # Contoh 2: Get weights untuk 3D Design
    print("=" * 70)
    print("CONTOH 2: Get AHP Weights untuk 3D Design")
    print("=" * 70)
    design_weights = get_intent_based_weights("3D_DESIGN")
    print(f"Result: {design_weights}\n")
    
    # Contoh 3: List semua intent
    print("=" * 70)
    print("CONTOH 3: Semua Intent yang Tersupported")
    print("=" * 70)
    intents = get_all_intents()
    for i, intent in enumerate(intents, 1):
        desc = get_intent_description(intent)
        print(f"{i:2d}. {intent:25s} - {desc}")
    print()
    
    # Contoh 4: Smart filtering (dengan dummy dataframe)
    print("=" * 70)
    print("CONTOH 4: Smart Filtering untuk Gaming")
    print("=" * 70)
    
    # Create dummy laptop data
    dummy_data = {
        'Brand': ['Asus', 'Dell', 'Lenovo', 'MSI', 'HP'],
        'Model': ['ROG', 'Alienware', 'Legion', 'Raider', 'Omen'],
        'RAM': [16, 32, 8, 16, 16],
        'CPU_score': [70, 80, 50, 75, 65],
        'GPU_score': [4, 5, 2, 4, 3],
        'Storage': [512, 1000, 256, 512, 512],
        'Final Price': [15_000_000, 25_000_000, 10_000_000, 18_000_000, 12_000_000]
    }
    df_dummy = pd.DataFrame(dummy_data)
    
    print("Original data:")
    print(df_dummy)
    print("\n")
    
    # Apply filter
    df_filtered = apply_smart_filters(
        df_dummy,
        intent="FIND_LAPTOP_FOR_GAME",
        budget=(10_000_000, 20_000_000),
        ram=8
    )
    
    print("\nFiltered data:")
    print(df_filtered)
