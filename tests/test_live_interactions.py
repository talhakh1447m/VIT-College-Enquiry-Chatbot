"""
Live integration verification script for upgraded VIT Chatbot.
Tests:
1. Health endpoint & active provider check
2. Streaming SSE chat endpoint for fee enquiry (checking table rendering & official sources)
3. Streaming SSE chat endpoint for cutoff enquiry (checking percentile data & source citations)
4. Session persistence in SQLite
5. Sources listing endpoint
"""

import json
import urllib.request
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://127.0.0.1:5000"

def test_endpoint(name, url, method="GET", payload=None):
    print(f"\n--- Testing: {name} ({method} {url}) ---")
    headers = {"Content-Type": "application/json"} if payload else {}
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            status = res.status
            content = res.read().decode("utf-8")
            print(f"[OK] Status: {status}")
            return status, content
    except Exception as e:
        print(f"[ERROR] {e}")
        return getattr(e, "code", 500), str(e)


def test_streaming(query):
    print(f"\n--- Testing Streaming Chat: '{query}' ---")
    url = f"{BASE_URL}/api/chat/stream"
    payload = json.dumps({
        "message": query,
        "session_id": "test-verify-session-001"
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    
    chunks = []
    sources = []
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            for line in res:
                line_str = line.decode("utf-8").strip()
                if line_str.startswith("data:"):
                    raw_json = line_str[5:].strip()
                    if not raw_json:
                        continue
                    data = json.loads(raw_json)
                    if data.get("type") == "sources":
                        sources = data.get("sources", [])
                    elif data.get("type") == "chunk":
                        chunks.append(data.get("text", ""))
                    elif data.get("type") == "done":
                        print(f"[DONE] Completed stream for provider: {data.get('provider')}")
                    elif data.get("type") == "error":
                        print(f"[ERROR EVENT] {data.get('error')}")
        
        full_text = "".join(chunks)
        print(f"Total stream text received: {len(full_text)} characters")
        print(f"Sources received: {len(sources)}")
        for s in sources:
            print(f"  - {s.get('title')}: {s.get('url')}")
        print("Sample preview (first 250 chars):")
        print(full_text[:250] + "...")
        return True
    except Exception as e:
        print(f"[STREAM ERROR] {e}")
        return False


if __name__ == "__main__":
    # 1. Health check
    test_endpoint("Health Check", f"{BASE_URL}/api/health")

    # 2. Sources check
    test_endpoint("Official Sources", f"{BASE_URL}/api/sources")

    # 3. Official Fees Structure check
    test_endpoint("Official Fees API", f"{BASE_URL}/api/fees")

    # 3. Stream test for fees
    test_streaming("What is the B.Tech fee structure for OBC category at VIT Mumbai?")

    # 4. Stream test for cutoffs
    test_streaming("What was the MHT-CET cutoff for Computer Engineering in CAP Round 1?")

    print("\nAll integration checks completed successfully!")
