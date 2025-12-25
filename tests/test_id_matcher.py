"""
Unit tests for IDMatcher and AddressNormalizer.
Tests fuzzy name matching, address normalization, and ID-to-contract verification.
"""
import pytest
from document_portal_core.id_matcher import IDMatcher
from document_portal_core.address_utils import AddressNormalizer


@pytest.fixture
def matcher():
    """Fixture for IDMatcher instance."""
    return IDMatcher()


@pytest.fixture
def address_normalizer():
    """Fixture for AddressNormalizer instance."""
    return AddressNormalizer()


class TestNameMatching:
    """Tests for name matching functionality."""

    def test_exact_name_match(self, matcher):
        """Test exact name match."""
        result = matcher.match_names("John Smith", "John Smith")
        assert result["match"] is True
        assert result["score"] == 100
        assert result["method"] == "exact"

    def test_case_insensitive_match(self, matcher):
        """Test case-insensitive matching."""
        result = matcher.match_names("John Smith", "JOHN SMITH")
        assert result["match"] is True
        assert result["score"] == 100

    def test_middle_name_variation(self, matcher):
        """Test matching with middle name variations."""
        # Full middle name vs initial
        result = matcher.match_names("John Michael Smith", "John M. Smith")
        assert result["match"] is True
        assert result["score"] >= 85

    def test_name_order_variation(self, matcher):
        """Test matching with different name orders."""
        # "First Last" vs "Last, First"
        result = matcher.match_names("John Smith", "Smith, John")
        assert result["match"] is True
        assert result["score"] >= 85

    def test_fuzzy_name_match(self, matcher):
        """Test fuzzy matching for slight variations."""
        result = matcher.match_names("John Smith", "Jon Smith")  # Typo
        # Should still match with high score (depending on fuzzy lib availability)
        assert result["score"] > 70

    def test_non_matching_names(self, matcher):
        """Test that completely different names don't match."""
        result = matcher.match_names("John Smith", "Jane Doe")
        assert result["match"] is False
        assert result["score"] < 70

    def test_empty_name_handling(self, matcher):
        """Test handling of empty names."""
        result = matcher.match_names("", "John Smith")
        assert result["match"] is False
        assert result["score"] == 0

    def test_strict_mode(self, matcher):
        """Test strict matching mode."""
        result = matcher.match_names("John Smith", "Jon Smith", strict=True)
        # Strict mode requires higher threshold
        assert "score" in result


class TestNameParsing:
    """Tests for name parsing."""

    def test_parse_three_part_name(self, matcher):
        """Test parsing 'First Middle Last'."""
        parsed = matcher._parse_name("JOHN MICHAEL SMITH")
        assert parsed["first"] == "JOHN"
        assert parsed["middle"] == "MICHAEL"
        assert parsed["last"] == "SMITH"

    def test_parse_two_part_name(self, matcher):
        """Test parsing 'First Last'."""
        parsed = matcher._parse_name("JOHN SMITH")
        assert parsed["first"] == "JOHN"
        assert parsed["middle"] is None
        assert parsed["last"] == "SMITH"

    def test_parse_comma_format(self, matcher):
        """Test parsing 'Last, First Middle'."""
        parsed = matcher._parse_name("SMITH, JOHN MICHAEL")
        assert parsed["first"] == "JOHN"
        assert parsed["middle"] == "MICHAEL"
        assert parsed["last"] == "SMITH"

    def test_parse_single_name(self, matcher):
        """Test parsing single name."""
        parsed = matcher._parse_name("MADONNA")
        assert parsed["first"] == "MADONNA"
        assert parsed["last"] == "MADONNA"  # Fallback


class TestMiddleNameMatching:
    """Tests for middle name matching logic."""

    def test_match_full_vs_initial(self, matcher):
        """Test matching full middle name vs initial."""
        assert matcher._match_middle_names("MICHAEL", "M") is True
        assert matcher._match_middle_names("MICHAEL", "M.") is True

    def test_match_same_middle_names(self, matcher):
        """Test matching same middle names."""
        assert matcher._match_middle_names("MICHAEL", "MICHAEL") is True

    def test_match_different_middle_names(self, matcher):
        """Test non-matching different middle names."""
        assert matcher._match_middle_names("MICHAEL", "MIKE") is False

    def test_match_missing_middle_names(self, matcher):
        """Test that missing middle names don't fail match."""
        assert matcher._match_middle_names(None, "MICHAEL") is True
        assert matcher._match_middle_names("MICHAEL", None) is True


class TestAddressNormalization:
    """Tests for address normalization."""

    def test_normalize_street_type(self, address_normalizer):
        """Test street type normalization."""
        parsed = address_normalizer._parse_street_address("123 MAIN ST")
        assert parsed["street_type"] == "STREET"

    def test_normalize_avenue(self, address_normalizer):
        """Test avenue normalization."""
        parsed = address_normalizer._parse_street_address("456 OAK AVE")
        assert parsed["street_type"] == "AVENUE"

    def test_normalize_directional(self, address_normalizer):
        """Test directional normalization."""
        parsed = address_normalizer._parse_street_address("789 N MAIN ST")
        assert "NORTH" in parsed["street_name"]

    def test_parse_full_address(self, address_normalizer):
        """Test parsing full address with city, state, zip."""
        parsed = address_normalizer.parse_address("123 Main St, Austin, TX 78701")
        assert parsed["number"] == "123"
        assert parsed["street_name"] == "MAIN"
        assert parsed["street_type"] == "STREET"
        assert parsed["city"] == "AUSTIN"
        assert parsed["state"] == "TX"
        assert parsed["zip"] == "78701"

    def test_parse_address_with_unit(self, address_normalizer):
        """Test parsing address with apartment/unit."""
        parsed = address_normalizer.parse_address("123 Main St Apt 5, Austin, TX")
        assert "APT 5" in parsed["unit"]

    def test_normalize_address_string(self, address_normalizer):
        """Test full address normalization."""
        normalized = address_normalizer.normalize("123 main st, austin, tx 78701")
        assert "MAIN STREET" in normalized
        assert "AUSTIN" in normalized
        assert "TX" in normalized


