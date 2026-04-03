# Phase 1 Implementation: Smart Filters + Dynamic AHP Weights
## Hybrid Recommender System Architecture

---

## 📋 Overview

**Goal:** Implement Rule-Based Reasoning (RBR) + Dynamic AHP for 10 user intents

**Architecture:**
```
User Query (NLP)
    ↓
Intent Recognition
    ↓
apply_smart_filters() [RBR Logic]
    ↓
Filtered Laptop Pool
    ↓
get_intent_based_weights() [Dynamic AHP]
    ↓
AHP Weights (prepared for TOPSIS)
    ↓
TOPSIS Ranking (Phase 2)
```

---

## 🎯 The 10 User Intents

| No. | Intent | Primary Focus | Min Specs | AHP Priority |
|-----|--------|---------------|-----------|--------------|
| 1 | **Gaming** | FPS & Graphics | GPU RTX+, 8GB RAM | GPU 40% |
| 2 | **3D Design** | Rendering Power | 32GB RAM, CUDA | GPU 30%, RAM 25% |
| 3 | **2D Design** | UI Responsiveness | 16GB RAM, fast CPU | CPU 30%, RAM 25% |
| 4 | **Data Analysis** | Computation Speed | 16GB RAM, multi-core | RAM 35%, CPU 30% |
| 5 | **AI/ML Dev** | CUDA Training | 32GB RAM, RTX GPU | GPU 40%, RAM 30% |
| 6 | **Web Dev** | Build Speed | 8GB RAM, fast CPU | CPU 35%, Storage 20% |
| 7 | **Multitasking** | Context Switching | 32GB+ RAM, responsive | RAM 40%, CPU 25% |
| 8 | **Office/General** | Balanced | 8GB RAM, modest specs | **Price 40%** |
| 9 | **Entertainment** | Media Playback | 8GB RAM, 500GB+ storage | Storage 25%, Price 30% |
| 10 | **Video Editing** | I/O Performance | 32GB RAM, NVMe SSD | Storage 20%, GPU 30% |

---

## 🔧 Function 1: `apply_smart_filters()`

### Purpose
Rule-Based Reasoning (RBR) untuk filter laptop berdasarkan intent specific requirements.

### Signature
```python
def apply_smart_filters(
    df: pd.DataFrame,           # Laptop dataframe
    intent: str,                # User intent (10 choices)
    budget: Tuple[int, int],    # Optional: (min, max) price range
    ram: int,                   # Optional: minimum RAM in GB
    brand: str,                 # Optional: brand preference
    game_list: list             # Optional: for gaming intent
) -> pd.DataFrame:               # Filtered laptop dataframe
```

### RBR Rules Per Intent

#### 1. **Gaming** 🎮
```
Minimum Requirements:
  - RAM: 8 GB (recommended: 16 GB)
  - CPU Score: 60 (i5/Ryzen 5)
  - GPU Score: 3+ (GTX 1050 or RTX equivalent)
  - GPU Type: DEDICATED (no integrated)
  - Storage: 512 GB SSD

Rationale:
  Dedicated GPU essential untuk high FPS. Multi-core CPU untuk physics/AI.
  SSD untuk fast loading. 8GB baseline, but 16GB recommended for modern games.
```

#### 2. **3D Design (CAD/Blender/VRAY)** 🎨
```
Minimum Requirements:
  - RAM: 32 GB (recommended: 64 GB)
  - CPU Score: 80 (high-core Ryzen 9/i9)
  - GPU Score: 4+ (RTX 2060 or better with CUDA)
  - GPU Type: PROFESSIONAL dedicated
  - Storage: 1 TB SSD

Rationale:
  3D rendering extremely memory-intensive. CUDA-capable GPU mandatory.
  High-core CPU untuk faster rendering. 1TB for cache & temporary files.
```

#### 3. **2D Design (Photoshop/Illustrator)** ✏️
```
Minimum Requirements:
  - RAM: 16 GB (recommended: 32 GB)
  - CPU Score: 50 (i5/Ryzen 5)
  - GPU Score: 1+ (integrated GPU acceptable)
  - Storage: 512 GB SSD

Rationale:
  UI responsiveness depends on CPU >= GPU. Integrated GPU OK.
  RAM untuk layer stacking in large canvas. SSD for responsiveness.
```

