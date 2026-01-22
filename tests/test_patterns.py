from src.utils.patterns import extract_emails, extract_phones, extract_ico

def test_extract_email():
    text = "Kontakt: info@firma.cz a podpora@firma.cz"
    emails = extract_emails(text)
    assert 'info@firma.cz' in emails
    assert len(emails) == 2

def test_extract_phone_cs():
    text = "Telefon: +420 123 456 789"
    phones = extract_phones(text, 'cs')
    assert '+420123456789' in phones

def test_extract_ico():
    text = "IČO: 12345678"
    ico = extract_ico(text, 'cs')
    assert ico == '12345678'
