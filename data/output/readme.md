Output dataset columns are of the form:

- `idx`: The 'idx' index of the license in the original dataset.
- `license`: The mapped output SPDX license or category.
- `mapping_type`: The type of mapping (SPDX ID, license family...).
    - `spdx_id`: The license was mapped to a specific SPDX ID.
    - `license_family`: The license was mapped to a license family.
    - `undetermined`: The license could not be determined by any map.
    - `unknown`: The license does not give enough information to map.
- `map_name`: The name of the map that mapped this entry.