# src/nlp_pipeline.py
import re
import string
from collections import defaultdict
from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory
from nltk.tokenize import RegexpTokenizer
from difflib import SequenceMatcher

# Roman numeral conversion utilities
ROMAN_PATTERN = r'\b(m{0,4}(?:cm|cd|d?c{0,3})(?:xc|xl|l?x{0,3})(?:ix|iv|v?i{0,3}))\b'
roman_numeral_pattern = re.compile(ROMAN_PATTERN, re.IGNORECASE)

def is_roman_numeral(s):
    return bool(roman_numeral_pattern.fullmatch(s))

def roman_to_int(roman):
    roman_numerals = {
        'i': 1, 'v': 5, 'x': 10, 'l': 50,
        'c': 100, 'd': 500, 'm': 1000
    }
    total = 0
    prev_value = 0
    for char in reversed(roman.lower()):
        value = roman_numerals[char]
        if value < prev_value:
            total -= value
        else:
            total += value
        prev_value = value
    return str(total)

def norm_digits_set(s):
    digits = set()
    digit_matches = re.findall(r'\d+', s)
    digits.update(digit_matches)
    tokens = s.split()
    for token in tokens:
        clean_token = re.sub(r'[^a-zA-Z]', '', token)
        if is_roman_numeral(clean_token):
            digits.add(roman_to_int(clean_token))
    return digits

def tokenize_with_span(text):
    pattern = re.compile(r'\w+')
    tokens = []
    for match in pattern.finditer(text):
        token = match.group()
        start = match.start()
        end = match.end()
        tokens.append((token, start, end))
    return tokens

tokenizer = RegexpTokenizer(r'\w+')

# Inisialisasi stopword remover Sastrawi
factory = StopWordRemoverFactory()
stopwords_sastrawi = set(factory.get_stop_words())

additional_stopwords = {
    'cocok', 'buat', 'main', 'dengan', 'rekomendasi', 'spesifikasi', 'spek',
    'apa', 'yang', 'harga', 'rp', 'ribu', 'juta', 'budget',
    'merek', 'brand', 'merk', 'duit', 'uang', 'dana', 'termurah', 'game', 'dan', 'atau', 'Rekomendasi', 'ram'
}
stopwords_sastrawi.update(additional_stopwords)

# === APPLICATION TO INTENT MAPPING ===
# Maps design/productivity applications to their corresponding intents
APP_TO_INTENT_MAP = {
    # 2D Design Applications
    '2d_design': [
        'photoshop', 'illustrator', 'corel draw', 'coreldraw', 'corel', 'gimp', 
        'paint', 'affinity', 'clip', 'krita', 'procreate', 'design', 'graphic', 
        'editing', 'photo', 'image', 'design'
    ],
    # 3D Design & Rendering
    '3d_design': [
        'blender', 'maya', 'cinema 4d', 'c4d', '3ds max', '3dsmax', 'lightwave',
        'sketchup', 'fusion 360', 'cad', 'autocad', 'solidworks', 'catia',
        'vray', 'arnold', 'rendering', 'model', 'sculpt', '3d'
    ],
    # AI/Machine Learning Development
    'ai_development': [
        'tensorflow', 'pytorch', 'keras', 'jupyter', 'anaconda', 'python', 'ml',
        'machine', 'learning', 'deep', 'neural', 'ai', 'model', 'training',
        'cuda', 'gpu compute', 'data science'
    ],
    # Web Development
    'web_development': [
        'vscode', 'visual studio', 'webstorm', 'sublime', 'nodejs', 'node.js',
        'npm', 'webpack', 'react', 'angular', 'vue', 'development', 'coding',
        'programming', 'ide', 'editor'
    ],
    # Video Editing
    'video_editor': [
        'premiere', 'davinci', 'resolve', 'vegas', 'final cut', 'ffmpeg',
        'video', 'edit', 'editor', 'codec', 'render', 'footage'
    ],
    # Multitasking/Workstation
    'multitasking': [
        'office', 'excel', 'word', 'chrome', 'browser', 'multitask', 'work',
        'productivity', 'meeting', 'zoom', 'teams', 'streaming'
    ]
}

EXPLICIT_GAME_CONTEXT_TERMS = [
    'main',
    'bermain',
    'memainkan',
    'game',
    'games',
    'mabar',
    'gaming',
    'ngegame',
]


def has_explicit_game_context(query: str) -> bool:
    query_lower = query.lower()
    for term in EXPLICIT_GAME_CONTEXT_TERMS:
        if re.search(r'\b' + re.escape(term) + r'\b', query_lower):
            return True
    return False


def apply_manual_game_aliases(user_query, found_games, game_list):
    normalized_query = normalize_lookup_key(user_query)
    found_lower = {g.lower() for g in found_games}

    has_cs2_alias = (
        re.search(r'\bcs\s*2\b', user_query.lower()) is not None
        or 'counterstrike2' in normalized_query
    )

    # Map CS:GO aliases with preference to legacy CS:GO entry if present.
    has_csgo_alias = (
        'csgo' in normalized_query
        or re.search(r'\bcs\s*:?-?\s*go\b', user_query.lower()) is not None
        or 'globaloffensive' in normalized_query
    )

    if has_cs2_alias:
        cs2_candidate = None
        for game in game_list:
            gl = game.lower()
            if 'counter-strike 2' in gl:
                cs2_candidate = game
                break
        if cs2_candidate and cs2_candidate.lower() not in found_lower:
            found_games.append(cs2_candidate)
            found_lower.add(cs2_candidate.lower())

    if has_csgo_alias:
        csgo_candidate = None
        cs2_fallback = None
        for game in game_list:
            gl = game.lower()
            if 'global offensive' in gl:
                csgo_candidate = game
                break
            if 'counter-strike 2' in gl:
                cs2_fallback = game

        selected = csgo_candidate or cs2_fallback
        if selected and selected.lower() not in found_lower:
            found_games.append(selected)

    return found_games

