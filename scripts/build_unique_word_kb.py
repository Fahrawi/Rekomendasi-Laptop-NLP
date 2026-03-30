# scripts/build_unique_word_kb.py
import re
from collections import defaultdict
import string
from nltk.stem import PorterStemmer

def build_unique_word_kb(min_req_df):
    game_list = min_req_df['App'].tolist()
    stemmer = PorterStemmer()
    
    def basic_preprocessing(text):
        text = text.lower()
        text = re.sub(r'[’‘]', "'", text)
        text = re.sub(r"\b(\w+)'s\b", r"\1s", text)
        text = re.sub(r"'", "", text)
        text = re.sub(r'\b((?:[a-z]\.)+[a-z])\b', lambda m: m.group(0).replace('.', ''), text)
        text = re.sub(r'(\w)\.(\w)', r'\1 \2', text)
        text = re.sub(f"[{re.escape(string.punctuation)}]", " ", text)
        return re.compile(r'\w+').findall(text)
    
    token_freq = defaultdict(int)
    for game in game_list:
        tokens = basic_preprocessing(game)
        for token in set(tokens):
            token_freq[token] += 1
    
    stem_freq = defaultdict(int)
    stem_to_tokens = defaultdict(set)
    for token in token_freq:
        if len(token) >= 3 and any(char.isalpha() for char in token):
            stem = stemmer.stem(token)
            stem_freq[stem] += 1
            stem_to_tokens[stem].add(token)
    
    unique_word_kb = {}
    for game in game_list:
        tokens = basic_preprocessing(game)
        unique_tokens = set(tokens)
        for token in unique_tokens:
            if token_freq[token] != 1 or len(token) < 3 or not any(char.isalpha() for char in token):
                continue
            stem = stemmer.stem(token)
            if stem_freq[stem] == 1 and stem in stem_to_tokens:
                unique_word_kb[token] = game
    return unique_word_kb