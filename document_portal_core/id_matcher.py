"""
ID-to-Contract Matching Module.
Verifies that ID information matches contract party information using fuzzy matching.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from logger import GLOBAL_LOGGER as log
from document_portal_core.address_utils import AddressNormalizer

try:
    from rapidfuzz import fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False
    log.warning("rapidfuzz not installed, falling back to basic string matching")


class IDMatcher:
    """
    Matches ID data against contract party information.
    Handles name variations, address normalization, and DOB verification.
    """

    def __init__(self):
        self.address_normalizer = AddressNormalizer()

    def match_names(self, id_name: str, contract_name: str, strict: bool = False) -> Dict[str, Any]:
        """
        Matches names using fuzzy logic to handle variations.

        Args:
            id_name: Name from ID (e.g., "John Michael Smith")
            contract_name: Name from contract (e.g., "John M. Smith" or "Smith, John")
            strict: If True, require higher similarity threshold (default: False)

        Returns:
            {
                "match": True/False,
                "score": 0-100,
                "method": "exact" | "fuzzy" | "partial",
                "details": {...}
            }

        Handles:
            - Exact match (case-insensitive)
            - Middle name variations (John Michael Smith vs John M. Smith)
            - Name order variations (John Smith vs Smith, John)
            - Nicknames (partial support via fuzzy matching)
        """
        if not id_name or not contract_name:
            return {
                "match": False,
                "score": 0,
                "method": "missing_data",
                "details": "One or both names are missing"
            }

        # Normalize: uppercase, remove extra spaces
        id_name_norm = " ".join(id_name.strip().upper().split())
        contract_name_norm = " ".join(contract_name.strip().upper().split())

        # Exact match
        if id_name_norm == contract_name_norm:
            return {
                "match": True,
                "score": 100,
                "method": "exact",
                "details": "Exact match"
            }

        # Parse names into components
        id_parts = self._parse_name(id_name_norm)
        contract_parts = self._parse_name(contract_name_norm)

        # Strategy 1: First + Last name match (ignore middle)
        first_match = self._fuzzy_compare(id_parts["first"], contract_parts["first"])
        last_match = self._fuzzy_compare(id_parts["last"], contract_parts["last"])

        if first_match > 90 and last_match > 90:
            # Check middle name handling
            middle_match = self._match_middle_names(id_parts["middle"], contract_parts["middle"])

            score = (first_match + last_match) / 2
            if middle_match:
                score = min(score + 5, 100)  # Bonus for middle name match

            threshold = 95 if strict else 85
            return {
                "match": score >= threshold,
                "score": score,
                "method": "fuzzy_components",
                "details": {
                    "first_name_score": first_match,
                    "last_name_score": last_match,
                    "middle_name_match": middle_match
                }
            }

        # Strategy 2: Full fuzzy match (fallback)
        if RAPIDFUZZ_AVAILABLE:
            fuzzy_score = fuzz.token_sort_ratio(id_name_norm, contract_name_norm)
        else:
            # Basic fallback
            fuzzy_score = self._basic_similarity(id_name_norm, contract_name_norm)

        threshold = 90 if strict else 80
        return {
            "match": fuzzy_score >= threshold,
            "score": fuzzy_score,
            "method": "fuzzy_full",
            "details": "Full string fuzzy match"
        }

    def _parse_name(self, name: str) -> Dict[str, Optional[str]]:
        """
        Parses a name into first, middle, last components.

        Handles:
            - "John Michael Smith" -> {first: John, middle: Michael, last: Smith}
            - "Smith, John" -> {first: John, middle: None, last: Smith}
            - "John M. Smith" -> {first: John, middle: M, last: Smith}
        """
        name = name.strip()

        # Handle "Last, First Middle" format
        if "," in name:
            parts = name.split(",")
            last = parts[0].strip()
            rest = parts[1].strip().split() if len(parts) > 1 else []
            first = rest[0] if rest else None
            middle = " ".join(rest[1:]) if len(rest) > 1 else None
            return {"first": first, "middle": middle, "last": last}

        # Handle "First Middle Last" format
        parts = name.split()
        if len(parts) == 1:
            return {"first": parts[0], "middle": None, "last": parts[0]}
        elif len(parts) == 2:
            return {"first": parts[0], "middle": None, "last": parts[1]}
        else:
            return {"first": parts[0], "middle": " ".join(parts[1:-1]), "last": parts[-1]}

    def _match_middle_names(self, middle1: Optional[str], middle2: Optional[str]) -> bool:
        """
        Matches middle names, handling abbreviations.

        Examples:
            - "Michael" vs "M" -> True
            - "Michael" vs "M." -> True
            - "Michael" vs "Mike" -> False (different names)
            - None vs "Michael" -> True (one missing is OK)
        """
        if not middle1 or not middle2:
            return True  # If one is missing, don't penalize

        # Remove periods and normalize
        m1 = middle1.replace(".", "").strip()
        m2 = middle2.replace(".", "").strip()

        if m1 == m2:
            return True

        # Check if one is initial of the other
        if len(m1) == 1 and m2.startswith(m1):
            return True
        if len(m2) == 1 and m1.startswith(m2):
            return True

        return False

    def _fuzzy_compare(self, str1: Optional[str], str2: Optional[str]) -> float:
        """Fuzzy string comparison returning 0-100 score."""
        if not str1 or not str2:
            return 0.0

        if str1 == str2:
            return 100.0

        if RAPIDFUZZ_AVAILABLE:
            return float(fuzz.ratio(str1, str2))
        else:
            return self._basic_similarity(str1, str2)

    def _basic_similarity(self, str1: str, str2: str) -> float:
        """Basic character-based similarity (fallback)."""
        if not str1 or not str2:
            return 0.0

        set1 = set(str1)
        set2 = set(str2)
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))

        return (intersection / union * 100) if union > 0 else 0.0

    def match_addresses(self, id_address: str, contract_address: str) -> Dict[str, Any]:
        """
        Matches addresses using normalization and component comparison.

        Args:
            id_address: Address from ID (e.g., "123 Main St, Austin, TX 78701")
            contract_address: Address from contract (e.g., "123 Main Street, Austin, Texas 78701")

        Returns:
            {
                "match": True/False,
                "score": 0-100,
                "method": "exact" | "normalized" | "fuzzy",
                "component_matches": {...}
            }
        """
        if not id_address or not contract_address:
            return {
                "match": False,
                "score": 0,
                "method": "missing_data",
                "details": "One or both addresses are missing"
            }

        score, component_matches = self.address_normalizer.compare_addresses(
            id_address,
            contract_address
        )

        return {
            "match": score >= 70,  # 70% threshold for address match
            "score": score,
            "method": "normalized_comparison",
            "component_matches": component_matches
        }

    def match_dob(self, id_dob: str, contract_dob: str) -> Dict[str, Any]:
        """
        Matches date of birth (exact match required).

        Args:
            id_dob: DOB from ID (MM/DD/YYYY)
            contract_dob: DOB from contract (various formats)

        Returns:
            {
                "match": True/False,
                "score": 100 or 0,
                "method": "exact_date",
                "details": {...}
            }
        """
        if not id_dob or not contract_dob:
            return {
                "match": False,
                "score": 0,
                "method": "missing_data",
                "details": "One or both DOBs are missing"
            }

        # Parse dates (handle multiple formats)
        id_date = self._parse_date(id_dob)
        contract_date = self._parse_date(contract_dob)

        if not id_date or not contract_date:
            return {
                "match": False,
                "score": 0,
                "method": "parsing_error",
                "details": "Failed to parse one or both dates"
            }

        match = id_date == contract_date

        return {
            "match": match,
            "score": 100 if match else 0,
            "method": "exact_date",
            "details": {
                "id_date": id_date.strftime("%Y-%m-%d"),
                "contract_date": contract_date.strftime("%Y-%m-%d")
            }
        }

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parses date from multiple formats."""
        if not date_str:
            return None

        # Try common formats
        formats = [
            "%m/%d/%Y",
            "%m-%d-%Y",
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%d/%m/%Y",
            "%B %d, %Y",  # "January 15, 2000"
            "%b %d, %Y",  # "Jan 15, 2000"
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        return None

    def match_id_to_contract(
        self,
        id_data: Dict[str, Any],
        contract_data: Dict[str, Any],
        verification_fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive matching of ID data against contract party information.

        Args:
            id_data: Extracted ID data (from ID extractor)
            contract_data: Contract party information
            verification_fields: List of fields to verify (default: ["name", "address", "dob"])

        Returns:
            {
                "overall_match": True/False,
                "overall_score": 0-100,
                "field_results": {
                    "name": {...},
                    "address": {...},
                    "dob": {...}
                },
                "recommendation": "verified" | "review_required" | "rejected"
            }

        Example contract_data format:
            {
                "party_name": "John Michael Smith",
                "party_address": "123 Main St, Austin, TX 78701",
                "party_dob": "01/15/1990"
            }
        """
        if verification_fields is None:
            verification_fields = ["name", "address", "dob"]

        field_results = {}

        # Extract ID fields
        id_name = id_data.get("full_name") or ""
        id_address_dict = id_data.get("address", {})
        if isinstance(id_address_dict, dict):
            id_address = f"{id_address_dict.get('street', '')}, {id_address_dict.get('city', '')}, {id_address_dict.get('state', '')} {id_address_dict.get('zip', '')}".strip()
        else:
            id_address = str(id_address_dict) if id_address_dict else ""
        id_dob = id_data.get("dob") or ""

        # Extract contract fields
        contract_name = contract_data.get("party_name") or contract_data.get("name") or ""
        contract_address = contract_data.get("party_address") or contract_data.get("address") or ""
        contract_dob = contract_data.get("party_dob") or contract_data.get("dob") or ""

        # Perform matching
        if "name" in verification_fields:
            field_results["name"] = self.match_names(id_name, contract_name)

        if "address" in verification_fields:
            field_results["address"] = self.match_addresses(id_address, contract_address)

        if "dob" in verification_fields:
            field_results["dob"] = self.match_dob(id_dob, contract_dob)

        # Calculate overall score (weighted average)
        weights = {"name": 0.4, "address": 0.4, "dob": 0.2}
        total_score = 0.0
        total_weight = 0.0

        for field in verification_fields:
            if field in field_results:
                weight = weights.get(field, 0.33)
                total_score += field_results[field]["score"] * weight
                total_weight += weight

        overall_score = total_score / total_weight if total_weight > 0 else 0.0

        # Determine overall match
        # All critical fields must pass for overall match
        critical_matches = [
            field_results.get("name", {}).get("match", False),
            field_results.get("dob", {}).get("match", True),  # DOB optional if not provided
        ]

        overall_match = all(critical_matches) and overall_score >= 70

        # Recommendation
        if overall_score >= 85 and all(field_results.get(f, {}).get("match", False) for f in verification_fields if f in field_results):
            recommendation = "verified"
        elif overall_score >= 60:
            recommendation = "review_required"
        else:
            recommendation = "rejected"

        return {
            "overall_match": overall_match,
            "overall_score": round(overall_score, 2),
            "field_results": field_results,
            "recommendation": recommendation,
            "verification_fields": verification_fields
        }


__all__ = ["IDMatcher"]