def detect_application_intent(query: str) -> str:
    """
    Detect intent from application keywords in query.
    Returns intent name (e.g., '2D_DESIGN') or None if not found.
    """
    query_lower = query.lower()
    intent_code_map = {
        '2d_design': '2D_DESIGN',
        '3d_design': '3D_DESIGN',
        'ai_development': 'AI_DEVELOPMENT',
        'web_development': 'WEB_DEVELOPMENT',
        'video_editor': 'VIDEO_EDITOR',
        'multitasking': 'MULTITASKING',
    }
    intent_priority = [
        'ai_development',
        '3d_design',
        'video_editor',
        '2d_design',
        'web_development',
        'multitasking',
    ]

    intent_scores = defaultdict(int)
    for intent, keywords in APP_TO_INTENT_MAP.items():
        for keyword in keywords:
            pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
            if re.search(pattern, query_lower):
                intent_scores[intent] += 2 if ' ' in keyword else 1

    if not intent_scores:
        return None

    best_score = max(intent_scores.values())
    tied_intents = [intent for intent, score in intent_scores.items() if score == best_score]

    for intent in intent_priority:
        if intent in tied_intents:
            return intent_code_map[intent]

    return intent_code_map[tied_intents[0]]
    return None

# === Indonesian Number Conversion ===
SIMPLE = {
    "nol":0, "satu":1, "dua":2, "tiga":3, "empat":4, "lima":5,
    "enam":6, "tujuh":7, "delapan":8, "sembilan":9, "sepuluh":10,
    "sebelas":11, "belas":10, "puluh":10, "ratus":100, "seratus":100,
    "seribu":1000, "ribu":1000, "juta":1000000, "milyar":1000000000, "miliar":1000000000
}

def indonesian_words_to_int(text):
    if not text or not isinstance(text, str):
        raise ValueError("Masukkan string kata angka Bahasa Indonesia.")
    t = text.lower().strip()
    t = re.sub(r'[-,\.]', ' ', t)
    t = re.sub(r'\s+', ' ', t)
    parts = t.split()
    total = 0
    current = 0
    i = 0
    while i < len(parts):
        w = parts[i]
        if w in SIMPLE:
            if w in ["puluh", "ratus", "ribu", "juta", "milyar", "miliar"]:
                if current == 0:
                    current = SIMPLE[w]
                else:
                    current *= SIMPLE[w]
            else:
                current += SIMPLE[w]
            i += 1
            continue
        if w == "belas":
            if current == 0 and i > 0:
                prev = parts[i-1]
                val_prev = SIMPLE.get(prev, 0)
                current = val_prev + 10
            else:
                current = current + 10
            i += 1
            continue
        if w == "puluh":
            if current == 0:
                current = 10
            else:
                current = current * 10
            i += 1
            continue
        if w == "ratus":
            if current == 0:
                current = 100
            else:
                current = current * 100
            i += 1
            continue
        if w in ("ribu", "juta", "milyar", "miliar"):
            mult = SIMPLE.get(w, 1)
            if current == 0:
                current = 1 * mult
            else:
                current = current * mult
            total += current
            current = 0
            i += 1
            continue
        if w.startswith("se") and w not in SIMPLE:
            root = w[2:]
            if root in SIMPLE and SIMPLE[root] >= 10:
                current += SIMPLE[root]
            i += 1
            continue
        if re.match(r'^\d+$', w):
            current += int(w)
            i += 1
            continue
        i += 1
    total += current
    return total

def remove_stopwords(tokens):
    return [t for t in tokens if t.lower() not in stopwords_sastrawi]

def basic_preprocessing(text):
    text = text.lower()
    text = re.sub(r'[’‘]', "'", text)
    text = re.sub(f"[{re.escape(string.punctuation)}]", " ", text)
    tokens = tokenizer.tokenize(text)
    return tokens

game_context_words = {'main', 'mabar', 'game', 'games', 'memainkan', 'playing', 'bisa', 'cocok', 'untuk', 'bermain'}
laptop_context_words = {'laptop', 'model', 'brand', 'merek', 'seri', 'type', 'tipe', 'produk'}
ram_context_words = {'ram', 'memory', 'memori', 'ddr'}

