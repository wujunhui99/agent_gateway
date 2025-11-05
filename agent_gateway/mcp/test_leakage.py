#!/usr/bin/env python3
"""
测试：exec() 中的变量和状态是否会泄漏？
回答：重置是否必须？
"""

import sys


def test_variable_leakage():
    """测试：变量会泄漏吗？"""
    print("="*60)
    print("测试 1: 变量会泄漏吗？")
    print("="*60)

    # 模拟我们的实现
    def execute_code(code: str):
        local_vars = {}  # 每次新建
        exec(code, {}, local_vars)
        return local_vars

    # 执行 1：设置变量
    print("\n第 1 次执行：x = 100, y = 200")
    result1 = execute_code("x = 100\ny = 200")
    print(f"  返回的 local_vars: {result1}")

    # 执行 2：尝试访问上次的变量
    print("\n第 2 次执行：尝试访问 x")
    try:
        result2 = execute_code("result = x")
        print(f"  ❌ 可以访问 x: {result2}")
        print("  变量泄漏了！")
    except Exception as e:
        # 这里会捕获错误，但是是在 exec 内部
        result2 = execute_code("try:\n    result = x\nexcept NameError as e:\n    result = f'Error: {e}'")
        print(f"  ✅ 不能访问 x: {result2['result']}")
        print("  变量没有泄漏！")

    print("\n✅ 结论：变量不会泄漏，因为每次使用新的 local_vars = {}")


def test_function_leakage():
    """测试：函数会泄漏吗？"""
    print("\n" + "="*60)
    print("测试 2: 函数会泄漏吗？")
    print("="*60)

    def execute_code(code: str):
        local_vars = {}
        exec(code, {}, local_vars)
        return local_vars

    # 执行 1：定义函数
    print("\n第 1 次执行：定义 my_function")
    result1 = execute_code("""
def my_function(x):
    return x * 2

result = my_function(10)
""")
    print(f"  返回的 result: {result1.get('result')}")
    print(f"  返回的函数: {result1.get('my_function')}")

    # 执行 2：尝试调用函数
    print("\n第 2 次执行：尝试调用 my_function")
    result2 = execute_code("""
try:
    result = my_function(20)
except NameError as e:
    result = f'Error: {e}'
""")
    print(f"  结果: {result2['result']}")

    print("\n✅ 结论：函数也不会泄漏！")


def test_sys_path_leakage():
    """测试：sys.path 会泄漏吗？"""
    print("\n" + "="*60)
    print("测试 3: sys.path 会泄漏吗？⚠️")
    print("="*60)

    def execute_code(code: str):
        local_vars = {}
        exec(code, {}, local_vars)
        return local_vars

    # 记录原始状态
    original_path = sys.path.copy()
    print(f"\n原始 sys.path 长度: {len(original_path)}")

    # 执行 1：修改 sys.path
    print("\n第 1 次执行：添加 /fake/path 到 sys.path")
    result1 = execute_code("""
import sys
sys.path.append('/fake/path')
result = len(sys.path)
""")
    print(f"  修改后 sys.path 长度: {result1['result']}")

    # 执行 2：检查 sys.path
    print("\n第 2 次执行：检查 sys.path")
    result2 = execute_code("""
import sys
result = '/fake/path' in sys.path
""")
    print(f"  /fake/path 还在吗? {result2['result']}")

    # 检查真实的 sys.path
    print(f"\n实际的 sys.path 长度: {len(sys.path)}")
    print(f"最后一个路径: {sys.path[-1]}")

    print("\n❌ 结论：sys.path 会泄漏！这是需要重置的原因！")

    # 清理
    sys.path[:] = original_path


def test_sys_modules_leakage():
    """测试：sys.modules 会累积吗？"""
    print("\n" + "="*60)
    print("测试 4: sys.modules 会累积吗？⚠️")
    print("="*60)

    def execute_code(code: str):
        local_vars = {}
        exec(code, {}, local_vars)
        return local_vars

    # 记录原始状态
    modules_before = set(sys.modules.keys())

    # 执行：导入一个不常用的模块
    print("\n执行：导入 uuid 模块")
    result = execute_code("""
import uuid
result = str(uuid.uuid4())[:8]
""")
    print(f"  生成的 UUID 前缀: {result['result']}")

    # 检查 sys.modules
    modules_after = set(sys.modules.keys())
    new_modules = modules_after - modules_before

    print(f"\n新增模块数: {len(new_modules)}")
    print(f"新增模块: {list(new_modules)[:5]}...")

    print(f"\nuuid 在 sys.modules 中? {('uuid' in sys.modules)}")

    print("\n⚠️  结论：导入的模块会留在 sys.modules 中")
    print("    但是！模块引用不会泄漏（因为空 globals）")


