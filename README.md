# 📚 Laptop Recommendation System API
**Sistem Rekomendasi Laptop berbasis Phase-Based Hybrid Architecture (RBR → AHP → TOPSIS)**

---

## 🎯 Quick Start

### 1. Setup Environment
```bash
cd "d:\projects\Sistem Rekomendasi laptop\Rekomendasi-Laptop-NLP"
pip install -r requirements.txt
```

### 2. Start Servers
```bash
# Terminal 1: FastAPI Server (port 8000)
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: HTTP Server (port 3000)
python -m http.server 3000
```

### 3. Access Services
- 📡 **API**: http://localhost:8000
- 📚 **Docs**: http://localhost:8000/docs (Swagger UI)
- 🌐 **Frontend**: http://localhost:3000

---

## 🏗️ System Architecture

```
INPUT (User Query)
    ↓
[PHASE 1] Rule-Based Reasoning + AHP Weighting
    • apply_smart_filters() → Smart filtering based on intent & criteria
    • get_intent_based_weights() → Dynamic AHP weights per user intent
    ↓
[PHASE 2] TOPSIS Ranking Engine
    • run_topsis() → Multi-criteria ranking (0-1 score)
    • get_topsis_summary() → Top-N recommendations
    ↓
OUTPUT (JSON Response with Ranked Laptops)
```

### Core Modules
| Module | Purpose | Location |
|--------|---------|----------|
| **Phase 1: RBR + AHP** | Smart filtering & weighting | `src/smart_filters_and_ahp.py` |
| **Phase 2: TOPSIS** | Multi-criteria ranking | `src/topsis_engine.py` |
| **NLP Pipeline** | Intent & criteria extraction | `src/nlp_pipeline.py` |
| **FastAPI App** | REST API + endpoints | `app.py` |

---

## 📡 API Endpoints

### 1. **Hybrid Recommendation** (NEW - GPU-Optimized) ⭐
```
POST /api/recommend-hybrid
```

**Request:**
```json
{
  "intent": "FIND_LAPTOP_FOR_GAME",
  "budget_max": 20000000,
  "ram_min": 8,
  "brand": "ASUS",
  "games": ["HI3RD", "VALORANT"],
  "top_n": 5
}
```

**Response:**
```json
{
  "status": "success",
  "intent": "FIND_LAPTOP_FOR_GAME",
  "filtered_count": 329,
  "ranked_count": 329,
  "weights_applied": {
    "GPU": 0.58,
    "CPU": 0.16,
    "RAM": 0.11,
    "Price": 0.10
  },
  "recommendations": [
    {
      "rank": 1,
      "brand": "MSI",
      "model": "Katana",
      "topsis_score": 0.8904,
      "specs": {
        "gpu_score": 23392,
        "cpu_score": 20086,
        "ram": 16,
        "storage": 512,
        "final_price": 17678760
      },
      "reasoning": "Rank #1: GPU excellent (skor 0.8904)."
    }
  ],
  "message": "Berhasil merekomendasikan 5 laptop dari 329 laptop yang cocok."
}
```

### 2. **Legacy NLP Endpoint**
```
GET /recommend?query=mau main hi3rd dengan budget 20jt&limit=20
```

### 3. **Health Check**
```
GET /health
GET /debug
```

---

## 🎮 Supported Intents (10 types)

| Intent | GPU Weight | Focus | Best For |
|--------|-----------|-------|----------|
| `FIND_LAPTOP_FOR_GAME` | **58%** | GPU-first ranking | Gaming |
| `AI_DEVELOPMENT` | 40% | GPU+CPU+RAM balanced | ML/AI |
| `FIND_LAPTOP_FOR_CONTENT_CREATION` | 30% | CPU+GPU+RAM | Video/3D |
| `PROGRAMMING` | 20% | CPU-focused | Development |
| `DAILY_USE` | 5% | Price-focused | Budget use |
| `OFFICE_USE` | 5% | Price-focused | Office/Admin |
| `WEB_DEVELOPMENT` | 20% | CPU+RAM balanced | Web dev |
| `SCIENTIFIC_COMPUTING` | 20% | CPU+RAM focused | Research |
| `LIGHT_TASKS` | 5% | Budget-first | Budget PC |
| `FIND_LAPTOP_GENERAL` | 20% | Balanced | General use |

---

## 📊 Data Specifications

### Input CSV Files
- `data/cleaned_dataset_v3.csv` - 2,160 laptops with specs
- `data/minimum_requirements_processed.csv` - Game min requirements
- `data/recommended_requirements_processed.csv` - Game recommended specs

### DataFrame Columns
```
laptop_df: ['Brand', 'Model', 'CPU', 'GPU', 'RAM', 'Storage', 'Final Price', 
            'CPU_score', 'GPU_score', 'Storage type', ...]
```

---

## 🧪 Testing Commands

