import pytest
from bs4 import BeautifulSoup
from src.utils.patterns import extract_phones, extract_org_num, extract_social_media_from_soup, validate_be_org_num, extract_social_media

class TestPatterns:
    def test_validate_be_org_num_edge_cases(self):
        # Happy paths
        assert validate_be_org_num("0403.227.515") is True # 10 digits starting with 0
        assert validate_be_org_num("403.227.515") is True # 9 digits padding to 0
        assert validate_be_org_num("1000.000.021") is True # 10 digits starting with 1. 10000000 % 97 = 76, 97 - 76 = 21

        # Length constraints
        assert validate_be_org_num("403.227.51") is False # Too short (8 digits -> padded to 9)
        assert validate_be_org_num("0403.227.5151") is False # Too long (11 digits)
        assert validate_be_org_num("") is False # Empty

        # Invalid characters (letters only, though it strips them out)
        assert validate_be_org_num("BEABCDEFGH") is False

        # Invalid starting digits
        assert validate_be_org_num("2403.227.515") is False # Starts with 2

        # Invalid range (starts with 0, second digit is 0 or 1)
        assert validate_be_org_num("0100.000.029") is False
        assert validate_be_org_num("0000.000.097") is False

        # Invalid checksums
        assert validate_be_org_num("0403.227.516") is False
        assert validate_be_org_num("1000.000.022") is False
    def test_extract_phones_be(self):
        text = """
        Call us at +32 2 555 12 12 or 02/555.12.12.
        Mobile: 0475 12 34 56.
        International: 0032 475 12 34 56.
        <p>0478 40 68 35<br>
        """
        phones = extract_phones(text, 'be')
        assert '+3225551212' in phones
        assert '025551212' in phones
        assert '0475123456' in phones
        assert '0032475123456' in phones
        assert '0478406835' in phones

    def test_extract_phones_cs(self):
        text = """
        Tel: +420 123 456 789
        S mezerami: +420 111 222 333
        """
        phones = extract_phones(text, 'cz')
        assert '+420123456789' in phones
        assert '+420111222333' in phones

    def test_extract_org_num_be(self):
        # KBC: 0403.227.515
        valid_1 = "Our enterprise number is 0403.227.515."
        valid_2 = "Another one: 0403 227 515" # Space separated
        valid_3 = "With prefix: BE0833.310.766" 
        invalid = "Fake number: 0403.227.516"
        
        assert extract_org_num(valid_1, 'be') == "0403.227.515"
        assert extract_org_num(valid_2, 'be') == "0403 227 515"
        assert extract_org_num(valid_3, 'be') == "BE0833.310.766"
        assert extract_org_num(invalid, 'be') is None
        
        # Test range < 0200.000.000 (starts with 0, second digit must be >= 2)
        invalid_range = "0100.000.000" # Technically valid modulo 97? 10000000 % 97 = 68. 97-68=29. So 0100.000.029 would be modulo valid.
        # Let's construct a modulo-valid but range-invalid number.
        # 0100000029
        invalid_range_mod_ok = "0100.000.029"
        assert extract_org_num(invalid_range_mod_ok, 'be') is None

    def test_extract_org_num_cz(self):
        # Seznam.cz: 25596641
        valid_1 = "IČO: 25596641"
        valid_2 = "ICO 00006947"
        invalid = "Bad ICO 12345678"
        
        assert extract_org_num(valid_1, 'cz') == "25596641"
        assert extract_org_num(valid_2, 'cz') == "00006947"
        assert extract_org_num(invalid, 'cz') is None

    def test_extract_social_media_from_soup(self):
        html = """
        <html>
            <body>
                <a href="https://www.facebook.com/ExamplePage">Facebook</a>
                <a href="https://twitter.com/ExampleUser">Twitter</a>
                <a href="https://instagram.com/example_pic">Instagram</a>
                <a href="https://www.linkedin.com/company/example-co">LinkedIn</a>
                <a href="https://youtube.com/channel/UC123456">YouTube</a>
                <a href="https://goo.gl/maps/xyz">Google Maps</a>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, 'lxml')
        socials = extract_social_media_from_soup(soup)
        
        assert socials['facebook'] == "https://www.facebook.com/ExamplePage"
        assert socials['twitter'] == "https://twitter.com/ExampleUser"
        assert socials['instagram'] == "https://instagram.com/example_pic"
        assert socials['linkedin'] == "https://www.linkedin.com/company/example-co"
        assert socials['youtube'] == "https://youtube.com/channel/UC123456"
        assert socials['google_business'] == "https://goo.gl/maps/xyz"

    def test_extract_social_media(self):
        text = """
        Visit us on Facebook: https://www.facebook.com/ExamplePage or FB: http://facebook.com/AnotherPage
        Follow us on X (Twitter): https://twitter.com/ExampleUser
        Check our pics on Instagram: www.instagram.com/example_pic
        Our professional network: https://www.linkedin.com/company/example-co
        Watch our videos on YouTube: https://youtube.com/channel/UC123456
        Find us here: https://goo.gl/maps/xyz
        """
        socials = extract_social_media(text)

        # Test happy path with various URL formats
        assert socials['facebook'] == "https://www.facebook.com/ExamplePage"
        assert socials['twitter'] == "https://twitter.com/ExampleUser"
        assert socials['instagram'] == "www.instagram.com/example_pic"
        assert socials['linkedin'] == "https://www.linkedin.com/company/example-co"
        assert socials['youtube'] == "https://youtube.com/channel/UC123456"
        assert socials['google_business'] == "https://goo.gl/maps/xyz"

        # Test edge cases: negative case (no valid social media links)
        empty_text = "There are no social media links here, just https://www.example.com and www.google.com."
        empty_socials = extract_social_media(empty_text)
        assert empty_socials == {}
