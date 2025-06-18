import re
import sys
import json
import joblib
from datetime import datetime

# 🔑 Django Model Support (Only if needed)
try:
    import os
    import django
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "your_project_name.settings")
    django.setup()
    from transactions.models import Provider
except:
    Provider = None

# Load trained model
try:
    model = joblib.load("sms_parser/sms_model.pkl")
except:
    model = None

# ✅ Enhanced Reference and Provider Extraction
def extract_reference_and_provider(sms_text, sender=None):
    sms_text = sms_text.strip()
    reference_id = None
    provider = sender or "UNKNOWN"

    # 1️⃣ M-Pesa Reference Patterns (Most Common)
    mpesa_patterns = [
        r'\b([A-Z]{2,3}\d{1,2}[A-Z]\d[A-Z0-9]{6,8})\b',  # Standard M-Pesa format like CCC3H3KXJZV
        r'\b(C[A-Z0-9]{8,12})\b',  # C followed by alphanumeric
        r'(?:Reference|Ref|TxnID|Transaction ID)[\s:]*([A-Z0-9]{8,15})'
    ]
    
    for pattern in mpesa_patterns:
        match = re.search(pattern, sms_text, re.IGNORECASE)
        if match:
            reference_id = match.group(1).upper()
            provider = "M-PESA"
            return reference_id, provider

    # 2️⃣ TigoPesa/Mixx by Yas Reference Patterns
    tigo_patterns = [
        r'(?:Kumbukumbu\s+No[:\.]?\s*)(\d{10,15})',
        r'(?:Kumbukumbu\s+namba[:\s]*)(\d{10,15})',
        r'(?:Kumbukumbu\s+no[:\.]?\s*)(\d{10,15})',
        r'(?:TxnID\s*[:\-]?\s*)(\d{6,15})'
    ]
    
    for pattern in tigo_patterns:
        match = re.search(pattern, sms_text, re.IGNORECASE)
        if match:
            reference_id = match.group(1)
            provider = "TIGOPESA" if "tigo" in sms_text.lower() else "YAS"
            return reference_id, provider

    # 3️⃣ AirtelMoney Reference Patterns
    airtel_patterns = [
        r'(?:TID|Transaction ID|TXN Id|Muamala No)[:\s]*([A-Z]{2}\d{6}\.\d{4}\.[A-Z0-9]{6,8})',
        r'(?:TID|Transaction ID)[:\s]*([A-Z0-9]{10,20})',
        r'Muamala\s+No[:\s]*([A-Z0-9]{10,20})'
    ]
    
    for pattern in airtel_patterns:
        match = re.search(pattern, sms_text, re.IGNORECASE)
        if match:
            reference_id = match.group(1)
            provider = "AIRTELMONEY"
            return reference_id, provider

    # 4️⃣ HaloPesa Reference Patterns
    halo_patterns = [
        r'(?:Utambulisho\s+wa\s+muamala|Utambulisho\s+wa\s+Muamala)[:\s]*(\d{10,15})',
        r'HALODEP(\d+)',  # For deposit references
    ]
    
    for pattern in halo_patterns:
        match = re.search(pattern, sms_text, re.IGNORECASE)
        if match:
            reference_id = match.group(1) if pattern != r'HALODEP(\d+)' else f"HALODEP{match.group(1)}"
            provider = "HALOPESA"
            return reference_id, provider

    # 5️⃣ Generic Reference Patterns (fallback)
    generic_patterns = [
        r'(?:Reference|Ref)[:\s]*([A-Z0-9]{6,15})',
        r'(?:Transaction|Txn)[:\s]*([A-Z0-9]{6,15})'
    ]
    
    for pattern in generic_patterns:
        match = re.search(pattern, sms_text, re.IGNORECASE)
        if match:
            reference_id = match.group(1)
            return reference_id, provider

    return reference_id, provider

