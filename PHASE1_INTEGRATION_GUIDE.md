# Phase 1 Integration Guide
## Adding Smart Filters + Dynamic AHP to Existing app.py

---

## 🎯 Integration Plan

Struktur aplikasi tetap sama, kita hanya **menambahkan** Phase 1 ke dalam workflow yang sudah ada.

```
Existing app.py (FastAPI)
    ├─ Load data (scripts/)
    ├─ Build KB (scripts/)
    ├─ Initialize globals
    └─ Endpoints
        ├─ /recommend (existing NLP)
        └─ [NEW] /recommend-hybrid (Phase 1 + NLP)
        
+ Phase 1 (smart_filters_and_ahp.py)
    ├─ apply_smart_filters()
    └─ get_intent_based_weights()
```

---

## 📝 How to Add Phase 1 to app.py

### **Step 1: Add Import (Top of app.py)**

Add this line after existing imports (around line 25):

```python
from src.smart_filters_and_ahp import apply_smart_filters, get_intent_based_weights
```

**Location:** After line `from src.nlp_pipeline import nlp_pipeline_fuzzy`

---

### **Step 2: Create New Endpoint (Bottom of app.py)**

Add this new endpoint for hybrid recommendations:

```python
# ============================================================================
# NEW ENDPOINT - Phase 1 Integration: Hybrid Recommender (NLP + RBR + AHP)
# ============================================================================

@app.post("/recommend-hybrid")
async def recommend_hybrid(
    query: str = Query(..., description="User query in Indonesian"),
    limit: int = Query(5, description="Number of recommendations to return")
):
    """
    Hybrid Recommendation System
    
    Workflow:
    1. NLP Pipeline → Extract intent, budget, games, brand
    2. [NEW] RBR Filter → Filter laptops by intent specs
    3. [NEW] Get AHP Weights → Load dynamic weights
    4. [PHASE 2] TOPSIS → Rank and return Top-N
    
    Example query:
    - "butuh laptop asus buat main Cities Skylines, budget 20 juta"
    - "laptop untuk AI development, minimal 32GB RAM"
    - "office laptop murah, dibawah 12 juta"
    """
    try:
        # Step 1: NLP Pipeline (existing)
        print(f"\n📝 Query: {query}")
        
        pipeline_result = nlp_pipeline_fuzzy(
            query,
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
        
        found_games = pipeline_result['found_games']
        found_laptops = pipeline_result['found_laptops']
        extracted_budget = pipeline_result['budget']
        extracted_ram = pipeline_result['ram']
        
        print(f"   Games: {found_games}")
        print(f"   Brand: {found_laptops}")
        print(f"   Budget: Rp{extracted_budget:,.0f}" if extracted_budget else "   Budget: Not specified")
        print(f"   RAM: {extracted_ram}GB" if extracted_ram else "   RAM: Not specified")
        
        # Detect intent
        from src.recommender_system import recognize_intent_simple
        detected_intent = recognize_intent_simple(
            query,
            found_games,
            found_laptops,
            extracted_budget
        )
        print(f"   Intent: {detected_intent}")
        
        # ====================================================================
        # Step 2: [NEW] Phase 1 - Apply RBR Filter
        # ====================================================================
        print(f"\n🔍 Applying RBR Filter (Phase 1)...")
        
        filtered_df = apply_smart_filters(
            df=laptop_df,
            intent=detected_intent,
            budget=extracted_budget,
            ram=extracted_ram,
            brand=found_laptops[0] if found_laptops else None,
            game_list=found_games
        )
        
        if filtered_df.empty:
            return {
                "status": "no_results",
                "message": "Tidak ada laptop yang cocok dengan kriteria Anda",
                "query": query,
                "intent": detected_intent,
                "filters_applied": {
                    "budget": extracted_budget,
                    "ram": extracted_ram,
                    "games": found_games,
                    "brand": found_laptops
                }
            }
        
        # ====================================================================
        # Step 3: [NEW] Phase 1 - Get Dynamic AHP Weights
        # ====================================================================
        print(f"⚖️  Getting AHP Weights for intent '{detected_intent}'...")
        
        ahp_weights = get_intent_based_weights(detected_intent)
        
        # ====================================================================
        # Step 4: [PLACEHOLDER] TOPSIS Ranking (Phase 2)
        # ====================================================================
        # TODO: Implement TOPSIS ranking in Phase 2
        # For now, just return Top-N by price (simple ranking)
        
        print(f"📊 Preparing {min(limit, len(filtered_df))} recommendations...")
        
        sorted_df = filtered_df.sort_values('Final Price').head(limit)
        
        # Return response
        recommendations = []
        for idx, (_, row) in enumerate(sorted_df.iterrows(), 1):
            recommendations.append({
                "rank": idx,
                "brand": row.get('Brand', 'N/A'),
                "model": row.get('Model', 'N/A'),
                "price_idr": f"Rp{row.get('Final Price', 0):,.0f}",
                "specs": {
                    "ram_gb": int(row.get('RAM', 0)) if pd.notna(row.get('RAM')) else 0,
                    "cpu": row.get('CPU', 'N/A'),
                    "gpu": row.get('GPU', 'N/A'),
                    "storage_gb": int(row.get('Storage', 0)) if pd.notna(row.get('Storage')) else 0,
                }
            })
        
        return {
            "status": "success",
            "query": query,
            "intent": detected_intent,
            "nlp_extracted": {
                "games": found_games,
                "brand": found_laptops,
                "budget": extracted_budget,
                "ram": extracted_ram
            },
            "filtering": {
                "total_laptops": len(laptop_df),
                "after_filter": len(filtered_df),
                "returned": len(recommendations)
            },
            "ahp_weights": {
                "CPU": f"{ahp_weights['CPU']:.1%}",
                "GPU": f"{ahp_weights['GPU']:.1%}",
                "RAM": f"{ahp_weights['RAM']:.1%}",
                "Storage": f"{ahp_weights['Storage']:.1%}",
                "Price": f"{ahp_weights['Price']:.1%}"
            },
            "recommendations": recommendations,
            "note": "Phase 2 (TOPSIS ranking) coming soon - currently ranked by price"
        }
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print(traceback.format_exc())
        return {
            "status": "error",
            "error": str(e),
            "query": query
        }
```

