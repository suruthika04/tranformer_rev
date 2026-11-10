import urllib.request
import urllib.error
import json
import time

BASE_URL = "http://127.0.0.1:8000/api"

def post(endpoint, data):
    req = urllib.request.Request(
        f"{BASE_URL}/{endpoint}",
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))

def get(endpoint):
    with urllib.request.urlopen(f"{BASE_URL}/{endpoint}") as resp:
        return json.loads(resp.read().decode('utf-8'))

def run_all_ten_tests():
    print("=" * 70)
    print("EXECUTING COMPLETE 10-SCENARIO VERIFICATION SUITE")
    print("=" * 70)

    # 1. Test "Hi"
    print("\n[Scenario 1] Testing Greeting: 'Hi'...")
    res1 = post("evaluate", {"text": "Hi", "threshold": 0.50})
    print(f"  -> Answer: {res1['answer'][:100]}...")
    print(f"  -> Evaluated Tokens: {res1['evaluated_tokens']}, Retained: {res1['selected_tokens']}")
    assert len(res1['answer']) > 0
    assert res1['evaluated_tokens'] >= 1

    # 2. Test "What is artificial intelligence?"
    print("\n[Scenario 2] Testing General Knowledge: 'What is artificial intelligence?'...")
    res2 = post("evaluate", {"text": "What is artificial intelligence?", "threshold": 0.50})
    print(f"  -> Answer: {res2['answer'][:120]}...")
    print(f"  -> Evaluated: {res2['evaluated_tokens']}, Selected: {res2['selected_tokens']}, Saved: {res2['tokens_saved']}")
    assert "intelligence" in res2['answer'].lower() or "machine" in res2['answer'].lower() or "ai" in res2['answer'].lower()
    assert res2['evaluated_tokens'] == res2['selected_tokens'] + res2['tokens_saved']

    # 3. Test "Explain self-attention in simple terms."
    print("\n[Scenario 3] Testing Technical Concept: 'Explain self-attention in simple terms.'...")
    res3 = post("evaluate", {"text": "Explain self-attention in simple terms.", "threshold": 0.50})
    print(f"  -> Answer: {res3['answer'][:120]}...")
    print(f"  -> Evaluated: {res3['evaluated_tokens']}, Saving %: {res3['token_saving_percentage']}%")
    assert "attention" in res3['answer'].lower() or "neural" in res3['answer'].lower() or "token" in res3['answer'].lower()

    # 4. Test "Write a Python program to add two numbers."
    print("\n[Scenario 4] Testing Programming: 'Write a Python program to add two numbers.'...")
    res4 = post("evaluate", {"text": "Write a Python program to add two numbers.", "threshold": 0.50})
    print(f"  -> Answer: {res4['answer'][:120]}...")
    assert "def " in res4['answer'] or "add" in res4['answer'] or "+" in res4['answer']

    # 5. Test "Give me an example." after a previous answer
    print("\n[Scenario 5] Testing Contextual Follow-up: 'Give me an example.'...")
    history = [
        {"role": "user", "content": "What is artificial intelligence?"},
        {"role": "assistant", "content": res2['answer']}
    ]
    res5 = post("evaluate", {
        "text": "Give me an example.",
        "threshold": 0.50,
        "history": history
    })
    print(f"  -> Follow-up Answer: {res5['answer'][:140]}...")
    assert len(res5['answer']) > 20

    # 6. Test A long input paragraph
    print("\n[Scenario 6] Testing Long Input Paragraph...")
    long_para = (
        "Transformers rely heavily on self-attention mechanisms to capture long-range dependencies "
        "across sequential data. While self-attention provides superior representation capacity, "
        "its quadratic computational complexity with respect to sequence length presents a substantial "
        "computational bottleneck during inference."
    )
    res6 = post("evaluate", {"text": long_para, "threshold": 0.50})
    print(f"  -> Evaluated Tokens: {res6['evaluated_tokens']}, Selected: {res6['selected_tokens']}, Saved: {res6['tokens_saved']}")
    print(f"  -> Token Saving %: {res6['token_saving_percentage']}%")
    print(f"  -> Answer: {res6['answer'][:120]}...")
    assert res6['evaluated_tokens'] > 20
    assert res6['evaluated_tokens'] == res6['selected_tokens'] + res6['tokens_saved']

    # 7. Test Empty Message
    print("\n[Scenario 7] Testing Empty Message...")
    res7 = post("evaluate", {"text": "   ", "threshold": 0.50})
    print(f"  -> Response: '{res7['answer']}'")
    print(f"  -> Evaluated: {res7['evaluated_tokens']}, Saving %: {res7['token_saving_percentage']}%")
    assert res7['evaluated_tokens'] == 0
    assert res7['token_saving_percentage'] == 0.0

    # 8. Test Genuine Backend/Model Error Handling
    print("\n[Scenario 8] Testing Error Handling on Malformed Request...")
    try:
        req = urllib.request.Request(
            f"{BASE_URL}/evaluate",
            data=b"{\"invalid_json\": true",
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        urllib.request.urlopen(req)
        assert False, "Should have thrown HTTP error"
    except urllib.error.HTTPError as err:
        print(f"  -> Correctly captured HTTP {err.code} on invalid payload.")
        assert err.code in [400, 422]

    # 9. Test Token selection at different thresholds
    print("\n[Scenario 9] Testing Adaptive Token Selection at Multiple Thresholds...")
    test_text = "The cat is sleeping on the mat because it is tired."
    res_base = post("evaluate", {"text": test_text, "threshold": 0.30})
    selected_low = res_base['selected_tokens']
    
    recalc_mid = post("recalculate", {
        "token_analysis": res_base["token_analysis"],
        "threshold": 0.50
    })
    selected_mid = recalc_mid['selected_tokens']

    recalc_high = post("recalculate", {
        "token_analysis": res_base["token_analysis"],
        "threshold": 0.85
    })
    selected_high = recalc_high['selected_tokens']

    print(f"  -> Threshold 0.30: Selected = {selected_low}, Saved = {res_base['tokens_saved']} ({res_base['saving_percentage']}%)")
    print(f"  -> Threshold 0.50: Selected = {selected_mid}, Saved = {recalc_mid['tokens_saved']} ({recalc_mid['saving_percentage']}%)")
    print(f"  -> Threshold 0.85: Selected = {selected_high}, Saved = {recalc_high['tokens_saved']} ({recalc_high['saving_percentage']}%)")
    assert selected_low >= selected_mid >= selected_high
    assert recalc_high['selected_tokens'] + recalc_high['tokens_saved'] == recalc_high['evaluated_tokens']

    # 10. Test A new chat after an existing conversation
    print("\n[Scenario 10] Testing Fresh New Chat Session (No History Carryover)...")
    res10 = post("evaluate", {
        "text": "What is the capital of France?",
        "threshold": 0.50,
        "history": [] # Fresh empty history
    })
    print(f"  -> New Chat Answer: {res10['answer'][:120]}...")
    assert "paris" in res10['answer'].lower() or "france" in res10['answer'].lower()

    print("\n" + "=" * 70)
    print("ALL 10 VERIFICATION SCENARIOS PASSED WITH FLYING COLORS!")
    print("=" * 70)

if __name__ == "__main__":
    run_all_ten_tests()
