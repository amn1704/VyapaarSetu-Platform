import datetime
import re

def calculate_luhn_check_digit(number_str: str) -> int:
    """
    Calculates a check digit for a numeric string using the Luhn algorithm.
    This helps catch transcription errors.
    """
    # Filter only numeric characters for the check
    digits = [int(d) for d in re.sub(r"\D", "", number_str)]
    
    # Luhn algorithm: double every second digit starting from the right (the 2nd to last)
    for i in range(len(digits) - 2, -1, -2):
        digits[i] *= 2
        if digits[i] > 9:
            digits[i] -= 9
            
    total = sum(digits)
    return (10 - (total % 10)) % 10

def generate_ubid_code(sequential_number: int, year: int = None) -> str:
    """
    Generates a UBID based on the nomenclature: UBID-KA-29-YYYY-NNNNNN-C
    Example: UBID-KA-29-2025-004821-7
    """
    if year is None:
        year = datetime.datetime.now().year
        
    prefix = f"UBID-KA-29-{year}-{sequential_number:06d}"
    
    # We use the numeric parts for the check digit
    numeric_base = f"29{year}{sequential_number:06d}"
    check_digit = calculate_luhn_check_digit(numeric_base)
    
    return f"{prefix}-{check_digit}"