# ✅ Enhanced Amount Extraction
def extract_amount(sms_text):
    sms_text = sms_text.lower()
    
    # Enhanced amount patterns covering all scenarios in dataset
    amount_patterns = [
        # Basic patterns
        r'(?:kiasi|amount)[\s:]*tsh[\s:\.]*([\d,]+(?:\.\d{2})?)',
        r'(?:umepokea|received)[\s]*(?:pesa[\s]*)?tsh[\s:\.]*([\d,]+(?:\.\d{2})?)',
        r'(?:umelipa|paid)[\s]*tsh[\s:\.]*([\d,]+(?:\.\d{2})?)',
        r'(?:umetuma|sent)[\s]*tsh[\s:\.]*([\d,]+(?:\.\d{2})?)',
        r'(?:umetoa|withdraw)[\s]*tsh[\s:\.]*([\d,]+(?:\.\d{2})?)',
        r'(?:umeweka|deposit)[\s]*tsh[\s:\.]*([\d,]+(?:\.\d{2})?)',
        r'(?:umeongeza[\s]*salio[\s]*la)[\s]*tsh[\s:\.]*([\d,]+(?:\.\d{2})?)',
        
        # M-Pesa specific
        r'tsh[\s:\.]*([\d,]+(?:\.\d{2})?)[\s]*(?:kutoka|kwenda|kwa)',
        r'tsh[\s:\.]*([\d,]+(?:\.\d{2})?)[\s]*(?:imetumwa|imehamishiwa)',
        
        # Airtel Money specific  
        r'(?:umepokea|umetuma|umetoa|umelipa)[\s]*tsh[\s]*([\d,]+(?:\.\d{2})?)',
        
        # HaloPesa specific
        r'(?:umelipia|umepokea|umetoa)[\s]*tsh[\s]*([\d,]+(?:\.\d{2})?)',
        
        # Yas/TigoPesa specific
        r'kiasi[\s]*tsh[\s]*([\d,]+(?:\.\d{2})?)',
        r'(?:kutoka|kwenda)[\s]*kwa.*?[\s]*tsh[\s]*([\d,]+(?:\.\d{2})?)',
        
        # Fee patterns
        r'(?:ada|kamisheni|makato)[\s]*(?:ya[\s]*)?tsh[\s:\.]*([\d,]+(?:\.\d{2})?)',
        r'(?:mrejaa|fee)[\s]*tsh[\s:\.]*([\d,]+(?:\.\d{2})?)',
        
        # General patterns
        r'tsh[\s:\.]*([\d,]+(?:\.\d{2})?)',
    ]

    for pattern in amount_patterns:
        match = re.search(pattern, sms_text)
        if match:
            amount_str = match.group(1).replace(",", "")
            try:
                return float(amount_str)
            except ValueError:
                continue
    return None

