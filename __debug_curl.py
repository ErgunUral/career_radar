import urllib.request, json

url = "http://127.0.0.1:8000/api/v1/logs?limit=5"
try:
    with urllib.request.urlopen(url, timeout=10) as resp:
        print("GET /api/v1/logs status:", resp.status)
        body = resp.read().decode("utf-8")
        print("length:", len(body))
        print("BODY:", body[:500])
except Exception as exc:
    print("HATA:", exc)

print("\n--- POST ---")
payload = json.dumps({"level": "INFO", "source": "pyurllib", "user_id": "default-user", "message": "test urllib"}).encode("utf-8")
req = urllib.request.Request("http://127.0.0.1:8000/api/v1/logs",
    data=payload, headers={"Content-Type": "application/json"}, method="POST")
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        print("POST status:", resp.status)
        print(resp.read().decode("utf-8")[:400])
except urllib.error.HTTPError as he:
    print("HTTP Error:", he.code, he.read().decode("utf-8")[:400])
except Exception as exc:
    print("HATA:", exc)
