import lex2spdx.map


def test_load_dataset():
    df = lex2spdx.map.load_dataset(100, False)

    assert 0 <= len(df) <= 100 # It drops rows with empty license fields.
    assert list(df.columns) == ['idx', 'pkg_idx', 'name', 'version', 'license', 'description', 'homepage', 'repository',
                                'author', 'maintainer', 'author_email', 'maintainer_email', 'requires_dist']

    lex2spdx.map.load_dataset(0, False)
    lex2spdx.map.load_dataset(0, True)
