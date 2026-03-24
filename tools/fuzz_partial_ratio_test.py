"""Print rapidfuzz partial ratio similarity for hardcoded pairs of strings."""

from rapidfuzz.fuzz import partial_ratio

from lex2spdx.load_spdx_licenses import get_licenses

LICENSES = get_licenses()

gpl3_text = LICENSES[4]["text"]

checks: list[tuple[str, str]] = [
    ("License :: OSI Approved :: Apache Software License",
     "The Apache Software License, Version 1.1 Copyright (c) 2000 The Apache Software Foundation. All "
     "rights reserved. Redistribution and use in source and binary forms, with or without "
     "modification, are permitted provide"),
    ("License :: OSI Approved :: Apache Software License", gpl3_text),
    ("1234567890", gpl3_text),
    ("MIT License: http://opensource.org/licenses/MIT", "MIT License"),
    ("http://opensource.org/licenses/MIT", "MIT License"),
]

# for i, l in enumerate(LICENSES):
#     print(i, l["name"])

for check in checks:
    license_field, ground_truth = check

    print(f"{partial_ratio(*check):.2f} partial ratio for:")
    print(f"{license_field= }")
    print(f"{ground_truth= }")
    print()