def test_with_reset():
    """测试：带重置的版本"""
    print("\n" + "="*60)
    print("测试 5: 带重置的版本 ✅")
    print("="*60)

    def execute_code_with_reset(code: str):
        # 保存原始状态
        original_path_len = len(sys.path)

        local_vars = {}
        exec(code, {}, local_vars)

        # 重置 sys.path
        while len(sys.path) > original_path_len:
            sys.path.pop()

        return local_vars

    print(f"\n原始 sys.path 长度: {len(sys.path)}")

    # 执行 1：修改 sys.path
    print("\n第 1 次执行：添加 /fake/path")
    result1 = execute_code_with_reset("""
import sys
sys.path.append('/fake/path')
result = len(sys.path)
""")
    print(f"  执行中 sys.path 长度: {result1['result']}")
    print(f"  执行后 sys.path 长度: {len(sys.path)} ← 已重置！")

    # 执行 2：检查
    print("\n第 2 次执行：检查 sys.path")
    result2 = execute_code_with_reset("""
import sys
result = '/fake/path' in sys.path
""")
    print(f"  /fake/path 还在吗? {result2['result']}")

    print("\n✅ 结论：重置后 sys.path 不会累积！")


def test_without_reset_accumulation():
    """测试：不重置会怎样？"""
    print("\n" + "="*60)
    print("测试 6: 不重置会累积多少？")
    print("="*60)

    def execute_code(code: str):
        local_vars = {}
        exec(code, {}, local_vars)
        return local_vars

    original_len = len(sys.path)
    print(f"\n原始 sys.path 长度: {original_len}")

    # 执行多次
    for i in range(10):
        execute_code(f"import sys; sys.path.append('/fake/path/{i}')")

    print(f"执行 10 次后 sys.path 长度: {len(sys.path)}")
    print(f"累积了: {len(sys.path) - original_len} 个路径")
    print(f"最后几个路径: {sys.path[-3:]}")

    print("\n❌ 不重置的话会不断累积！")

    # 清理
    while len(sys.path) > original_len:
        sys.path.pop()


def compare_with_and_without_reset():
    """对比：有无重置的区别"""
    print("\n" + "="*60)
    print("总结：重置是否必须？")
    print("="*60)

    print("\n📊 不会泄漏（不需要重置）:")
    print("  ✅ 局部变量 - 每次新的 local_vars = {}")
    print("  ✅ 函数定义 - 存储在 locals 中")
    print("  ✅ 类定义 - 存储在 locals 中")
    print("  ✅ 模块引用 - 空 globals 隔离")

    print("\n⚠️  会泄漏/累积（需要重置）:")
    print("  ❌ sys.path - 修改会保留")
    print("  ❌ sys.argv - 修改会保留")
    print("  ⚠️  sys.modules - 模块留在内存（但引用隔离）")
    print("  ⚠️  os.environ - 环境变量修改")

    print("\n💡 结论：")
    print("  1. 变量、函数 → 不会泄漏，不需要特别处理")
    print("  2. sys 状态 → 会泄漏，需要重置或定期重启")
    print("  3. 如果用户代码不修改 sys → 不重置也可以")
    print("  4. 但为了安全和稳定 → 建议重置 sys.path")


def main():
    """运行所有测试"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║           测试：exec() 中的变量和状态是否泄漏？               ║
║           回答：重置是否必须？                               ║
╚══════════════════════════════════════════════════════════════╝
""")

    test_variable_leakage()
    test_function_leakage()
    test_sys_path_leakage()
    test_sys_modules_leakage()
    test_with_reset()
    test_without_reset_accumulation()
    compare_with_and_without_reset()

    print("\n" + "="*60)
    print("最终回答")
    print("="*60)
    print("""
Q: exec 里面执行的代码，变量会泄漏到外部吗？
A: ✅ **不会！** 因为我们用 exec(code, {}, local_vars)
   每次都是新的 local_vars = {}

Q: 那为什么还要重置？
A: 因为 **sys 状态会泄漏**：
   - sys.path 的修改会保留
   - sys.modules 会累积
   这些是 Python 解释器级别的全局状态

Q: 重置是必须的吗？
A: 看场景：
   ✅ 必须重置 - 如果用户代码可能修改 sys.path 等
   🟡 建议重置 - 为了长期稳定运行
   ⚠️  可不重置 - 如果用户代码完全可信且不修改 sys

Q: 我们的 executor_isolated.py 做得对吗？
A: ✅ **完全正确！**
   - 变量自动隔离（exec 机制）
   - sys.path 手动重置（清理累积）
   - 定期重启进程（终极保险）
""")


if __name__ == "__main__":
    main()
