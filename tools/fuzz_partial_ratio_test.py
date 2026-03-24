"""Print rapidfuzz partial ratio similarity for hardcoded pairs of strings."""
from rapidfuzz.fuzz import partial_ratio

checks: list[tuple[str, str]] = [
    ("License :: OSI Approved :: Apache Software License",
     "The Apache Software License, Version 1.1 Copyright (c) 2000 The Apache Software Foundation. All "
     "rights reserved. Redistribution and use in source and binary forms, with or without "
     "modification, are permitted provide"),
    ("", ""),
]

for check in checks:
    license_field, ground_truth = check

    print(f"partial ratio for:")
    print(f"{license_field= }")
    print(f"{ground_truth= }")
    print("is ", partial_ratio(*check))
    print()
