import requests
import json

CLIENT_ID = "XVCOPDQTCRYLINJK"
CLIENT_SECRET = "O5AJ26OS64RIDZTR4HD4ZOFWU4UDQBDC"

resp = requests.get(
    "https://api.ouraring.com/v2/webhook/subscription",
    headers={
        "x-client-id": CLIENT_ID,
        "x-client-secret": CLIENT_SECRET,
        "Content-Type": "application/json"
    }
)

print(resp.status_code)
print(json.dumps(resp.json(), indent=2))