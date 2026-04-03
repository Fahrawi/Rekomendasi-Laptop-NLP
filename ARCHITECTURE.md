# 🏗️ System Architecture

## Overview

Sistem Rekomendasi Laptop adalah sistem rekomendasi berbasis hybrid dengan 3 fase:
- **Phase 1:** Smart Filtering + Analytic Hierarchy Process (AHP)
- **Phase 2:** TOPSIS (Technique for Order Preference by Similarity to Ideal Solution)
- **Phase 3:** FastAPI REST API Integration

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      CLIENT REQUEST                             │
│                 (HTTP POST to /api/recommend-hybrid)             │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
        ┌──────────────────────────────────────────────────┐
        │          NLP INTENT EXTRACTION                   │
        │     (src/nlp_pipeline.py)                        │
        │  - Extract intent from natural language          │
        │  - Supported: 10 intents (GAMING, AI_DEV, etc.)  │
        └──────────────────────┬───────────────────────────┘
                               │
                               ▼
        ┌──────────────────────────────────────────────────┐
        │     PHASE 1: SMART FILTERING + AHP               │
        │   (src/smart_filters_and_ahp.py)                 │
        │                                                  │
        │  1. Apply Rule-Based Filtering                  │
        │     - Budget filtering (min/max)                │
        │     - RAM filtering                             │
        │     - Brand filtering (optional)                │
        │     - Game requirements filtering               │
        │                                                  │
        │  2. Calculate Intent-Based Weights (AHP)        │
        │     - Gaming: GPU 57.9%, CPU 15.8%, ...         │
        │     - AI Dev: GPU 40%, CPU 35%, ...             │
        │     - Daily Use: Price 40%, CPU 20%, ...        │
        │                                                  │
        │  3. Normalize weights                           │
        │     - Sum to 1.0                                │
        │                                                  │
        │  Output: Filtered laptop list + weights         │
        └──────────────────────┬───────────────────────────┘
                               │
                               ▼
        ┌──────────────────────────────────────────────────┐
        │   PHASE 2: TOPSIS RANKING                        │
        │   (src/topsis_engine.py)                         │
        │                                                  │
        │  1. Normalize scores (0-1 range)               │
        │     - CPU_score, GPU_score                      │
        │     - RAM, Storage                              │
        │     - Final_Price                               │
        │                                                  │
        │  2. Apply weighted normalization                │
        │     - Each value × criteria weight              │
        │     - Creates weighted decision matrix          │
        │                                                  │
        │  3. Calculate ideal/negative ideal solutions    │
        │     - Best possible: max for benefit, min for cost │
        │     - Worst possible: min for benefit, max for cost│
        │                                                  │
        │  4. Calculate TOPSIS score (0-1)               │
        │     - Distance to ideal / total distance        │
        │     - Higher = better                           │
        │                                                  │
        │  5. Rank by TOPSIS score (descending)          │
        │     - Return top_n = 5 recommendations          │
        │                                                  │
        │  Output: Top 5 ranked laptops with scores       │
        └──────────────────────┬───────────────────────────┘
                               │
                               ▼
        ┌──────────────────────────────────────────────────┐
        │   PHASE 3: RESPONSE FORMATTING                  │
        │   (app.py)                                       │
        │                                                  │
        │  1. Format results as JSON                      │
        │  2. Add reasoning per laptop                    │
        │  3. Include weights applied                     │
        │  4. Add metadata (filtered_count, etc.)        │
        │                                                  │
        │  Output: HTTP 200 JSON response                 │
        └──────────────────────┬───────────────────────────┘
                               │
                               ▼
        ┌──────────────────────────────────────────────────┐
        │         CLIENT RESPONSE (JSON)                   │
        │  [                                                │
        │    {rank, brand, model, specs, score},          │
        │    {rank, brand, model, specs, score},          │
        │    ...                                          │
        │  ]                                              │
        └──────────────────────────────────────────────────┘
```

---

## Component Architecture

### 1. Entry Point: `app.py`

**Responsibilities:**
- FastAPI application setup
- Route definitions
- Request validation (Pydantic models)
- Response formatting

**Key Routes:**
```python
@app.post("/api/recommend-hybrid")
├── Validate request
├── Call Phase 1 (filtering + AHP)
├── Call Phase 2 (TOPSIS ranking)
└── Format and return response

@app.get("/recommend")
├── Legacy NLP-based endpoint
└── For backward compatibility

@app.get("/health")
├── Health check

@app.get("/debug")
└── Data loading status
```

**Startup Events:**
```python
@app.on_event("startup")
├── Load laptops CSV (2,160 entries)
├── Load minimum requirements KB
├── Load recommended requirements KB
├── Initialize NLP pipeline
└── Cache computation results
```

### 2. Phase 1: `src/smart_filters_and_ahp.py`

**Main Functions:**

#### `apply_smart_filters()`
```
Input:  laptops DF + filtering criteria
Logic:  - Apply budget filter
        - Apply RAM filter
        - Apply brand filter (optional)
        - Apply game requirements
