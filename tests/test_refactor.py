import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from document_portal_core.extractor import IDExtractor
from document_portal_core.compliance import ComplianceChecker

def test_id_extractor_regex():
    extractor = IDExtractor()
    # Simulated OCR output
    text = """
    TEXAS DRIVER LICENSE
    DL: 12345678  EXP: 05/20/2028
    LN: DOE  FN: JOHN
    DOB: 01/15/1985
    GENDER: M  HGT: 5-10
    """
    result = extractor.extract_from_text(text)
    data = result["data"]
    
    assert data["license_number"] == "12345678"
    assert data["dob"] == "01/15/1985"
    assert data["expiration_date"] == "05/20/2028"
    assert data["sex"] == "M"
    assert result["confidence"] >= 80

def test_compliance_checker():
    checker = ComplianceChecker()
    # Compliant Lease text
    lease_text = """
    This lease agreement...
    Landlord shall repair or remedy any condition affecting the physical health or safety...
    Security deposit will be returned within 30 days of surrender...
    We provide notice...
    """
    result = checker.check_texas_lease_compliance(lease_text)
    
    assert result["jurisdiction"] == "Texas, USA"
    # Should pass all 3 checks
    assert result["compliance_score"] == 100.0
    
    # Non-Compliant Lease text
    bad_lease = "Use this property as you wish."
    bad_result = checker.check_texas_lease_compliance(bad_lease)
    assert bad_result["compliance_score"] == 0.0

if __name__ == "__main__":
    try:
        test_id_extractor_regex()
        print("ID Extractor Test Passed")
        test_compliance_checker()
        print("Compliance Checker Test Passed")
    except AssertionError as e:
        print(f"Test Failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
