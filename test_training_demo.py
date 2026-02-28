"""Training simulation that pushes progress to the running Bannin agent.

Requires: bannin CLI agent already running (bannin start or python -m bannin.cli start).
The agent must be connected to the relay server for dashboard display.

Usage:
    python test_training_demo.py
"""

from __future__ import annotations

import time

import bannin


def main() -> None:
    print("Pushing training progress to running Bannin agent...")
    print("Make sure the CLI agent is running with --relay-key.\n")

    # Phase 1: Simulated fine-tuning (60 steps, ~30s)
    print("=== Phase 1: Fine-tuning GPT (60 steps) ===")
    for step in range(1, 61):
        bannin.progress("Fine-tuning GPT", current=step, total=60)
        time.sleep(0.5)

    # Phase 2: Simulated epoch training (5 epochs, ~25s)
    print("\n=== Phase 2: Epoch training (5 epochs) ===")
    for epoch in range(1, 6):
        bannin.progress("Epoch Training", current=epoch, total=5)
        print(f"  Epoch {epoch}/5")
        time.sleep(5)

    # Phase 3: Quick validation (20 steps, ~6s)
    print("\n=== Phase 3: Validation (20 steps) ===")
    for step in range(1, 21):
        bannin.progress("Validation", current=step, total=20)
        time.sleep(0.3)

    print("\n=== Training complete! ===")
    print("Check the dashboard for completed tasks and toast notifications.")


if __name__ == "__main__":
    main()