#### 4. **Data Analysis (Stats/DB)** 📊
```
Minimum Requirements:
  - RAM: 16 GB (recommended: 32 GB)
  - CPU Score: 60 (multi-core important)
  - GPU Score: 0+ (optional, CUDA nice-to-have)
  - Storage: 512 GB SSD

Rationale:
  CPU multi-core untuk data processing. RAM critical untuk in-memory analytics.
  GPU optional but beneficial for parallel compute (pandas GPU acceleration).
```

#### 5. **AI/ML Development** 🤖
```
Minimum Requirements:
  - RAM: 32 GB (recommended: 64 GB)
  - CPU Score: 70 (high-end processor)
  - GPU Score: 4+ (RTX 2060+ with CUDA 7.0+ compute capability)
  - GPU Type: DEDICATED with CUDA support
  - Storage: 1 TB SSD

Rationale:
  Most demanding use case. NVIDIA CUDA MANDATORY for model training.
  32GB+ for batch processing & gradient computation.
  1TB for datasets, models, checkpoints.
```

#### 6. **Web Development** 💻
```
Minimum Requirements:
  - RAM: 8 GB (recommended: 16 GB)
  - CPU Score: 40 (i5/Ryzen 5, fast clock important)
  - GPU Score: 0 (not needed)
  - Storage: 512 GB SSD

Rationale:
  IO-bound work (compilation, bundling). CPU clock speed matters.
  RAM for editor + browser + localhost servers.
  SSD for fast npm install & webpack builds.
```

#### 7. **Multitasking (Power User)** ⚡
```
Minimum Requirements:
  - RAM: 32 GB (recommended: 64 GB)
  - CPU Score: 60 (good multi-core)
  - GPU Score: 1+ (any GPU OK)
  - Storage: 512 GB SSD

Rationale:
  RAM is bottleneck for many concurrent applications.
  CPU for context-switching responsiveness.
  Fast storage for application cache invalidation.
```

#### 8. **Workstation (Office/General)** 💼
```
Minimum Requirements:
  - RAM: 8 GB
  - CPU Score: 30 (i5/Ryzen 5, even i3 acceptable)
  - GPU Score: 0 (not needed)
  - Storage: 256 GB (can be HDD acceptable)

Rationale:
  Light productivity apps (Word, Excel, Zoom) don't require high specs.
  Budget is primary concern for office segment.
  Even integrated GPU sufficient.
```

#### 9. **Entertainment (Video/Music)** 🎬
```
Minimum Requirements:
  - RAM: 8 GB (recommended: 16 GB)
  - CPU Score: 35 (low requirement)
  - GPU Score: 1+ (for video decoding h.264/h.265)
  - Storage: 512 GB (any type OK for media)

Rationale:
  Low compute demand. GPU for efficient video decoding.
  Storage untuk local media library.
  Good display more important than specs (not in dataset).
```

#### 10. **Video Editing (DaVinci/Premiere/Vegas)** 🎥
```
Minimum Requirements:
  - RAM: 32 GB (recommended: 64 GB)
  - CPU Score: 70 (high-core untuk timeline)
  - GPU Score: 4+ (RTX 2060+ με CUDA)
  - GPU Type: DEDICATED with CUDA
  - Storage: 1 TB NVMe SSD (CRITICAL)

Rationale:
  Most I/O intensive task. NVMe SSD ESSENTIAL untuk real-time preview.
  CUDA GPU untuk effects rendering & transcoding.
  32GB+ untuk timeline cache & effects layer computation.
```

---

## ⚖️ Function 2: `get_intent_based_weights()`

### Purpose
Generate dynamic AHP weight matrix for TOPSIS ranking based on intent.

### Signature
```python
def get_intent_based_weights(intent: str) -> Dict[str, float]:
    # Returns: {'CPU': 0.20, 'GPU': 0.40, 'RAM': 0.15, 'Storage': 0.10, 'Price': 0.15, ...}
    # Total MUST = 1.0
```

### Weight Matrix for All 10 Intents

```
                   CPU    GPU    RAM   STOR  PRICE  SSD_BONUS  Total
Gaming            0.20   0.40   0.15  0.10  0.15   0.05       1.00
3D Design         0.25   0.30   0.25  0.10  0.10   0.05       1.00
2D Design         0.30   0.15   0.25  0.12  0.18   0.03       1.00
Data Analysis     0.30   0.10   0.35  0.10  0.15   0.03       1.00
AI/ML Dev         0.15   0.40   0.30  0.10  0.05   0.05       1.00
Web Dev           0.35   0.05   0.25  0.20  0.15   0.08       1.00
Multitasking      0.25   0.10   0.40  0.15  0.10   0.05       1.00
Workstation       0.20   0.05   0.20  0.15  0.40   0.03       1.00
Entertainment     0.15   0.15   0.15  0.25  0.30   0.02       1.00
Video Editor      0.20   0.30   0.25  0.20  0.05   0.08       1.00
```

