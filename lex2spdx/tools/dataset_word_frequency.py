"""Print most common words in a column of the dataset (with sampling)."""
import json

from tqdm import tqdm

from lex2spdx import map, preprocess, cvar

sample_size = int(1e6)
df = map.load_dataset(sample_size, True)

word_freq = {}
for license_field in tqdm(df["license"]):
    if not isinstance(license_field, str):
        continue
    license_field = preprocess.normalize_license_field(license_field, False, False)
    words = license_field.split()
    for word in words:
        word_freq[word] = word_freq.get(word, 0) + 1

sorted_word_freq = dict(sorted(word_freq.items(), key=lambda item: item[1], reverse=True))

with open(cvar.data_dir / "license_field_word_frequency.json", "w", encoding="utf-8") as f:
    json.dump(dict(list(sorted_word_freq.items())[:100]), f, indent=4)