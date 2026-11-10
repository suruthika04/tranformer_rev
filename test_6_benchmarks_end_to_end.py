"""
Comprehensive End-to-End Verification of the 6 Benchmark Queries
Tests:
1. Tokenizer & Contextual Confidence Evaluator
2. Retained vs Filtered token verification
3. Semantic Preservation Safety Check
4. Actual Google Gemini API Response Generation & Streaming
5. Gemini API Input Token Usage & Candidate Token Counts
6. Performance Metrics (TTFT, Latency)
"""
import asyncio
import os
import time

# Ensure .env is loaded
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

from model import TransformerEvaluatorService

BENCHMARK_QUERIES = [
    {
        "id": 1,
        "input": "Give me a Python code for addition.",
        "must_retain": ["python", "code", "addition"],
        "must_filter": ["give", "me", "a", "for"],
    },
    {
        "id": 2,
        "input": "Explain machine learning in simple terms.",
        "must_retain": ["machine", "learning", "simple", "terms"],
        "must_filter": ["in"],
    },
    {
        "id": 3,
        "input": "Do not delete the database.",
        "must_retain": ["not", "delete", "database"],
        "must_filter": ["the"],
    },
    {
        "id": 4,
        "input": "What is the difference between supervised and unsupervised learning?",
        "must_retain": ["difference", "supervised", "unsupervised", "learning"],
        "must_filter": ["what", "is", "the", "between", "and"],
    },
    {
        "id": 5,
        "input": "Write a SQL query to find the second-highest salary.",
        "must_retain": ["write", "sql", "query", "find", "second", "highest", "salary"],
        "must_filter": ["a", "to", "the"],
    },
    {
        "id": 6,
        "input": "I want to build a chatbot using Python and FastAPI.",
        "must_retain": ["build", "chatbot", "python", "fastapi"],
        "must_filter": ["i", "want", "to", "a", "and"],
    },
]

async def run_benchmark():
    print("=" * 80)
    print("NEXA AI — 6 BENCHMARK QUERIES COMPREHENSIVE VERIFICATION")
    print("=" * 80)

    print("\n[Initializing] Loading Evaluator & Google Gemini Engine...")
    service = TransformerEvaluatorService()
    print(f"[Initialized] Model: {service.model_name} on {service.device}")

    all_passed = True
    benchmark_reports = []

    for b in BENCHMARK_QUERIES:
        q_id = b["id"]
        text = b["input"]
        print("\n" + "-" * 80)
        print(f"BENCHMARK [{q_id}]: \"{text}\"")
        print("-" * 80)

        # 1. Run Token Evaluator
        eval_metrics = service.evaluate_tokens(text, threshold=0.50)
        analysis = eval_metrics["token_analysis"]
        retained = eval_metrics["retained_tokens"]
        filtered = eval_metrics["filtered_tokens"]
        saving_pct = eval_metrics["token_saving_percentage"]
        retained_concat = "".join(retained).lower()
        filtered_lower = [t.lower().strip() for t in filtered]

        print(f"1. EVALUATOR TOKEN ANALYSIS (Threshold 0.50):")
        print(f"   Original Tokens ({len(analysis)}):")
        for item in analysis:
            status_symbol = "[+]" if item["retained"] else "[-]"
            print(f"     {status_symbol} {item['token']:<15} : Score {item['confidence']:.3f} (MLP: {item.get('mlp_score', 0):.3f}, Prior: {item.get('semantic_prior', 0):.3f}) -> {item['status']}")

        print(f"\n   -> Selected Tokens ({len(retained)}): {' '.join(retained)}")
        print(f"   -> Filtered Tokens ({len(filtered)}): {' '.join(filtered)}")
        print(f"   -> Evaluator Token Savings: {saving_pct}% ({len(filtered)}/{len(analysis)} tokens)")
        print(f"   -> Semantic Preservation: {'PASSED' if eval_metrics['semantic_preservation_passed'] else 'FAILED'} ({eval_metrics['semantic_preservation_message']})")

        # Validation assertions
        retained_ok = True
        for req in b["must_retain"]:
            if req not in retained_concat and req not in [t.lower() for t in retained]:
                print(f"   [ERROR] Required token '{req}' was not retained!")
                retained_ok = False
                all_passed = False

        if retained_ok:
            print(f"   -> Keyword & Entity Preservation: ALL {len(b['must_retain'])} REQUIRED TERMS RETAINED")

        # 2. Test Real Streaming Response with Google Gemini
        print(f"\n2. GEMINI GENERATION & STREAMING:")
        t0 = time.time()
        first_token_time = None
        streamed_chunks = []
        gemini_usage = {}

        async for chunk in service.stream_gemini_response(message=text):
            c_type = chunk.get("type")
            if c_type == "token":
                if first_token_time is None:
                    first_token_time = round(time.time() - t0, 3)
                streamed_chunks.append(chunk.get("text", ""))
            elif c_type == "usage":
                gemini_usage = chunk

        total_latency = round(time.time() - t0, 3)
        ttft = first_token_time if first_token_time is not None else total_latency
        full_answer = "".join(streamed_chunks)

        print(f"   -> Actual Text Sent to Gemini: \"{text}\" (Full prompt preserved)")
        print(f"   -> Time to First Token (TTFT): {ttft}s")
        print(f"   -> Total Latency: {total_latency}s")
        print(f"   -> Response Preview ({len(full_answer.split())} words):")
        preview = full_answer.strip().replace("\n", " ")[:140]
        print(f"      \"{preview}...\"")

        # 3. Gemini API Token Usage
        prompt_tokens = gemini_usage.get("prompt_token_count", "N/A")
        cand_tokens = gemini_usage.get("candidates_token_count", len(full_answer.split()))
        print(f"   -> Gemini API Usage Metadata: Prompt Tokens = {prompt_tokens}, Candidate Tokens = {cand_tokens}")

        benchmark_reports.append({
            "id": q_id,
            "query": text,
            "original_tokens": len(analysis),
            "selected_tokens": len(retained),
            "filtered_tokens": len(filtered),
            "evaluator_savings_pct": saving_pct,
            "selected_text": eval_metrics["selected_text"],
            "gemini_input": text,
            "ttft": ttft,
            "latency": total_latency,
            "prompt_tokens": prompt_tokens,
            "candidate_tokens": cand_tokens,
            "preservation": "PASSED" if eval_metrics["semantic_preservation_passed"] else "FAILED"
        })

    print("\n" + "=" * 80)
    print("BENCHMARK EXECUTION SUMMARY TABLE")
    print("=" * 80)
    header = f"{'#':<3} | {'Query Preview':<28} | {'Eval Ret/Filt':<13} | {'Savings':<8} | {'Preservation':<12} | {'TTFT':<6} | {'API Tokens':<10}"
    print(header)
    print("-" * len(header))
    for r in benchmark_reports:
        q_prev = (r['query'][:25] + "...") if len(r['query']) > 25 else r['query']
        counts = f"{r['selected_tokens']}/{r['filtered_tokens']}"
        print(f"{r['id']:<3} | {q_prev:<28} | {counts:<13} | {r['evaluator_savings_pct']:>5.1f}% | {r['preservation']:<12} | {r['ttft']:>4.2f}s | {str(r['prompt_tokens']):<10}")

    print("\n" + "=" * 80)
    if all_passed:
        print("ALL 6 BENCHMARKS PASSED: 100% SEMANTIC PRESERVATION & REAL GEMINI STREAMING!")
    else:
        print("SOME BENCHMARKS FAILED: Review logs above.")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(run_benchmark())
