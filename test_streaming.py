"""Test streaming + non-streaming LLM tracking with a real Anthropic API key.

Run: python test_streaming.py
Then check localhost:8420/llm/usage to see tokens tracked for both call types.
"""
import os
import sys
import time

# Ensure bannin is importable
sys.path.insert(0, os.path.dirname(__file__))

import bannin

def main():
    try:
        from anthropic import Anthropic
    except ImportError:
        print("ERROR: anthropic package not installed. Run: pip install anthropic")
        return

    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        key = input("Paste your Anthropic API key: ").strip()
        os.environ["ANTHROPIC_API_KEY"] = key

    client = bannin.wrap(Anthropic(api_key=key))

    with bannin.watch():
        # Give the server a moment to start
        time.sleep(2)

        # --- Test 1: Non-streaming call ---
        print("=" * 60)
        print("TEST 1: Non-streaming call")
        print("=" * 60)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=50,
            messages=[{"role": "user", "content": "Say hello in exactly 5 words."}],
        )
        print(f"Response: {response.content[0].text}")
        print(f"Usage: {response.usage.input_tokens} in / {response.usage.output_tokens} out")
        print()

        # --- Test 2: Streaming call ---
        print("=" * 60)
        print("TEST 2: Streaming call")
        print("=" * 60)
        stream = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=50,
            stream=True,
            messages=[{"role": "user", "content": "Count from 1 to 5, one number per line."}],
        )

        print("Streamed response: ", end="")
        for event in stream:
            event_type = getattr(event, "type", "")
            if event_type == "content_block_delta":
                delta = getattr(event, "delta", None)
                if delta:
                    text = getattr(delta, "text", "")
                    print(text, end="", flush=True)
        print("\n")

        # --- Check results ---
        print("=" * 60)
        print("RESULTS: Checking tracker...")
        print("=" * 60)
        from bannin.llm.tracker import LLMTracker
        tracker = LLMTracker.get()
        summary = tracker.get_summary()

        print(f"Total calls:  {summary['total_calls']}")
        print(f"Total tokens: {summary['total_tokens']}")
        print(f"Total cost:   ${summary['total_cost_usd']}")
        print()

        calls = tracker.get_calls()
        for i, call in enumerate(calls):
            print(f"Call {i+1}: {call['model']} | {call['input_tokens']} in + {call['output_tokens']} out = {call['total_tokens']} tokens | ${call['cost_usd']} | {call['latency_seconds']}s")

        print()
        by_provider = summary.get("by_provider", {})
        for provider, info in by_provider.items():
            print(f"Provider '{provider}': {info['calls']} calls, {info['total_tokens']} tokens, ${info['cost_usd']}")

        print()
        if summary["total_calls"] >= 2 and summary["total_tokens"] > 0:
            print("SUCCESS: Both streaming and non-streaming calls tracked!")
        elif summary["total_calls"] == 1:
            print("PARTIAL: Only one call tracked. Streaming may not have recorded.")
        else:
            print("FAIL: No calls tracked.")

        # Keep server alive briefly so you can check the dashboard
        print("\nDashboard live at http://127.0.0.1:8420 — checking for 10 seconds...")
        time.sleep(10)


if __name__ == "__main__":
    main()
