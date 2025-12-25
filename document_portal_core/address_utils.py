"""
Address Normalization and Parsing Utilities.
Handles address standardization for matching ID addresses to contract addresses.
"""
import re
from typing import Dict, Optional, Tuple
from logger import GLOBAL_LOGGER as log


class AddressNormalizer:
    """
    Normalizes and parses addresses for fuzzy matching.
    Handles common variations in street types, directionals, and formatting.
    """

    # Street type abbreviations (USPS standard)
    STREET_TYPES = {
        "ALLEY": ["ALY", "ALLEE", "ALLY"],
        "AVENUE": ["AVE", "AV", "AVEN", "AVENU", "AVN", "AVNUE"],
        "BOULEVARD": ["BLVD", "BOUL", "BOULV"],
        "CIRCLE": ["CIR", "CIRC", "CIRCL", "CRCL", "CRCLE"],
        "COURT": ["CT", "CRT"],
        "DRIVE": ["DR", "DRIV", "DRV"],
        "EXPRESSWAY": ["EXPY", "EXP", "EXPRESS", "EXPW"],
        "HIGHWAY": ["HWY", "HIGHWY", "HIWAY", "HIWY"],
        "LANE": ["LN", "LA"],
        "PARKWAY": ["PKWY", "PARKWY", "PKY", "PKWAY"],
        "PLACE": ["PL"],
        "PLAZA": ["PLZ", "PLZA"],
        "ROAD": ["RD"],
        "SQUARE": ["SQ", "SQR", "SQRE", "SQU"],
        "STREET": ["ST", "STR", "STRT"],
        "TERRACE": ["TER", "TERR"],
        "TRAIL": ["TRL", "TRLS"],
        "WAY": ["WY"],
    }

    # Directionals
    DIRECTIONALS = {
        "NORTH": ["N", "NO"],
        "SOUTH": ["S", "SO"],
        "EAST": ["E"],
        "WEST": ["W"],
        "NORTHEAST": ["NE"],
        "NORTHWEST": ["NW"],
        "SOUTHEAST": ["SE"],
        "SOUTHWEST": ["SW"],
    }

    # Unit types
    UNIT_TYPES = {
        "APARTMENT": ["APT", "APPT", "#"],
        "UNIT": ["UN", "UNIT"],
        "SUITE": ["STE", "SU"],
        "BUILDING": ["BLDG", "BLD"],
        "FLOOR": ["FL", "FLR"],
    }

    def __init__(self):
        # Create reverse lookup maps
        self.street_type_map = {}
        for standard, abbrevs in self.STREET_TYPES.items():
            for abbrev in abbrevs:
                self.street_type_map[abbrev.upper()] = standard
            self.street_type_map[standard.upper()] = standard

        self.directional_map = {}
        for standard, abbrevs in self.DIRECTIONALS.items():
            for abbrev in abbrevs:
                self.directional_map[abbrev.upper()] = standard
            self.directional_map[standard.upper()] = standard

    def parse_address(self, address_str: str) -> Dict[str, Optional[str]]:
        """
        Parses an address string into components.

        Args:
            address_str: Full address string (e.g., "123 Main St, Austin, TX 78701")

        Returns:
            {
                "number": "123",
                "street_name": "Main",
                "street_type": "STREET",
                "unit": "Apt 5",
                "city": "Austin",
                "state": "TX",
                "zip": "78701",
                "full_street": "123 MAIN STREET"
            }
        """
        if not address_str:
            return {}

        try:
            # Split by comma to separate street, city, state, zip
            parts = [p.strip() for p in address_str.split(",")]

            result = {
                "number": None,
                "street_name": None,
                "street_type": None,
                "unit": None,
                "city": None,
                "state": None,
                "zip": None,
                "full_street": None
            }

            # Parse street address (first part)
            if parts:
                street_parts = self._parse_street_address(parts[0])
                result.update(street_parts)

            # Parse city (second part if exists)
            if len(parts) > 1:
                result["city"] = parts[1].strip().upper()

            # Parse state and zip (third part if exists)
            if len(parts) > 2:
                state_zip = parts[2].strip()
                state_zip_match = re.search(r"([A-Z]{2})\s*(\d{5}(?:-\d{4})?)?", state_zip.upper())
                if state_zip_match:
                    result["state"] = state_zip_match.group(1)
                    result["zip"] = state_zip_match.group(2) if state_zip_match.group(2) else None

            return result

        except Exception as e:
            log.warning(f"Address parsing failed: {e}")
            return {}

    def _parse_street_address(self, street_str: str) -> Dict[str, Optional[str]]:
        """Parses street address into number, name, type, unit."""
        result = {
            "number": None,
            "street_name": None,
            "street_type": None,
            "unit": None,
            "full_street": None
        }

        # Clean up the string
        street_str = street_str.strip().upper()

        # Extract unit (if present)
        unit_match = re.search(r"(APT|APARTMENT|UNIT|STE|SUITE|#)\s*[#]?\s*([A-Z0-9-]+)", street_str)
        if unit_match:
            result["unit"] = unit_match.group(0)
            # Remove unit from street string
            street_str = street_str.replace(unit_match.group(0), "").strip()

        # Split into words
        words = street_str.split()

        if not words:
            return result

        # First word should be the house number
        if words[0].replace("-", "").isdigit():
            result["number"] = words[0]
            words = words[1:]

        if not words:
            return result

        # Last word might be street type
        if words[-1] in self.street_type_map:
            result["street_type"] = self.street_type_map[words[-1]]
            words = words[:-1]

        # Check if first word is a directional (e.g., "N Main St")
        if words and words[0] in self.directional_map:
            directional = self.directional_map[words[0]]
            words = words[1:]
            # Include directional in street name
            result["street_name"] = f"{directional} {' '.join(words)}" if words else directional
        else:
            # Remaining words are the street name
            result["street_name"] = " ".join(words) if words else None

        # Build full_street
        parts = []
        if result["number"]:
            parts.append(result["number"])
        if result["street_name"]:
            parts.append(result["street_name"])
        if result["street_type"]:
            parts.append(result["street_type"])
        result["full_street"] = " ".join(parts) if parts else None

        return result

    def normalize(self, address_str: str) -> str:
        """
        Normalizes an address to a standard format for matching.

        Args:
            address_str: Address string to normalize

        Returns:
            Normalized address string (uppercase, standardized abbreviations)

        Example:
            "123 main st" -> "123 MAIN STREET"
            "456 N. Oak Ave, Apt 5" -> "456 NORTH OAK AVENUE APT 5"
        """
        if not address_str:
            return ""

        parsed = self.parse_address(address_str)

        # Build normalized string
        parts = []
        if parsed.get("full_street"):
            parts.append(parsed["full_street"])
        if parsed.get("unit"):
            parts.append(parsed["unit"])
        if parsed.get("city"):
            parts.append(parsed["city"])
        if parsed.get("state"):
            parts.append(parsed["state"])
        if parsed.get("zip"):
            parts.append(parsed["zip"])

        return " ".join(parts).upper()

    def compare_addresses(self, addr1: str, addr2: str) -> Tuple[float, Dict[str, bool]]:
        """
        Compares two addresses and returns similarity score.

        Args:
            addr1: First address string
            addr2: Second address string

        Returns:
            (similarity_score, component_matches) tuple where:
            - similarity_score: 0-100 (100 = exact match)
            - component_matches: {"street": True, "city": True, ...}

        Scoring:
            - Exact match: 100
            - Street + City + State match: 90
            - Street + City match: 70
            - Street number + name match: 50
            - Otherwise: 0
        """
        if not addr1 or not addr2:
            return 0.0, {}

        parsed1 = self.parse_address(addr1)
        parsed2 = self.parse_address(addr2)

        matches = {}

        # Compare components
        matches["number"] = parsed1.get("number") == parsed2.get("number")
        matches["street_name"] = self._fuzzy_match(parsed1.get("street_name"), parsed2.get("street_name"))
        matches["street_type"] = parsed1.get("street_type") == parsed2.get("street_type")
        matches["city"] = self._fuzzy_match(parsed1.get("city"), parsed2.get("city"))
        matches["state"] = parsed1.get("state") == parsed2.get("state")
        matches["zip"] = parsed1.get("zip") == parsed2.get("zip")

        # Calculate score
        score = 0.0

        # Full match (street + city + state + zip)
        if matches["number"] and matches["street_name"] and matches["city"] and matches["state"]:
            if matches["zip"]:
                score = 100.0
            else:
                score = 95.0
        # Street + City + State
        elif matches["number"] and matches["street_name"] and matches["city"] and matches["state"]:
            score = 90.0
        # Street + City
        elif matches["number"] and matches["street_name"] and matches["city"]:
            score = 75.0
        # Street only
        elif matches["number"] and matches["street_name"]:
            score = 60.0
        # Street number + partial name
        elif matches["number"] and matches.get("street_name"):
            score = 40.0

        return score, matches

    def _fuzzy_match(self, str1: Optional[str], str2: Optional[str], threshold: float = 0.85) -> bool:
        """
        Fuzzy string matching for street names and cities.
        Handles minor typos and variations.
        """
        if str1 is None or str2 is None:
            return False

        if str1 == str2:
            return True

        # Normalize both strings
        str1 = re.sub(r"[^A-Z0-9]", "", str1.upper())
        str2 = re.sub(r"[^A-Z0-9]", "", str2.upper())

        if str1 == str2:
            return True

        # Simple length-based similarity
        if len(str1) == 0 or len(str2) == 0:
            return False

        # Check if one is substring of the other (e.g., "AUSTIN" vs "AUSTINTX")
        if str1 in str2 or str2 in str1:
            return True

        # Compute simple character overlap
        set1 = set(str1)
        set2 = set(str2)
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))

        similarity = intersection / union if union > 0 else 0
        return similarity >= threshold


__all__ = ["AddressNormalizer"]