### Weight Rationale

| Weight | Rationale | Example |
|--------|-----------|---------|
| **0.40-0.50** | PRIMARY criteria | GPU for Gaming (0.40), RAM for Multitasking (0.40), Price for Office (0.40) |
| **0.25-0.35** | SECONDARY criteria | CPU for Web Dev (0.35), RAM for Data/3D (0.25-0.35) |
| **0.10-0.20** | TERTIARY criteria | Storage generic (0.10-0.20), Price for professionals (0.05-0.10) |
| **0.05** | OPTIONAL/BONUS | SSD type bonus for speed-critical tasks |

### Key Characteristics

1. **Gaming (0.40 GPU)**
   - GPU dominates (FPS depends on GPU)
   - CPU secondary (physics/AI)
   - Price considerations for budget gamers

2. **3D Design (GPU 0.30 + RAM 0.25)**
   - Balanced GPU/RAM (both important)
   - CUDA rendering + project cache
   - CPU for modeling speed

3. **AI/ML (GPU 0.40 + RAM 0.30)**
   - GPU highest (CUDA training)
   - RAM close second (batch processing)
   - Lowest price weight (willing to invest)

4. **Office/General (Price 0.40)**
   - Price is PRIMARY concern
   - Balanced other specs
   - Budget segment

5. **Video Editor (GPU 0.30 + Storage 0.20)**
   - High GPU (CUDA encoding)
   - High Storage (I/O critical)
   - RAM & CPU moderate

---

## 📝 Implementation Checklist

- [x] Create `smart_filters_and_ahp.py` with 2 main functions
- [x] Document RBR rules for 10 intents (min specs)
- [x] Document AHP weights for 10 intents
- [x] Add helper functions (validate_intent, get_all_intents)
- [ ] **Phase 1a:** Unit tests for both functions
- [ ] **Phase 1b:** Integration test with real laptop data
- [ ] **Phase 2:** Integrate with app.py FastAPI endpoints
- [ ] **Phase 3:** TOPSIS calculation module
- [ ] **Phase 4:** End-to-end testing with NLP pipeline

---

## 🧪 Testing (Manual)

Run the example at the bottom of `smart_filters_and_ahp.py`:

```bash
python src/smart_filters_and_ahp.py
```

Expected outputs:
1. AHP weights untuk Gaming
2. AHP weights untuk 3D Design
3. List of all 10 intents
4. Filtered laptop data before/after

---

## 🔗 Integration with Existing Code

### Current NLP Pipeline
```python
# In recommender_system.py
from src.smart_filters_and_ahp import apply_smart_filters, get_intent_based_weights

# Modified workflow:
pipeline_result = nlp_pipeline_fuzzy(user_query, ...)
intent = recognize_intent_simple(...)

# NEW: Apply RBR filter
filtered_df = apply_smart_filters(
    laptop_df,
    intent=intent,
    budget=pipeline_result['budget'],
    ram=pipeline_result['ram'],
    brand=pipeline_result.get('brand'),
    game_list=pipeline_result.get('games')
)

# NEW: Get dynamic AHP weights
ahp_weights = get_intent_based_weights(intent)

# EXISTING (Phase 2): Pass to TOPSIS
# topsis_result = run_topsis(filtered_df, ahp_weights, ...)
```

---

## 📚 File Structure

```
Rekomendasi-Laptop-NLP/
├── src/
│   ├── smart_filters_and_ahp.py    ← NEW (Phase 1)
│   ├── nlp_pipeline.py             (existing)
│   ├── recommender_system.py       (will modify for integration)
│   └── recommender_core.py         (existing)
├── PHASE1_DESIGN.md                ← This file
├── tests/
│   └── test_phase1.py              (to be created)
└── ...
```

---

## 🎓 Learning Outcomes

After Phase 1:
- Understand RBR (Rule-Based Reasoning) pattern
- Dynamic weight generation based on context
- Modular architecture for maintainability
- Foundation for Phase 2 (TOPSIS integration)

---

**Status:** Phase 1 Core Functions ✅ Complete  
**Next:** Phase 1a - Unit Tests & Validation