def extract_ram(user_query):
    query_lower = user_query.lower()
    ram_patterns = [
        r'(\d+)\s*gb\s*ram', r'ram\s*(\d+)\s*gb', r'(\d+)\s*gb\s*ddr',
        r'ddr\s*(\d+)\s*gb', r'(\d+)\s*gb', r'ram\s*(\d+)',
        r'memori\s*(\d+)\s*gb', r'memory\s*(\d+)\s*gb', r'(\d+)\s*giga',
        r'ram\s*(\d+)\s*giga', r'memory\s*(\d+)\s*giga', r'memori\s*(\d+)\s*giga',
        r'(\d+)\s*gigabyte', r'ram\s*(\d+)\s*gigabyte', r'memory\s*(\d+)\s*gigabyte',
        r'memori\s*(\d+)\s*gigabyte'
    ]
    ram_values = []
    for pattern in ram_patterns:
        matches = re.finditer(pattern, query_lower)
        for match in matches:
            try:
                ram_values.append(int(match.group(1)))
            except ValueError:
                continue
    ram_values = sorted(list(set(ram_values)))
    return ram_values

def remove_general_games_if_specific_found(games):
    games_list = list(games)
    games_to_remove = set()
    for i in range(len(games_list)):
        for j in range(len(games_list)):
            if i != j and games_list[i].lower() in games_list[j].lower() and games_list[i] != games_list[j]:
                games_to_remove.add(games_list[i])
    return [game for game in games if game not in games_to_remove]

def jaro_winkler_similarity(s1, s2):
    def jaro_similarity(s1, s2):
        len_s1, len_s2 = len(s1), len(s2)
        match_distance = max(len_s1, len_s2) // 2 - 1
        matches = 0
        transpositions = 0
        matched_s1 = [False] * len_s1
        matched_s2 = [False] * len_s2
        for i in range(len_s1):
            start = max(0, i - match_distance)
            end = min(i + match_distance + 1, len_s2)
            for j in range(start, end):
                if not matched_s2[j] and s1[i] == s2[j]:
                    matched_s1[i] = True
                    matched_s2[j] = True
                    matches += 1
                    break
        if matches == 0:
            return 0.0
        k = 0
        for i in range(len_s1):
            if matched_s1[i]:
                while not matched_s2[k]:
                    k += 1
                if s1[i] != s2[k]:
                    transpositions += 1
                k += 1
        transpositions //= 2
        jaro = (matches/len_s1 + matches/len_s2 + (matches - transpositions)/matches) / 3
        return jaro
    jaro = jaro_similarity(s1, s2)
    prefix = 0
    for i in range(min(4, len(s1), len(s2))):
        if s1[i] == s2[i]:
            prefix += 1
        else:
            break
    return jaro + (prefix * 0.1 * (1 - jaro))

def find_best_match(token, candidates, threshold=0.85):
    best_match = None
    best_score = 0
    for candidate in candidates:
        score = jaro_winkler_similarity(token.lower(), candidate.lower())
        if score > best_score and score >= threshold:
            best_score = score
            best_match = candidate
    return best_match


def normalize_lookup_key(text):
    return re.sub(r'[^a-zA-Z0-9]', '', text.lower())

