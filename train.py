"""Fake training script for testing detected-task stop/kill.

The agent's TrainingDetector picks this up because the filename matches
the 'train.py' pattern. It just sleeps -- no bannin import needed.

Usage:
    python train.py
"""

import time

print("Training started (fake). PID:", __import__("os").getpid())
print("This will run for 10 minutes. Stop it from the dashboard.")

for epoch in range(1, 601):
    time.sleep(1)
    if epoch % 30 == 0:
        print(f"  Still running... {epoch}s elapsed")

print("Training finished.")
