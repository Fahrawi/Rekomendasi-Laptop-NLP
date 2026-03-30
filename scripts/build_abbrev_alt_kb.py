# scripts/build_abbrev_alt_kb.py
import re
from collections import defaultdict, OrderedDict
from nltk.tokenize import RegexpTokenizer
import string
import difflib

def build_abbrev_alt_kb(game_list, series_abbreviations, series_games):
    # Initialize tokenizer
    tokenizer = RegexpTokenizer(r'\w+')

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

    def convert_2k_year(token):
        pattern = r'^(\d+)k(\d+)$'
        match = re.match(pattern, token, re.IGNORECASE)
        if match:
            century = match.group(1)
            year_suffix = match.group(2)
            if len(year_suffix) == 2:
                return century + "0" + year_suffix
            elif len(year_suffix) == 1:
                return century + "00" + year_suffix
        return token

    def is_ordinal_number(token):
        return bool(re.match(r'^\d+(st|nd|rd|th)$', token.lower()))

    def normalize_token(tok):
        if is_roman_numeral(tok):
            return roman_to_int(tok)
        return convert_2k_year(tok)

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
        text = re.sub(f"[{re.escape(string.punctuation)}]", " ", text)
        return tokenizer.tokenize(text)

    def generate_abbr_variants(tokens):
        grouped_tokens_roman = []
        current_group_roman = []
        grouped_tokens_arabic = []
        current_group_arabic = []

        for token in tokens:
            is_roman = is_roman_numeral(token)
            is_ordinal = is_ordinal_number(token)
            is_digit = token.isdigit()

            if is_roman or is_digit or is_ordinal:
                if current_group_roman:
                    grouped_tokens_roman.append(''.join(current_group_roman))
                    current_group_roman = []
                grouped_tokens_roman.append(token)
            else:
                current_group_roman.append(token[0])

            if is_roman:
                arabic_token = roman_to_int(token)
                if current_group_arabic:
                    grouped_tokens_arabic.append(''.join(current_group_arabic))
                    current_group_arabic = []
                grouped_tokens_arabic.append(arabic_token)
            elif is_digit:
                if current_group_arabic:
                    grouped_tokens_arabic.append(''.join(current_group_arabic))
                    current_group_arabic = []
                grouped_tokens_arabic.append(token)
            elif is_ordinal:
                arabic_token = re.sub(r'(st|nd|rd|th)$', '', token, flags=re.IGNORECASE)
                if current_group_arabic:
                    grouped_tokens_arabic.append(''.join(current_group_arabic))
                    current_group_arabic = []
                grouped_tokens_arabic.append(arabic_token)
            else:
                current_group_arabic.append(token[0])

        if current_group_roman:
            grouped_tokens_roman.append(''.join(current_group_roman))
        if current_group_arabic:
            grouped_tokens_arabic.append(''.join(current_group_arabic))

        variants = set()
        if grouped_tokens_roman:
            variants.add(' '.join(grouped_tokens_roman))
            variants.add(''.join(grouped_tokens_roman))
            if len(grouped_tokens_roman) > 1 and any(is_roman_numeral(t) or is_ordinal_number(t) or t.isdigit() for t in grouped_tokens_roman):
                combined_initials = ''.join([t for t in grouped_tokens_roman if not (is_roman_numeral(t) or is_ordinal_number(t) or t.isdigit())])
                numbers = [t for t in grouped_tokens_roman if (is_roman_numeral(t) or is_ordinal_number(t) or t.isdigit())]
                if combined_initials and numbers:
                    variants.add(f"{combined_initials} {' '.join(numbers)}")
        if grouped_tokens_arabic:
            variants.add(' '.join(grouped_tokens_arabic))
            variants.add(''.join(grouped_tokens_arabic))
            if len(grouped_tokens_arabic) > 1 and any(t.isdigit() for t in grouped_tokens_arabic):
                combined_initials = ''.join([t for t in grouped_tokens_arabic if not t.isdigit()])
                numbers = [t for t in grouped_tokens_arabic if t.isdigit()]
                if combined_initials and numbers:
                    variants.add(f"{combined_initials} {' '.join(numbers)}")
        return variants

    abbreviation_candidates = defaultdict(list)
    alt_title_candidates = defaultdict(list)

    def process_game(game):
        normalized_game = ' '.join(basic_preprocessing(game))

        for series_name, abbr in series_abbreviations.items():
            games_in_series = series_games.get(series_name, [])
            if game not in games_in_series:
                continue

            if series_name.endswith('_full_2'):
                base_series = series_name.replace('_full_2', '')
                normalized_base = ' '.join(basic_preprocessing(base_series))
                if normalized_game.startswith(normalized_base):
                    remaining = normalized_game[len(normalized_base):].strip()
                    if remaining:
                        alt_title = f"{abbr} {remaining}"
                        alt_title_candidates[alt_title].append(game)
                        remaining_tokens = remaining.split()
                        normalized_remaining = ' '.join([normalize_token(t) for t in remaining_tokens])
                        if normalized_remaining != remaining:
                            alt_title_candidates[f"{abbr} {normalized_remaining}"].append(game)
                        if remaining_tokens:
                            last_token = remaining_tokens[-1]
                            if is_roman_numeral(last_token) or last_token.isdigit() or is_ordinal_number(last_token):
                                short_alt = f"{abbr} {last_token}"
                                alt_title_candidates[short_alt].append(game)
                                if is_roman_numeral(last_token):
                                    arabic_last = roman_to_int(last_token)
                                    alt_title_candidates[f"{abbr} {arabic_last}"].append(game)
                                elif is_ordinal_number(last_token):
                                    numeric_last = re.sub(r'(st|nd|rd|th)$', '', last_token, flags=re.IGNORECASE)
                                    alt_title_candidates[f"{abbr} {numeric_last}"].append(game)
            elif series_name.endswith('_full'):
                base_series = series_name.replace('_full', '')
                normalized_base = ' '.join(basic_preprocessing(base_series))
                if normalized_game.startswith(normalized_base):
                    remaining = normalized_game[len(normalized_base):].strip()
                    if remaining:
                        alt_title = f"{abbr} {remaining}"
                        alt_title_candidates[alt_title].append(game)
                        remaining_tokens = remaining.split()
                        normalized_remaining = ' '.join([normalize_token(t) for t in remaining_tokens])
                        if normalized_remaining != remaining:
                            alt_title_candidates[f"{abbr} {normalized_remaining}"].append(game)
                        if remaining_tokens:
                            last_token = remaining_tokens[-1]
                            if is_roman_numeral(last_token) or last_token.isdigit() or is_ordinal_number(last_token):
                                short_alt = f"{abbr} {last_token}"
                                alt_title_candidates[short_alt].append(game)
                                if is_roman_numeral(last_token):
                                    arabic_last = roman_to_int(last_token)
                                    alt_title_candidates[f"{abbr} {arabic_last}"].append(game)
                                elif is_ordinal_number(last_token):
                                    numeric_last = re.sub(r'(st|nd|rd|th)$', '', last_token, flags=re.IGNORECASE)
                                    alt_title_candidates[f"{abbr} {numeric_last}"].append(game)
            else:
                normalized_series = ' '.join(basic_preprocessing(series_name))
                if normalized_game.startswith(normalized_series):
                    remaining = normalized_game[len(normalized_series):].strip()
                    if remaining:
                        alt_title = f"{abbr} {remaining}"
                        alt_title_candidates[alt_title].append(game)
                        remaining_tokens = remaining.split()
                        normalized_remaining = ' '.join([normalize_token(t) for t in remaining_tokens])
                        if normalized_remaining != remaining:
                            alt_title_candidates[f"{abbr} {normalized_remaining}"].append(game)
                        if remaining_tokens:
                            last_token = remaining_tokens[-1]
                            if is_roman_numeral(last_token) or last_token.isdigit() or is_ordinal_number(last_token):
                                short_alt = f"{abbr} {last_token}"
                                alt_title_candidates[short_alt].append(game)
                                if is_roman_numeral(last_token):
                                    arabic_last = roman_to_int(last_token)
                                    alt_title_candidates[f"{abbr} {arabic_last}"].append(game)
                                elif is_ordinal_number(last_token):
                                    numeric_last = re.sub(r'(st|nd|rd|th)$', '', last_token, flags=re.IGNORECASE)
                                    alt_title_candidates[f"{abbr} {numeric_last}"].append(game)

        is_in_series = any(game in games for games in series_games.values())

        if ':' in game and not is_in_series:
            main_part, sub_part = game.split(':', 1)
            main_tokens = basic_preprocessing(main_part)
            sub_tokens = basic_preprocessing(sub_part)
            if len(main_tokens) >= 2:
                normalized_main_tokens = [normalize_token(tok) for tok in main_tokens]
                variant1 = ' '.join(normalized_main_tokens + sub_tokens)
                alt_title_candidates[variant1].append(game)

                initials = []
                numbers = []
                for token in main_tokens:
                    if is_roman_numeral(token) or token.isdigit() or is_ordinal_number(token):
                        numbers.append(token)
                    else:
                        initials.append(token[0])
                if initials:
                    abbr_main = ''.join(initials)
                    if numbers:
                        variant2 = f"{abbr_main} {' '.join(numbers)} {' '.join(sub_tokens)}"
                        alt_title_candidates[variant2].append(game)
                        arabic_numbers = []
                        for num in numbers:
                            if is_roman_numeral(num):
                                arabic_numbers.append(roman_to_int(num))
                            elif is_ordinal_number(num):
                                arabic_numbers.append(re.sub(r'(st|nd|rd|th)$', '', num, flags=re.IGNORECASE))
                            else:
                                arabic_numbers.append(num)
                        variant3 = f"{abbr_main} {' '.join(arabic_numbers)} {' '.join(sub_tokens)}"
                        alt_title_candidates[variant3].append(game)
                    else:
                        variant2 = f"{abbr_main} {' '.join(sub_tokens)}"
                        alt_title_candidates[variant2].append(game)

        if ':' in game:
            main_part, sub_part = game.split(':', 1)
            main_tokens = basic_preprocessing(main_part)
            if len(main_tokens) == 1 and is_in_series:
                variants = set()
            else:
                sub_tokens = basic_preprocessing(sub_part)
                all_tokens = main_tokens + sub_tokens
                variants = generate_abbr_variants(all_tokens)
        else:
            all_tokens = basic_preprocessing(game)
            variants = generate_abbr_variants(all_tokens)

        for variant in variants:
            if len(variant) > 1:
                abbreviation_candidates[variant].append(game)

        normalized_tokens = [normalize_token(tok) for tok in basic_preprocessing(game)]
        normalized_title = ' '.join(normalized_tokens)
        if normalized_title != normalized_game:
            alt_title_candidates[normalized_title].append(game)

    # Process all games
    for game in game_list:
        process_game(game)

    def choose_best_game_for_alt(alt_title, games):
        for g in games:
            processed_tokens = [normalize_token(tok) for tok in basic_preprocessing(g)]
            processed_title = ' '.join(processed_tokens)
            if processed_title == alt_title:
                return g
        best = None
        best_score = -1.0
        for g in games:
            norm_g = ' '.join(basic_preprocessing(g))
            score = difflib.SequenceMatcher(None, alt_title, norm_g).ratio()
            if score > best_score:
                best_score = score
                best = g
        return best

    game_abbreviations_kb = OrderedDict()
    game_alt_titles_kb = OrderedDict()

    for abbr, games in abbreviation_candidates.items():
        if len(games) == 1 and len(abbr) > 1:
            if len(abbr) == 2 and abbr.isalpha():
                game = games[0]
                is_in_series = any(game in gs for gs in series_games.values())
                if not is_in_series:
                    continue
            game_abbreviations_kb[abbr] = games[0]

    for alt_title, games in alt_title_candidates.items():
        if not games:
            continue
        if len(games) == 1:
            game_alt_titles_kb[alt_title] = games[0]
        else:
            chosen = choose_best_game_for_alt(alt_title, games)
            if chosen:
                game_alt_titles_kb[alt_title] = chosen

    abbr_keys = set(game_abbreviations_kb.keys())
    game_alt_titles_kb = OrderedDict(
        (alt, game) for alt, game in game_alt_titles_kb.items()
        if alt not in abbr_keys
    )

    return game_abbreviations_kb, game_alt_titles_kb