---

## 🧪 Testing Phase 1 Integration

### **1. Start the server:**
```bash
cd "d:\projects\Sistem Rekomendasi laptop\Rekomendasi-Laptop-NLP"
uvicorn app:app --reload
```

### **2. Start HTTP server for frontend:**
```bash
python -m http.server 3000
```

### **3. Test with curl (new endpoint):**

#### Test Case 1: Gaming
```bash
curl "http://localhost:8000/recommend-hybrid?query=butuh%20laptop%20asus%20buat%20main%20Cities%20Skylines%20budget%2020%20juta"
```

#### Test Case 2: AI Development
```bash
curl "http://localhost:8000/recommend-hybrid?query=laptop%20untuk%20AI%20development%20minimal%2032GB%20RAM"
```

#### Test Case 3: Office/Budget
```bash
curl "http://localhost:8000/recommend-hybrid?query=office%20laptop%20murah%20dibawah%2012%20juta"
```

#### Test Case 4: 3D Design
```bash
curl "http://localhost:8000/recommend-hybrid?query=laptop%20untuk%203D%20rendering%20Blender%20budget%2030%20juta"
```

---

## 🔄 How It Works

```
User Query (POST /recommend-hybrid)
    ↓
Step 1: NLP Pipeline (existing)
    ├─ Tokenize & clean
    ├─ Extract intent
    ├─ Extract entities (games, brands, budget)
    └─ Output: intent, budget, games, brand
    ↓ [NEW Phase 1]
Step 2: apply_smart_filters()
    ├─ Read detected intent
    ├─ Apply RBR rules for that intent
    ├─ Filter by budget, RAM, GPU, CPU, Storage
    └─ Output: Filtered laptop dataframe (500 → 45 laptops)
    ↓ [NEW Phase 1]
Step 3: get_intent_based_weights()
    ├─ Map intent to optimal weights
    ├─ Get {CPU, GPU, RAM, Storage, Price} weights
    └─ Output: Weight dict (sum = 1.0)
    ↓ [PHASE 2 - TODO]
Step 4: TOPSIS Ranking (coming next)
    ├─ Normalize filtered data
    ├─ Apply AHP weights
    ├─ Calculate scores
    └─ Output: Top 5 ranked laptops
    ↓
Response (JSON)
    ├─ status, intent, filters applied
    ├─ NLP extracted data
    ├─ Filtering statistics
    ├─ AHP weights used
    └─ Top N recommendations
```

---

## 📊 Response Format