# ✅ Enhanced Customer Info Extraction
def extract_customer_info(sms_text):
    text = sms_text.replace(",", " ").replace(".", " ").replace("-", " ")
    
    # Enhanced phone patterns for Tanzania
    phone_patterns = [
        r'\b(255\d{9})\b',  # 255xxxxxxxxx
        r'\b(0[67]\d{8})\b',  # 06xxxxxxxx or 07xxxxxxxx
        r'\b([67]\d{8})\b',   # 6xxxxxxxx or 7xxxxxxxx
        r'\b(\d{8,9})\b'      # 8-9 digit numbers
    ]
    
    customer_phone = None
    customer_name = "UNKNOWN"
    
    # Extract phone number
    for pattern in phone_patterns:
        match = re.search(pattern, text)
        if match:
            customer_phone = match.group(1)
            break
    
    # Enhanced name extraction patterns
    name_patterns = [
        # Pattern: "kutoka 255xxx - NAME" or "kutoka NAME"
        r'(?:kutoka|from)[\s]*(?:\d+[\s]*-[\s]*)?([A-Z][A-Z\s]+?)(?:\.|,|\s+\d|\s+wakati|\s+salio)',
        
        # Pattern: "kwenda NAME" or "kwa NAME"
        r'(?:kwenda|kwa)[\s]*(?:\d+[\s]*-[\s]*)?([A-Z][A-Z\s]+?)(?:\.|,|\s+\d|\s+salio|\s+wakati)',
        
        # Pattern: "NAME, wakati" or "NAME wakati"
        r'([A-Z][A-Z\s]+?)[\s]*,?[\s]*wakati',
        
        # Pattern for Airtel: "Wakala: NAME"
        r'[Ww]akala:[\s]*([A-Z][A-Z\s]+?)(?:\.|,|\s+\d|\s+salio)',
        
        # Generic capitalized name pattern
        r'([A-Z]{2,}(?:\s+[A-Z]{2,})*(?:\s+[A-Z]{2,})*)',
    ]
    
    for pattern in name_patterns:
        matches = re.findall(pattern, sms_text, re.IGNORECASE)
        if matches:
            # Find the longest meaningful name
            best_name = max(matches, key=len) if matches else ""
            # Clean up the name
            clean_name = ' '.join(word for word in best_name.split() 
                                if word.isalpha() and len(word) > 1 
                                and word.upper() not in ['TSH', 'KWA', 'KUTOKA', 'SALIO', 'WAKATI'])
            if len(clean_name) > 3:
                customer_name = clean_name.strip().upper()
                break

    return customer_name, customer_phone

# ✅ Enhanced Balance Extraction
def extract_balance(sms_text):
    sms_text = sms_text.lower()
    
    balance_patterns = [
        # M-Pesa patterns
        r'salio\s+lako\s+(?:jipya\s+)?(?:la\s+)?(?:m-pesa\s+)?ni\s+tsh[\s:\.]*([\d,]+(?:\.\d{2})?)',
        r'salio\s+(?:jipya\s+)?ni\s+tsh[\s:\.]*([\d,]+(?:\.\d{2})?)',
        r'salio\s+(?:la\s+)?(?:akaunti\s+ya\s+)?(?:mtaji|kazi)\s+ni\s+tsh[\s:\.]*([\d,]+(?:\.\d{2})?)',
        
        # Airtel Money patterns
        r'salio\s+tsh[\s:\.]*([\d,]+(?:\.\d{2})?)',
        
        # HaloPesa patterns
        r'salio\s+lako\s+(?:jipya\s+)?(?:la\s+)?halopesa\s+ni\s+tsh[\s:\.]*([\d,]+(?:\.\d{2})?)',
        
        # Yas/TigoPesa patterns
        r'salio\s+(?:jipya\s+)?ni\s+tsh[\s:\.]*([\d,]+(?:\.\d{2})?)',
        
        # Generic patterns
        r'salio[\s\w]*tsh[\s:\.]*([\d,]+(?:\.\d{2})?)',
    ]

    for pattern in balance_patterns:
        match = re.search(pattern, sms_text)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except ValueError:
                continue
    return None

# ✅ Enhanced Transaction Fee Extraction
def extract_transaction_fee(sms_text):
    sms_text = sms_text.lower()
    
    fee_patterns = [
        # Standard fee patterns
        r'(?:kamisheni|commission)[\s]*(?:pamoja\s+na\s+kodi\s*)?tsh[\s:\.]*([\d,]+(?:\.\d{2})?)',
        r'(?:ada|fee)[\s]*(?:ya\s*)?tsh[\s:\.]*([\d,]+(?:\.\d{2})?)',
        r'(?:makato|deduction)[\s]*tsh[\s:\.]*([\d,]+(?:\.\d{2})?)',
        r'(?:mrejaa|charges)[\s]*tsh[\s:\.]*([\d,]+(?:\.\d{2})?)',
        r'(?:tozo|tax)[\s]*tsh[\s:\.]*([\d,]+(?:\.\d{2})?)',
        
        # Combined fee patterns
        r'jumla\s+ya\s+makato\s+tsh[\s:\.]*([\d,]+(?:\.\d{2})?)',
        r'ada\s+ya\s+huduma[\s]*tsh[\s:\.]*([\d,]+(?:\.\d{2})?)',
        
        # Service fee patterns
        r'ada\s+ya\s+huduma.*?imekatwa[\s]*tsh[\s:\.]*([\d,]+(?:\.\d{2})?)',
    ]

    for pattern in fee_patterns:
        match = re.search(pattern, sms_text)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except ValueError:
                continue
    return None

