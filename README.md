# lex2spdx

This project is part of an introductory experiment that tries to answer the question "Can we map free-text license fields with scarce information to exact [SPDX license identifiers](https://spdx.org/licenses/) on a large scale?".

It's a staged pipeline that maps free-text license fields (FTLFs) to exact System Package Data Exchange (SPDX) license identifiers or license families using only ecosystem metadata. The FTLFs are user-defined licenses of Python libraries in the Python Package Index (PyPI), meaning the users should theoretically input the software license, preferably an SPDX identifier, but are allowed to input any text possible, and input any text possible they do. The pipeline normalizes inputs, resolves explicit unknowns, performs exact matching against SPDX identifiers, names, and texts, falls back to license-family labels, and then applies conservative fuzzy matching with tuned confidence to preserve precision. What we get in the end is the exact SPDX identifiers of licenses of numerous Python libraries. Knowing the SPDX identifier means we can map it to an exact license and know all the terms and conditions it specifies. We can then do a lot of automated stuff, because machines work very well with precise inputs, like SPDX identifiers. This allows for some trend analysis of ecosystems, or better software bill of materials generation.

It's currently prepared to run on the PyPI metadata dataset. The used snapshot is available at https://zenodo.org/records/20345847 and can be added to the project at `data/pypi/raw/pypi_versions_05-19-2025.csv`. 

## Results

The large-scale requirement of this project means that the solution naturally had to be very fast. I applied lex2spdx to the unique entries of the full dataset of PyPI package license FTLFs, with size 17,689. The operation completed in 506.33 seconds (8 minutes and 26 seconds). The achieved coverage is 80.81%. Table III shows how many FTLFs each stage has classified.

<img width="399" height="226" alt="image" src="https://github.com/user-attachments/assets/50da4383-55fb-48c1-8832-c6b0bbb56af8" />

I show the equivalence-aware variants of precision and recall. An equivalence-aware metric is one where a prediction is considered correct if it is within the same version family as the ground truth. For example, for a ground truth of GPL-3.0, equivalence-aware metrics will consider the prediction correct if it is one of its same-version variants: GPL-3.0, GPL-3.0+, GPL-3.0-or-later, or GPL-3.0-only. The equivalence-aware recall with a fuzzy matching confidence threshold of 90 is 71.64%, the equivalence-aware precision is 82.05%, and the equivalence-aware F1 score is 76.49% when applied to a test set.
