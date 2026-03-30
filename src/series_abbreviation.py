import re
import string
from collections import defaultdict, OrderedDict
from nltk.tokenize import RegexpTokenizer

# Initialize tokenizer
tokenizer = RegexpTokenizer(r'\w+')

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
    tokens = tokenizer.tokenize(text)
    return tokens

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

def create_abbreviations(game_list):
    base_series = OrderedDict()
    base_series_games = defaultdict(list)
    covered_games = set()

    # Phase 1: Process colon games
    colon_groups = defaultdict(list)
    for game in game_list:
        if ':' in game:
            front_part = game.split(':', 1)[0].strip()
            tokens = basic_preprocessing(front_part)
            prefix = ' '.join(tokens)
            if prefix == 'the':
                continue
            colon_groups[prefix].append(game)

    for prefix, games in colon_groups.items():
        if len(games) < 2:
            continue
        if len(prefix.split()) == 1:
            abbr = prefix
        else:
            abbr = ''.join(word[0] for word in prefix.split())
        base_series[prefix] = abbr
        for game in games:
            base_series_games[prefix].append(game)
        covered_games.update(games)

    # Phase 2: Process non-colon games
    non_colon_games = [game for game in game_list if game not in covered_games]
    token_map = {}
    normalized_map = {}

    for game in non_colon_games:
        tokens = basic_preprocessing(game)
        token_map[game] = tokens
        normalized_map[game] = ' '.join(tokens)

    prefix_groups = defaultdict(list)
    for game in non_colon_games:
        tokens = token_map[game]
        for n in range(1, len(tokens) + 1):
            prefix = ' '.join(tokens[:n])
            if prefix == 'the':
                continue
            prefix_groups[prefix].append(game)

    valid_groups = {}
    for prefix, games in prefix_groups.items():
        if len(games) < 2:
            continue

        if len(prefix.split()) == 1:
            is_valid = True
            for game in games:
                tokens = token_map[game]
                if len(tokens) < 2:
                    is_valid = False
                    break
                second_token = tokens[1]
                if not (second_token.isdigit() or is_roman_numeral(second_token)):
                    is_valid = False
                    break
            if is_valid:
                valid_groups[prefix] = games
        else:
            valid_groups[prefix] = games

    sorted_groups = sorted(
        valid_groups.items(),
        key=lambda x: (len(x[1]), len(x[0])),
        reverse=True
    )

    non_colon_covered = set()
    for prefix, games in sorted_groups:
        if any(game in non_colon_covered for game in games):
            continue
        word_count = len(prefix.split())
        if word_count == 1:
            abbr = prefix
        else:
            abbr = ''.join(word[0] for word in prefix.split())
        base_series[prefix] = abbr
        for game in games:
            base_series_games[prefix].append(game)
        non_colon_covered.update(games)

    # Phase 3: Konsolidasi base_series
    base_series_list = list(base_series.keys())
    base_series_list_sorted = sorted(base_series_list, key=lambda x: len(x.split()))

    consolidated_base_series_games = defaultdict(list)
    for key, value in base_series_games.items():
        consolidated_base_series_games[key] = value.copy()

    consolidated_base_series = OrderedDict()
    for key, value in base_series.items():
        consolidated_base_series[key] = value

    series_to_remove = set()
    for i, short_prefix in enumerate(base_series_list_sorted):
        for j in range(i+1, len(base_series_list_sorted)):
            long_prefix = base_series_list_sorted[j]
            if long_prefix.startswith(short_prefix + " "):
                consolidated_base_series_games[short_prefix].extend(base_series_games[long_prefix])
                series_to_remove.add(long_prefix)

    for prefix in consolidated_base_series_games:
        consolidated_base_series_games[prefix] = list(OrderedDict.fromkeys(consolidated_base_series_games[prefix]))

    for prefix in series_to_remove:
        if prefix in consolidated_base_series:
            del consolidated_base_series[prefix]
        if prefix in consolidated_base_series_games:
            del consolidated_base_series_games[prefix]

    base_series = consolidated_base_series
    base_series_games = consolidated_base_series_games

    # Phase 4: Create sub-series
    sub_series = OrderedDict()
    sub_series_games = defaultdict(list)

    for base_prefix, games in base_series_games.items():
        if len(games) < 2:
            continue

        sisa_list = []
        for game in games:
            tokens = basic_preprocessing(game)
            normalized_game = ' '.join(tokens)
            if normalized_game.startswith(base_prefix):
                sisa = normalized_game[len(base_prefix):].strip()
            else:
                sisa = normalized_game
            if sisa:
                sisa_list.append((game, sisa))

        if not sisa_list:
            continue

        sisa_token_map = {}
        for game, sisa in sisa_list:
            tokens = sisa.split()
            sisa_token_map[game] = tokens

        sisa_prefix_groups = defaultdict(list)
        for game, sisa in sisa_list:
            tokens = sisa_token_map[game]
            for n in range(1, len(tokens) + 1):
                prefix = ' '.join(tokens[:n])
                sisa_prefix_groups[prefix].append(game)

        valid_sisa_groups = {p: g for p, g in sisa_prefix_groups.items() if len(g) >= 2}
        sorted_sisa_groups = sorted(
            valid_sisa_groups.items(),
            key=lambda x: (len(x[1]), len(x[0])),
            reverse=True
        )

        covered_by_sub = set()
        for sub_prefix, sub_games in sorted_sisa_groups:
            if any(game in covered_by_sub for game in sub_games):
                continue

            words = sub_prefix.split()
            if len(words) == 1:
                sub_abbr = words[0]
                full_abbr = f"{base_series[base_prefix]} {sub_abbr}"
                key = f"{base_prefix} {sub_prefix}"
                sub_series[key] = full_abbr
                sub_series_games[key] = sub_games
            else:
                sub_abbr_initials = ''.join(word[0] for word in words)
                full_abbr_initials = f"{base_series[base_prefix]} {sub_abbr_initials}"
                key_initials = f"{base_prefix} {sub_prefix}"
                sub_series[key_initials] = full_abbr_initials
                sub_series_games[key_initials] = sub_games

                full_abbr_full = f"{base_series[base_prefix]} {sub_prefix}"
                key_full = f"{base_prefix} {sub_prefix}_full"
                sub_series[key_full] = full_abbr_full
                sub_series_games[key_full] = sub_games

                full_abbr_base_full = f"{base_prefix} {sub_abbr_initials}"
                key_base_full = f"{base_prefix} {sub_prefix}_full_2"
                sub_series[key_base_full] = full_abbr_base_full
                sub_series_games[key_base_full] = sub_games

            covered_by_sub.update(sub_games)

    final_series = OrderedDict()
    final_series.update(base_series)
    final_series.update(sub_series)

    all_series_games = {}
    for series in base_series:
        all_series_games[series] = base_series_games[series]
    for series in sub_series:
        all_series_games[series] = sub_series_games[series]

    # Add numeric variants for Roman numerals
    final_series_with_variants = OrderedDict()
    series_games_with_variants = {}

    for name, abbr in final_series.items():
        final_series_with_variants[name] = abbr
        series_games_with_variants[name] = all_series_games[name]

        words = name.split()
        abbr_words = abbr.split()

        new_name_parts = []
        new_abbr_parts = []
        name_changed = False
        abbr_changed = False

        for word in words:
            if is_roman_numeral(word):
                numeric_value = roman_to_int(word)
                new_name_parts.append(numeric_value)
                name_changed = True
            else:
                new_name_parts.append(word)

        for word in abbr_words:
            if is_roman_numeral(word):
                numeric_value = roman_to_int(word)
                new_abbr_parts.append(numeric_value)
                abbr_changed = True
            else:
                new_abbr_parts.append(word)

        if name_changed:
            new_name = ' '.join(new_name_parts)
            new_abbr = ' '.join(new_abbr_parts) if abbr_changed else abbr
            if new_name not in final_series_with_variants:
                final_series_with_variants[new_name] = new_abbr
                series_games_with_variants[new_name] = all_series_games[name]

    return final_series_with_variants, series_games_with_variants