def extract_text_budget(query):
    query_lower = query.lower()
    
    # ===== NUMERIC BUDGET EXTRACTION (20000000 or 20.000.000 format) =====
    numeric_pattern = r'(?:rp|budget|harga|sekitar)?\s*(\d{1,3}(?:[.,]\d{3})*)\s*(?:ribu|rbu|rb|jt|juta)?'
    numeric_match = re.search(numeric_pattern, query_lower, re.IGNORECASE)
    if numeric_match:
        numeric_str = numeric_match.group(1).replace('.', '').replace(',', '')
        try:
            numeric_val = int(numeric_str)
            # If it looks like a price (too small), assume it's in thousands or its original value
            if numeric_val > 100000:  # Likely already in full rupiah (>100k)
                return numeric_val, numeric_match.span(0)
            elif numeric_val > 1000:  # Could be in thousands
                return (numeric_val * 1000), numeric_match.span(0)
        except (ValueError, AttributeError):
            pass
    
    # ===== TEXT-BASED BUDGET EXTRACTION =====
    pattern_range = r'(?:harga|rp|budget|sekitar|harga sekitar|budget sekitar|rp\s*:?)\s*([a-z\s]+?)\s*(?:sampai|hingga|-)\s*([a-z\s]+?)\s*(ribu|rbu|rb|jt|juta)'
    pattern_single = r'(?:harga|rp|budget|sekitar|harga sekitar|budget sekitar|rp\s*:?)\s*([a-z\s]+?)\s*(ribu|rbu|rb|jt|juta)'
    pattern_range_no_keyword = r'(\b(?:[a-z]+\s)+?)\s*(?:sampai|hingga|-)\s*(\b(?:[a-z]+\s)+?)\s*(ribu|rbu|rb|jt|juta)\b'
    pattern_single_no_keyword = r'(\b(?:[a-z]+\s)+?)\s*(ribu|rbu|rb|jt|juta)\b'

    range_match = re.search(pattern_range, query_lower, re.IGNORECASE)
    if range_match:
        low_text = range_match.group(1).strip()
        high_text = range_match.group(2).strip()
        unit = range_match.group(3).strip()
        low_text = re.sub(r'\b(rb|rbu)\b', 'ribu', low_text)
        low_text = re.sub(r'\b(jt)\b', 'juta', low_text)
        high_text = re.sub(r'\b(rb|rbu)\b', 'ribu', high_text)
        high_text = re.sub(r'\b(jt)\b', 'juta', high_text)
        try:
            low_num = indonesian_words_to_int(low_text)
            high_num = indonesian_words_to_int(high_text)
            low_has_unit = re.search(r'\b(juta|ribu|rbu|rb|jt)\b', low_text, re.IGNORECASE) is not None
            high_has_unit = re.search(r'\b(juta|ribu|rbu|rb|jt)\b', high_text, re.IGNORECASE) is not None
            if not low_has_unit and not high_has_unit:
                if unit in ['juta', 'jt']:
                    low_num *= 1000000
                    high_num *= 1000000
                elif unit in ['ribu', 'rbu', 'rb']:
                    low_num *= 1000
                    high_num *= 1000
            return (low_num, high_num), range_match.span(0)
        except Exception:
            return None, None

    single_match = re.search(pattern_single, query_lower, re.IGNORECASE)
    if single_match:
        text_budget = single_match.group(1).strip()
        unit = single_match.group(2).strip()
        text_budget = re.sub(r'\b(rb|rbu)\b', 'ribu', text_budget)
        text_budget = re.sub(r'\b(jt)\b', 'juta', text_budget)
        try:
            num = indonesian_words_to_int(text_budget)
            has_unit = re.search(r'\b(juta|ribu|rbu|rb|jt)\b', text_budget, re.IGNORECASE) is not None
            if not has_unit:
                if unit in ['juta', 'jt']:
                    num *= 1000000
                elif unit in ['ribu', 'rbu', 'rb']:
                    num *= 1000
            return num, single_match.span(0)
        except Exception:
            return None, None

    range_match_no_keyword = re.search(pattern_range_no_keyword, query_lower, re.IGNORECASE)
    if range_match_no_keyword:
        low_text = range_match_no_keyword.group(1).strip()
        high_text = range_match_no_keyword.group(2).strip()
        unit = range_match_no_keyword.group(3).strip()
        low_text = re.sub(r'\b(rb|rbu)\b', 'ribu', low_text)
        low_text = re.sub(r'\b(jt)\b', 'juta', low_text)
        high_text = re.sub(r'\b(rb|rbu)\b', 'ribu', high_text)
        high_text = re.sub(r'\b(jt)\b', 'juta', high_text)
        try:
            low_num = indonesian_words_to_int(low_text)
            high_num = indonesian_words_to_int(high_text)
            if unit in ['juta', 'jt']:
                low_num *= 1000000
                high_num *= 1000000
            elif unit in ['ribu', 'rbu', 'rb']:
                low_num *= 1000
                high_num *= 1000
            return (low_num, high_num), range_match_no_keyword.span(0)
        except Exception:
            return None, None

    single_match_no_keyword = re.search(pattern_single_no_keyword, query_lower, re.IGNORECASE)
    if single_match_no_keyword:
        text_budget = single_match_no_keyword.group(1).strip()
        unit = single_match_no_keyword.group(2).strip()
        text_budget = re.sub(r'\b(rb|rbu)\b', 'ribu', text_budget)
        text_budget = re.sub(r'\b(jt)\b', 'juta', text_budget)
        try:
            num = indonesian_words_to_int(text_budget)
            if unit in ['juta', 'jt']:
                num *= 1000000
            elif unit in ['ribu', 'rbu', 'rb']:
                num *= 1000
            return num, single_match_no_keyword.span(0)
        except Exception:
            return None, None
    return None, None

