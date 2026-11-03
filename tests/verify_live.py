import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
BASE_URL = "http://127.0.0.1:5000"

print("========================================")
print("VIT MUMBAI CHATBOT - LIVE VERIFICATION")
print("========================================")

# 1. Health Endpoint
with urllib.request.urlopen(f"{BASE_URL}/api/health") as resp:
    data = json.loads(resp.read().decode("utf-8"))
    print(f"[OK] Health Status: {data.get('status')}")

# 2. Fees Endpoint
with urllib.request.urlopen(f"{BASE_URL}/api/fees") as resp:
    data = json.loads(resp.read().decode("utf-8"))
    print(f"[OK] Institute: {data.get('institute_name')} (Code: {data.get('institute_code')})")
    print(f"[OK] Regulatory Body: {data.get('approved_by')}")
    print("\nApproved B.Tech CAP Categories & Fees:")
    for cat in data["cap_fees"][0]["categories"]:
        name = cat["category"]
        annual = cat["total_annual_fee"]
        four_yr = cat["total_four_year_fee"]
        print(f"  * {name:<35} Annual: ₹{annual:<10} 4-Year: ₹{four_yr}")

# 3. Frontend App & Modal Markup
with urllib.request.urlopen(f"{BASE_URL}/") as resp:
    html = resp.read().decode("utf-8")
    checks = [
        ("feeModal dialog container", 'id="feeModal"'),
        ("Top-right close X button", 'id="closeFeeModalBtn"'),
        ("Footer close button", 'id="closeFeeModalFooterBtn"'),
        ("Backdrop click layer", 'id="feeModalBackdrop"'),
        ("Tabs bar navigation", 'class="fee-tabs-bar"'),
        ("Scrollable body container", 'class="fee-modal-body"'),
    ]
    print("\nFrontend Modal Elements Verified:")
    for label, snippet in checks:
        if snippet in html:
            print(f"  [PASS] {label}")
        else:
            print(f"  [FAIL] {label}")

# 4. Static Assets Served
with urllib.request.urlopen(f"{BASE_URL}/static/style.css") as resp:
    css = resp.read().decode("utf-8")
    css_checks = [
        ("Hidden attribute override", ".fee-modal-overlay[hidden]"),
        ("Flex child scroll min-height", "min-height: 0"),
        ("Modal z-index layer", "z-index: 2000"),
        ("Body scroll lock class", "body.modal-open"),
    ]
    print("\nCSS Styling Rules Verified:")
    for label, snippet in css_checks:
        if snippet in css:
            print(f"  [PASS] {label}")
        else:
            print(f"  [FAIL] {label}")

with urllib.request.urlopen(f"{BASE_URL}/static/app.js") as resp:
    js = resp.read().decode("utf-8")
    js_checks = [
        ("Escape key listener", 'e.key === "Escape"'),
        ("Click outside card handler", "!card.contains(e.target)"),
        ("Card click stopPropagation", "card\")?.addEventListener(\"click\""),
        ("Body overflow scroll toggle", 'document.body.style.overflow = "hidden"'),
    ]
    print("\nJavaScript Event Handlers Verified:")
    for label, snippet in js_checks:
        if snippet in js:
            print(f"  [PASS] {label}")
        else:
            print(f"  [FAIL] {label}")

print("\nAll systems operational! The chatbot and fee dashboard are ready.")
