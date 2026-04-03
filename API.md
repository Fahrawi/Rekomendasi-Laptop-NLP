# 📡 API Documentation

## Base URL
```
http://localhost:8000
```

---

## Endpoints Overview

| Method | Endpoint | Purpose | Status |
|--------|----------|---------|--------|
| POST | `/api/recommend-hybrid` | Hybrid recommendation (Phase 1+2) | ✅ Active |
| GET | `/recommend` | Legacy NLP recommendation | ⚠️ Working |
| GET | `/health` | Server health check | ✅ Active |
| GET | `/debug` | Data loading status | ✅ Active |
| GET | `/docs` | Swagger UI documentation | ✅ Active |

---

## 1. Hybrid Recommendation Endpoint ⭐ (RECOMMENDED)

### Endpoint
```
POST /api/recommend-hybrid
```

### Description
Combines Phase 1 (Smart Filtering + AHP Weighting) and Phase 2 (TOPSIS Ranking) for intelligent laptop recommendations.

**Workflow:**
```
Input → Phase 1 Filter → Phase 1 Weights → Phase 2 TOPSIS → JSON Response
```

### Request Schema

```json
{
  "intent": "string (required)",
  "budget_min": "integer (optional, IDR)",
  "budget_max": "integer (optional, IDR)",
  "ram_min": "integer (optional, GB)",
  "brand": "string (optional)",
  "games": ["string", "..."] (optional),
  "top_n": "integer (optional, default: 5, max: 10)"
}
```

### Parameters

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `intent` | string | ✅ YES | User's purpose/intent | `FIND_LAPTOP_FOR_GAME` |
| `budget_min` | integer | ❌ NO | Minimum budget (IDR) | `5000000` |
| `budget_max` | integer | ❌ NO | Maximum budget (IDR) | `20000000` |
| `ram_min` | integer | ❌ NO | Minimum RAM (GB) | `8` |
| `brand` | string | ❌ NO | Brand filter | `ASUS` |
| `games` | array | ❌ NO | Game list (for gaming) | `["HI3RD", "VALORANT"]` |
| `top_n` | integer | ❌ NO | Number of results (1-10) | `5` |

### Response Schema

```json
{
  "status": "string",
  "intent": "string",
  "filtered_count": "integer",
  "ranked_count": "integer",
  "weights_applied": "object",
  "recommendations": [
    {
      "rank": "integer",
      "brand": "string",
      "model": "string",
      "topsis_score": "float (0-1)",
      "specs": {
        "cpu_score": "float or null",
        "gpu_score": "float or null",
        "ram": "integer (GB)",
        "storage": "integer (GB)",
        "final_price": "integer (IDR)"
      },
      "reasoning": "string"
    }
  ],
  "message": "string"
}
```

### Supported Intents

```
FIND_LAPTOP_FOR_GAME              Gaming
FIND_LAPTOP_FOR_CONTENT_CREATION  3D/Video editing
AI_DEVELOPMENT                    AI/ML work
PROGRAMMING                       Software development
WEB_DEVELOPMENT                   Web development
SCIENTIFIC_COMPUTING              Scientific research
DAILY_USE                         General use
OFFICE_USE                        Office work
LIGHT_TASKS                       Budget-friendly
FIND_LAPTOP_GENERAL               General purpose
```

### Request Examples

#### Example 1: Gaming Laptop (Best GPU)
```bash
curl -X POST http://localhost:8000/api/recommend-hybrid \
  -H "Content-Type: application/json" \
  -d '{
    "intent": "FIND_LAPTOP_FOR_GAME",
    "budget_max": 20000000,
    "ram_min": 8,
    "games": ["HI3RD", "VALORANT"],
    "top_n": 5
  }'
```

#### Example 2: AI Development (High CPU/RAM)
```bash
curl -X POST http://localhost:8000/api/recommend-hybrid \
  -H "Content-Type: application/json" \
  -d '{
    "intent": "AI_DEVELOPMENT",
    "budget_max": 50000000,
    "ram_min": 32,
    "brand": "ASUS",
    "top_n": 5
  }'
```

#### Example 3: Budget Daily Use
```bash
curl -X POST http://localhost:8000/api/recommend-hybrid \
  -H "Content-Type: application/json" \
  -d '{
    "intent": "DAILY_USE",
    "budget_max": 8000000
  }'
```

#### Example 4: Content Creation
```bash
curl -X POST http://localhost:8000/api/recommend-hybrid \
  -H "Content-Type: application/json" \
  -d '{
    "intent": "FIND_LAPTOP_FOR_CONTENT_CREATION",
    "budget_max": 30000000,
    "ram_min": 16,
    "top_n": 5
  }'
```

### Response Examples

#### Success Response (200)
```json
{
  "status": "success",
  "intent": "FIND_LAPTOP_FOR_GAME",
  "filtered_count": 329,
  "ranked_count": 329,
  "weights_applied": {
    "CPU": 0.158,
    "GPU": 0.579,
    "RAM": 0.105,
    "Storage": 0.053,
    "Price": 0.105
  },
  "recommendations": [
    {
      "rank": 1,
      "brand": "MSI",
      "model": "Katana",
      "topsis_score": 0.8904,
      "specs": {
        "cpu_score": 20086.0,
        "gpu_score": 23392.0,
        "ram": 16,
        "storage": 512,
        "final_price": 17678760.0
      },
      "reasoning": "Rank #1: GPU excellent (skor 0.8904)."
    },
    {
      "rank": 2,
      "brand": "Lenovo",
      "model": "Legion",
      "topsis_score": 0.8873,
      "specs": {
        "cpu_score": 20856.0,
        "gpu_score": 23392.0,
        "ram": 16,
        "storage": 512,
        "final_price": 19474785.0
      },
      "reasoning": "Rank #2: GPU excellent (skor 0.8873)."
    }
  ],
  "message": "Berhasil merekomendasikan 5 laptop dari 329 laptop yang cocok."
}
```