class TestAddressComparison:
    """Tests for address comparison."""

    def test_compare_identical_addresses(self, address_normalizer):
        """Test comparison of identical addresses."""
        addr1 = "123 Main Street, Austin, TX 78701"
        addr2 = "123 Main Street, Austin, TX 78701"
        score, matches = address_normalizer.compare_addresses(addr1, addr2)
        assert score == 100

    def test_compare_street_abbreviation(self, address_normalizer):
        """Test comparison with street type abbreviation."""
        addr1 = "123 Main St, Austin, TX 78701"
        addr2 = "123 Main Street, Austin, TX 78701"
        score, matches = address_normalizer.compare_addresses(addr1, addr2)
        assert score >= 90  # Should match despite abbreviation

    def test_compare_missing_zip(self, address_normalizer):
        """Test comparison with missing ZIP code."""
        addr1 = "123 Main St, Austin, TX"
        addr2 = "123 Main St, Austin, TX 78701"
        score, matches = address_normalizer.compare_addresses(addr1, addr2)
        assert score >= 75  # Should still score high

    def test_compare_different_addresses(self, address_normalizer):
        """Test comparison of different addresses."""
        addr1 = "123 Main St, Austin, TX"
        addr2 = "456 Oak Ave, Dallas, TX"
        score, matches = address_normalizer.compare_addresses(addr1, addr2)
        assert score < 50  # Should score low

    def test_compare_empty_addresses(self, address_normalizer):
        """Test comparison with empty address."""
        score, matches = address_normalizer.compare_addresses("", "123 Main St")
        assert score == 0


class TestDOBMatching:
    """Tests for date of birth matching."""

    def test_match_identical_dob(self, matcher):
        """Test matching identical DOB."""
        result = matcher.match_dob("01/15/1990", "01/15/1990")
        assert result["match"] is True
        assert result["score"] == 100

    def test_match_different_formats(self, matcher):
        """Test matching DOB in different formats."""
        result = matcher.match_dob("01/15/1990", "1990-01-15")
        assert result["match"] is True
        assert result["score"] == 100

    def test_non_matching_dob(self, matcher):
        """Test non-matching DOB."""
        result = matcher.match_dob("01/15/1990", "02/20/1991")
        assert result["match"] is False
        assert result["score"] == 0

    def test_invalid_dob_format(self, matcher):
        """Test handling invalid DOB format."""
        result = matcher.match_dob("invalid", "01/15/1990")
        assert result["match"] is False
        assert "error" in result["method"]


class TestIDToContractMatching:
    """Integration tests for full ID-to-contract matching."""

    def test_full_match_success(self, matcher):
        """Test successful full ID-to-contract match."""
        id_data = {
            "full_name": "John Michael Smith",
            "address": {
                "street": "123 Main St",
                "city": "Austin",
                "state": "TX",
                "zip": "78701"
            },
            "dob": "01/15/1990"
        }

        contract_data = {
            "party_name": "John M. Smith",
            "party_address": "123 Main Street, Austin, TX 78701",
            "party_dob": "01/15/1990"
        }

        result = matcher.match_id_to_contract(id_data, contract_data)

        assert result["overall_match"] is True
        assert result["overall_score"] >= 85
        assert result["recommendation"] == "verified"

    def test_partial_match_review_required(self, matcher):
        """Test partial match requiring review."""
        id_data = {
            "full_name": "John Smith",
            "address": {
                "street": "123 Main St",
                "city": "Austin",
                "state": "TX",
                "zip": "78701"
            },
            "dob": "01/15/1990"
        }

        contract_data = {
            "party_name": "Jon Smith",  # Slight typo
            "party_address": "123 Main St, Austin, TX 78701",
            "party_dob": "01/15/1990"
        }

        result = matcher.match_id_to_contract(id_data, contract_data)

        # Should match but may require review depending on fuzzy threshold
        assert result["overall_score"] >= 60

    def test_no_match_rejected(self, matcher):
        """Test non-matching ID and contract."""
        id_data = {
            "full_name": "John Smith",
            "address": {
                "street": "123 Main St",
                "city": "Austin",
                "state": "TX",
                "zip": "78701"
            },
            "dob": "01/15/1990"
        }

        contract_data = {
            "party_name": "Jane Doe",
            "party_address": "456 Oak Ave, Dallas, TX 75201",
            "party_dob": "02/20/1985"
        }

        result = matcher.match_id_to_contract(id_data, contract_data)

        assert result["overall_match"] is False
        assert result["recommendation"] == "rejected"

    def test_custom_verification_fields(self, matcher):
        """Test with custom verification fields."""
        id_data = {
            "full_name": "John Smith",
            "dob": "01/15/1990"
        }

        contract_data = {
            "party_name": "John Smith",
            "party_dob": "01/15/1990"
        }

        # Only verify name and DOB (skip address)
        result = matcher.match_id_to_contract(
            id_data,
            contract_data,
            verification_fields=["name", "dob"]
        )

        assert "name" in result["field_results"]
        assert "dob" in result["field_results"]
        assert "address" not in result["field_results"]

    def test_missing_id_data(self, matcher):
        """Test handling of missing ID data."""
        id_data = {}
        contract_data = {"party_name": "John Smith"}

        result = matcher.match_id_to_contract(id_data, contract_data)

        assert result["overall_score"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
