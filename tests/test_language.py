from src.utils.language import detect_language

def test_detect_czech():
    # Make text longer than 50 chars to pass the threshold and use unique czech chars
    html = '<html><body>Příliš žluťoučký kůň úpěl ďábelské ódy. Toto je jasně český text s písmenem ř.</body></html>'
    lang, conf = detect_language(html)
    assert lang == 'cs'
    assert conf > 0.9

def test_detect_from_html_tag():
    html = '<html lang="de"><body>Hello</body></html>'
    lang, conf = detect_language(html)
    assert lang == 'de'
    assert conf == 0.99

def test_detect_unknown():
    html = '<html><body>...</body></html>'
    lang, conf = detect_language(html)
    # Could be unknown or something random, but checks handling
    assert isinstance(lang, str)
    assert isinstance(conf, float)