Output: Filtered laptop list
```

**Filtering Logic:**

```python
# Budget filtering (AND logic)
filtered = df[(df['Final Price'] >= budget_min) & 
              (df['Final Price'] <= budget_max)]

# RAM filtering
filtered = filtered[filtered['RAM'] >= ram_min]

# Brand filtering (if specified)
if brand:
    filtered = filtered[filtered['Brand'] == brand]

# Game requirements (if games specified)
for game in games:
    min_reqs = get_minimum_requirements(game)
    filtered = apply_game_requirements(filtered, min_reqs)

return filtered
```

#### `get_intent_based_weights()`
```
Input:  Intent (e.g., "FIND_LAPTOP_FOR_GAME")
Logic:  - Look up intent → weights mapping
        - Normalize weights (sum = 1.0)
Output: {"CPU": 0.158, "GPU": 0.579, ...}
```

**Weight Mappings:**

```python
WEIGHTS_MAPPING = {
    "FIND_LAPTOP_FOR_GAME": {
        "GPU": 0.55,      # Gaming = GPU primary
        "CPU": 0.15,
        "RAM": 0.10,
        "Storage": 0.05,
        "Price": 0.10
    },
    "AI_DEVELOPMENT": {
        "GPU": 0.40,      # AI = GPU + CPU important
        "CPU": 0.35,
        "RAM": 0.20,
        "Storage": 0.00,  # Not relevant
        "Price": 0.05
    },
    "DAILY_USE": {
        "GPU": 0.05,      # Daily use = price primary
        "CPU": 0.20,
        "RAM": 0.20,
        "Storage": 0.05,
        "Price": 0.40
    },
    # ... 7 more intents
}
```

**Normalization:**
```python
total = sum(weights.values())
normalized = {k: v/total for k, v in weights.items()}
# Result: sum(normalized.values()) = 1.0
```

### 3. Phase 2: `src/topsis_engine.py`

**Main Function: `run_topsis()`**

**Algorithm Steps:**

```
Step 1: Prepare Decision Matrix
        ┌─────────────────────────┐
        │ Laptop1 │ CPU │ GPU │ RAM│
        │ Laptop2 │ ... │ ... │ ..│
        │ Laptop3 │     │     │   │
        └─────────────────────────┘

Step 2: Normalize Matrix (0-1 scale)
        for each criterion:
          normalized[i] = value[i] / sqrt(sum(value[i]^2))

Step 3: Apply Weights (Weighted Normalized Matrix)
        weighted[i] = normalized[i] × weight[i]

Step 4: Identify Ideal Solutions
        Ideal:         {max(weighted_CPU), max(weighted_GPU), ...}
        Negative Ideal: {min(weighted_CPU), min(weighted_GPU), ...}

Step 5: Calculate Distance to Each
        Distance_to_Ideal = sqrt(sum((value[i] - ideal[i])^2))
        Distance_to_Neg_Ideal = sqrt(sum((value[i] - neg_ideal[i])^2))

Step 6: Calculate TOPSIS Score
        TOPSIS = Distance_to_Neg_Ideal / (Distance_to_Ideal + Distance_to_Neg_Ideal)
        Note: Higher score = better match
        Range: 0.0 to 1.0

Step 7: Rank by TOPSIS Score (Descending)
        Sort and return top_n results
```

**Example Calculation (Simplified):**

```
Laptops: A (GPU=2000, Price=10M), B (GPU=1500, Price=8M)
Weights: GPU=60%, Price=40%

After normalization & weighting:
  A_weighted = [GPU_norm×0.6, Price_norm×0.4]
  B_weighted = [GPU_norm×0.6, Price_norm×0.4]

Ideal = [max_GPU×0.6, min_Price×0.4]
Neg_ideal = [min_GPU×0.6, max_Price×0.4]

TOPSIS_A = distance_to_neg_ideal / total_distance
TOPSIS_B = distance_to_neg_ideal / total_distance

If TOPSIS_A > TOPSIS_B: Laptop A ranks higher
```

**Key Functions:**

```python
def run_topsis(
    filtered_df,           # From Phase 1
    weights,               # From Phase 1 AHP
    criteria=['CPU', 'GPU', 'RAM', 'Storage', 'Price'],
    benefit_criteria=['CPU', 'GPU', 'RAM'],  # Higher = better
    cost_criteria=['Storage', 'Price'],      # Lower = better
    top_n=5
):
    # Internal steps shown above
    return top_n_laptops_with_scores

def get_topsis_summary(topsis_df, top_n=5):
    # Returns list of top_n recommendations
    return topsis_df.head(top_n)

