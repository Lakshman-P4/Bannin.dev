"""Stress test with training simulation to trigger Bannin alerts and training progress.

This script:
1. Hammers CPU and RAM to trigger threshold alerts (80%+ usage)
2. Simulates a training run with tqdm progress bars and Epoch/Step patterns
3. All progress is detected by Bannin's ProgressTracker

Usage:
    python stress_test.py                     # Full test (CPU + RAM + training) for 90s
    python stress_test.py --cpu               # CPU stress only
    python stress_test.py --ram               # RAM stress only
    python stress_test.py --train             # Training simulation only
    python stress_test.py -t 120              # Custom duration
    python stress_test.py --epochs 20         # Custom epoch count

IMPORTANT: Stop the standalone agent first if running. This script starts its
own agent with relay support via bannin.watch().

    python stress_test.py --relay-key <KEY>   # Connect to relay
    python stress_test.py --relay-key <KEY> --relay-url ws://localhost:3001
"""

from __future__ import annotations

import argparse
import ctypes
import os
import sys
import time
import threading
import math


def stress_cpu(duration: int, stop_event: threading.Event) -> None:
    """Spin all CPU cores at 100% for the given duration."""
    cores = os.cpu_count() or 4

    def spin() -> None:
        while not stop_event.is_set():
            _ = sum(i * i for i in range(10_000))

    print(f"[CPU] Spinning {cores} threads for {duration}s...")
    threads = [threading.Thread(target=spin, daemon=True) for _ in range(cores)]
    for t in threads:
        t.start()

    stop_event.wait(timeout=duration)
    stop_event.set()
    for t in threads:
        t.join(timeout=2)
    print("[CPU] Done.")


def stress_ram(duration: int, stop_event: threading.Event, target_mb: int = 0) -> None:
    """Allocate memory to push RAM usage above 80%."""
    try:
        import psutil
        mem = psutil.virtual_memory()
        current_pct = mem.percent
        total_mb = mem.total / (1024 * 1024)

        if target_mb <= 0:
            target_pct = 85.0
            if current_pct >= target_pct:
                target_mb = 100
                print(f"[RAM] Already at {current_pct:.1f}%, small allocation to maintain pressure.")
            else:
                needed_pct = target_pct - current_pct
                target_mb = int((needed_pct / 100) * total_mb)
                print(f"[RAM] Current: {current_pct:.1f}% of {total_mb:.0f}MB total")
                print(f"[RAM] Allocating ~{target_mb}MB to reach ~{target_pct:.0f}%...")
    except ImportError:
        if target_mb <= 0:
            target_mb = 2048
        print(f"[RAM] psutil not available, allocating {target_mb}MB...")

    chunk_size = 64 * 1024 * 1024
    chunks: list[ctypes.Array] = []
    allocated = 0

    try:
        while allocated < target_mb * 1024 * 1024:
            remaining = target_mb * 1024 * 1024 - allocated
            size = min(chunk_size, remaining)
            try:
                buf = (ctypes.c_char * size)()
                ctypes.memset(buf, 0x42, size)
                chunks.append(buf)
                allocated += size
            except (MemoryError, OSError):
                print(f"[RAM] Hit allocation limit at {allocated / (1024 * 1024):.0f}MB")
                break

        print(f"[RAM] Holding {allocated / (1024 * 1024):.0f}MB for {duration}s...")
        stop_event.wait(timeout=duration)
    finally:
        chunks.clear()
        print("[RAM] Released.")


