# scripts/load_data.py
from pathlib import Path
import re
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'


def normalize_benchmark_key(text):
    if pd.isna(text):
        return ''
    normalized = str(text).lower().strip()
    normalized = re.sub(r'\([^\)]*\)', '', normalized)
    normalized = re.sub(r'[^a-z0-9]+', ' ', normalized)
    return re.sub(r'\s+', ' ', normalized).strip()


def make_benchmark_aliases(text):
    normalized = normalize_benchmark_key(text)
    aliases = {normalized}
    if not normalized:
        return aliases

    stripped = normalized
    for prefix in ['nvidia ', 'intel ', 'amd ', 'geforce ', 'radeon ']:
        if stripped.startswith(prefix):
            aliases.add(stripped[len(prefix):].strip())

    aliases.add(stripped.replace('geforce ', ''))
    aliases.add(stripped.replace('nvidia ', ''))
    aliases.add(stripped.replace('amd ', ''))
    aliases.add(stripped.replace('intel ', ''))
    return {alias for alias in aliases if alias}


def build_benchmark_lookup(df, model_col, score_col):
    lookup = {}
    for _, row in df.iterrows():
        model = row.get(model_col)
        score = row.get(score_col)
        if pd.isna(model) or pd.isna(score):
            continue
        try:
            score_val = float(score)
        except (TypeError, ValueError):
            continue
        for alias in make_benchmark_aliases(model):
            lookup.setdefault(alias, score_val)
    return lookup


def enrich_cpu_gpu_scores(df, cpu_lookup, gpu_lookup, keep_legacy=True):
    df = df.copy()
    if keep_legacy:
        if 'CPU_score' in df.columns and 'Legacy_CPU_score' not in df.columns:
            df['Legacy_CPU_score'] = df['CPU_score']
        if 'GPU_score' in df.columns and 'Legacy_GPU_score' not in df.columns:
            df['Legacy_GPU_score'] = df['GPU_score']

    if 'CPU' in df.columns:
        cpu_scores = []
        for cpu_name, old_score in zip(df['CPU'], df['CPU_score'] if 'CPU_score' in df.columns else [None] * len(df)):
            bench_score = None
            for alias in make_benchmark_aliases(cpu_name):
                if alias in cpu_lookup:
                    bench_score = cpu_lookup[alias]
                    break
            cpu_scores.append(bench_score if bench_score is not None else old_score)
        df['CPU_score'] = cpu_scores

    if 'GPU' in df.columns:
        gpu_scores = []
        for gpu_name, old_score in zip(df['GPU'], df['GPU_score'] if 'GPU_score' in df.columns else [None] * len(df)):
            bench_score = None
            for alias in make_benchmark_aliases(gpu_name):
                if alias in gpu_lookup:
                    bench_score = gpu_lookup[alias]
                    break
            gpu_scores.append(bench_score if bench_score is not None else old_score)
        df['GPU_score'] = gpu_scores

    return df


def enrich_requirement_scores(df, cpu_lookup, gpu_lookup):
    df = df.copy()

    cpu_columns = [
        ('CPU_Intel', 'CPU_Intel_score'),
        ('CPU_AMD', 'CPU_AMD_score'),
    ]
    gpu_columns = [
        ('GPU_NVIDIA', 'GPU_NVIDIA_score'),
        ('GPU_AMD', 'GPU_AMD_score'),
        ('GPU_Intel', 'GPU_Intel_score'),
    ]

    for name_col, score_col in cpu_columns:
        if name_col not in df.columns:
            continue
        new_scores = []
        for spec_name, old_score in zip(df[name_col], df[score_col] if score_col in df.columns else [None] * len(df)):
            bench_score = None
            for alias in make_benchmark_aliases(spec_name):
                if alias in cpu_lookup:
                    bench_score = cpu_lookup[alias]
                    break
            new_scores.append(bench_score if bench_score is not None else old_score)
        df[score_col] = new_scores

    for name_col, score_col in gpu_columns:
        if name_col not in df.columns:
            continue
        new_scores = []
        for spec_name, old_score in zip(df[name_col], df[score_col] if score_col in df.columns else [None] * len(df)):
            bench_score = None
            for alias in make_benchmark_aliases(spec_name):
                if alias in gpu_lookup:
                    bench_score = gpu_lookup[alias]
                    break
            new_scores.append(bench_score if bench_score is not None else old_score)
        df[score_col] = new_scores

    return df

def load_data():
    laptop_df = pd.read_csv(DATA_DIR / 'cleaned_dataset_v3.csv')
    min_req_df = pd.read_csv(DATA_DIR / 'minimum_requirements_processed.csv')
    rec_req_df = pd.read_csv(DATA_DIR / 'recommended_requirements_processed.csv')

    cpu_benchmark_df = pd.read_csv(DATA_DIR / 'cpu_benchmarks.csv')
    gpu_benchmark_df = pd.read_csv(DATA_DIR / 'gpu_benchmarks.csv')

    cpu_lookup = build_benchmark_lookup(cpu_benchmark_df, 'CPU Model', 'CPU Score')
    gpu_lookup = build_benchmark_lookup(gpu_benchmark_df, 'GPU Model', 'GPU Score')

    laptop_df = enrich_cpu_gpu_scores(laptop_df, cpu_lookup, gpu_lookup)
    min_req_df = enrich_requirement_scores(min_req_df, cpu_lookup, gpu_lookup)
    rec_req_df = enrich_requirement_scores(rec_req_df, cpu_lookup, gpu_lookup)

    return laptop_df, min_req_df, rec_req_df