def map_criteria_to_weight_key(column_name):
    # Maps 'GPU_score' → 'GPU', 'Final Price' → 'Price'
    mapping = {
        'CPU_score': 'CPU',
        'GPU_score': 'GPU',
        'Final Price': 'Price',
        'RAM': 'RAM',
        'Storage': 'Storage'
    }
    return mapping.get(column_name, column_name)
```

### 4. Data Processing: `src/nlp_pipeline.py`

**NLP Pipeline Stages:**

```
Raw User Input
     │
     ▼
Tokenization (split by spaces, punctuation)
     │
     ▼
Lowercasing & Cleaning (remove special chars)
     │
     ▼
Intent Classification
  ├─ Check game keywords (Hi3rd, Valorant, etc.)
  ├─ Check budget keywords (juta, budget, etc.)
  ├─ Check use-case keywords (gaming, AI, coding, etc.)
  └─ Match to 10 defined intents
     │
     ▼
Requirement Extraction
  ├─ Extract budget amount
  ├─ Extract RAM requirement  
  ├─ Extract brand preference
  └─ Extract game list
     │
     ▼
Normalized Request Object
  {
    intent: "FIND_LAPTOP_FOR_GAME",
    budget_max: 20000000,
    ram_min: 8,
    games: ["HI3RD"],
    ...
  }
```

### 5. Data Layer

**Data Files:**

```
data/
├── laptop_specs.csv              (2,160 rows × 7 columns)
│   ├── Brand, Model, CPU_score, GPU_score, RAM, Storage, Final_Price
│   └── Used by: Phase 1 + 2
│
├── minimum_requirements.csv      (Games → Min specs)
│   ├── Game, MinCPU, MinGPU, MinRAM, MinStorage
│   └── Used by: Phase 1 filtering
│
└── recommended_requirements.csv  (Games → Recommended specs)
    ├── Game, RecCPU, RecGPU, RecRAM, RecStorage
    └── Used by: Phase 1 filtering (optional)
```

**Data Loading (Startup):**

```python
@app.on_event("startup")
async def load_data():
    global laptop_df, min_req_df, rec_req_df
    
    # Load CSV files
    laptop_df = pd.read_csv("data/laptop_specs.csv")           # 2,160 rows
    min_req_df = pd.read_csv("data/minimum_requirements.csv")  # ~50 games
    rec_req_df = pd.read_csv("data/recommended_requirements.csv")
    
    # Cache for quick access
    app.state.laptop_data = laptop_df
    app.state.min_req_data = min_req_df
    app.state.rec_req_data = rec_req_df
    
    # Status logged
    print("✅ Data loading complete")
```

---

## Data Flow Examples

### Example 1: Gaming Laptop Query

```
USER INPUT:
"Saya mau main Hi3rd dengan budget max 20jt"
     │
     ▼ (app.py)
Parse into:
{
  "intent": "FIND_LAPTOP_FOR_GAME",
  "budget_max": 20000000,
  "games": ["HI3RD"]
}
     │
     ▼ (Phase 1: smart_filters_and_ahp.py)
First, get game requirements:
  HI3RD minimum: GPU ≥ 15000, RAM ≥ 8GB, CPU ≥ 15000

Then filter:
  ✓ Final Price ≤ 20M
  ✓ RAM ≥ 8
  ✓ GPU_score ≥ 15000 (from game requirement)
  Result: 329 laptops match

Then calculate weights:
  Gaming intent weights: GPU 55%, CPU 15%, RAM 10%, Storage 5%, Price 10%
  After normalization: GPU 57.9%, CPU 15.8%, etc.
     │
     ▼ (Phase 2: topsis_engine.py)
For each of 329 laptops:
  1. Normalize criteria values
  2. Apply weights
  3. Calculate distance to ideal
  4. Calculate distance to neg-ideal
  5. TOPSIS = Neg_dist / (Ideal_dist + Neg_dist)

Result: All 329 ranked by TOPSIS score
     │
     ▼ (Phase 3: app.py)
Select top 5:
  1. MSI Katana (score 0.8904)
  2. Lenovo Legion (score 0.8873)
  3. HP Omen (score 0.8863)
  4. ASUS TUF (score 0.8840)
  5. Acer Predator (score 0.8820)
     │
     ▼
Return JSON response with:
  - Recommendations list
  - Weights applied
  - Filtered/ranked counts
  - Reasoning for each
```

### Example 2: AI/ML Development Query

```
USER INPUT:
"Laptop untuk AI development, budget 50 juta, RAM minimum 32GB"
     │
     ▼
Parse to:
{
  "intent": "AI_DEVELOPMENT",
  "budget_max": 50000000,
  "ram_min": 32
}
     │
     ▼ (Phase 1: smart_filters_and_ahp.py)
