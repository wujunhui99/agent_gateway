#!/usr/bin/env python3
"""Test state isolation in persistent Python executor.

This script demonstrates whether previous code execution affects subsequent runs.
"""

from executor import run_python_sandbox
from executor_optimized import run_python_sandbox_optimized, cleanup_executor
import atexit

atexit.register(cleanup_executor)


def test_variable_pollution():
    """Test if variables from one execution affect the next."""
    print("\n" + "="*60)
    print("TEST 1: Variable Pollution")
    print("="*60)

    # Test with baseline (each execution is isolated)
    print("\n--- Baseline (每次新进程) ---")
    result1 = run_python_sandbox("x = 100")
    print(f"执行 1: x = 100")
    print(f"  结果: {result1}")

    result2 = run_python_sandbox("result = x")
    print(f"\n执行 2: result = x")
    print(f"  结果: {result2}")
    print(f"  是否隔离: {'✅ 是' if 'error' in result2 else '❌ 否'}")

    # Test with optimized (persistent process)
    print("\n--- Optimized (持久化进程) ---")
    result3 = run_python_sandbox_optimized("x = 100")
    print(f"执行 1: x = 100")
    print(f"  结果: {result3}")

    result4 = run_python_sandbox_optimized("result = x")
    print(f"\n执行 2: result = x")
    print(f"  结果: {result4}")
    print(f"  是否隔离: {'✅ 是' if 'error' in result4 else '❌ 否，变量被保留了！'}")


def test_import_pollution():
    """Test if imports from one execution affect the next."""
    print("\n" + "="*60)
    print("TEST 2: Import Pollution")
    print("="*60)

    print("\n--- Optimized (持久化进程) ---")

    # First execution: import a module
    result1 = run_python_sandbox_optimized("import math\nresult = math.pi")
    print(f"执行 1: import math; result = math.pi")
    print(f"  结果: {result1.get('stdout', result1)}")

    # Second execution: try to use math without importing
    result2 = run_python_sandbox_optimized("result = math.sqrt(16)")
    print(f"\n执行 2: result = math.sqrt(16) (没有 import)")
    print(f"  结果: {result2.get('stdout', result2)}")
    print(f"  是否隔离: {'✅ 是' if 'error' in result2 else '❌ 否，math 模块被保留了！'}")


def test_function_pollution():
    """Test if function definitions persist across executions."""
    print("\n" + "="*60)
    print("TEST 3: Function Definition Pollution")
    print("="*60)

    print("\n--- Optimized (持久化进程) ---")

    # Define a function
    result1 = run_python_sandbox_optimized("""
def my_func(x):
    return x * 2
result = my_func(5)
""")
    print(f"执行 1: 定义 my_func 并调用")
    print(f"  结果: {result1}")

    # Try to use the function without defining it
    result2 = run_python_sandbox_optimized("result = my_func(10)")
    print(f"\n执行 2: 调用 my_func(10) (未重新定义)")
    print(f"  结果: {result2}")
    print(f"  是否隔离: {'✅ 是' if 'error' in result2 else '❌ 否，函数定义被保留了！'}")


def test_global_state_mutation():
    """Test if global state mutations persist."""
    print("\n" + "="*60)
    print("TEST 4: Global State Mutation")
    print("="*60)

    print("\n--- Optimized (持久化进程) ---")

    # Modify sys.path
    result1 = run_python_sandbox_optimized("""
import sys
original_path_len = len(sys.path)
sys.path.append('/fake/path')
result = f"Added path, now {len(sys.path)} entries"
""")
    print(f"执行 1: 修改 sys.path")
    print(f"  结果: {result1.get('stdout', result1)}")

    # Check if the modification persists
    result2 = run_python_sandbox_optimized("""
import sys
result = f"sys.path has {len(sys.path)} entries, last: {sys.path[-1]}"
""")
    print(f"\n执行 2: 检查 sys.path")
    print(f"  结果: {result2.get('stdout', result2)}")
    print(f"  是否隔离: {'✅ 是' if '/fake/path' not in str(result2) else '❌ 否，全局状态被保留了！'}")


def test_memory_accumulation():
    """Test if memory accumulates across executions."""
    print("\n" + "="*60)
    print("TEST 5: Memory Accumulation")
    print("="*60)

    print("\n--- Optimized (持久化进程) ---")

    # Create large objects in multiple executions
    for i in range(3):
        result = run_python_sandbox_optimized(f"""
import sys
big_list = list(range(100000))
result = f"Iteration {i+1}: Created list with {{len(big_list)}} elements"
""")
        print(f"执行 {i+1}: {result.get('stdout', result)}")

    print("\n  ⚠️  警告: 大对象可能累积在内存中（如果没有被 GC）")


def test_exception_state():
    """Test if exception state persists."""
    print("\n" + "="*60)
    print("TEST 6: Exception State")
    print("="*60)

    print("\n--- Optimized (持久化进程) ---")

    # Cause an exception
    result1 = run_python_sandbox_optimized("x = 1 / 0")
    print(f"执行 1: 除以零错误")
    print(f"  结果: {'有错误' if 'error' in result1 else '无错误'}")

    # Check if the next execution is affected
    result2 = run_python_sandbox_optimized("result = 2 + 2")
    print(f"\n执行 2: 简单计算")
    print(f"  结果: {result2}")
    print(f"  是否影响: {'❌ 是' if 'error' in result2 else '✅ 否，异常不影响后续执行'}")


def main():
    """Run all isolation tests."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║         State Isolation Test Suite                          ║
║  测试持久化 Python 进程的状态隔离情况                           ║
╚══════════════════════════════════════════════════════════════╝
""")

    test_variable_pollution()
    test_import_pollution()
    test_function_pollution()
    test_global_state_mutation()
    test_memory_accumulation()
    test_exception_state()

    print("\n" + "="*60)
    print("总结")
    print("="*60)
    print("""
当前优化版本（executor_optimized.py）使用 exec() 时传入空的 locals():
    exec(code, {}, local_vars)

这提供了**部分隔离**:
  ✅ 局部变量会被清空（每次 local_vars = {}）
  ❌ 全局状态会被保留（imports, 全局变量, sys 修改等）
  ❌ 内存可能累积（大对象不会自动清理）

建议: 查看 ISOLATION_SOLUTIONS.md 了解改进方案
""")


if __name__ == "__main__":
    main()
