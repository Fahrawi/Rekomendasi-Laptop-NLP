# 🔧 Setup & Installation Guide

## Prerequisites

- **Python:** 3.8 or higher
- **OS:** Windows, macOS, or Linux
- **RAM:** 4GB minimum (8GB recommended)
- **Disk:** 500MB free space

---

## Installation Steps

### Step 1: Clone/Setup Project
```bash
cd d:\projects\Sistem Rekomendasi laptop\Rekomendasi-Laptop-NLP
```

### Step 2: Create Virtual Environment (Optional but Recommended)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

**Required Packages:**
- fastapi - Web framework
- uvicorn - ASGI server
- pandas - Data processing
- numpy - Numerical computations
- scikit-learn - Machine learning utilities
- nltk - NLP processing
- Sastrawi - Indonesian stemmer
- fuzzywuzzy - String matching

### Step 4: Download NLP Data (First Run Only)
```bash
python -c "
import nltk
nltk.download('punkt')
nltk.download('averaged_perceptron_tagger')
"
```

### Step 5: Verify Setup
```bash
# Test imports
python -c "from src.smart_filters_and_ahp import apply_smart_filters; print('✅ Setup OK')"

# Check data files
ls data/*.csv
```

---

## Running the Application

### Option 1: Launch Both Servers (PowerShell)
```powershell
# Terminal 1: FastAPI
cd d:\projects\Sistem Rekomendasi laptop\Rekomendasi-Laptop-NLP
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: HTTP Server
cd d:\projects\Sistem Rekomendasi laptop\Rekomendasi-Laptop-NLP
python -m http.server 3000
```

### Option 2: Using Batch File
```bash
cd d:\projects\Sistem Rekomendasi laptop\Rekomendasi-Laptop-NLP
.\launch.bat
```

### Option 3: Single Server Only
```bash
# If you only need FastAPI
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

---

## Verify Installation

### Check Services
```bash
# Health Check
curl http://localhost:8000/health
# Expected: {"status": "ok"}

# Debug Info
curl http://localhost:8000/debug
# Expected: Data loading status

# Swagger UI
# Visit: http://localhost:8000/docs
```

### Test Hybrid Endpoint
```bash
curl -X POST http://localhost:8000/api/recommend-hybrid \
  -H "Content-Type: application/json" \
  -d "{\"intent\": \"FIND_LAPTOP_FOR_GAME\", \"budget_max\": 20000000}"
```

---

## Running Tests

### Run All Testssh
```bash
pytest tests/ -v
```

### Run Specific Test Suite
```bash
# Phase 1 Tests (RBR + AHP)
pytest tests/test_phase1.py -v

# Phase 2 Tests (TOPSIS)
pytest tests/test_phase2.py -v

# Show coverage
pytest tests/ --cov=src --cov-report=html
```

Expected Results:
- ✅ Phase 1: 122/122 tests passing
- ✅ Phase 2: 26/26 tests passing

---

## Configuration

### Port Configuration
Edit `app.py`, line 26:
```python
uvicorn app:app --port 8000  # Change 8000 to desired port
```

### HTTP Server Port
```bash
python -m http.server 3000  # Change 3000 to desired port
```

### CORS Origins
Edit `app.py`, line 33-36:
```python
allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
# Add more allowed origins as needed
```

---

## Data Setup

### Directory Structure
```
data/
├── cleaned_dataset_v3.csv              (2,160 laptops)
├── minimum_requirements_processed.csv  (Game specs)
└── recommended_requirements_processed.csv
```

### Data Format
All CSVs must have:
- UTF-8 encoding
- Comma delimiter (,)
- Header row

### Add New Data
```python
# In scripts/load_data.py - modify file paths if needed
laptop_df = pd.read_csv('../data/cleaned_dataset_v3.csv')
```

---

## Troubleshooting

### Issue: ModuleNotFoundError: No module named 'fastapi'
**Solution:** Run `pip install -r requirements.txt`

### Issue: Port 8000 already in use
**Solution:** 
```bash
# Windows: Find and kill process on port 8000
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Or use different port:
uvicorn app:app --port 8001
```

### Issue: Data files not found
**Solution:** Check current directory and ensure data/ folder exists
```bash
cd d:\projects\Sistem Rekomendasi laptop\Rekomendasi-Laptop-NLP
ls data/  # Should show .csv files
```

### Issue: NLTK data missing (first run)
**Solution:** Download required data:
```bash
python -c "import nltk; nltk.download('punkt'); nltk.download('averaged_perceptron_tagger')"
```

### Issue: Slow response on first request
**Solution:** Normal - data is being loaded into memory. Subsequent requests will be fast.

---

## Performance Optimization

### For Production
```bash
# Run with multiple workers
uvicorn app:app --workers 4 --host 0.0.0.0 --port 8000

# Use gunicorn (if available)
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app:app
```

### For Development
```bash
# Auto-reload on code changes
uvicorn app:app --reload

# Enable debug logging
# (Edit app.py to add logging configuration)
```

---

## Environment Variables

Optional - Create `.env` file:
```
PORT=8000
HOST=0.0.0.0
DEBUG=False
LOG_LEVEL=INFO
```

Load in app.py:
```python
from dotenv import load_dotenv
import os

load_dotenv()
PORT = os.getenv('PORT', 8000)
HOST = os.getenv('HOST', '0.0.0.0')
```

---

## Docker Setup (Optional)

### Create Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Build & Run
```bash
docker build -t laptop-recommender .
docker run -p 8000:8000 laptop-recommender
```

---

## Complete Setup Example (Windows)

```powershell
# 1. Navigate to project
cd d:\projects\Sistem Rekomendasi laptop\Rekomendasi-Laptop-NLP

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Download NLP data
python -c "import nltk; nltk.download('punkt')"

# 5. Run tests
pytest tests/ -v

# 6. Start FastAPI
uvicorn app:app --reload

# 7. Open in browser
# Visit: http://localhost:8000/docs
```

---

## Next Steps

✅ Setup complete!

**What to do next:**
1. Read `README.md` for quick start
2. Check `API.md` for endpoint documentation
3. Review `ARCHITECTURE.md` for system design
4. See `TROUBLESHOOTING.md` if issues arise

**Common Commands:**
```bash
# View logs
uvicorn app:app --reload --log-level debug

# Test single endpoint
curl http://localhost:8000/health

# Run full test suite
pytest tests/ -v --tb=short
```

---

**For help:** Check the main README.md or TROUBLESHOOTING.md
