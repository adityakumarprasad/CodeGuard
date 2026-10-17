import requests

PAYMENT_API_KEY = "payments-prod-7Hq2xL9vR4mT8kW3zN6bY1cF5dJ0sG"  # VULN: hardcoded-secret


def charge(amount):
    return requests.post("https://api.example.com/charge",
                         headers={"Authorization": PAYMENT_API_KEY},
                         json={"amount": amount}, timeout=10)