# ✅ Enhanced Provider Detection
def detect_provider(sender, sms_text):
    if sender is None:
        sender = ""

    sender = sender.strip().upper()
    sms_lower = sms_text.lower()

    # Check Django model first
    if Provider and Provider.objects.filter(name__iexact=sender).exists():
        return sender

    # Provider detection based on SMS content and sender
    if sender in ["MPESA", "M-PESA"] or "m-pesa" in sms_lower:
        return "M-PESA"
    elif sender in ["TIGOPESA", "TIGO"] or "tigo pesa sasa ni mixx by yas" in sms_lower:
        return "YAS"  # TigoPesa is now Mixx by Yas
    elif "mixx by yas" in sms_lower or "yas" in sender:
        return "YAS"
    elif sender in ["AIRTELMONEY", "AIRTEL"] or "airtelmoney" in sms_lower:
        return "AIRTELMONEY"
    elif sender in ["HALOPESA", "HALO"] or "halopesa" in sms_lower:
        return "HALOPESA"

    # Try to detect from reference patterns
    reference_id, provider_from_text = extract_reference_and_provider(sms_text, sender)
    if provider_from_text != "UNKNOWN":
        return provider_from_text

    return "UNKNOWN"

# ✅ Enhanced Transaction Type Detection
def detect_transaction_type(sms_text):
    sms_lower = sms_text.lower()
    
    # Insufficient funds patterns
    if any(phrase in sms_lower for phrase in [
        "hakitoshi", "insufficient", "haukukamilika", "declined", 
        "salio halitoshi", "huduma haikufanikiwa"
    ]):
        return "insufficient_funds"
    
    # Fee notice patterns
    if any(phrase in sms_lower for phrase in [
        "ada ya huduma", "kamisheni pamoja na kodi", "lengo lako",
        "zawadi", "punguzo la tozo", "imekatwa"
    ]) and not any(phrase in sms_lower for phrase in ["umepokea", "umelipa", "umetuma"]):
        return "fee_notice"
    
    # Received patterns
    if any(phrase in sms_lower for phrase in [
        "umepokea", "received", "salio lako jipya ni tsh", "umeongeza salio"
    ]):
        return "received" if "umepokea" in sms_lower else "deposit"
    
    # Payment patterns
    if any(phrase in sms_lower for phrase in [
        "umelipa", "umelipia", "malipo yamekamilika"
    ]):
        return "payment"
    
    # Transfer patterns  
    if any(phrase in sms_lower for phrase in [
        "imehamishiwa", "umetuma", "zoezi la kuhamisha", "imeamishiwa"
    ]):
        return "transfer"
    
    # Withdrawal patterns
    if any(phrase in sms_lower for phrase in [
        "umetoa", "toa tsh", "withdrawal", "kuchukua"
    ]):
        return "withdrawal"
    
    # Deposit patterns
    if any(phrase in sms_lower for phrase in [
        "umeweka", "umeongeza salio", "deposit", "kuweka"
    ]):
        return "deposit"
    
    return "unknown"

