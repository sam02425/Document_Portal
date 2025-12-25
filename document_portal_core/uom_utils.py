"""
Unit of Measure (UOM) Standardization Utilities.
Normalizes various unit of measure formats for POS integration.
"""
from typing import Dict, Optional, Tuple
from logger import GLOBAL_LOGGER as log


class UOMStandardizer:
    """
    Standardizes units of measure across different invoice/receipt formats.
    Essential for POS integration where consistent UOM codes are required.
    """

    # Standard UOM codes with their variations
    UOM_MAPPINGS = {
        # Count/Quantity
        "EA": ["EACH", "E", "PC", "PIECE", "UNIT", "U", "PCS", "PIECES"],
        "CS": ["CASE", "CASES", "C", "CA", "CSE"],
        "BX": ["BOX", "BOXES", "B"],
        "PK": ["PACK", "PACKS", "PAK", "PKG", "PACKAGE"],
        "DZ": ["DOZEN", "DOZ", "DZN"],
        "CT": ["COUNT", "CNT"],

        # Weight
        "LB": ["POUND", "POUNDS", "LBS", "#"],
        "OZ": ["OUNCE", "OUNCES", "ONZ"],
        "KG": ["KILOGRAM", "KILOGRAMS", "KILO", "KILOS"],
        "G": ["GRAM", "GRAMS", "GRM", "GR"],
        "TON": ["TONS", "T", "TN"],

        # Volume - Liquid
        "GAL": ["GALLON", "GALLONS", "GALS", "GL"],
        "QT": ["QUART", "QUARTS", "QTS"],
        "PT": ["PINT", "PINTS", "PTS"],
        "FL OZ": ["FLUID OUNCE", "FLUID OUNCES", "FLOZ", "FO"],
        "L": ["LITER", "LITERS", "LITRE", "LITRES", "LTR"],
        "ML": ["MILLILITER", "MILLILITERS", "MILLILITRE", "MILLILITRES", "MLTR"],

        # Length
        "FT": ["FOOT", "FEET", "F"],
        "IN": ["INCH", "INCHES", "\""],
        "YD": ["YARD", "YARDS", "Y"],
        "M": ["METER", "METERS", "METRE", "METRES", "MTR"],
        "CM": ["CENTIMETER", "CENTIMETERS", "CENTIMETRE", "CENTIMETRES"],

        # Area
        "SQ FT": ["SQUARE FOOT", "SQUARE FEET", "SQFT", "SF"],
        "SQ M": ["SQUARE METER", "SQUARE METRES", "SQM", "SM"],

        # Other
        "ROLL": ["ROLLS", "RL"],
        "BAG": ["BAGS", "BG"],
        "BOTTLE": ["BOTTLES", "BTL", "BTLS"],
        "CAN": ["CANS", "CN"],
        "JAR": ["JARS", "JR"],
        "TUB": ["TUBS"],
        "BAR": ["BARS"],
        "PALLET": ["PALLETS", "PLT", "PLTS"],
        "CARTON": ["CARTONS", "CTN", "CTNS"],
    }

    # Common pack sizes and their standardized forms
    PACK_SIZE_PATTERNS = {
        # 12-pack variations
        "12-PACK": ["12PK", "12 PK", "12PACK", "12 PACK", "12CT", "12 CT"],
        "24-PACK": ["24PK", "24 PK", "24PACK", "24 PACK", "24CT", "24 CT"],
        "6-PACK": ["6PK", "6 PK", "6PACK", "6 PACK", "6CT", "6 CT"],

        # Bottle sizes
        "12OZ": ["12 OZ", "12-OZ", "12 OUNCE"],
        "16OZ": ["16 OZ", "16-OZ", "16 OUNCE"],
        "20OZ": ["20 OZ", "20-OZ", "20 OUNCE"],
        "2L": ["2 LITER", "2L BOTTLE", "2 L"],
    }

    def __init__(self):
        # Create reverse lookup dictionary for fast matching
        self.reverse_map = {}
        for standard, variants in self.UOM_MAPPINGS.items():
            for variant in variants:
                self.reverse_map[variant.upper()] = standard
            # Add the standard code itself
            self.reverse_map[standard.upper()] = standard

    def standardize(self, uom: str) -> str:
        """
        Standardizes a unit of measure string to a standard code.

        Args:
            uom: Unit of measure string (e.g., "CASE", "cs", "each")

        Returns:
            Standardized UOM code (e.g., "CS", "EA")

        Examples:
            "case" -> "CS"
            "EACH" -> "EA"
            "lbs" -> "LB"
            "gallon" -> "GAL"
        """
        if not uom:
            return "EA"  # Default to Each if missing

        # Clean and uppercase
        uom_clean = uom.strip().upper()

        # Direct lookup
        if uom_clean in self.reverse_map:
            return self.reverse_map[uom_clean]

        # Try removing common suffixes and prefixes
        # Remove trailing 's' for plurals
        if uom_clean.endswith("S") and len(uom_clean) > 1:
            uom_singular = uom_clean[:-1]
            if uom_singular in self.reverse_map:
                return self.reverse_map[uom_singular]

        # If no match found, return original (uppercase)
        log.warning(f"Unknown UOM: {uom}, returning as-is")
        return uom_clean

    def parse_pack_size(self, description: str) -> Optional[str]:
        """
        Extracts pack size from product description.

        Args:
            description: Product description (e.g., "Coca-Cola 12oz 24pk")

        Returns:
            Standardized pack size (e.g., "24-PACK") or None

        Examples:
            "Coca-Cola 12oz 24pk" -> "24-PACK"
            "PEPSI 2L 8PK" -> "8-PACK"
        """
        if not description:
            return None

        desc_upper = description.upper()

        # Check against pack size patterns
        for standard, variants in self.PACK_SIZE_PATTERNS.items():
            for variant in variants:
                if variant in desc_upper:
                    return standard

        # Pattern matching for common formats
        import re

        # Match "12pk", "24 pk", "6-pack", etc.
        pack_match = re.search(r"(\d+)\s*[-]?\s*(PK|PACK|CT|COUNT)", desc_upper)
        if pack_match:
            count = pack_match.group(1)
            return f"{count}-PACK"

        # Match bottle/can sizes "12oz", "2L", etc.
        size_match = re.search(r"(\d+)\s*(OZ|L|ML|LITER|OUNCE)", desc_upper)
        if size_match:
            size = size_match.group(1)
            unit = "L" if "L" in size_match.group(2) else "OZ"
            return f"{size}{unit}"

        return None

    def validate_uom(self, uom: str) -> Tuple[bool, Optional[str]]:
        """
        Validates if a UOM is recognized and returns standardized version.

        Args:
            uom: Unit of measure to validate

        Returns:
            (is_valid, standardized_uom) tuple

        Examples:
            "case" -> (True, "CS")
            "xyz" -> (False, None)
        """
        if not uom:
            return False, None

        standardized = self.standardize(uom)

        # Check if it's in our known UOM list
        is_valid = standardized in self.UOM_MAPPINGS

        return is_valid, standardized if is_valid else None

    def convert_quantity(
        self,
        quantity: float,
        from_uom: str,
        to_uom: str,
        conversion_factors: Optional[Dict[str, float]] = None
    ) -> Optional[float]:
        """
        Converts quantity from one UOM to another (basic conversions only).

        Args:
            quantity: Quantity to convert
            from_uom: Source unit of measure
            to_uom: Target unit of measure
            conversion_factors: Optional custom conversion factors

        Returns:
            Converted quantity or None if conversion not supported

        Examples:
            (12, "DZ", "EA") -> 144  (12 dozen = 144 each)
            (2, "GAL", "QT") -> 8    (2 gallons = 8 quarts)

        Note: This is a basic implementation. For complex conversions,
        consider using a library like pint.
        """
        # Standardize UOMs
        from_std = self.standardize(from_uom)
        to_std = self.standardize(to_uom)

        if from_std == to_std:
            return quantity

        # Basic conversion factors
        default_conversions = {
            # Count
            ("DZ", "EA"): 12,
            ("CS", "EA"): 12,  # Assuming typical case = 12 units (customizable)

            # Weight
            ("LB", "OZ"): 16,
            ("KG", "G"): 1000,
            ("TON", "LB"): 2000,

            # Volume - Liquid
            ("GAL", "QT"): 4,
            ("QT", "PT"): 2,
            ("PT", "FL OZ"): 16,
            ("GAL", "FL OZ"): 128,
            ("L", "ML"): 1000,

            # Length
            ("FT", "IN"): 12,
            ("YD", "FT"): 3,
            ("M", "CM"): 100,
        }

        conversions = conversion_factors if conversion_factors else default_conversions

        # Try direct conversion
        if (from_std, to_std) in conversions:
            return quantity * conversions[(from_std, to_std)]

        # Try reverse conversion
        if (to_std, from_std) in conversions:
            return quantity / conversions[(to_std, from_std)]

        log.warning(f"No conversion available from {from_std} to {to_std}")
        return None

    def extract_uom_from_description(self, description: str) -> Optional[str]:
        """
        Attempts to extract UOM from product description.

        Args:
            description: Product description

        Returns:
            Extracted and standardized UOM or None

        Examples:
            "Coca-Cola 12oz Case" -> "CS"
            "Apples per lb" -> "LB"
        """
        if not description:
            return None

        desc_upper = description.upper()

        # Check for each UOM variant in the description
        for standard, variants in self.UOM_MAPPINGS.items():
            # Check standard code
            if f" {standard} " in f" {desc_upper} " or desc_upper.endswith(f" {standard}"):
                return standard

            # Check variants
            for variant in variants:
                if f" {variant} " in f" {desc_upper} " or desc_upper.endswith(f" {variant}"):
                    return standard

        return None


__all__ = ["UOMStandardizer"]