#### No Results (200 with empty list)
```json
{
  "status": "success",
  "intent": "FIND_LAPTOP_FOR_GAME",
  "filtered_count": 0,
  "ranked_count": 0,
  "weights_applied": {},
  "recommendations": [],
  "message": "Tidak ada laptop yang sesuai dengan kriteria Anda."
}
```

#### Error: Invalid Intent (400)
```json
{
  "detail": "Intent tidak valid: INVALID_INTENT_NAME"
}
```

#### Error: Server Not Ready (503)
```json
{
  "detail": "Data belum siap untuk rekomendasi."
}
```

---

## 2. Legacy NLP Endpoint

### Endpoint
```
GET /recommend
```

### Parameters
```
?query=<user_query>&limit=<number>
```

### Example
```bash
curl "http://localhost:8000/recommend?query=mau main hi3rd dengan budget 20jt&limit=20"
```

**Note:** This endpoint uses natural language processing and may have different ranking logic than the hybrid endpoint.

---

## 3. Health Check

### Endpoint
```
GET /health
```

### Response
```json
{
  "status": "ok"
}
```

### Example
```bash
curl http://localhost:8000/health
```

---

## 4. Debug Endpoint

### Endpoint
```
GET /debug
```

### Response
```json
{
  "laptop_df_loaded": true,
  "min_req_df_loaded": true,
  "rec_req_df_loaded": true,
  "min_req_kb_size": 8472,
  "rec_req_kb_size": 8472,
  "laptop_list_size": 2160,
  "laptop_brand_list": ["ASUS", "MSI", "HP", ...],
  "unique_word_kb_size": 12345,
  "game_abbreviations_kb_size": 456,
  "game_alt_titles_kb_size": 789,
  "series_abbreviations_size": 123,
  "bigram_unique_kb_size": 4567,
  "series_games_size": 89,
  "brand_models_mapping_keys": ["ASUS", "MSI", ...]
}
```

### Example
```bash
curl http://localhost:8000/debug
```

---

## TOPSIS Score Interpretation

| Score Range | Meaning |
|-------------|---------|
| 0.85-1.00 | Excellent match - Highly recommended |
| 0.75-0.85 | Very good match - Recommended |
| 0.65-0.75 | Good match - Consider |
| 0.55-0.65 | Acceptable match - Possible option |
| <0.55 | Below average - Look for better options |

---

## Weight Explanation

### Gaming (FIND_LAPTOP_FOR_GAME)
```
GPU:     57.9%  ← Determines FPS & visual quality
CPU:     15.8%  ← Physics simulation, AI
RAM:     10.5%  ← 16GB already filtered minimum
Storage:  5.3%  ← 512GB SSD already filtered minimum
Price:   10.5%  ← Budget constraint
```

### AI Development (AI_DEVELOPMENT)
```
GPU:     40.0%  ← CUDA acceleration
CPU:     35.0%  ← Primary for training
RAM:     20.0%  ← Very important for datasets
Storage:  5.0%  ← Less critical
```

### Daily Use (DAILY_USE)
```
Price:   40.0%  ← Primary concern
CPU:     20.0%  ← Adequate performance
GPU:      5.0%  ← UI smoothness
RAM:     20.0%  ← Multitasking
Storage:  5.0%  ← Less critical
```

---

## Rate Limiting (Production)

Current deployment: No rate limiting

Recommended for production:
```
Max 10 requests per second per IP
Max 100 requests per minute per IP
```

---

## CORS Configuration

**Allowed Origins:**
```
http://localhost:3000
http://127.0.0.1:3000
```

**To add more origins**, edit `app.py` line 33:
```python
allow_origins=["http://localhost:3000", "http://yourdomain.com"],
```

---

## Error Codes

| Code | Message | Solution |
|------|---------|----------|
| 200 | Success | Request successful |
| 400 | Intent tidak valid | Check supported intents list |
| 400 | Invalid input | Verify request parameters |
| 503 | Data belum siap | Wait for server startup |
| 500 | Internal error | Check server logs |

---

## Response Time

| Operation | Time |
|-----------|------|
| Data loading (startup) | ~2 seconds |
| Phase 1 filtering | ~10-50ms |
| Phase 2 TOPSIS | ~50-200ms |
| Total response | ~100-300ms |

---

## Testing with Swagger UI

1. Open: http://localhost:8000/docs
2. Click "Try it out" on any endpoint
3. Fill in parameters
4. Click "Execute"

---

## Rate Limits & Quotas

**Current:** No limits (development mode)

**Recommended for production:**
- Max results per request: 10
- Max requests: 10/sec per IP
- Max batch processing: 100 laptops

---

## API Versioning

Current API version: **v1.0** (implicit in `/api/recommend-hybrid`)

Future versions would use:
- `/api/v2/recommend-hybrid`
- `/api/v1/recommend-hybrid` (current)

---

**Need help?** Check README.md or TROUBLESHOOTING.md
