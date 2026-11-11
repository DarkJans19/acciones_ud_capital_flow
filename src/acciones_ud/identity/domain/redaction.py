import re


def last4(tax_id: str) -> str:
    return tax_id[-4:]


def redact(text: str, tax_id: str = "") -> str:
    if tax_id:
        text = text.replace(tax_id, "***")
    return re.sub(r"[0-9]{5,}", "***", text)[:500]
