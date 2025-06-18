import requests

url = "http://192.168.72.243:8000/api/parse-sms/"

sms_text = """
Umewekewa TSh10,000 kutoka kwa John Doe, Salio lako ni TSh50,000. TxnID:123456789
"""

data = {
    "sms_text": sms_text
}

headers = {
    "Content-Type": "application/json"
}

# ✅ The problem was using 'data=json.dumps(data)'.
# ✅ Use 'json=data' directly.
response = requests.post(url, headers=headers, json=data)

print("Status Code:", response.status_code)
print("Response Body:", response.json())
