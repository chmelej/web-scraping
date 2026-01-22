import pytest
from bs4 import BeautifulSoup
from src.utils.patterns import extract_phones, extract_org_num, extract_social_media_from_soup

class TestPatterns:
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

    def test_extract_social_media(self):
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
