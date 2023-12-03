import unittest
from your_module import _parse_numbers

class TestParseNumbers(unittest.TestCase):

    def test_integer(self):
        result = _parse_numbers("42")
        self.assertEqual(result, decimal.Decimal("42"))

    def test_with_kilo(self):
        result = _parse_numbers("1.5K")
        self.assertEqual(result, decimal.Decimal("1500"))

    def test_with_mega(self):
        result = _parse_numbers("2.5M")
        self.assertEqual(result, decimal.Decimal("2500000"))

    # Add more test cases for other units and scenarios

if __name__ == '__main__':
    unittest.main()
