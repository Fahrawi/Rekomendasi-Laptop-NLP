from src.nlp_pipeline import has_cheapest_preference

queries = [
    "Laptop untuk buat keria kantoran paling umum",
    "laptop untuk buat excel banyak tab 20 juta teringan",
    "Laptop untuk buat menjalankan comfy ui 20 juta terkencang",
]

for q in queries:
    result = has_cheapest_preference(q)
    print(f"{q!r}")
    print(f"  → prefer_cheapest: {result}\n")