### Test Gaming Laptop (Best GPU Ranking)
```bash
curl -X POST http://localhost:8000/api/recommend-hybrid \
  -H "Content-Type: application/json" \
  -d "{
    \"intent\": \"FIND_LAPTOP_FOR_GAME\",
    \"budget_max\": 20000000,
    \"ram_min\": 8,
    \"games\": [\"HI3RD\"],
    \"top_n\": 5
  }"
```

**Expected Result:** RTX 3070 ranked above RTX 2060 ✅

### Test Budget Daily Use
```bash
curl -X POST http://localhost:8000/api/recommend-hybrid \
  -H "Content-Type: application/json" \
  -d "{
    \"intent\": \"DAILY_USE\",
    \"budget_max\": 8000000
  }"
```

### Access Swagger UI
```
http://localhost:8000/docs
```

---

## 🔧 Key Features

✅ **Phase 1: Smart Rule-Based Filtering**
- 10 intent-specific filter rules
- Dynamic minimum spec requirements
- Game compatibility checking
- Brand & budget filtering

✅ **Phase 1: Dynamic AHP Weighting**
- Context-aware criteria weighting
- Intent-specific prioritization
- Returns weights in response

✅ **Phase 2: TOPSIS Ranking**
- Multi-criteria decision making
- Normalized scores (0-1)
- Benefit vs Cost criteria handling
- Gaming-optimized criteria (excludes Storage)

✅ **Input Validation**
- Pydantic BaseModel validation
- Intent verification
- Budget range checking

✅ **Error Handling**
- HTTPException with status codes
- Graceful empty result handling
- Debug endpoint for troubleshooting

---

## 🐛 Recent Bug Fixes

### Issue: GPU Ranking Incorrect
**Problem:** RTX 3070 ranked below RTX 2060 in gaming recommendations
**Root Cause:** Weight mapping bug + Storage criterion overpowered GPU differences

**Fix Applied:**
1. ✅ Fixed TOPSIS weight mapping (GPU_score → GPU)
2. ✅ Increased GPU weight for gaming: 40% → 58%
3. ✅ Created gaming-specific criteria (excludes Storage)

**Result:** Best GPU laptops now correctly ranked in top 3 ✅

---

## 📂 Project Structure

```
Rekomendasi-Laptop-NLP/
├── app.py                          # FastAPI application
├── requirements.txt                # Python dependencies
├── README.md                       # This file
├── SETUP.md                        # Detailed setup guide
├── API.md                          # API documentation
├── ARCHITECTURE.md                 # System design
├── TROUBLESHOOTING.md              # Debug guide & fixes
│
├── src/
│   ├── smart_filters_and_ahp.py   # Phase 1: RBR + AHP
│   ├── topsis_engine.py           # Phase 2: TOPSIS
│   ├── nlp_pipeline.py            # NLP intent extraction
│   └── recommender_system.py      # Legacy system
│
├── scripts/
│   ├── load_data.py               # CSV loading
│   ├── build_kb.py                # Knowledge base building
│   └── ...other helper scripts
│
├── data/
│   ├── cleaned_dataset_v3.csv     # 2,160 laptops
│   ├── minimum_requirements_processed.csv
│   └── recommended_requirements_processed.csv
│
└── tests/
    ├── test_phase1.py             # Phase 1 tests (122/122 ✅)
    ├── test_phase2.py             # Phase 2 tests (26/26 ✅)
    └── test_integration.py        # End-to-end tests
```

---

## 🚀 Deployment

### Local Development
```bash
uvicorn app:app --reload
```

### Production
```bash
uvicorn app:app --workers 4 --host 0.0.0.0 --port 8000
```

### Docker (Optional)
```bash
docker build -t laptop-recommender .
docker run -p 8000:8000 laptop-recommender
```

---

## 📞 Support

### Documentation Files
- **Setup Issues?** → See `SETUP.md`
- **API Questions?** → See `API.md`
- **Architecture?** → See `ARCHITECTURE.md`
- **Bug Reports?** → See `TROUBLESHOOTING.md`

### Debug Commands
```bash
# Check data loading
curl http://localhost:8000/debug

# Check health
curl http://localhost:8000/health

# Run tests
pytest tests/test_phase1.py -v
pytest tests/test_phase2.py -v
```

---

## 📈 Performance

- **Response Time:** 100-300ms (typical)
- **Data Loading:** ~2 seconds at startup
- **Max Results:** 10 recommendations per request
- **Support:** 2,160 laptop models × 10 intents

---

## ✅ Status

- ✅ Phase 1 (RBR + AHP) - 122 tests passing
- ✅ Phase 2 (TOPSIS) - 26 tests passing
- ✅ Phase 3 (FastAPI) - Production ready
- ✅ GPU ranking fixed - Tested & verified
- ✅ Documentation consolidated

**Last Updated:** April 4, 2026
