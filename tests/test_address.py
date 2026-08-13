import pytest
from src.utils.address import unaccent

class TestAddressUtils:
    def test_unaccent_basic(self):
        assert unaccent("Hello World") == "Hello World"
        assert unaccent("12345!@#") == "12345!@#"
        assert unaccent("") == ""

    def test_unaccent_cz_sk(self):
        # Czech and Slovak characters
        assert unaccent("Příliš žluťoučký kůň úpěl ďábelské ódy") == "Prilis zlutoucky kun upel dabelske ody"
        assert unaccent("Môj ľúbezný kôň") == "Moj lubezny kon"
        assert unaccent("čťžýáíéäô") == "ctzyaieao"

    def test_unaccent_fr(self):
        # French characters
        assert unaccent("Liberté, Égalité, Fraternité") == "Liberte, Egalite, Fraternite"
        assert unaccent("à, è, ù, â, ê, î, ô, û, ç, ë, ï, ü") == "a, e, u, a, e, i, o, u, c, e, i, u"
        assert unaccent("l'hôpital") == "l'hopital"

    def test_unaccent_nl_de(self):
        # Dutch and German characters
        assert unaccent("Mädchen") == "Madchen"
        assert unaccent("schön") == "schon"
        # Note: the unicode decomposition of ß (Eszett) doesn't reduce it to 'ss'
        # and since it's not ASCII, it gets stripped out by `encode('ascii', 'ignore')`
        assert unaccent("füß") == "fu"
        assert unaccent("Gefühl") == "Gefuhl"

    def test_unaccent_ro(self):
        # Romanian characters
        assert unaccent("ăâîșțĂÂÎȘȚ") == "aaistAAIST"

    def test_unaccent_edge_cases(self):
        # Edge cases and error conditions
        assert unaccent(None) == ""
        assert unaccent(12345) == "12345"
        assert unaccent(3.14) == "3.14"
        assert unaccent(["test"]) == "['test']"
