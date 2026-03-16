import unittest

import lex2spdx.maps


class TestMaps(unittest.TestCase):
    def test_map_exact_match(self):
        map_exact_match = lex2spdx.maps.MapExactMatch()

        self.assertEqual("MIT", map_exact_match.map("MIT License"))
        self.assertIsNone(map_exact_match.map("MIT License "))
        self.assertIsNone(map_exact_match.map("MIT  License"))
        self.assertIsNone(map_exact_match.map("mit  License"))
        self.assertEqual("LGPL-2.0", map_exact_match.map("GNU LIBRARY GENERAL PUBLIC LICENSE Version 2, June 1991"))


if __name__ == '__main__':
    unittest.main()