def extract_entities_and_budget(user_query, game_list, laptop_list, laptop_brand_list,
                               unique_word_kb, game_abbreviations_kb, game_alt_titles_kb, series_abbreviations,
                               bigram_unique_kb, brand_models_mapping):
    found_games = set()
    found_laptops = set()
    extracted_budget = None
    extracted_ram = []
    budget_span = None

    query_lower = user_query.lower()
    tokens_with_span = tokenize_with_span(user_query)
    token_strings = [token for token, start, end in tokens_with_span]

    extracted_ram = extract_ram(user_query)

    ram_tokens = set()
    if extracted_ram:
        for ram_value in extracted_ram:
            ram_tokens.add(f"{ram_value}gb")
            ram_tokens.add(f"{ram_value} gb")
            ram_tokens.add(f"ram{ram_value}")
            ram_tokens.add(f"ddr{ram_value}")
            ram_tokens.add(f"{ram_value}giga")
            ram_tokens.add(f"{ram_value} giga")

    # --- budget extraction with dot thousand separator and max/min keywords ---
    # 1. Budget dengan kata kunci max / min (prioritas tertinggi)
    pattern_max = r'(?:maksimal|max)\s*:?\s*(\d{1,3}(?:\.\d{3})*(?:,\d+)?)\s*(rb|ribu|jt|juta|miliar|milyar)?'
    match_max = re.search(pattern_max, query_lower, re.IGNORECASE)
    if match_max:
        try:
            amount_str = match_max.group(1).replace('.', '')
            amount = float(amount_str.replace(',', '.'))
            unit = match_max.group(2)
            if unit:
                unit = unit.lower()
                if unit in ['juta', 'jt']:
                    amount = int(amount * 1_000_000)
                elif unit in ['ribu', 'rb']:
                    amount = int(amount * 1_000)
                elif unit in ['miliar', 'milyar']:
                    amount = int(amount * 1_000_000_000)
            extracted_budget = int(amount)
            budget_span = match_max.span(0)
        except:
            pass

    if extracted_budget is None:
        pattern_min = r'(?:minimal|min)\s*:?\s*(\d{1,3}(?:\.\d{3})*(?:,\d+)?)\s*(rb|ribu|jt|juta|miliar|milyar)?'
        match_min = re.search(pattern_min, query_lower, re.IGNORECASE)
        if match_min:
            try:
                amount_str = match_min.group(1).replace('.', '')
                amount = float(amount_str.replace(',', '.'))
                unit = match_min.group(2)
                if unit:
                    unit = unit.lower()
                    if unit in ['juta', 'jt']:
                        amount = int(amount * 1_000_000)
                    elif unit in ['ribu', 'rb']:
                        amount = int(amount * 1_000)
                    elif unit in ['miliar', 'milyar']:
                        amount = int(amount * 1_000_000_000)
                extracted_budget = int(amount)
                budget_span = match_min.span(0)
            except:
                pass

    # 2. Range dengan kata kunci budget
    if extracted_budget is None:
        pattern_range_with_keyword = r'(?:harga|rp|rp\.|budget)\s*:?\s*(\d{1,3}(?:\.\d{3})*(?:,\d+)?)\s*(?:sampai|hingga|-)\s*(\d{1,3}(?:\.\d{3})*(?:,\d+)?)\s*(rb|ribu|jt|juta)'
        match_range_keyword = re.search(pattern_range_with_keyword, query_lower, re.IGNORECASE)
        if match_range_keyword:
            try:
                amount1 = float(match_range_keyword.group(1).replace('.', '').replace(',', '.'))
                amount2 = float(match_range_keyword.group(2).replace('.', '').replace(',', '.'))
                unit = match_range_keyword.group(3).lower()
                if unit in ['juta', 'jt']:
                    amount1 = int(amount1 * 1_000_000)
                    amount2 = int(amount2 * 1_000_000)
                elif unit in ['ribu', 'rb']:
                    amount1 = int(amount1 * 1_000)
                    amount2 = int(amount2 * 1_000)
                else:
                    amount1 = int(amount1)
                    amount2 = int(amount2)
                extracted_budget = (min(amount1, amount2), max(amount1, amount2))
                budget_span = match_range_keyword.span(0)
            except:
                pass

    # 3. Range tanpa kata kunci
    if extracted_budget is None:
        pattern_range_no_keyword = r'(\d{1,3}(?:\.\d{3})*(?:,\d+)?)\s*(?:sampai|hingga|-)\s*(\d{1,3}(?:\.\d{3})*(?:,\d+)?)\s*(rb|ribu|jt|juta)'
        match_range = re.search(pattern_range_no_keyword, query_lower, re.IGNORECASE)
        if match_range:
            try:
                amount1 = float(match_range.group(1).replace('.', '').replace(',', '.'))
                amount2 = float(match_range.group(2).replace('.', '').replace(',', '.'))
                unit = match_range.group(3).lower()
                if unit in ['juta', 'jt']:
                    amount1 = int(amount1 * 1_000_000)
                    amount2 = int(amount2 * 1_000_000)
                elif unit in ['ribu', 'rb']:
                    amount1 = int(amount1 * 1_000)
                    amount2 = int(amount2 * 1_000)
                else:
                    amount1 = int(amount1)
                    amount2 = int(amount2)
                extracted_budget = (min(amount1, amount2), max(amount1, amount2))
                budget_span = match_range.span(0)
            except:
                pass

    # 4. Single value dengan kata kunci
    if extracted_budget is None:
        pattern_single_with_keyword = r'(?:harga|rp|rp\.|budget)\s*:?\s*(\d{1,3}(?:\.\d{3})*(?:,\d+)?)\s*(rb|ribu|jt|juta)?'
        match_single_keyword = re.search(pattern_single_with_keyword, query_lower, re.IGNORECASE)
        if match_single_keyword:
            try:
                amount = float(match_single_keyword.group(1).replace('.', '').replace(',', '.'))
                unit = match_single_keyword.group(2)
                if unit is None:
                    extracted_budget = int(amount)
                else:
                    unit = unit.lower()
                    if unit in ['juta', 'jt']:
                        extracted_budget = int(amount * 1_000_000)
                    elif unit in ['ribu', 'rb']:
                        extracted_budget = int(amount * 1_000)
                    else:
                        extracted_budget = int(amount)
                budget_span = match_single_keyword.span(0)
            except:
                pass

    # 5. Single value tanpa kata kunci
    if extracted_budget is None:
        pattern_single_no_keyword = r'\b(\d{1,3}(?:\.\d{3})*(?:,\d+)?)\s*(rb|ribu|jt|juta)\b'
        match_single = re.search(pattern_single_no_keyword, query_lower, re.IGNORECASE)
        if match_single:
            try:
                amount = float(match_single.group(1).replace('.', '').replace(',', '.'))
                unit = match_single.group(2).lower()
                if unit in ['juta', 'jt']:
                    extracted_budget = int(amount * 1_000_000)
                elif unit in ['ribu', 'rb']:
                    extracted_budget = int(amount * 1_000)
                else:
                    extracted_budget = int(amount)
                budget_span = match_single.span(0)
            except:
                pass

    # 6. Text-based budget
    if extracted_budget is None:
        text_budget, text_budget_span = extract_text_budget(user_query)
        if text_budget is not None:
            extracted_budget = text_budget
            budget_span = text_budget_span

    # Non-budget tokens
    non_budget_tokens = []
    if budget_span is not None:
        budget_start, budget_end = budget_span
        for token, start, end in tokens_with_span:
            if not (start < budget_end and end > budget_start):
                non_budget_tokens.append(token)
    else:
        non_budget_tokens = token_strings[:]

    non_budget_non_ram_tokens = [token for token in non_budget_tokens if token.lower() not in ram_tokens]

    # --- Detect Game Context Zones ---
    game_context_zones = []
    game_keywords = list(game_context_words)
    pattern = r'\b(' + '|'.join(game_keywords) + r')\b'
    for match in re.finditer(pattern, query_lower):
        context_start = match.start()
        next_laptop_context = re.search(r'\b(laptop|merek|brand|model)\b', query_lower[context_start:])
        if next_laptop_context:
            context_end = context_start + next_laptop_context.start()
        else:
            context_end = len(query_lower)
        game_context_zones.append((context_start, context_end))

    # --- Laptop detection ---
    laptop_lookup = {e.lower(): e for e in (laptop_list + laptop_brand_list)}
    laptop_entities = set(laptop_lookup.keys())
    ambiguous_indices = set()
    laptop_token_indices = set()

    for i, token in enumerate(non_budget_non_ram_tokens):
        token_lower = token.lower()
        if token_lower in game_context_words and i + 1 < len(non_budget_non_ram_tokens):
            ambiguous_indices.add(i + 1)

    i = 0
    while i < len(non_budget_non_ram_tokens):
        token = non_budget_non_ram_tokens[i]
        token_lower = token.lower()
        token_start = tokens_with_span[i][1]
        in_game_zone = False
        for zone_start, zone_end in game_context_zones:
            if zone_start <= token_start < zone_end:
                in_game_zone = True
                break
        if in_game_zone:
            i += 1
            continue

        max_lookahead = 6
        matched = False
        for length in range(max_lookahead, 0, -1):
            if i + length > len(non_budget_non_ram_tokens):
                continue
            cand = " ".join(non_budget_non_ram_tokens[i:i+length]).lower()
            if cand in laptop_lookup:
                found_laptops.add(laptop_lookup[cand])
                for idx in range(i, i+length):
                    laptop_token_indices.add(idx)
                matched = True
                i += length
                break
        if not matched:
            if token_lower in laptop_entities:
                found_laptops.add(laptop_lookup[token_lower])
                laptop_token_indices.add(i)
                i += 1
            else:
                i += 1

    for i in range(len(non_budget_non_ram_tokens)):
        token = non_budget_non_ram_tokens[i]
        token_lower = token.lower()
        token_start = tokens_with_span[i][1]
        in_game_zone = False
        for zone_start, zone_end in game_context_zones:
            if zone_start <= token_start < zone_end:
                in_game_zone = True
                break
        if in_game_zone:
            continue
        if token_lower in game_context_words or token_lower in laptop_context_words:
            continue
        if token_lower in laptop_entities:
            is_laptop_context = False
            is_game_context = False
            if i > 0:
                prev_token = non_budget_non_ram_tokens[i-1].lower()
                if prev_token in laptop_context_words:
                    is_laptop_context = True
                if prev_token in game_context_words:
                    is_game_context = True
            if i + 1 < len(non_budget_non_ram_tokens):
                next_token = non_budget_non_ram_tokens[i+1].lower()
                if next_token in laptop_context_words:
                    is_laptop_context = True
                if next_token in game_context_words:
                    is_game_context = True
            for k in range(max(0, i-3), i):
                if non_budget_non_ram_tokens[k].lower() in laptop_context_words:
                    is_laptop_context = True
                    break
            if is_laptop_context and not is_game_context:
                found_laptops.add(laptop_lookup[token_lower])
                laptop_token_indices.add(i)
            elif is_game_context and i in ambiguous_indices:
                pass
            else:
                if (i > 0 and non_budget_non_ram_tokens[i-1].lower() in laptop_context_words) or \
                   (i + 1 < len(non_budget_non_ram_tokens) and non_budget_non_ram_tokens[i+1].lower() in laptop_context_words):
                    found_laptops.add(laptop_lookup[token_lower])
                    laptop_token_indices.add(i)

    laptop_brand_set_lower = set([b.lower() for b in laptop_brand_list])
    separators = {'atau', 'or', ',', 'dan'}
    for i, token in enumerate(non_budget_non_ram_tokens):
        token_start = tokens_with_span[i][1]
        in_game_zone = False
        for zone_start, zone_end in game_context_zones:
            if zone_start <= token_start < zone_end:
                in_game_zone = True
                break
        if in_game_zone:
            continue
        tl = token.lower()
        if tl in laptop_brand_set_lower:
            found_laptops.add(laptop_lookup[tl])
            if i + 2 < len(non_budget_non_ram_tokens):
                sep = non_budget_non_ram_tokens[i+1].lower()
                nxt = non_budget_non_ram_tokens[i+2].lower()
                if sep in separators and nxt in laptop_brand_set_lower:
                    found_laptops.add(laptop_lookup[nxt])

    for i, token in enumerate(non_budget_non_ram_tokens):
        token_start = tokens_with_span[i][1]
        in_game_zone = False
        for zone_start, zone_end in game_context_zones:
            if zone_start <= token_start < zone_end:
                in_game_zone = True
                break
        if in_game_zone:
            continue
        if token.lower() in laptop_brand_set_lower and len(token) >= 3 and token.lower() not in stopwords_sastrawi:
            found_laptops.add(laptop_lookup[token.lower()])

    # --- NEW: Combine brand and model using brand_models_mapping ---
    # Separate detected strings into brands and models
    brand_list = [e for e in found_laptops if e in laptop_brand_list]
    model_list = [e for e in found_laptops if e in laptop_list]

    # Build a list of final filters
    final_laptop_filters = set()

    # Track used brands and models to avoid duplicates
    used_brands = set()
    used_models = set()

    # For each brand, try to combine with each model if the model belongs to that brand
    for brand in brand_list:
        if brand not in brand_models_mapping:
            continue
        brand_models = set(brand_models_mapping[brand])
        for model in model_list:
            if model in brand_models:
                combined = f"{brand} {model}"
                final_laptop_filters.add(combined)
                used_brands.add(brand)
                used_models.add(model)

    # Add remaining brands that were not combined
    for brand in brand_list:
        if brand not in used_brands:
            final_laptop_filters.add(brand)

    # Add remaining models that were not combined
    for model in model_list:
        if model not in used_models:
            final_laptop_filters.add(model)

    # Replace found_laptops with the combined set
    found_laptops = final_laptop_filters

    # Continue with game detection (unchanged)
    non_laptop_tokens = []
    for idx, token in enumerate(non_budget_non_ram_tokens):
        if idx not in laptop_token_indices:
            non_laptop_tokens.append(token)

    exact_kb = {}
    exact_kb.update(game_alt_titles_kb)
    exact_kb.update(game_abbreviations_kb)
    exact_kb.update(unique_word_kb)
    exact_kb.update(bigram_unique_kb)

    normalized_game_lookup = {}
    for game in game_list:
        normalized = re.sub(r'[^a-zA-Z0-9]', '', game).lower()
        normalized_game_lookup[normalized] = game
    exact_kb.update(normalized_game_lookup)
    exact_kb_lower = {k.lower(): v for k, v in exact_kb.items()}

    # Add normalized keys so aliases like "cs:go" can match "csgo" from user query.
    normalized_exact_kb = {}
    for key, value in exact_kb_lower.items():
        norm_key = normalize_lookup_key(key)
        if len(norm_key) >= 3 and norm_key not in normalized_exact_kb:
            normalized_exact_kb[norm_key] = value

    game_segments = []
    current_segment = []
    separators = {',', 'dan', 'atau', 'sama'}
    for token in non_laptop_tokens:
        if token.lower() in separators:
            if current_segment:
                game_segments.append(current_segment)
                current_segment = []
        else:
            current_segment.append(token)
    if current_segment:
        game_segments.append(current_segment)
    if not game_segments:
        game_segments = [non_laptop_tokens]

    confirmed_games = set()
    matched_game_tokens = set()

    for segment in game_segments:
        segment_text = ' '.join(segment).lower()
        normalized_segment = re.sub(r'[^a-zA-Z0-9]', '', segment_text).lower()
        segment_confirmed_games = set()
        matched_spans = []
        if normalized_segment in normalized_exact_kb:
            game_name = normalized_exact_kb[normalized_segment]
            segment_confirmed_games.add(game_name)
            matched_spans.append((0, len(segment_text)))
        sorted_keys = sorted(exact_kb_lower.keys(), key=len, reverse=True)
        for key in sorted_keys:
            if key == normalized_segment:
                continue
            pattern = r'\b' + re.escape(key) + r'\b'
            matches = list(re.finditer(pattern, segment_text))
            for match in matches:
                start, end = match.span()
                overlap = False
                for (s, e) in matched_spans:
                    if max(start, s) < min(end, e):
                        overlap = True
                        break
                if not overlap:
                    game_name = exact_kb_lower[key]
                    segment_confirmed_games.add(game_name)
                    matched_spans.append((start, end))
                    for token in segment:
                        if token.lower() in key:
                            matched_game_tokens.add(token)
                    break
        confirmed_games.update(segment_confirmed_games)
        if segment_confirmed_games:
            for token in segment:
                matched_game_tokens.add(token)

    non_laptop_non_game_tokens = [token for token in non_laptop_tokens if token not in matched_game_tokens]

    for segment in game_segments:
        segment_text = ' '.join(segment).lower()
        if any(game.lower() in segment_text for game in confirmed_games):
            continue
        combined_token = ''.join(segment).lower()
        matching_games = []
        for game in game_list:
            if combined_token in game.lower():
                matching_games.append(game)
        if len(matching_games) == 1:
            confirmed_games.add(matching_games[0])
            for token in segment:
                matched_game_tokens.add(token)
        elif len(matching_games) > 1:
            best_match = min(matching_games, key=len)
            confirmed_games.add(best_match)
            for token in segment:
                matched_game_tokens.add(token)

    non_laptop_non_game_tokens = [token for token in non_laptop_non_game_tokens if token not in matched_game_tokens]

    remaining_game_tokens = [token for token in non_laptop_non_game_tokens if token.lower() not in stopwords_sastrawi]
    filtered_remaining_tokens = []
    for i, token in enumerate(remaining_game_tokens):
        if (is_roman_numeral(token) or token.isdigit()) and len(token) <= 3:
            if (i > 0 and remaining_game_tokens[i-1].lower() not in stopwords_sastrawi) or \
               (i < len(remaining_game_tokens)-1 and remaining_game_tokens[i+1].lower() not in stopwords_sastrawi):
                filtered_remaining_tokens.append(token)
        else:
            filtered_remaining_tokens.append(token)

    i = 0
    while i < len(filtered_remaining_tokens):
        token = filtered_remaining_tokens[i]
        token_lower = token.lower()
        if token_lower in stopwords_sastrawi or len(token) < 3:
            i += 1
            continue
        matching_games = []
        for game in game_list:
            # Avoid generic substring matches from short tokens like "go" or "ai".
            if len(token_lower) >= 4 and token_lower in game.lower():
                matching_games.append(game)
        if len(matching_games) == 1:
            confirmed_games.add(matching_games[0])
            matched_game_tokens.add(token)
            i += 1
        elif len(matching_games) > 1:
            if i + 1 < len(filtered_remaining_tokens):
                next_token = filtered_remaining_tokens[i + 1]
                next_token_lower = next_token.lower()
                disambiguated_matches = []
                for game in matching_games:
                    if token_lower in game.lower() and next_token_lower in game.lower():
                        disambiguated_matches.append(game)
                if len(disambiguated_matches) == 1:
                    confirmed_games.add(disambiguated_matches[0])
                    matched_game_tokens.add(token)
                    matched_game_tokens.add(next_token)
                    i += 2
                    continue
                elif len(disambiguated_matches) > 1 and next_token.isdigit():
                    exact_numeric_matches = []
                    for game in disambiguated_matches:
                        if re.search(r'\b' + next_token + r'\b', game):
                            exact_numeric_matches.append(game)
                    if len(exact_numeric_matches) == 1:
                        confirmed_games.add(exact_numeric_matches[0])
                        matched_game_tokens.add(token)
                        matched_game_tokens.add(next_token)
                        i += 2
                        continue
            i += 1
        else:
            i += 1

    remaining_tokens_after_phase3 = [token for token in non_laptop_non_game_tokens if token not in matched_game_tokens and len(token) >= 3]
    all_game_candidates = set(game_list)
    all_game_candidates.update(game_alt_titles_kb.values())
    all_game_candidates.update(unique_word_kb.values())
    all_game_candidates.update(bigram_unique_kb.values())

    matched_in_phase4 = set()
    n = len(remaining_tokens_after_phase3)
    i = 0
    while i < n - 1:
        token_a = remaining_tokens_after_phase3[i]
        token_b = remaining_tokens_after_phase3[i+1]
        if len(token_a) < 3 or len(token_b) < 3:
            i += 1
            continue
        bigram = token_a + " " + token_b
        if len(bigram.replace(" ", "")) < 6:
            i += 1
            continue
        best_match = find_best_match(bigram, all_game_candidates, threshold=0.88)
        if best_match:
            confirmed_games.add(best_match)
            matched_in_phase4.update([i, i+1])
            i += 2
        else:
            i += 1
    for i in range(n):
        if i not in matched_in_phase4:
            token = remaining_tokens_after_phase3[i]
            if len(token) < 4:
                continue
            best_match = find_best_match(token, all_game_candidates, threshold=0.90)
            if best_match:
                confirmed_games.add(best_match)
                matched_in_phase4.add(i)
    for i in matched_in_phase4:
        matched_game_tokens.add(remaining_tokens_after_phase3[i])

    confirmed_games = remove_general_games_if_specific_found(confirmed_games)

    return list(confirmed_games), list(found_laptops), extracted_budget, extracted_ram, budget_span

