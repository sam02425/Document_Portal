
import unittest
from datetime import datetime, timedelta
from document_portal_core.extractor import IDExtractor

class TestIDValidation(unittest.TestCase):
    def setUp(self):
        self.extractor = IDExtractor()

    def test_valid_adult(self):
        # 30 years old, valid expiry
        today = datetime.today()
        dob = today.replace(year=today.year - 30).strftime("%m/%d/%Y")
        exp = (today + timedelta(days=365*2)).strftime("%m/%d/%Y")
        data = {"dob": dob, "expiration_date": exp}
        
        result = self.extractor.validate_id_data(data)
        self.assertTrue(result["valid"])
        self.assertFalse(result["is_expired"])
        self.assertEqual(result["age"], 30)

    def test_expired_id(self):
        # Card expired yesterday
        today = datetime.today()
        dob = today.replace(year=today.year - 30).strftime("%m/%d/%Y")
        exp = (today - timedelta(days=1)).strftime("%m/%d/%Y")
        data = {"dob": dob, "expiration_date": exp}
        
        result = self.extractor.validate_id_data(data)
        self.assertFalse(result["valid"])
        self.assertTrue(result["is_expired"])
        self.assertIn("ID is Expired.", result["errors"])

    def test_under_21(self):
        # 19 years old
        today = datetime.today()
        dob = today.replace(year=today.year - 19).strftime("%m/%d/%Y")
        exp = (today + timedelta(days=365*2)).strftime("%m/%d/%Y")

        data = {"dob": dob, "expiration_date": exp}
        
        result = self.extractor.validate_id_data(data)
        self.assertTrue(result["valid"]) # Still a valid ID, just a warning
        self.assertIn("Under 21 years old.", result["warnings"])
        self.assertEqual(result["age"], 19)

    def test_future_dob(self):
        # Born tomorrow
        dob = (datetime.today() + timedelta(days=1)).strftime("%m/%d/%Y")
        exp = (datetime.today() + timedelta(days=365*20)).strftime("%m/%d/%Y")
        data = {"dob": dob, "expiration_date": exp}
        
        result = self.extractor.validate_id_data(data)
        self.assertFalse(result["valid"])
        self.assertIn("Date of Birth is in the future.", result["errors"])

    def test_bad_formats(self):
        data = {"dob": "invalid", "expiration_date": "12-34-5678"}
        result = self.extractor.validate_id_data(data)
        self.assertIn("Unparseable DOB format.", result["warnings"])

if __name__ == '__main__':
    unittest.main()
