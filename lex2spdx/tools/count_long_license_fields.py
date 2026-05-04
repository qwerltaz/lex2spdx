"""Print most common words in a column of the dataset (with sampling)."""
import json

from lex2spdx import map, preprocess, cvar

from tqdm import tqdm

sample_size = int(1e6)
df = map.load_dataset(sample_size, True)

long_fields = 0
for license_field in tqdm(df["license"]):
    license_field_normalized = preprocess.normalize_license_field(license_field)
    if len(license_field_normalized) > 1000:
        long_fields += 1

print(f"Number of long license fields: {long_fields} out of {len(df)} ({long_fields / len(df) * 100:.2f}%)")
# 4%