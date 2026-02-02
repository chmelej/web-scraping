from src.utils.patterns import extract_phones, extract_org_num

def test_phones():
    print("Testing Phones...")
    
    # BE Tests
    be_text = """
    Call us at +32 2 555 12 12 or 02/555.12.12.
    Mobile: 0475 12 34 56.
    International: 0032 475 12 34 56.
    Garbage: 12345, 0000000000.
    """
    phones_be = extract_phones(be_text, 'be')
    print(f"BE Found: {phones_be}")
    # Expected: Normalized versions of the above numbers

    # CS Tests
    cs_text = """
    Tel: +420 123 456 789
    Bez predvolby: 123 456 789 (Should this be found? Current regex expects 420)
    S mezerami: +420 111 222 333
    """
    phones_cs = extract_phones(cs_text, 'cs')
    print(f"CS Found: {phones_cs}")

def test_org_num():
    print("\nTesting Org Num...")

    # BE Tests
    # KBC: 0403.227.515
    be_valid = "Our enterprise number is 0403.227.515."
    be_valid_2 = "Another one: 0403 227 515" # Space separated
    be_invalid = "Fake number: 0403.227.516"
    
    print(f"BE Valid 1 (0403.227.515): {extract_org_num(be_valid, 'be')}")
    print(f"BE Valid 2 (0403 227 515): {extract_org_num(be_valid_2, 'be')}")
    print(f"BE Invalid (0403.227.516): {extract_org_num(be_invalid, 'be')}")

    # CZ Tests
    # Seznam.cz: 25596641
    cz_valid = "IČO: 25596641"
    cz_valid_2 = "ICO 00006947"
    cz_invalid = "Bad ICO 12345678"
    
    print(f"CZ Valid 1 (25596641): {extract_org_num(cz_valid, 'cs')}")
    print(f"CZ Valid 2 (00006947): {extract_org_num(cz_valid_2, 'cs')}")
    print(f"CZ Invalid (12345678): {extract_org_num(cz_invalid, 'cs')}")

if __name__ == "__main__":
    test_phones()
    test_org_num()