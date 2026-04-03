# 🔧 Troubleshooting Guide

## Quick Diagnosis

**Endpoint not responding?**
```bash
# Check if server is running
curl http://localhost:8000/health

# Check data status
curl http://localhost:8000/debug
```

**Getting recommendations but they're wrong?**
- See: [GPU Ranking Issues](#gpu-ranking-issues)
- See: [Weight Mapping Problems](#weight-mapping-problems)

**Performance problems?**
- See: [Performance Optimization](#performance-optimization)

---

## Common Issues & Solutions

### 1. Server Not Starting

#### Problem: `Address already in use: ('0.0.0.0', 8000)`

**Cause:** Port 8000 already in use (previous server still running)

**Solutions:**

Option 1: Kill existing process
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac
lsof -i :8000
kill -9 <PID>
```

Option 2: Use different port
```bash
uvicorn app:app --host 0.0.0.0 --port 8001
```

Option 3: Use provided launcher
```bash
python launch.bat  # Auto handles port conflicts
```

---

#### Problem: `ModuleNotFoundError: No module named 'fastapi'`

**Cause:** Dependencies not installed

**Solutions:**

```bash
# Install requirements
pip install -r requirements.txt

# Or install specific packages
pip install fastapi uvicorn pandas numpy scikit-learn

# Verify installation
python -c "import fastapi; print(fastapi.__version__)"
```

---

#### Problem: `FileNotFoundError: 'data/laptop_specs.csv'`

**Cause:** Data files missing or in wrong location

**Solutions:**

```bash
# Check data directory exists
ls data/

# Should show:
# laptop_specs.csv
# minimum_requirements.csv
# recommended_requirements.csv

# If missing, verify structure:
# Project Root/
# ├── app.py
# ├── data/
# │   ├── laptop_specs.csv
# │   ├── minimum_requirements.csv
# │   └── recommended_requirements.csv
# ├── src/
# │   ├── smart_filters_and_ahp.py
# │   ├── topsis_engine.py
# │   └── nlp_pipeline.py
```

---

### 2. Data Loading Issues

#### Problem: `Data belum siap untuk rekomendasi` (503 error)

**Cause:** Server still loading data on startup

**Solution:** Wait 5-10 seconds for startup

```bash
# Monitor startup
# You should see:
# ✅ Semua data dan KB berhasil dimuat
# ✅ Aplikasi siap

# Then test:
curl http://localhost:8000/health  # Should return {"status": "ok"}
```

---

#### Problem: CSVs loading but incomplete data

**Cause:** File encoding or format issues

**Solutions:**

```bash
# Check CSV format
head data/laptop_specs.csv

# Should show column headers:
# Brand,Model,CPU_score,GPU_score,RAM,Storage,Final_Price

# Verify no empty rows
wc -l data/laptop_specs.csv  # Should show 2161 lines (2160 data + 1 header)

# Check encoding (should be UTF-8)
file data/laptop_specs.csv
```

**If still broken, reload data:**
```bash
# Delete corrupted data and restore
rm data/*.csv
# Restore from backup or re-download from source
```

---

### 3. API Request Issues

#### Problem: `400 Bad Request - Intent tidak valid`

**Cause:** Intent not in supported list

**Solution:** Use valid intent

```python
VALID_INTENTS = [
    "FIND_LAPTOP_FOR_GAME",
    "FIND_LAPTOP_FOR_CONTENT_CREATION",
    "AI_DEVELOPMENT",
    "PROGRAMMING",
    "WEB_DEVELOPMENT",
    "SCIENTIFIC_COMPUTING",
    "DAILY_USE",
    "OFFICE_USE",
    "LIGHT_TASKS",
    "FIND_LAPTOP_GENERAL"
]

# ✅ Correct
curl -X POST http://localhost:8000/api/recommend-hybrid \
  -H "Content-Type: application/json" \
  -d '{"intent": "FIND_LAPTOP_FOR_GAME"}'

# ❌ Wrong
curl -X POST http://localhost:8000/api/recommend-hybrid \
  -H "Content-Type: application/json" \
  -d '{"intent": "GAMING"}'  # Not in list
```

---

#### Problem: `400 Bad Request - Invalid JSON`

**Cause:** Malformed JSON in request

**Solutions:**

```bash
# Check JSON syntax
python -m json.tool << 'EOF'
{
  "intent": "FIND_LAPTOP_FOR_GAME",
  "budget_max": 20000000
}
EOF
# Should output without errors

# Common mistakes:
❌ Single quotes: {"intent": 'FIND_LAPTOP_FOR_GAME'}
✅ Double quotes: {"intent": "FIND_LAPTOP_FOR_GAME"}

❌ Unquoted keys: {intent: "FIND_LAPTOP_FOR_GAME"}
✅ Quoted keys: {"intent": "FIND_LAPTOP_FOR_GAME"}

❌ Trailing comma: {"intent": "FIND_LAPTOP_FOR_GAME",}
✅ No trailing comma: {"intent": "FIND_LAPTOP_FOR_GAME"}
```

---

#### Problem: `Empty recommendations` returned

**Cause:** No laptops match filter criteria

**Solutions:**

```bash
# Check filter constraints
# Too strict combination?

❌ Unrealistic:
{
  "intent": "GAMING",
  "budget_max": 5000000,      # Too low for gaming laptop
  "ram_min": 64,               # Extremely high
  "brand": "RARE_BRAND"
}

✅ Realistic:
{
  "intent": "FIND_LAPTOP_FOR_GAME",
  "budget_max": 20000000,      # 20 million IDR is reasonable
  "ram_min": 8,                # Standard minimum
  "games": ["HI3RD"]
}

# Debug: Check available ranges
curl http://localhost:8000/debug
# Look at laptop stats
```

---

### 4. GPU Ranking Issues

#### Problem: "Better GPU laptop ranked lower than worse GPU laptop"

**Cause (Already Fixed):** Three bugs identified and fixed:

1. **TOPSIS Weight Mapping Bug** (src/topsis_engine.py)
   - ❌ Old: Tried to use 'GPU_score' as key directly
   - ✅ Fixed: Added `map_criteria_to_weight_key()` function
   
2. **Storage Overpowering GPU** (TOPSIS algorithm)
   - ❌ Old: 1000GB vs 512GB storage dominated over GPU differences
   - ✅ Fixed: Gaming-specific criteria excludes low-relevance factors

3. **Gaming Weights Suboptimal** (src/smart_filters_and_ahp.py)
   - ❌ Old: GPU weight only 0.40 (40% of scoring)
   - ✅ Fixed: GPU weight now 0.55, normalized to 57.9%

**Verification:**
```bash
# Test Hi3rd query to verify GPU ranking
python test_direct_hybrid.py

# Expected output:
# Rank 1: MSI Katana - GPU 23392 (score 0.8904)
# Rank 2: Lenovo Legion - GPU 23392 (score 0.8873)
# Rank 3: HP Omen - GPU 23392 (score 0.8863)
# ✅ Higher GPU scores ranked higher
```

**If still seeing issues:**

1. Check Phase 1 weights applied correctly:
```python
# In app.py, after Phase 1:
print(f"Weights applied: {weights}")
# Should show GPU weight highest for gaming
```

2. Check Phase 2 normalization:
```python
# In topsis_engine.py, debug output:
print(f"GPU weight applied to criteria: {weighted_matrix['GPU']}")
# Should use correct weight key 'GPU', not 'GPU_score'
```

---

### 5. Weight Mapping Problems

#### Problem: `KeyError: Column name not in weights`

**Example Error:**
```
KeyError: 'GPU_score' not found in weights keys
```

**Cause:** Column name ≠ weight key

**Solution:** Use `map_criteria_to_weight_key()` function

```python
# File: src/topsis_engine.py

def map_criteria_to_weight_key(column_name: str):
    """Maps DataFrame column names to weight dict keys"""
    mapping = {
        'CPU_score': 'CPU',      # Column CPU_score → weight key CPU
        'GPU_score': 'GPU',      # Column GPU_score → weight key GPU
        'Final Price': 'Price',  # Column Final Price → weight key Price
        'RAM': 'RAM',
        'Storage': 'Storage'
    }
    return mapping.get(column_name, column_name)

# Usage in TOPSIS:
for col in criteria_columns:
    weight_key = map_criteria_to_weight_key(col)  # ✅ Always map!
    weighted[col] = normalized[col] * weights[weight_key]
```

---

### 6. Performance Issues

#### Problem: `Response takes >2 seconds`

**Cause:** Data still loading or large dataset processed

**Analysis:**

```bash
# Measure response time
time curl -X POST http://localhost:8000/api/recommend-hybrid \
  -H "Content-Type: application/json" \
  -d '{"intent": "FIND_LAPTOP_FOR_GAME"}'

# Typical times:
# <300ms: Excellent
# 300-500ms: Good
# 500-1000ms: Acceptable (many results)
# >1000ms: Slow (investigate)
```

#### Performance Optimization

**1. Reduce top_n:**
```json
{
  "intent": "FIND_LAPTOP_FOR_GAME",
  "top_n": 3          // Instead of 5, only get top 3
}
```

**2. Add stricter filters:**
```json
{
  "intent": "FIND_LAPTOP_FOR_GAME",
  "budget_min": 15000000,  // Narrows search space
  "brand": "ASUS"          // Pre-filter by brand
}
```

**3. Enable caching (production):**
```python
# In app.py
from functools import lru_cache

@lru_cache(maxsize=100)  # Cache last 100 queries
async def cached_recommend(intent, budget_max, ...):
    # Implementation
```

**4. Use indexing (future):**
```python
# For large datasets, create indices
laptop_df.set_index('GPU_score', inplace=True)
laptop_df.set_index('Price', inplace=True)
# Speeds up filtering
```

---

### 7. CORS Issues

#### Problem: Browser shows `CORS error` when calling from frontend

**Error Message:**
```
Access to XMLHttpRequest at 'http://localhost:8000/api/recommend-hybrid' 
from origin 'http://localhost:3000' has been blocked by CORS policy
```

**Cause:** Frontend (port 3000) can't access backend (port 8000)

**Solution:** Configure CORS in app.py

```python
# Current configuration allows localhost:3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],     # ✅ Allowed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# To add more origins:
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8080",
        "https://yourdomain.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Restart server after change
uvicorn app:app --reload
```

---

### 8. Testing Failures

#### Problem: `test_direct_hybrid.py` fails with assertion error

```
AssertionError: GPU rank should be 0.8904 but got 0.7896
```

**Cause:** Changes to weights without updating test expectations

**Solution:**

```bash
# Option 1: Update test with new expected values
# Edit test_direct_hybrid.py with new TOPSIS scores

# Option 2: Regenerate baseline
python test_direct_hybrid.py > expected_output.txt
# Compare with current output to verify correctness

# Option 3: Run all tests
pytest tests/ -v
# Shows which tests fail and why
```

---

### 9. Database/CSV Issues

#### Problem: Duplicate laptop entries causing wrong ranks

**Symptom:** Same laptop appears multiple times in results

**Cause:** CSV contains duplicates

**Solution:**

```bash
# Check for duplicates
python -c "
import pandas as pd
df = pd.read_csv('data/laptop_specs.csv')
duplicates = df[df.duplicated(subset=['Brand', 'Model'])]
print(f'Found {len(duplicates)} duplicates')
print(duplicates)
"

# Remove duplicates if found
python -c "
import pandas as pd
df = pd.read_csv('data/laptop_specs.csv')
df_clean = df.drop_duplicates(subset=['Brand', 'Model'])
df_clean.to_csv('data/laptop_specs.csv', index=False)
print(f'Removed {len(df) - len(df_clean)} duplicates')
"
```

---

### 10. Legacy Endpoint Issues

#### Problem: `/recommend` endpoint returns different results than `/api/recommend-hybrid`

**Cause:** Different algorithms (NLP vs Hybrid)

**Explanation:**
```
/recommend (Old):
  - Uses NLP to interpret query
  - Legacy recommendation algorithm
  - May have different ranking logic

/api/recommend-hybrid (New):
  - Structured input (no NLP needed)
  - Phase 1 + Phase 2 algorithm
  - More predictable rankings
```

**Solution:** Use `/api/recommend-hybrid` for better results

```bash
# ❌ Old (unpredictable)
curl "http://localhost:8000/recommend?query=mau main hi3rd&limit=20"

# ✅ New (recommended)
curl -X POST http://localhost:8000/api/recommend-hybrid \
  -H "Content-Type: application/json" \
  -d '{
    "intent": "FIND_LAPTOP_FOR_GAME",
    "games": ["HI3RD"],
    "budget_max": 20000000,
    "top_n": 5
  }'
```

---

## Debug Mode

### Enable Debug Logging

```python
# In app.py, add at top:
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Then add debug prints:
@app.post("/api/recommend-hybrid")
async def recommend(request: RecommendationRequest):
    logger.debug(f"Request received: {request}")
    logger.debug(f"Phase 1 filtering...")
    filtered = apply_smart_filters(...)
    logger.debug(f"Filtered count: {len(filtered)}")
    logger.debug(f"Phase 1 weights: {weights}")
    ...
```

### Check System Status

```bash
# Full debug info
curl http://localhost:8000/debug

# Output includes:
{
  "laptop_df_loaded": true,
  "min_req_df_loaded": true,
  "rec_req_df_loaded": true,
  "laptop_list_size": 2160,
  "unique_word_kb_size": 12345,
  "game_abbreviations_kb_size": 456,
  ...
}

# Interpretation:
# - All _loaded fields should be true
# - laptop_list_size should be ~2160
# - All KB sizes >0
```

### Test Real Data Flow

```bash
# 1. Test health
curl http://localhost:8000/health
# Should return {"status": "ok"}

# 2. Test with minimal request
curl -X POST http://localhost:8000/api/recommend-hybrid \
  -H "Content-Type: application/json" \
  -d '{"intent": "DAILY_USE"}'
# Should return ≥5 laptops

# 3. Test with filters
curl -X POST http://localhost:8000/api/recommend-hybrid \
  -H "Content-Type: application/json" \
  -d '{
    "intent": "DAILY_USE",
    "budget_max": 10000000,
    "ram_min": 8
  }'
# Fewer results expected

# 4. Test for specific issue
curl -X POST http://localhost:8000/api/recommend-hybrid \
  -H "Content-Type: application/json" \
  -d '{
    "intent": "FIND_LAPTOP_FOR_GAME",
    "games": ["HI3RD"],
    "budget_max": 20000000,
    "top_n": 5
  }'
# Should show RTX 3070 in top 3
```

---

## Logging Inspection

### View Server Logs

```bash
# If running with Console output:
# Logs appear directly in terminal

# If running with file logging:
tail -f logs/app.log

# Search for errors:
grep "ERROR" logs/app.log
grep "WARNING" logs/app.log

# Check startup messages:
grep "✅" logs/app.log  # Success markers
grep "❌" logs/app.log  # Errors
```

---

## Performance Profiling

### Measure Phase 1 Time

```python
import time
from src.smart_filters_and_ahp import apply_smart_filters, get_intent_based_weights

start = time.time()
filtered = apply_smart_filters(laptop_df, {"budget_max": 20000000})
end = time.time()
print(f"Phase 1 filtering: {(end-start)*1000:.2f}ms")
# Typical: 10-50ms

start = time.time()
weights = get_intent_based_weights("FIND_LAPTOP_FOR_GAME")
end = time.time()
print(f"Phase 1 AHP: {(end-start)*1000:.2f}ms")
# Typical: <1ms
```

### Measure Phase 2 Time

```python
import time
from src.topsis_engine import run_topsis

start = time.time()
results = run_topsis(filtered, weights, top_n=5)
end = time.time()
print(f"Phase 2 TOPSIS: {(end-start)*1000:.2f}ms")
# Typical: 50-200ms
```

### Profile Memory Usage

```bash
# Install memory profiler
pip install memory-profiler

# Run with memory tracking
python -m memory_profiler app.py

# Shows memory usage by line
```

---

## Rollback & Reset

### Reset to Known Good State

```bash
# 1. Stop server
# Press Ctrl+C in terminal

# 2. Check git status
git status

# 3. Reset changes if needed
git checkout -- .

# 4. Clear any caches
rm -rf __pycache__ .pytest_cache

# 5. Reinstall dependencies
pip install --upgrade -r requirements.txt

# 6. Restart server
python launch.bat
```

---

## Getting Help

### Information to Include in Bug Report

```
1. Python version:
   python --version

2. OS:
   Windows / Linux / Mac

3. Server status:
   curl http://localhost:8000/debug

4. Full request that failed:
   {json request body}

5. Full error message:
   {complete error output}

6. Steps to reproduce:
   1. ...
   2. ...

7. Screenshots (if applicable):
   - Server startup log
   - API response
   - Browser console error
```

### Support Resources

- **Code:** See [ARCHITECTURE.md](ARCHITECTURE.md)
- **API Docs:** See [API.md](API.md)
- **Setup:** See [SETUP.md](SETUP.md)
- **Quick Start:** See [README.md](README.md)

---

**Last Updated:** 2024  
**For questions:** Check documentation files above