def nlp_pipeline_fuzzy(user_query, game_list, laptop_list, laptop_brand_list,
                       unique_keyword_game_map, game_abbreviations_kb, game_alt_titles_kb, series_abbreviations,
                       bigram_unique_kb, brand_models_mapping):
    tokens = basic_preprocessing(user_query)
    tokens = remove_stopwords(tokens)
    found_games, found_laptops, extracted_budget, extracted_ram, budget_span = extract_entities_and_budget(
        user_query, game_list, laptop_list, laptop_brand_list,
        unique_keyword_game_map, game_abbreviations_kb, game_alt_titles_kb, series_abbreviations,
        bigram_unique_kb, brand_models_mapping
    )
    
    # Detect application intent (design, AI, web dev, etc.)
    app_intent = detect_application_intent(user_query)
    has_game_context = has_explicit_game_context(user_query)

    found_games = apply_manual_game_aliases(user_query, found_games, game_list)

    # If the query is clearly about productivity/design intent and does not
    # explicitly mention gaming context, drop accidental game matches.
    if app_intent and found_games and not has_game_context:
        found_games = []
    
    return {
        "tokens": tokens,
        "found_games": found_games,
        "found_laptops": found_laptops,
        "budget": extracted_budget,
        "ram": extracted_ram,
        "budget_span": budget_span,
        "app_intent": app_intent,  # NEW: Application intent mapping
        "has_game_context": has_game_context
    }