def simulate_training(epochs: int, steps_per_epoch: int, stop_event: threading.Event) -> None:
    """Simulate a training run with tqdm progress bars and stdout patterns.

    This prints Epoch/Step patterns that Bannin's ProgressTracker detects via
    stdout hooking, and uses tqdm bars that get monkey-patched by hook_tqdm().
    """
    try:
        from tqdm import tqdm
    except ImportError:
        print("[TRAIN] tqdm not installed. Install with: pip install tqdm")
        print("[TRAIN] Falling back to stdout-only patterns...")
        tqdm = None

    print(f"\n[TRAIN] Starting simulated training: {epochs} epochs, {steps_per_epoch} steps each")
    print("=" * 60)

    for epoch in range(1, epochs + 1):
        if stop_event.is_set():
            break

        # Print epoch pattern that ProgressTracker detects via stdout
        print(f"\nEpoch {epoch}/{epochs}")

        # Simulate steps within each epoch
        if tqdm is not None:
            pbar = tqdm(
                range(steps_per_epoch),
                desc=f"Epoch {epoch}/{epochs}",
                unit="step",
                ncols=80,
            )
            for step in pbar:
                if stop_event.is_set():
                    pbar.close()
                    return
                # Simulate compute time per step (50-150ms)
                time.sleep(0.08)
                # Simulate loss decreasing
                loss = 2.5 * math.exp(-0.3 * (epoch - 1)) + 0.1 * math.exp(-step / steps_per_epoch)
                pbar.set_postfix(loss=f"{loss:.4f}")
            pbar.close()
        else:
            for step in range(1, steps_per_epoch + 1):
                if stop_event.is_set():
                    return
                time.sleep(0.08)
                loss = 2.5 * math.exp(-0.3 * (epoch - 1)) + 0.1 * math.exp(-step / steps_per_epoch)
                # Print step pattern
                if step % 10 == 0 or step == steps_per_epoch:
                    print(f"  Step {step}/{steps_per_epoch} - loss: {loss:.4f}")

        # Epoch summary
        epoch_loss = 2.5 * math.exp(-0.3 * epoch)
        accuracy = min(99.0, 60 + epoch * (35 / epochs))
        print(f"  -> loss: {epoch_loss:.4f}, accuracy: {accuracy:.1f}%")

    print("\n" + "=" * 60)
    print("[TRAIN] Training complete!")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bannin stress test with training simulation")
    parser.add_argument("--cpu", action="store_true", help="CPU stress only")
    parser.add_argument("--ram", action="store_true", help="RAM stress only")
    parser.add_argument("--train", action="store_true", help="Training simulation only")
    parser.add_argument("-t", "--time", type=int, default=90, help="Duration in seconds (default: 90)")
    parser.add_argument("--ram-mb", type=int, default=0, help="RAM to allocate in MB (0 = auto)")
    parser.add_argument("--epochs", type=int, default=10, help="Training epochs (default: 10)")
    parser.add_argument("--steps", type=int, default=50, help="Steps per epoch (default: 50)")
    parser.add_argument("--relay-key", type=str, default=None, help="Relay API key for remote monitoring")
    parser.add_argument("--relay-url", type=str, default="ws://localhost:3001", help="Relay server URL")
    args = parser.parse_args()

    # If no specific flags, do everything
    none_selected = not args.cpu and not args.ram and not args.train
    do_cpu = args.cpu or none_selected
    do_ram = args.ram or none_selected
    do_train = args.train or none_selected

    print("Bannin Stress Test")
    print(f"  Duration: {args.time}s")
    print(f"  CPU stress: {'yes' if do_cpu else 'no'}")
    print(f"  RAM stress: {'yes' if do_ram else 'no'}")
    print(f"  Training sim: {'yes' if do_train else 'no'} ({args.epochs} epochs x {args.steps} steps)")
    if args.relay_key:
        print(f"  Relay: {args.relay_url}")
    print()

    # Set relay env vars before importing bannin
    if args.relay_key:
        os.environ["BANNIN_RELAY_KEY"] = args.relay_key
        os.environ["BANNIN_RELAY_URL"] = args.relay_url

    # Use bannin.watch() so ProgressTracker hooks tqdm and stdout,
    # MetricHistory records data, and alerts evaluate.
    from bannin import watch

    print("Starting Bannin agent...")
    with watch():
        print("Agent running. Starting stress test...\n")

        stop_event = threading.Event()
        threads: list[threading.Thread] = []

        if do_cpu:
            t = threading.Thread(target=stress_cpu, args=(args.time, stop_event))
            threads.append(t)

        if do_ram:
            t = threading.Thread(target=stress_ram, args=(args.time, stop_event, args.ram_mb))
            threads.append(t)

        if do_train:
            t = threading.Thread(target=simulate_training, args=(args.epochs, args.steps, stop_event))
            threads.append(t)

        for t in threads:
            t.start()

        try:
            for t in threads:
                t.join()
        except KeyboardInterrupt:
            print("\nInterrupted. Stopping...")
            stop_event.set()
            for t in threads:
                t.join(timeout=5)

    print("\nStress test complete. Check your Bannin dashboard for alerts and training progress.")


if __name__ == "__main__":
    main()
