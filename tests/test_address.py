import unittest
from unittest.mock import patch
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

from utils.address import AddressExtractor, extract_addresses_from_text

class MockBloom:
    def __init__(self, elements):
        # elements should be upper case without diacritics based on unaccent(w.upper())
        self.elements = set(elements)

    def __contains__(self, item):
        return item in self.elements

class TestAddressExtraction(unittest.TestCase):
    def setUp(self):
        # Reset the singleton before each test to ensure a clean state
        AddressExtractor._instance = None

    def tearDown(self):
        AddressExtractor._instance = None

    @patch('utils.address.Bloom')
    def test_extract_addresses_happy_path(self, mock_bloom_class):
        # Setup mocks
        def bloom_side_effect(path):
            if "streets" in path:
                return MockBloom(['MAIN', 'STREET'])
            elif "municipalities" in path:
                return MockBloom(['BRUSSELS'])
            elif "post_codes" in path:
                return MockBloom(['1000'])
            return MockBloom([])

        mock_bloom_class.side_effect = bloom_side_effect

        text = "My address is Main Street 123 1000 Brussels"
        addresses = extract_addresses_from_text(text, language='be')

        self.assertEqual(len(addresses), 1)
        self.assertEqual(addresses[0], "MAIN STREET 123 1000 BRUSSELS")

    @patch('utils.address.Bloom')
    def test_invalid_language(self, mock_bloom_class):
        addresses = extract_addresses_from_text("Main Street 123 1000 Brussels", language='en')
        self.assertEqual(addresses, [])
        # Also check it didn't even try to load bloom filters
        mock_bloom_class.assert_not_called()

    @patch('utils.address.Bloom')
    def test_failed_bloom_load(self, mock_bloom_class):
        mock_bloom_class.side_effect = Exception("File not found")

        text = "Main Street 123 1000 Brussels"
        addresses = extract_addresses_from_text(text, language='be')

        self.assertEqual(addresses, [])

        # Check that it tried to load and handled the exception
        extractor = AddressExtractor()
        self.assertFalse(extractor.loaded)

    @patch('utils.address.Bloom')
    def test_reset_on_phone_number(self, mock_bloom_class):
        def bloom_side_effect(path):
            if "streets" in path:
                return MockBloom(['MAIN'])
            elif "municipalities" in path:
                return MockBloom(['BRUSSELS'])
            elif "post_codes" in path:
                return MockBloom(['1000'])
            return MockBloom([])

        mock_bloom_class.side_effect = bloom_side_effect

        # 0123456789 should match phone number regex ^[0-9.()/-]{9,20} and reset the found values
        # We start building an address "Main", then hit the phone number, so it resets.
        # Following with the rest of the address wouldn't complete unless it finds at least 4 items.
        text = "Main 0123456789 Street 123 1000 Brussels"
        addresses = extract_addresses_from_text(text, language='be')

        self.assertEqual(addresses, [])

    @patch('utils.address.Bloom')
    def test_reset_on_address_keyword(self, mock_bloom_class):
        def bloom_side_effect(path):
            if "streets" in path:
                return MockBloom(['MAIN'])
            elif "municipalities" in path:
                return MockBloom(['BRUSSELS'])
            elif "post_codes" in path:
                return MockBloom(['1000'])
            return MockBloom([])

        mock_bloom_class.side_effect = bloom_side_effect

        # ADRESSE is in extra_split_terms, resets state
        text = "Main ADRESSE Street 123 1000 Brussels"
        addresses = extract_addresses_from_text(text, language='be')

        self.assertEqual(addresses, [])

    @patch('utils.address.Bloom')
    def test_accept_error_limit(self, mock_bloom_class):
        def bloom_side_effect(path):
            if "streets" in path:
                return MockBloom(['MAIN'])
            elif "municipalities" in path:
                return MockBloom(['BRUSSELS'])
            elif "post_codes" in path:
                return MockBloom(['1000'])
            return MockBloom([])

        mock_bloom_class.side_effect = bloom_side_effect

        # UNKNOWN1 uses 1 error (accept_err = 1)
        # UNKNOWN2 uses 2nd error, resetting the extraction
        text = "Main UNKNOWN1 UNKNOWN2 123 1000 Brussels"
        addresses = extract_addresses_from_text(text, language='be')

        self.assertEqual(addresses, [])

if __name__ == '__main__':
    unittest.main()