# ✅ Enhanced Date Parsing
def parse_transaction_date(sms_text):
    # Multiple date format patterns
    date_patterns = [
        r'(\d{1,2}/\d{1,2}/\d{2,4}\s+\d{1,2}:\d{2}(?::\d{2})?)',  # dd/mm/yyyy hh:mm or dd/mm/yy hh:mm
        r'(\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2}:\d{2})',          # yyyy/mm/dd hh:mm:ss
        r'tarehe\s+(\d{1,2}/\d{1,2}/\d{2,4})\s+(?:saa\s+)?(\d{1,2}:\d{2})',  # tarehe dd/mm/yyyy saa hh:mm
        r'mnamo\s+(\d{1,2}/\d{1,2}/\d{2,4})[,\s]+(\d{1,2}:\d{2})',  # mnamo dd/mm/yyyy, hh:mm
        r'(\d{1,2}/\d{1,2}/\d{2,4})\s+(\d{1,2}:\d{2})',             # dd/mm/yyyy hh:mm separate
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, sms_text)
        if match:
            try:
                if len(match.groups()) == 1:
                    # Single group with full datetime
                    date_str = match.group(1)
                    # Determine format based on content
                    if date_str.count('/') == 2:
                        parts = date_str.split()
                        date_part = parts[0]
                        time_part = parts[1] if len(parts) > 1 else "00:00"
                        
                        date_components = date_part.split('/')
                        if len(date_components[2]) == 2:
                            # 2-digit year
                            year = int(date_components[2])
                            year = 2000 + year if year < 50 else 1900 + year
                            formatted_date = f"{date_components[0]}/{date_components[1]}/{year} {time_part}"
                            return datetime.strptime(formatted_date, "%d/%m/%Y %H:%M")
                        else:
                            # 4-digit year  
                            if date_components[0].isdigit() and int(date_components[0]) > 12:
                                # yyyy/mm/dd format
                                return datetime.strptime(date_str, "%Y/%m/%d %H:%M:%S")
                            else:
                                # dd/mm/yyyy format
                                return datetime.strptime(date_str, "%d/%m/%Y %H:%M")
                else:
                    # Separate date and time groups
                    date_part = match.group(1)
                    time_part = match.group(2)
                    
                    date_components = date_part.split('/')
                    if len(date_components[2]) == 2:
                        year = int(date_components[2])
                        year = 2000 + year if year < 50 else 1900 + year
                        formatted_date = f"{date_components[0]}/{date_components[1]}/{year} {time_part}"
                        return datetime.strptime(formatted_date, "%d/%m/%Y %H:%M")
                    else:
                        return datetime.strptime(f"{date_part} {time_part}", "%d/%m/%Y %H:%M")
                        
            except Exception as e:
                print(f"Date parse error for '{match.group()}': {e}")
                continue
    
    return None

# ✅ Enhanced SMS Parser Entry Point
def parse_sms(sms_text, sender=None):
    result = {
        "reference_id": None,
        "network_provider": None,
        "type": "unknown",
        "amount": None,
        "customer_phone": None,
        "customer_name": None,
        "balance": None,
        "transaction_fee": None,
        "date_transaction": None,
        "raw_sms": sms_text,
        "sender": sender
    }

    # Enhanced transaction type detection
    if model:
        try:
            predicted_type = model.predict([sms_text])[0]
            result["type"] = predicted_type
        except:
            result["type"] = detect_transaction_type(sms_text)
    else:
        result["type"] = detect_transaction_type(sms_text)

    # Extract all fields using enhanced functions
    reference_id, _ = extract_reference_and_provider(sms_text, sender)
    result["reference_id"] = reference_id
    
    result["network_provider"] = detect_provider(sender, sms_text)
    result["amount"] = extract_amount(sms_text)
    result["balance"] = extract_balance(sms_text)
    result["transaction_fee"] = extract_transaction_fee(sms_text)
    
    customer_name, customer_phone = extract_customer_info(sms_text)
    result["customer_phone"] = customer_phone
    result["customer_name"] = customer_name
    
    result["date_transaction"] = parse_transaction_date(sms_text)

    return result

# CLI Test
if __name__ == "__main__":
    sms = sys.argv[1] if len(sys.argv) > 1 else "No SMS provided"
    sender = sys.argv[2] if len(sys.argv) > 2 else None
    parsed = parse_sms(sms, sender)
    print(json.dumps(parsed, indent=4, default=str))

