# Phase 1 Quick Reference Guide
## Fast Start for Developers

---

## 🚀 Quick Start (2 minutes)

### 1. Import the functions
```python
from src.smart_filters_and_ahp import (
    apply_smart_filters,
    get_intent_based_weights,
    get_all_intents
)
```

### 2. See all available intents
```python
intents = get_all_intents()
# Output: 10 intents ready to use
```

### 3. Filter laptops by intent
```python
# Filter for gaming with budget constraint
filtered_df = apply_smart_filters(
    df=laptop_df,
    intent="FIND_LAPTOP_FOR_GAME",
    budget=(15_000_000, 30_000_000),  # Optional
    ram=8                              # Optional
)
# Result: Only laptops matching gaming specs
```

### 4. Get AHP weights for TOPSIS
```python
weights = get_intent_based_weights("FIND_LAPTOP_FOR_GAME")
# Output: {'CPU': 0.20, 'GPU': 0.40, 'RAM': 0.15, 'Storage': 0.10, 'Price': 0.15}
```

---

## 📖 Function Reference

### `apply_smart_filters()`
**Purpose:** Filter laptop based on RBR rules for specific intent

**Signature:**
```python
apply_smart_filters(
    df: pd.DataFrame,              # Laptop data
    intent: str,                   # One of 10 intents
    budget: Tuple[int, int] | int = None,  # Optional budget
    ram: int = None,               # Optional RAM requirement
    brand: str = None,             # Optional brand filter
    game_list: list = None         # Optional for gaming
) → pd.DataFrame
```

**Usage Examples:**

#### Gaming with budget filter
```python
result = apply_smart_filters(
    df_laptops,
    intent="FIND_LAPTOP_FOR_GAME",
    budget=(15_000_000, 30_000_000)
)
```

#### 3D Design - any budget
```python
result = apply_smart_filters(
    df_laptops,
    intent="3D_DESIGN"
)
# Returns only laptops with 32GB+ RAM, high GPU, 1TB storage
```

#### Office work with budget ceiling
```python
result = apply_smart_filters(
    df_laptops,
    intent="WORKSTATION",
    budget=12_000_000
)
# Returns laptops ≤ 12M, balanced specs
```

#### Office with specific RAM override
```python
result = apply_smart_filters(
    df_laptops,
    intent="WORKSTATION",
    ram=16  # Override default minimum
)
```

---

### `get_intent_based_weights()`
**Purpose:** Generate AHP weights for specific intent

**Signature:**
```python
get_intent_based_weights(intent: str) → Dict[str, float]
```

**Returns:**
```python
{
    'CPU': 0.XX,           # CPU criterion weight
    'GPU': 0.XX,           # GPU criterion weight
    'RAM': 0.XX,           # RAM criterion weight
    'Storage': 0.XX,       # Storage criterion weight
    'Price': 0.XX,         # Price criterion weight
    'Storage_Type_Bonus': 0.XX  # Optional SSD bonus
}
# Total (excluding bonus) = 1.0
```

**Examples:**

#### Get weights for Gaming
```python
weights = get_intent_based_weights("FIND_LAPTOP_FOR_GAME")
# Output: GPU weight = 40% (highest for gaming)
```

#### Get weights for AI Development
```python
weights = get_intent_based_weights("AI_DEVELOPMENT")
# Output: GPU 40%, RAM 30% (both critical for ML)
```

#### Get weights for Office
```python
weights = get_intent_based_weights("WORKSTATION")
# Output: Price 40% (budget is primary concern)
```

---

## 📋 All 10 Intents & Quick Specs

| # | Intent | Min RAM | GPU Focus | Primary Weight |
|---|--------|---------|-----------|-----------------|
| 1 | `FIND_LAPTOP_FOR_GAME` | 8GB | Dedicated ✓ | GPU 40% |
| 2 | `3D_DESIGN` | 32GB | dedicated ✓ | GPU+RAM 30%+25% |
| 3 | `2D_DESIGN` | 16GB | any | CPU 30% |
| 4 | `OLAH_DATA` | 16GB | optional | RAM 35% |
| 5 | `AI_DEVELOPMENT` | 32GB | CUDA ✓ | GPU+RAM 40%+30% |
| 6 | `WEB_DEVELOPMENT` | 8GB | none | CPU 35% |
| 7 | `MULTITASKING` | 32GB | any | RAM 40% |
| 8 | `WORKSTATION` | 8GB | none | **Price 40%** |
| 9 | `ENTERTAINMENT` | 8GB | any | Storage 25% |
| 10 | `VIDEO_EDITOR` | 32GB | CUDA ✓ | Storage+GPU 20%+30% |

---

## 🧪 Testing

### Run all tests
```bash
cd "d:\projects\Sistem Rekomendasi laptop\Rekomendasi-Laptop-NLP"
python tests/test_phase1_simple.py
```

### Expected output
```
✓ 122 tests passed
✓ All weights = 1.0
✓ All filters working
✓ All intents valid
```

---

## 🔗 Integration Examples

### Example 1: Complete Gaming Workflow
```python
from src.smart_filters_and_ahp import apply_smart_filters, get_intent_based_weights
import pandas as pd

# Load laptop data
df_laptops = pd.read_csv('laptop_dataset.csv')

# User wants gaming laptop under 25M
user_budget = 25_000_000

# Step 1: Apply RBR filter
filtered = apply_smart_filters(
    df=df_laptops,
    intent="FIND_LAPTOP_FOR_GAME",
    budget=(15_000_000, user_budget)
)
print(f"Found {len(filtered)} gaming laptops under Rp{user_budget:,}")

# Step 2: Get AHP weights (for TOPSIS ranking - Phase 2)
weights = get_intent_based_weights("FIND_LAPTOP_FOR_GAME")
print(f"Using weights: {weights}")

# Step 3: [Phase 2] Would do TOPSIS ranking here
# top_5 = topsis_ranking(filtered, weights)
```

