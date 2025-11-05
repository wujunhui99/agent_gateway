#!/usr/bin/env python3
"""Performance benchmark for Python sandbox execution.

Tests current implementation and compares with optimized version.
"""

import asyncio
import json
import statistics
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from executor import run_python_sandbox
from executor_optimized import run_python_sandbox_optimized, cleanup_executor


@dataclass
class BenchmarkResult:
    """Store benchmark metrics."""
    name: str
    total_calls: int
    total_time: float
    avg_time: float
    median_time: float
    min_time: float
    max_time: float
    p95_time: float
    p99_time: float
    throughput: float  # calls per second

    def __str__(self) -> str:
        return f"""
{self.name}
{'='*60}
Total calls:    {self.total_calls}
Total time:     {self.total_time:.3f}s
Average time:   {self.avg_time*1000:.2f}ms
Median time:    {self.median_time*1000:.2f}ms
Min time:       {self.min_time*1000:.2f}ms
Max time:       {self.max_time*1000:.2f}ms
P95 time:       {self.p95_time*1000:.2f}ms
P99 time:       {self.p99_time*1000:.2f}ms
Throughput:     {self.throughput:.2f} calls/sec
"""


def benchmark_sync(func: Callable, test_cases: List[Dict[str, Any]], name: str, warmup: int = 2) -> BenchmarkResult:
    """Benchmark a synchronous function."""
    print(f"\n🧪 Running benchmark: {name}")
    print(f"   Test cases: {len(test_cases)}, Warmup: {warmup}")

    # Warmup
    print("   Warming up...", end=" ", flush=True)
    for i in range(min(warmup, len(test_cases))):
        func(**test_cases[i])
    print("✓")

    # Actual benchmark
    print("   Benchmarking...", end=" ", flush=True)
    timings = []
    start_total = time.perf_counter()

    for i, test_case in enumerate(test_cases):
        start = time.perf_counter()
        try:
            result = func(**test_case)
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

            # Show progress every 10 calls
            if (i + 1) % 10 == 0:
                print(f"{i+1}", end=" ", flush=True)
        except Exception as e:
            print(f"\n   ❌ Error on call {i+1}: {e}")
            elapsed = time.perf_counter() - start
            timings.append(elapsed)

    total_time = time.perf_counter() - start_total
    print("✓")

    # Calculate statistics
    timings.sort()
    n = len(timings)

    return BenchmarkResult(
        name=name,
        total_calls=n,
        total_time=total_time,
        avg_time=statistics.mean(timings),
        median_time=statistics.median(timings),
        min_time=min(timings),
        max_time=max(timings),
        p95_time=timings[int(n * 0.95)] if n > 0 else 0,
        p99_time=timings[int(n * 0.99)] if n > 0 else 0,
        throughput=n / total_time if total_time > 0 else 0,
    )


def generate_test_cases() -> Dict[str, List[Dict[str, Any]]]:
    """Generate various test cases for benchmarking."""
    return {
        "simple_calc": [
            {"code": "result = 1 + 1", "user_input": None}
            for _ in range(50)
        ],
        "loop_calc": [
            {"code": "result = sum(range(1000))", "user_input": None}
            for _ in range(30)
        ],
        "string_ops": [
            {"code": "result = 'hello ' * 100", "user_input": None}
            for _ in range(30)
        ],
        "list_comp": [
            {"code": "result = [i**2 for i in range(100)]", "user_input": None}
            for _ in range(30)
        ],
        "dict_ops": [
            {"code": "result = {str(i): i**2 for i in range(50)}", "user_input": None}
            for _ in range(30)
        ],
        "json_parsing": [
            {"code": 'import json\ndata = \'{"key": "value"}\'\nresult = json.loads(data)', "user_input": None}
            for _ in range(30)
        ],
        "mixed_workload": [
            {"code": "result = 1 + 1", "user_input": None},
            {"code": "result = sum(range(1000))", "user_input": None},
            {"code": "result = 'hello ' * 100", "user_input": None},
            {"code": "result = [i**2 for i in range(100)]", "user_input": None},
            {"code": "import math\nresult = math.sqrt(16)", "user_input": None},
        ] * 10,  # Repeat 10 times
    }