### Success Response:
```json
{
  "status": "success",
  "query": "butuh laptop asus buat main Cities Skylines budget 20 juta",
  "intent": "FIND_LAPTOP_FOR_GAME",
  "nlp_extracted": {
    "games": ["Cities Skylines"],
    "brand": ["Asus"],
    "budget": 20000000,
    "ram": null
  },
  "filtering": {
    "total_laptops": 500,
    "after_filter": 15,
    "returned": 5
  },
  "ahp_weights": {
    "CPU": "20.0%",
    "GPU": "40.0%",     ← Highest for gaming
    "RAM": "15.0%",
    "Storage": "10.0%",
    "Price": "15.0%"
  },
  "recommendations": [
    {
      "rank": 1,
      "brand": "Asus",
      "model": "ROG Strix G16",
      "price_idr": "Rp 18,999,000",
      "specs": {
        "ram_gb": 16,
        "cpu": "Intel Core i7-13700H",
        "gpu": "NVIDIA RTX 4070",
        "storage_gb": 512
      }
    },
    ...
  ],
  "note": "Phase 2 (TOPSIS ranking) coming soon"
}
```

### No Results Response:
```json
{
  "status": "no_results",
  "message": "Tidak ada laptop yang cocok dengan kriteria Anda",
  "query": "...",
  "intent": "...",
  "filters_applied": {...}
}
```

### Error Response:
```json
{
  "status": "error",
  "error": "Error message",
  "query": "..."
}
```

---

## 🔗 Testing with Browser

### **Access via HTTP Server (Port 3000):**

Navigate to: `http://localhost:3000/`

Add a simple HTML form to test:

```html
<form id="recommendForm">
  <input type="text" id="queryInput" placeholder="Masukkan query..." />
  <button onclick="sendRequest()">Dapatkan Rekomendasi</button>
  <pre id="result"></pre>
</form>

<script>
function sendRequest() {
  const query = document.getElementById('queryInput').value;
  const url = `http://localhost:8000/recommend-hybrid?query=${encodeURIComponent(query)}`;
  
  fetch(url)
    .then(r => r.json())
    .then(data => {
      document.getElementById('result').textContent = JSON.stringify(data, null, 2);
    })
    .catch(e => console.error(e));
}
</script>
```

---

## 🎯 Implementation Checklist

- [ ] Add import statement to app.py (line 25)
- [ ] Add new endpoint `/recommend-hybrid` to app.py
- [ ] Start uvicorn server
- [ ] Start HTTP server on port 3000
- [ ] Test endpoint with curl or browser
- [ ] Verify RBR filtering works correctly
- [ ] Verify AHP weights display correctly
- [ ] Verify NLP extraction works
- [ ] Check response format matches expectations

---

## 🚀 Next Phase

### Phase 2: TOPSIS Implementation

What will be added:
1. TOPSIS ranking algorithm
2. Replace price-based sorting with TOPSIS scores
3. Add confidence/match score
4. Add detailed explanation per recommendation

```python
# Will replace this (current):
sorted_df = filtered_df.sort_values('Final Price').head(limit)

# With this (Phase 2):
topsis_scores = calculate_topsis(filtered_df, ahp_weights)
sorted_df = filtered_df.iloc[topsis_scores.argsort()[::-1]].head(limit)
```

---

## 📚 Files Reference

| File | Purpose |
|------|---------|
| `app.py` | Main FastAPI app (add import + new endpoint) |
| `src/smart_filters_and_ahp.py` | Phase 1 functions (already created) |
| `tests/test_phase1_simple.py` | Phase 1 tests (already created) |

---

## 💡 Notes

- ✅ Phase 1 completely standalone - doesn't break existing endpoints
- ✅ Existing `/recommend` endpoint still works as before
- ✅ New `/recommend-hybrid` endpoint uses Phase 1 functions
- ✅ All data already in memory (laptop_df, etc.)
- ✅ Can deploy and test immediately
- ✅ Phase 2 (TOPSIS) will plug right in

---

## 🔍 Debugging Tips

### To see RBR filter output:
Look at console logs when running uvicorn - you'll see:
```
📋 Applying RBR Rules for intent: FIND_LAPTOP_FOR_GAME
   ✓ Budget filter: Rp 15,000,000 - Rp 30,000,000
   ✓ RAM filter: ≥ 8GB
   ✓ GPU filter: score ≥ 3
   ✓ GPU type filter: dedicated GPU required
   📊 Filtering Result: 15 / 500 laptops match criteria
```

### To check AHP weights:
Response JSON includes `ahp_weights` field showing the percentages used.

### To test RBR with different intents:
Change the query to match different intents:
- "buat gaming" → FIND_LAPTOP_FOR_GAME
- "untuk AI" → AI_DEVELOPMENT  
- "office" → WORKSTATION
- "video editing" → VIDEO_EDITOR

---

**Status:** Ready to implement ✅  
**Estimated Integration Time:** 5-10 minutes  
**Testing Time:** 10-15 minutes  
**Go Live:** Immediately after testing  

---

*Phase 1 is production-ready and waiting to be integrated into your existing FastAPI app!*
