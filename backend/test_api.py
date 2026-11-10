import urllib.request
import json

BASE_URL = "http://127.0.0.1:8000/api"

def make_post_request(url, data_dict):
    req = urllib.request.Request(
        url,
        data=json.dumps(data_dict).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))

def make_get_request(url):
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read().decode('utf-8'))

def test_api():
    print("=" * 60)
    print("Testing Nexa AI - API Endpoints")
    print("=" * 60)

    print("\n1. Testing GET /api/health...")
    h = make_get_request(f"{BASE_URL}/health")
    print("Health response:", h)
    assert h["status"] == "ok"
    assert h["model_loaded"] is True

    print("\n2. Testing POST /api/evaluate with greeting...")
    res1 = make_post_request(f"{BASE_URL}/evaluate", {"text": "Hi", "threshold": 0.50})
    print(f"Answer: {res1['answer']}")
    print(f"Latency: {res1['latency_seconds']}s")
    assert len(res1['answer']) > 0

    print("\n3. Testing POST /api/evaluate with technical question & follow-up...")
    res2 = make_post_request(f"{BASE_URL}/evaluate", {
        "text": "Explain self-attention in simple terms.",
        "threshold": 0.50
    })
    print(f"Answer: {res2['answer'][:120]}...")
    print(f"Input Tokens: {res2['input_tokens']}, Output Tokens: {res2['output_tokens']}")
    print(f"Evaluated Tokens: {res2['evaluated_tokens']}, Selected: {res2['selected_tokens']}, Saved: {res2['tokens_saved']}")
    print(f"Saving Percentage: {res2['token_saving_percentage']}%")

    print("\n4. Testing POST /api/recalculate with threshold=0.75...")
    recalc = make_post_request(f"{BASE_URL}/recalculate", {
        "token_analysis": res2["token_analysis"],
        "threshold": 0.75
    })
    print(f"Recalculated Selected Tokens: {recalc['selected_tokens']}")
    print(f"Recalculated Tokens Saved: {recalc['tokens_saved']}")
    print(f"Recalculated Saving %: {recalc['saving_percentage']}%")
    assert recalc['selected_tokens'] + recalc['tokens_saved'] == recalc['evaluated_tokens']

    print("\n" + "=" * 60)
    print("[SUCCESS] ALL API ENDPOINTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    test_api()
