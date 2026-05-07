import hashlib
import re
from typing import Dict, Any, Optional

class Pseudonymiser:
    """
    Deterministic pseudonymisation service for government business data.
    Ensures PII is never sent to LLMs while maintaining audit traceability.
    """
    
    def __init__(self):
        # In-memory mapping to reverse pseudonymisation for display purposes
        self._mapping: Dict[str, str] = {}

    def _get_hash(self, text: str, length: int = 8) -> str:
        """Helper to generate deterministic hash."""
        if not text:
            return "unknown"
        return hashlib.sha256(text.lower().strip().encode()).hexdigest()[:length]

    def pseudonymise_name(self, name: str) -> str:
        """
        Deterministic: same input always gives same output.
        Returns 'BIZ-' + first 8 chars of SHA256 hash.
        """
        if not name:
            return "BIZ-unknown"
            
        h = self._get_hash(name, 8)
        pseudonym = f"BIZ-{h}"
        
        # Store for restoration (human-in-the-loop reviewers only)
        self._mapping[pseudonym] = name.strip()
        return pseudonym

    def pseudonymise_address(self, address: str) -> str:
        """
        Keeps the pin code (non-PII) and scrambles the rest.
        Returns 'ADDR-{hash}, PIN-{pincode}'
        """
        if not address:
            return "ADDR-none"
            
        # Extract 6-digit pin code if present
        pin_match = re.search(r"\b(\d{6})\b", address)
        pincode = pin_match.group(1) if pin_match else "XXXXXX"
        
        h = self._get_hash(address, 6)
        return f"ADDR-{h}, PIN-{pincode}"

    def pseudonymise_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scrambles all PII fields in a record.
        Keeps: pin_code, sector, district.
        """
        pseudonymised = record.copy()
        
        if "name" in record:
            pseudonymised["name"] = self.pseudonymise_name(record["name"])
            
        if "address" in record:
            pseudonymised["address"] = self.pseudonymise_address(record["address"])
            
        if "pan" in record and record["pan"]:
            pan = str(record["pan"])
            pseudonymised["pan"] = f"PAN-{pan[-4:]}" if len(pan) >= 4 else "PAN-XXXX"
            
        if "gstin" in record and record["gstin"]:
            gstin = str(record["gstin"])
            pseudonymised["gstin"] = f"GST-{gstin[-6:]}" if len(gstin) >= 6 else "GST-XXXXXX"
            
        if "director" in record:
            pseudonymised["director"] = self.pseudonymise_name(record["director"])
            
        return pseudonymised

    def restore_mapping(self, pseudonym: str) -> str:
        """
        Reverses the mapping from the in-memory dict.
        Used for displaying results back to authorized reviewers.
        """
        return self._mapping.get(pseudonym, pseudonym)

# Global singleton instance
pseudonymiser = Pseudonymiser()
