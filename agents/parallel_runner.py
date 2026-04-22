"""
agents/parallel_runner.py — ThreadPoolExecutor wrapper for parallel agent calls.

Simple, generic, zero domain knowledge. Knows nothing about reels or hooks.
All logic about what to run in parallel lives in orchestrate.py.

Public API:
    runner = ParallelRunner()
    results = runner.run_parallel(fn, tasks, max_workers=5)
    # results[i] is fn(tasks[i]) or None if task i failed/timed out

Design decisions:
- Uses threads (not processes) — LLM API calls are I/O-bound, not CPU-bound.
- Results returned in original task order regardless of completion order.
- Failed tasks return None. Caller decides what to do with gaps.
- Timeout applies to the whole batch, not individual tasks.
  Default 120s covers one Claude API call per task comfortably.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from typing import Any, Callable

log = logging.getLogger(__name__)


class ParallelRunner:
    """
    Run a callable over a list of task dicts in parallel.

    Each task dict is passed as a single argument to `fn`.
    The callable must be thread-safe (no shared mutable state without locks).
    """

    def run_parallel(
        self,
        fn: Callable[[dict], Any],
        tasks: list[dict],
        max_workers: int = 5,
        timeout: float = 120.0,
    ) -> list[Any | None]:
        """
        Execute fn(task) for each task in parallel.

        Args:
            fn: callable receiving one dict, returning one result.
            tasks: list of input dicts. Order is preserved in output.
            max_workers: max concurrent threads (capped at len(tasks)).
            timeout: wall-clock seconds for the whole batch.

        Returns:
            list of results, same length as tasks.
            Failed or timed-out slots contain None.
        """
        if not tasks:
            return []

        n = len(tasks)
        workers = min(max_workers, n)
        results: list[Any | None] = [None] * n

        log.info(f"[parallel] Starting {n} tasks with {workers} workers (timeout={timeout}s)")
        t0 = time.time()

        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_idx = {executor.submit(fn, task): i for i, task in enumerate(tasks)}

            try:
                for future in as_completed(future_to_idx, timeout=timeout):
                    idx = future_to_idx[future]
                    try:
                        results[idx] = future.result()
                        log.debug(f"[parallel] Task {idx} completed")
                    except Exception as e:
                        log.warning(f"[parallel] Task {idx} raised exception: {e}")
            except TimeoutError:
                remaining = sum(1 for r in results if r is None)
                log.warning(
                    f"[parallel] Batch timed out after {timeout}s — "
                    f"{remaining}/{n} tasks still pending (their slots will be None)"
                )

        elapsed = time.time() - t0
        success_count = sum(1 for r in results if r is not None)
        log.info(
            f"[parallel] Done — {success_count}/{n} succeeded "
            f"in {elapsed:.1f}s (avg {elapsed/n:.1f}s/task)"
        )
        return results