Filter:
  ✓ Final Price ≤ 50M
  ✓ RAM ≥ 32GB (strict requirement)
  Result: 45 laptops match (RAM ≥32GB rare)

Calculate weights:
  AI_DEV intent: GPU 40%, CPU 35%, RAM 20%
  After norm: GPU 40%, CPU 35%, RAM 20%, Storage 0%, Price 5%
     │
     ▼ (Phase 2: topsis_engine.py)
Rank 45 laptops:
  - CPU & GPU primary factors
  - RAM already filtered (≥32GB)
  - Storage less important (0%)
     │
     ▼
Top 5 results (premium laptops with best CPU+GPU)
```

---

## Configuration & Customization

### Intent-Weight Mapping

Located in `src/smart_filters_and_ahp.py`:

```python
def get_intent_based_weights(intent: str):
    weights = {
        "FIND_LAPTOP_FOR_GAME": {
            "GPU": 0.55,
            "CPU": 0.15,
            "RAM": 0.10,
            "Storage": 0.05,
            "Price": 0.10
        },
        # ... other intents
    }
```

**To customize:** Edit the dictionary to adjust weighting for each intent.

### Criteria Definition

In `app.py`:

```python
CRITERIA = {
    "CPU": {"column": "CPU_score", "benefit": True},
    "GPU": {"column": "GPU_score", "benefit": True},
    "RAM": {"column": "RAM", "benefit": True},
    "Storage": {"column": "Storage", "benefit": True},
    "Price": {"column": "Final Price", "benefit": False}
}
```

**Benefit vs Cost:**
- Benefit criterion: Higher value = better (CPU, GPU, RAM)
- Cost criterion: Lower value = better (Price)

### TOPSIS Parameters

In `src/topsis_engine.py`:

```python
def run_topsis(
    ...,
    benefit_criteria=['CPU', 'GPU', 'RAM'],  # Modify here
    cost_criteria=['Price'],                 # Modify here
    top_n=5                                  # Change default top-N
)
```

---

## Performance Characteristics

### Time Complexity

| Operation | Complexity | Typical Time |
|-----------|-----------|--------------|
| Phase 1 Filtering | O(n) | 10-50ms |
| Phase 1 AHP weighting | O(1) | <1ms |
| Phase 2 TOPSIS | O(n×m) | 50-200ms |
| Total response | O(n×m) | 100-300ms |

Where:
- n = number of filtered laptops (100-500)
- m = number of criteria (5)

### Memory Usage

| Component | Size |
|-----------|------|
| Laptop CSV (2,160 items) | ~2 MB |
| Requirements CSVs | ~500 KB |
| NLP Knowledge Base | ~1 MB |
| FastAPI in-memory cache | ~5 MB |
| Per-request dataframe | 100-500 KB |

**Total startup memory:** ~10 MB

---

## Error Handling & Recovery

```python
# Phase 1 errors
├─ Invalid intent → 400 Bad Request
├─ Budget validation → Check budget_min < budget_max
└─ Data loading error → Retry on startup

# Phase 2 errors
├─ Empty filtered list → Return empty recommendations
├─ Numerical errors → Graceful degradation
└─ Missing columns → Column mapping handles it

# API errors
├─ 400 Bad Request (invalid input)
├─ 503 Service Unavailable (data not loaded)
└─ 500 Internal Server Error (system error)
```

---

## Testing Strategy

### Unit Tests (Phase 1)
- 122 tests in `tests/test_smart_filters_and_ahp.py`
- Coverage: Filtering, AHP, normalization

### Unit Tests (Phase 2)
- 26 tests in `tests/test_topsis_engine.py`
- Coverage: TOPSIS algorithm, scoring

### Integration Tests
- End-to-end API tests
- Real data with known queries
- Known good results verification

---

## Deployment Architecture

### Development
```
Client (curl/Postman)
   │
   ▼ :8000
FastAPI (Uvicorn)
   │
   ├─ /api/recommend-hybrid
   ├─ /recommend
   ├─ /health
   └─ /debug
```

### Production (Recommended)
```
                    ┌─── Nginx (port 80/443)
                    │
                    ▼
        ┌─── Load Balancer
        │
        ├─ FastAPI Instance 1 (port 8001)
        ├─ FastAPI Instance 2 (port 8002)
        ├─ FastAPI Instance 3 (port 8003)
        │
        └─► Redis Cache (optional)
```

---

## Future Enhancements

### Phase 4: Machine Learning Ranking
- User feedback collection
- ML model training on feedback
- Personalized recommendations

### Phase 5: Real-time Market Data
- Price update integration
- Availability checking
- Competitor pricing

### Phase 6: Advanced NLP
- Multi-language support
- Spelling correction
- Entity recognition

---

**See also:** [API.md](API.md) for endpoint specs, [README.md](README.md) for quick start
