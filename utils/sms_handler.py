from transactions.models import Transaction, RejectedSMS
from sms_parser.parser import parse_sms
from datetime import datetime
from django.db import IntegrityError

def handle_sms_submission(sms_text):
    # ✅ Clean control characters (multiline to single-line)
    sms_text = sms_text.replace("\r", " ").replace("\n", " ").replace("\t", " ").strip()

    parsed = parse_sms(sms_text)

    result = {
        "saved": False,
        "rejected": False,
        "error": None,
        "parsed": parsed
    }

    if parsed['type'] != 'unknown' and parsed['network_provider'] != 'UNKNOWN':
        try:
            Transaction.objects.create(
                reference_id = parsed.get("reference_id"),
                network_provider = parsed.get("network_provider"),
                type = parsed.get("type"),
                amount = parsed.get("amount"),
                customer_phone = parsed.get("customer_phone") or "UNKNOWN",
                customer_name = parsed.get("customer_name") or "UNKNOWN",
                balance = parsed.get("balance"),
                transaction_fee = parsed.get("transaction_fee"),
                date_transaction = parsed.get("date_transaction") or datetime.now(),
                raw_sms = sms_text
            )
            result["saved"] = True
        except IntegrityError as e:
            if "UNIQUE constraint failed" in str(e):
                result["error"] = "Duplicate transaction"
            else:
                result["error"] = str(e)
    else:
        RejectedSMS.objects.create(
            sender = parsed.get("customer_phone") or "UNKNOWN",
            message = sms_text,
            reason = "Unrecognized provider or transaction type"
        )
        result["rejected"] = True

    return result