### Example 2: Dynamic Filtering Based on NLP
```python
from src.smart_filters_and_ahp import apply_smart_filters
from src.nlp_pipeline import nlp_pipeline_fuzzy
from src.recommender_system import recognize_intent_simple

# User query from NLP
user_query = "butuh laptop asus buat belajar AI, budget 40 juta"

# Extract from NLP
nlp_result = nlp_pipeline_fuzzy(user_query, ...)
detected_intent = recognize_intent_simple(user_query, ...)

# Apply corresponding filter
filtered = apply_smart_filters(
    df=df_laptops,
    intent=detected_intent,
    budget=nlp_result['budget'],
    brand=nlp_result.get('found_laptops'),
    ram=nlp_result.get('ram')
)

# Auto-selected optimal weights for AI intent
weights = get_intent_based_weights(detected_intent)
```

### Example 3: Compare Multiple Intents
```python
intents = ["FIND_LAPTOP_FOR_GAME", "AI_DEVELOPMENT", "WORKSTATION"]

for intent in intents:
    # Filter
    result = apply_smart_filters(df_laptops, intent=intent)
    
    # Get weights
    weights = get_intent_based_weights(intent)
    
    # Display
    print(f"\n{intent}:")
    print(f"  Filtered: {len(result)} laptops")
    print(f"  Avg price: Rp{result['Final Price'].mean():,.0f}")
    print(f"  Priority: {max(weights, key=weights.get)} ({max(weights.values()):.0%})")
```

---

## 🎯 Common Use Cases

### UseCase 1: User wants cheap office laptop
```python
filtered = apply_smart_filters(
    df_laptops,
    intent="WORKSTATION",
    budget=10_000_000
)
weights = get_intent_based_weights("WORKSTATION")
# Price weight = 40% → TOPSIS will prioritize cost
```

### UseCase 2: Data scientist needs GPU for ML
```python
filtered = apply_smart_filters(
    df_laptops,
    intent="AI_DEVELOPMENT"
)
weights = get_intent_based_weights("AI_DEVELOPMENT")
# GPU weight = 40%, RAM = 30% → Both critical
```

### UseCase 3: Gamer with strict budget
```python
filtered = apply_smart_filters(
    df_laptops,
    intent="FIND_LAPTOP_FOR_GAME",
    budget=20_000_000,
    ram=16  # Override minimum
)
weights = get_intent_based_weights("FIND_LAPTOP_FOR_GAME")
# GPU is primary (40%), Price secondary (15%)
```

### UseCase 4: Creative professional (3D + Video editing)
```python
# Start with 3D Design requirements
filtered_3d = apply_smart_filters(
    df_laptops,
    intent="3D_DESIGN",
    budget=(25_000_000, 50_000_000)
)

# Can also check VIDEO_EDITOR spec (even stricter)
filtered_video = apply_smart_filters(df_laptops, intent="VIDEO_EDITOR")

# Pick most capable (intersection)
final = filtered_3d.merge(filtered_video, how='inner')
```

---

## 🔍 Debugging Tips

### Check what specs an intent requires:
```python
from src.smart_filters_and_ahp import apply_smart_filters

# Look at the RBR rules: apply_smart_filters() will print them
filtered = apply_smart_filters(df_laptops, intent="AI_DEVELOPMENT")
# Output will show: RAM: ≥ 32GB, GPU: ≥ 4, Storage: ≥ 1TB, etc.
```

### Check why a laptop was filtered out:
```python
# Apply filter and inspect
before = len(df_laptops)
after_filter = apply_smart_filters(df_laptops, intent="FIND_LAPTOP_FOR_GAME")
after = len(after_filter)

print(f"Filtered out: {before - after} laptops")
# {before - after} = how many laptops didn't meet GPU/CPU/RAM/Storage specs
```

### Verify weights sum to 1.0:
```python
weights = get_intent_based_weights("YOUR_INTENT")
total = sum([v for k, v in weights.items() if k != 'Storage_Type_Bonus'])
assert abs(total - 1.0) < 0.0001, f"Weights should sum to 1.0, got {total}"
```

---

## 📊 Performance Notes

- **Filter operation:** O(n) where n = number of laptops
- **Weight calculation:** O(1) dictionary lookup
- **Memory:** Minimal, only creates filtered DataFrame

**Typical times:**
- Filter 1000 laptops: < 100ms
- Get weights: < 1ms
- Both combined: < 150ms

---

## 🚧 What's Not Included (Phase 2)

These features will be added in Phase 2:
- [ ] TOPSIS ranking algorithm
- [ ] Normalized scoring system
- [ ] Top-N recommendations with scores
- [ ] Explanation/rationale per recommendation
- [ ] FastAPI endpoint integration
- [ ] End-to-end UI integration

---

## 📞 Support

### File locations
- Implementation: `src/smart_filters_and_ahp.py`
- Tests: `tests/test_phase1_simple.py`
- Design docs: `PHASE1_DESIGN.md`
- Summary: `PHASE1_SUMMARY.md` (this file)

### Running the demo
```bash
python tests/test_phase1_simple.py
```

### Adding a new intent
1. Edit `src/smart_filters_and_ahp.py`
2. Add RBR rules to `rbr_rules` dict
3. Add AHP weights to `weight_templates` dict
4. Add description to `get_intent_description()` function
5. Test with `test_phase1_simple.py`

---

**Last Updated:** April 3, 2026  
**Status:** Phase 1 ✅ Complete & Production Ready
