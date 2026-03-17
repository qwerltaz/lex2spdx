import unittest

import lex2spdx.maps


class TestMaps(unittest.TestCase):
    def test_map_exact_ID(self):
        map_exact_id = lex2spdx.maps.MapExactID()

        self.assertEqual("MIT", map_exact_id.map("MIT"))
        self.assertIsNone(map_exact_id.map("MIT License"))
        self.assertIsNone(map_exact_id.map(""))
        self.assertIsNone(map_exact_id.map("GNU LIBRARY GENERAL PUBLIC LICENSE Version 2, June 1991"))

    def test_map_exact_match(self):
        map_exact_match = lex2spdx.maps.MapExactMatch()

        self.assertEqual("MIT", map_exact_match.map("MIT License"))
        self.assertIsNone(map_exact_match.map("MIT License "))
        self.assertIsNone(map_exact_match.map("MIT  License"))
        self.assertIsNone(map_exact_match.map("mit  License"))
        self.assertEqual("LGPL-2.0", map_exact_match.map("GNU LIBRARY GENERAL PUBLIC LICENSE Version 2, June 1991"))

    def test_map_substring(self):
        map_substring = lex2spdx.maps.MapSubstring()

        self.assertEqual("MIT", map_substring.map("MIT License"))
        self.assertEqual("MIT", map_substring.map(" MIT License "))
        self.assertIsNone(map_substring.map("MIT  License"))


if __name__ == '__main__':
    unittest.main()