def run_baseline_benchmark():
    """Benchmark the current implementation."""
    print("\n" + "="*60)
    print("BASELINE BENCHMARK - Current Implementation")
    print("="*60)

    test_cases = generate_test_cases()
    results = []

    for test_name, cases in test_cases.items():
        result = benchmark_sync(run_python_sandbox, cases, f"Baseline - {test_name}")
        results.append(result)
        print(result)

    # Summary
    print("\n" + "="*60)
    print("BASELINE SUMMARY")
    print("="*60)
    total_calls = sum(r.total_calls for r in results)
    total_time = sum(r.total_time for r in results)
    avg_throughput = statistics.mean([r.throughput for r in results])

    print(f"Total calls:        {total_calls}")
    print(f"Total time:         {total_time:.3f}s")
    print(f"Avg throughput:     {avg_throughput:.2f} calls/sec")
    print(f"Overall throughput: {total_calls / total_time:.2f} calls/sec")

    return results


def compare_results(baseline_results: List[BenchmarkResult], optimized_results: List[BenchmarkResult]):
    """Compare baseline and optimized results."""
    print("\n" + "="*60)
    print("PERFORMANCE COMPARISON")
    print("="*60)

    print(f"\n{'Metric':<30} {'Baseline':<15} {'Optimized':<15} {'Improvement':<15}")
    print("-" * 75)

    for baseline, optimized in zip(baseline_results, optimized_results):
        test_name = baseline.name.replace("Baseline - ", "")

        # Calculate improvements
        time_improvement = (baseline.avg_time - optimized.avg_time) / baseline.avg_time * 100
        throughput_improvement = (optimized.throughput - baseline.throughput) / baseline.throughput * 100

        print(f"\n{test_name}")
        print(f"  Avg latency:      {baseline.avg_time*1000:>10.2f}ms {optimized.avg_time*1000:>10.2f}ms {time_improvement:>10.1f}%")
        print(f"  Throughput:       {baseline.throughput:>10.2f}/s {optimized.throughput:>10.2f}/s {throughput_improvement:>10.1f}%")


def run_optimized_benchmark():
    """Benchmark the optimized implementation."""
    print("\n" + "="*60)
    print("OPTIMIZED BENCHMARK - Persistent Process")
    print("="*60)

    test_cases = generate_test_cases()
    results = []

    try:
        for test_name, cases in test_cases.items():
            result = benchmark_sync(
                run_python_sandbox_optimized,
                cases,
                f"Optimized - {test_name}"
            )
            results.append(result)
            print(result)

        # Summary
        print("\n" + "="*60)
        print("OPTIMIZED SUMMARY")
        print("="*60)
        total_calls = sum(r.total_calls for r in results)
        total_time = sum(r.total_time for r in results)
        avg_throughput = statistics.mean([r.throughput for r in results])

        print(f"Total calls:        {total_calls}")
        print(f"Total time:         {total_time:.3f}s")
        print(f"Avg throughput:     {avg_throughput:.2f} calls/sec")
        print(f"Overall throughput: {total_calls / total_time:.2f} calls/sec")

    finally:
        # Cleanup
        cleanup_executor()

    return results


def main():
    """Run all benchmarks."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║      MCP Python Sandbox Performance Benchmark Suite         ║
╚══════════════════════════════════════════════════════════════╝
""")

    # Check if Docker container is running
    print("Checking prerequisites...")
    try:
        result = run_python_sandbox("print('test')", None)
        print("✓ Docker container is running")
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nPlease ensure the MCP Docker container is running:")
        print("  cd agent_gateway/mcp")
        print("  docker compose up -d")
        return

    # Run baseline benchmark
    baseline_results = run_baseline_benchmark()

    # Run optimized benchmark
    optimized_results = run_optimized_benchmark()

    # Compare results
    compare_results(baseline_results, optimized_results)

    # Save results
    results_file = "benchmark_results.json"
    with open(results_file, "w") as f:
        json.dump(
            {
                "baseline": [
                    {
                        "name": r.name,
                        "avg_time_ms": r.avg_time * 1000,
                        "median_time_ms": r.median_time * 1000,
                        "p95_time_ms": r.p95_time * 1000,
                        "p99_time_ms": r.p99_time * 1000,
                        "throughput": r.throughput,
                    }
                    for r in baseline_results
                ],
                "optimized": [
                    {
                        "name": r.name,
                        "avg_time_ms": r.avg_time * 1000,
                        "median_time_ms": r.median_time * 1000,
                        "p95_time_ms": r.p95_time * 1000,
                        "p99_time_ms": r.p99_time * 1000,
                        "throughput": r.throughput,
                    }
                    for r in optimized_results
                ]
            },
            f,
            indent=2,
        )
    print(f"\n✓ Results saved to {results_file}")

    print("\n" + "="*60)
    print("BENCHMARK COMPLETE")
    print("="*60)


if __name__ == "__main__":
    main()
