"""Test: Real Anthropic Claude calls tracked on Bannin dashboard."""

import os
import time
import anthropic
import bannin

# --- Configure Anthropic ---
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
if not API_KEY:
    API_KEY = input("Paste your Anthropic API key: ").strip()

client = anthropic.Anthropic(api_key=API_KEY)

# --- Wrap with Bannin and start dashboard ---
bannin.wrap(client)

with bannin.watch():
    print()
    print("  Dashboard running at http://localhost:8420")
    print("  Open that URL in your browser now!")
    print()

    prompts = [
        "What is the capital of France? One sentence.",
        "Explain gravity to a 5 year old in 2 sentences.",
        "Write a haiku about coding.",
        "What is 42 * 73?",
        "Name 3 fun facts about octopuses. Keep it brief.",
    ]

    for i, prompt in enumerate(prompts, 1):
        print(f"  [{i}/{len(prompts)}] Sending: {prompt}")
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        print(f"           Reply: {response.content[0].text[:80]}...")
        print()
        time.sleep(3)  # Space out so you can watch the dashboard update live

    print("  All 5 calls done! Check the dashboard LLM card.")
    print("  Press Enter to stop...")
    input()
