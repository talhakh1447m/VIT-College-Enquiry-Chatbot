import urllib.request
import urllib.error
import json

urls = [
    "https://vit-college-enquiry-chatbot.vercel.app/api/health",
    "https://vit-college-enquiry-chatbot.vercel.app/",
    "https://vit-college-enquiry-chatbot.vercel.app/api/index.py"
]

for url in urls:
    print(f"\n--- Testing {url} ---")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as res:
            print("Status:", res.status)
            body = res.read().decode("utf-8", errors="replace")
            print("Body preview:", body[:500])
    except urllib.error.HTTPError as e:
        print("HTTP Error:", e.code)
        body = e.read().decode("utf-8", errors="replace")
        print("Body:", body[:500])
    except Exception as e:
        print("Error:", e)
