"""
Compliance module for Document Portal.
Handles jurisdiction-specific validations (e.g., Texas Property Code).
"""
from typing import Dict, List, Any

class ComplianceChecker:
    """
    Checks documents against specific legal requirements.
    """
    
    # Texas Residential Lease Requirements (simplified)
    TEXAS_LEASE_REQUIREMENTS = [
        {
            "id": "tx_prop_92_056",
            "description": "Landlord's duty to repair or remedy",
            "keywords": ["repair", "remedy", "condition", "affecting", "physical", "health"],
            "must_contain": "repair or remedy"
        },
        {
            "id": "tx_right_of_entry",
            "description": "Right of entry conditions",
            "keywords": ["access", "entry", "inspection", "notice"],
            "must_contain": "notice" # Usually 24 hours in practice, but 'notice' keyword is valid check
        },
        {
            "id": "tx_security_deposit",
            "description": "Security deposit return timeline (30 days)",
            "keywords": ["security deposit", "return", "refund", "30 days", "thirty days"],
            "must_contain": ["30 days", "thirty days"] 
        }
    ]

    def __init__(self):
        pass

    def check_texas_lease_compliance(self, text: str) -> Dict[str, Any]:
        """
        Checks if a text contains mandatory Texas lease clauses.
        """
        text_lower = text.lower()
        results = []
        passed_count = 0
        
        for req in self.TEXAS_LEASE_REQUIREMENTS:
            check = {"id": req["id"], "description": req["description"], "status": "fail"}
            
            # Simple keyword matching first
            required_phrases = req["must_contain"]
            if isinstance(required_phrases, str):
                required_phrases = [required_phrases]
                
            found = False
            for phrase in required_phrases:
                if phrase in text_lower:
                    found = True
                    break
            
            if found:
                check["status"] = "pass"
                passed_count += 1
            
            results.append(check)
            
        score = (passed_count / len(self.TEXAS_LEASE_REQUIREMENTS)) * 100
        
        return {
            "jurisdiction": "Texas, USA",
            "document_type": "Residential Lease",
            "compliance_score": score,
            "checks": results
        }
