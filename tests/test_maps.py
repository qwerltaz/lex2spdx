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

        # Title text
        self.assertEqual("MIT", map_exact_match.map("MIT License"))
        self.assertIsNone(map_exact_match.map("MIT License "))
        self.assertIsNone(map_exact_match.map("MIT  License"))
        self.assertIsNone(map_exact_match.map("mit  License"))
        # Name
        self.assertEqual("Unlicense", map_exact_match.map("The Unlicense"))
        # Text
        self.assertEqual("LGPL-2.0", map_exact_match.map("GNU LIBRARY GENERAL PUBLIC LICENSE Version 2, June 1991"))
        self.assertEqual("MIPS", map_exact_match.map(
            "Copyright (c) 1992, 1991, 1990 MIPS Computer Systems, Inc. MIPS Computer Systems, Inc. grants "
            "reproduction and use rights to all parties, PROVIDED that this comment is maintained in the copy."))

    def test_map_substring(self):
        map_substring = lex2spdx.maps.MapSubstring()

        # Title text
        self.assertEqual("MIT", map_substring.map("MIT License"))
        self.assertEqual("MIT", map_substring.map(" MIT License "))
        # Name
        self.assertEqual("Unlicense", map_substring.map("The Unlicense"))
        # Text
        self.assertEqual("MIPS", map_substring.map(
            "Copyright (c) 1992, 1991, 1990 MIPS Computer Systems, Inc. MIPS Computer Systems, Inc. grants "
            "reproduction and use rights to all parties, PROVIDED that this comment is maintained in the copy."))
        self.assertEqual("MIPS", map_substring.map(
            "lipsum Copyright (c) 1992, 1991, 1990 MIPS Computer Systems, Inc. MIPS Computer Systems, Inc. grants "
            "reproduction and use rights to all parties, PROVIDED that this comment is maintained in the copy. lipsum"))

        self.assertIsNone(map_substring.map("MIT  License"))


if __name__ == '__main__':
    unittest.main()
