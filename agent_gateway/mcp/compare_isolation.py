#!/usr/bin/env python3
"""Compare isolation and performance across different implementations."""

import time
from executor import run_python_sandbox
from executor_optimized import run_python_sandbox_optimized, cleanup_executor as cleanup_opt
from executor_isolated import run_python_sandbox_isolated, cleanup_executor as cleanup_iso, get_executor_stats
import atexit

atexit.register(cleanup_opt)
atexit.register(cleanup_iso)


def test_performance(name: str, func, iterations: int = 50):
    """Test execution performance."""
    print(f"\n{'='*60}")
    print(f"Performance Test: {name}")
    print(f"{'='*60}")

    # Warmup
    func("x = 1")

    # Benchmark
    start = time.perf_counter()
    for i in range(iterations):
        func("result = 2 + 2")
    elapsed = time.perf_counter() - start

    avg_time = (elapsed / iterations) * 1000  # ms
    throughput = iterations / elapsed

    print(f"Iterations:     {iterations}")
    print(f"Total time:     {elapsed:.3f}s")
    print(f"Avg time:       {avg_time:.2f}ms")
    print(f"Throughput:     {throughput:.2f} calls/s")

    return {
        "avg_time_ms": avg_time,
        "throughput": throughput,
    }


def test_variable_isolation(name: str, func):
    """Test if variables persist across executions."""
    print(f"\n{'='*60}")
    print(f"Variable Isolation Test: {name}")
    print(f"{'='*60}")

    # Set a variable
    result1 = func("secret_value = 12345")
    print(f"Step 1: Set secret_value = 12345")

    # Try to access it in next execution
    result2 = func("result = secret_value if 'secret_value' in dir() else 'ISOLATED'")
    print(f"Step 2: Try to access secret_value")

    is_isolated = 'error' in result2 or result2.get('locals', {}).get('result') == 'ISOLATED'
    print(f"Result: {'✅ ISOLATED' if is_isolated else '❌ NOT ISOLATED'}")

    return is_isolated


def test_module_pollution(name: str, func):
    """Test if imported modules persist."""
    print(f"\n{'='*60}")
    print(f"Module Pollution Test: {name}")
    print(f"{'='*60}")

    # Import a module
    result1 = func("import hashlib\nresult = hashlib.md5(b'test').hexdigest()")
    print(f"Step 1: Import hashlib and use it")
    print(f"  Result: {result1.get('locals', {}).get('result', 'N/A')[:20]}...")

    # Try to use it without importing
    result2 = func("result = hashlib.md5(b'test2').hexdigest()")
    print(f"Step 2: Use hashlib without importing")

    is_isolated = 'error' in result2
    print(f"Result: {'✅ ISOLATED' if is_isolated else '❌ NOT ISOLATED (module cached)'}")

    return is_isolated


def test_sys_path_pollution(name: str, func):
    """Test if sys.path modifications persist."""
    print(f"\n{'='*60}")
    print(f"sys.path Pollution Test: {name}")
    print(f"{'='*60}")

    # Get original path length
    result1 = func("import sys\nresult = len(sys.path)")
    original_len = int(result1.get('locals', {}).get('result', 0))
    print(f"Step 1: Original sys.path length: {original_len}")

    # Modify sys.path
    result2 = func("import sys\nsys.path.append('/fake/path')\nresult = len(sys.path)")
    modified_len = int(result2.get('locals', {}).get('result', 0))
    print(f"Step 2: After adding fake path: {modified_len}")

    # Check if modification persists
    result3 = func("import sys\nresult = len(sys.path)")
    final_len = int(result3.get('locals', {}).get('result', 0))
    print(f"Step 3: In next execution: {final_len}")

    is_isolated = final_len == original_len
    print(f"Result: {'✅ ISOLATED' if is_isolated else '❌ NOT ISOLATED (sys.path modified)'}")

    return is_isolated


def main():
    """Run comprehensive comparison."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║    Comprehensive Comparison: Isolation vs Performance        ║
╚══════════════════════════════════════════════════════════════╝
""")

    implementations = [
        ("Baseline (subprocess)", run_python_sandbox),
        ("Optimized (persistent)", run_python_sandbox_optimized),
        ("Isolated (with reset)", run_python_sandbox_isolated),
    ]

    # Performance comparison
    print("\n" + "="*60)
    print("PART 1: PERFORMANCE COMPARISON")
    print("="*60)

    perf_results = {}
    for name, func in implementations:
        if "Baseline" in name:
            iterations = 20  # Baseline is slow
        else:
            iterations = 50
        perf_results[name] = test_performance(name, func, iterations)

    # Isolation comparison
    print("\n\n" + "="*60)
    print("PART 2: ISOLATION COMPARISON")
    print("="*60)

    isolation_results = {}
    for name, func in implementations:
        isolation_results[name] = {
            "variable": test_variable_isolation(name, func),
            "module": test_module_pollution(name, func),
            "sys_path": test_sys_path_pollution(name, func),
        }

    # Summary
    print("\n\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    print("\n📊 Performance Comparison:")
    print(f"{'Implementation':<30} {'Avg Time':<15} {'Throughput':<15}")
    print("-" * 60)
    for name, metrics in perf_results.items():
        print(f"{name:<30} {metrics['avg_time_ms']:>10.2f}ms {metrics['throughput']:>10.1f}/s")

    print("\n🔒 Isolation Comparison:")
    print(f"{'Implementation':<30} {'Variable':<12} {'Module':<12} {'sys.path':<12}")
    print("-" * 66)
    for name, tests in isolation_results.items():
        var_icon = "✅" if tests['variable'] else "❌"
        mod_icon = "✅" if tests['module'] else "⚠️ "
        sys_icon = "✅" if tests['sys_path'] else "❌"
        print(f"{name:<30} {var_icon:<12} {mod_icon:<12} {sys_icon:<12}")

    # Show executor stats for isolated version
    print("\n📈 Isolated Executor Stats:")
    stats = get_executor_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print("\n" + "="*60)
    print("RECOMMENDATIONS")
    print("="*60)
    print("""
根据你的需求选择：

1. 🚀 **Isolated (with reset)** - 最佳选择
   - 性能优秀 (~1800 calls/s)
   - 隔离良好（sys.path 被重置）
   - 定期重启防止状态累积
   ✅ 推荐用于生产环境

2. ⚡ **Optimized (persistent)** - 极致性能
   - 性能最好 (~1900 calls/s)
   - 基本隔离（变量、函数）
   - 但模块和 sys 状态会累积
   ⚠️  适合可信代码，或添加监控

3. 🐌 **Baseline (subprocess)** - 完全隔离
   - 性能差 (~4 calls/s)
   - 完全隔离
   - 开销巨大
   ❌ 不推荐，仅作对比
""")


if __name__ == "__main__":
    main()
