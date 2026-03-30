# scripts/build_bigram_trigram_kb.py
import re
import string
from collections import defaultdict, OrderedDict
from nltk.tokenize import RegexpTokenizer

def build_bigram_trigram_kb(min_req_df):
    # Initialize tokenizer dengan pattern yang mempertahankan tanda hubung dalam token
    tokenizer = RegexpTokenizer(r'[\w\-]+')

    # Roman numeral conversion utilities
    def is_roman_numeral(s):
        pattern = r'^m{0,4}(cm|cd|d?c{0,3})(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})$'
        return bool(re.match(pattern, s.lower()))

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

    # Daftar game dari dataframe
    game_list = min_req_df['App'].tolist()

    def basic_preprocessing(text):
        text = text.lower()
        text = re.sub(r'[’‘]', "'", text)
        text = re.sub(r"\b(\w+)'s\b", r"\1s", text)
        text = re.sub(r"'", "", text)
        text = re.sub(
            r'\b((?:[a-z]\.)+[a-z])\b',
            lambda m: m.group(0).replace('.', ''),
            text
        )
        text = re.sub(r'(\w)\.(\w)', r'\1 \2', text)

        # Hapus tanda hubung yang berdiri sendiri (dikelilingi spasi)
        text = re.sub(r'\s-\s', ' ', text)

        # Hapus semua tanda baca kecuali tanda hubung dalam kata
        text = re.sub(f"[{re.escape(string.punctuation.replace('-', ''))}]", " ", text)

        tokens = tokenizer.tokenize(text)
        return tokens

    # Fungsi untuk menghasilkan varian dari token dengan tanda hubung
    def generate_hyphen_variants(token):
        variants = set()
        variants.add(token)
        if '-' in token and len(token) > 1:
            variants.add(token.replace('-', ''))
            split_tokens = token.split('-')
            if len(split_tokens) > 1:
                variants.add(' '.join(split_tokens))
        return variants

    # Hitung frekuensi bigram dan trigram
    bigram_freq = defaultdict(int)
    trigram_freq = defaultdict(int)

    for game in game_list:
        tokens = basic_preprocessing(game)
        normalized_tokens = []
        for token in tokens:
            if is_roman_numeral(token):
                normalized_tokens.append(roman_to_int(token))
            else:
                normalized_tokens.append(token)

        # Generate variants untuk semua token
        variants_list = []
        for token in normalized_tokens:
            variants = generate_hyphen_variants(token)
            variants_list.append(variants)

        # Hitung frekuensi bigram
        for i in range(len(variants_list) - 1):
            for v1 in variants_list[i]:
                for v2 in variants_list[i+1]:
                    if ' ' in v1:
                        parts = v1.split(' ')
                        if len(parts) == 2:
                            trigram = f"{parts[0]} {parts[1]} {v2}"
                            trigram_freq[trigram] += 1
                        elif len(parts) == 3:
                            fourgram = f"{parts[0]} {parts[1]} {parts[2]} {v2}"
                            # tidak dihitung
                            pass
                    elif ' ' in v2:
                        parts = v2.split(' ')
                        if len(parts) == 2:
                            trigram = f"{v1} {parts[0]} {parts[1]}"
                            trigram_freq[trigram] += 1
                    else:
                        bigram = f"{v1} {v2}"
                        bigram_freq[bigram] += 1

        # Hitung frekuensi trigram
        for i in range(len(variants_list) - 2):
            for v1 in variants_list[i]:
                for v2 in variants_list[i+1]:
                    for v3 in variants_list[i+2]:
                        if ' ' not in v1 and ' ' not in v2 and ' ' not in v3:
                            trigram = f"{v1} {v2} {v3}"
                            trigram_freq[trigram] += 1

    # Buat pemetaan bigram dan trigram unik
    bigram_unique_kb = OrderedDict()

    for game in game_list:
        tokens = basic_preprocessing(game)
        normalized_tokens = []
        for token in tokens:
            if is_roman_numeral(token):
                normalized_tokens.append(roman_to_int(token))
            else:
                normalized_tokens.append(token)

        variants_list = []
        for token in normalized_tokens:
            variants = generate_hyphen_variants(token)
            variants_list.append(variants)

        # Proses bigram dan trigram unik
        for i in range(len(variants_list) - 1):
            for v1 in variants_list[i]:
                for v2 in variants_list[i+1]:
                    if ' ' in v1:
                        parts = v1.split(' ')
                        if len(parts) == 2:
                            trigram = f"{parts[0]} {parts[1]} {v2}"
                            if trigram_freq[trigram] == 1:
                                if (any(char.isalpha() for char in parts[0]) or
                                    any(char.isalpha() for char in parts[1]) or
                                    any(char.isalpha() for char in v2)):
                                    if trigram not in bigram_unique_kb:
                                        bigram_unique_kb[trigram] = game
                        elif len(parts) == 3:
                            fourgram = f"{parts[0]} {parts[1]} {parts[2]} {v2}"
                            if (any(char.isalpha() for char in parts[0]) or
                                any(char.isalpha() for char in parts[1]) or
                                any(char.isalpha() for char in parts[2]) or
                                any(char.isalpha() for char in v2)):
                                if fourgram not in bigram_unique_kb:
                                    bigram_unique_kb[fourgram] = game
                    elif ' ' in v2:
                        parts = v2.split(' ')
                        if len(parts) == 2:
                            trigram = f"{v1} {parts[0]} {parts[1]}"
                            if trigram_freq[trigram] == 1:
                                if (any(char.isalpha() for char in v1) or
                                    any(char.isalpha() for char in parts[0]) or
                                    any(char.isalpha() for char in parts[1])):
                                    if trigram not in bigram_unique_kb:
                                        bigram_unique_kb[trigram] = game
                        elif len(parts) == 3:
                            fourgram = f"{v1} {parts[0]} {parts[1]} {parts[2]}"
                            if (any(char.isalpha() for char in v1) or
                                any(char.isalpha() for char in parts[0]) or
                                any(char.isalpha() for char in parts[1]) or
                                any(char.isalpha() for char in parts[2])):
                                if fourgram not in bigram_unique_kb:
                                    bigram_unique_kb[fourgram] = game
                    else:
                        bigram = f"{v1} {v2}"
                        if bigram_freq[bigram] == 1:
                            if (any(char.isalpha() for char in v1) or
                                any(char.isalpha() for char in v2)):
                                if bigram not in bigram_unique_kb:
                                    bigram_unique_kb[bigram] = game

        # Proses trigram asli (tiga token terpisah)
        for i in range(len(variants_list) - 2):
            for v1 in variants_list[i]:
                for v2 in variants_list[i+1]:
                    for v3 in variants_list[i+2]:
                        if ' ' not in v1 and ' ' not in v2 and ' ' not in v3:
                            trigram = f"{v1} {v2} {v3}"
                            if trigram_freq[trigram] == 1:
                                if (any(char.isalpha() for char in v1) or
                                    any(char.isalpha() for char in v2) or
                                    any(char.isalpha() for char in v3)):
                                    if trigram not in bigram_unique_kb:
                                        bigram_unique_kb[trigram] = game

    # (Opsional) Hapus print jika tidak ingin output
    # print("Bigram and trigram unique mappings count:", len(bigram_unique_kb))
    return bigram_unique_kb