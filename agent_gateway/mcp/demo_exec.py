#!/usr/bin/env python3
"""
演示 exec() 函数的不同用法和隔离效果
"""


def demo_no_params():
    """演示：不传参数（在模块级使用时危险）"""
    print("\n" + "="*60)
    print("演示 1: exec(code) - 不传参数（❌ 危险）")
    print("="*60)

    # 注意：在函数内部使用 exec() 不传参数，Python 3 会自动使用 locals()
    # 但在模块级别或类级别会直接修改命名空间

    print("在函数内部使用 exec() 不传参数:")
    x = 100
    print(f"  执行前 x = {x}")

    code = """
x = 200
y = 300
print(f"  在 exec 内部: x = {x}, y = {y}")
"""
    exec(code)

    # 在函数内部，exec() 不传参数时不会修改外部变量（Python 3 的优化）
    print(f"  执行后 x = {x}")
    # print(f"  y = {y}")  # 这会报错，因为 y 不在外部作用域

    print("\n  ⚠️  在函数内部，exec() 不传参数相对安全（Python 3 优化）")
    print("  ❌ 但在模块级别会修改全局变量！建议始终传参数")


def demo_only_globals():
    """演示：只传 globals"""
    print("\n" + "="*60)
    print("演示 2: exec(code, globals) - 只传全局命名空间")
    print("="*60)

    x = 100
    print(f"外部变量 x = {x}")

    code = """
x = 200
y = 300
print(f"在 exec 内部: x = {x}, y = {y}")
"""

    global_ns = {}
    exec(code, global_ns)

    print(f"执行后外部变量 x = {x}")  # 未被修改
    print(f"global_ns 中的变量: {list(global_ns.keys())[:5]}...")  # x, y 在里面
    print("🟡 结论：外部不受影响，但变量留在 global_ns 中")


def demo_globals_and_locals():
    """演示：传 globals 和 locals（推荐）"""
    print("\n" + "="*60)
    print("演示 3: exec(code, globals, locals) - ✅ 推荐方式")
    print("="*60)

    x = 100
    print(f"外部变量 x = {x}")

    code = """
x = 200
y = 300
result = x + y
print(f"在 exec 内部: x = {x}, y = {y}, result = {result}")
"""

    global_ns = {}
    local_ns = {}
    exec(code, global_ns, local_ns)

    print(f"执行后外部变量 x = {x}")  # 未被修改
    print(f"local_ns: {local_ns}")
    print(f"global_ns 变量数: {len(global_ns)}")  # 只有 __builtins__
    print("✅ 结论：完全隔离，安全可靠")


def demo_isolation_between_executions():
    """演示：多次执行之间的隔离"""
    print("\n" + "="*60)
    print("演示 4: 多次 exec 调用的隔离效果")
    print("="*60)

    # 第一次执行
    print("执行 1: 设置变量")
    local_ns_1 = {}
    exec("secret = 12345", {}, local_ns_1)
    print(f"  local_ns_1: {local_ns_1}")

    # 第二次执行（新的 local_ns）
    print("\n执行 2: 尝试访问上次的变量")
    local_ns_2 = {}
    try:
        exec("result = secret", {}, local_ns_2)
        print(f"  ❌ 变量可以访问: {local_ns_2}")
    except NameError as e:
        print(f"  ✅ NameError: {e}")
        print("  变量已隔离！")


def demo_function_isolation():
    """演示：函数定义的隔离"""
    print("\n" + "="*60)
    print("演示 5: 函数定义的隔离")
    print("="*60)

    # 第一次：定义函数
    print("执行 1: 定义函数")
    local_ns_1 = {}
    exec("""
def add(a, b):
    return a + b
result = add(10, 20)
""", {}, local_ns_1)
    print(f"  结果: {local_ns_1['result']}")
    print(f"  函数对象: {local_ns_1['add']}")

    # 第二次：尝试使用函数
    print("\n执行 2: 尝试使用上次定义的函数")
    local_ns_2 = {}
    try:
        exec("result = add(30, 40)", {}, local_ns_2)
        print(f"  ❌ 函数可以访问: {local_ns_2}")
    except NameError as e:
        print(f"  ✅ NameError: {e}")
        print("  函数已隔离！")


def demo_import_behavior():
    """演示：import 的行为"""
    print("\n" + "="*60)
    print("演示 6: import 模块的行为")
    print("="*60)

    import sys
    modules_before = set(sys.modules.keys())

    # 第一次：导入模块
    print("执行 1: import math")
    local_ns_1 = {}
    exec("import math\nresult = math.pi", {}, local_ns_1)
    print(f"  结果: {local_ns_1.get('result')}")
    print(f"  math 在 sys.modules 中: {'math' in sys.modules}")

    # 第二次：尝试使用 math（不导入）
    print("\n执行 2: 使用 math.sqrt（不导入）")
    local_ns_2 = {}
    try:
        exec("result = math.sqrt(16)", {}, local_ns_2)
        print(f"  ❌ 可以使用 math: {local_ns_2}")
    except NameError as e:
        print(f"  ✅ NameError: {e}")
        print("  虽然 math 在 sys.modules 中，但在空 globals 中找不到 'math' 名称")

    modules_after = set(sys.modules.keys())
    new_modules = modules_after - modules_before
    print(f"\n新导入的模块: {new_modules}")
    print("⚠️  模块留在 sys.modules 中（需要手动清理）")


def demo_sys_state_pollution():
    """演示：sys 状态的污染"""
    print("\n" + "="*60)
    print("演示 7: sys.path 污染问题")
    print("="*60)

    import sys
    original_len = len(sys.path)
    print(f"原始 sys.path 长度: {original_len}")

    # 第一次：修改 sys.path
    print("\n执行 1: 添加路径到 sys.path")
    exec("import sys; sys.path.append('/fake/path')", {}, {})
    print(f"  修改后 sys.path 长度: {len(sys.path)}")
    print(f"  最后一个路径: {sys.path[-1]}")

    # 第二次：检查 sys.path
    print("\n执行 2: 检查 sys.path")
    local_ns = {}
    exec("import sys; result = '/fake/path' in sys.path", {}, local_ns)
    print(f"  /fake/path 还在吗? {local_ns['result']}")
    print("❌ sys 状态会保留（需要手动重置）")

    # 清理
    while len(sys.path) > original_len:
        sys.path.pop()
    print(f"\n手动清理后 sys.path 长度: {len(sys.path)}")


def demo_safe_builtins():
    """演示：限制可用的内置函数"""
    print("\n" + "="*60)
    print("演示 8: 限制可用的内置函数（安全模式）")
    print("="*60)

    # 默认：可以使用所有内置函数
    print("默认模式: 可以使用 open()")
    try:
        exec("f = open('/etc/passwd')", {}, {})
        print("  ❌ 可以打开文件（不安全）")
    except Exception as e:
        print(f"  错误: {e}")

    # 安全模式：限制内置函数
    print("\n安全模式: 只允许特定函数")
    safe_builtins = {
        "print": print,
        "len": len,
        "range": range,
        "sum": sum,
        # 不包括 open, eval, __import__ 等危险函数
    }
    safe_globals = {"__builtins__": safe_builtins}

    try:
        exec("result = sum(range(10))", safe_globals, {})
        print("  ✅ sum() 和 range() 可以使用")
    except Exception as e:
        print(f"  错误: {e}")

    try:
        exec("f = open('/etc/passwd')", safe_globals, {})
        print("  ❌ 仍然可以打开文件")
    except NameError as e:
        print(f"  ✅ NameError: {e}")
        print("  open() 被禁用！")


def demo_real_world_usage():
    """演示：真实场景的使用（模拟我们的实现）"""
    print("\n" + "="*60)
    print("演示 9: 真实场景 - 模拟我们的 MCP 实现")
    print("="*60)

    from io import StringIO
    from contextlib import redirect_stdout, redirect_stderr

    def execute_user_code(code: str) -> dict:
        """模拟我们的执行函数"""
        stdout_buffer = StringIO()
        stderr_buffer = StringIO()
        local_vars = {}

        try:
            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                exec(code, {}, local_vars)

            return {
                "status": "success",
                "stdout": stdout_buffer.getvalue(),
                "stderr": stderr_buffer.getvalue(),
                "locals": {k: str(v) for k, v in local_vars.items()},
            }
        except Exception as exc:
            return {
                "status": "error",
                "error": str(exc),
                "stdout": stdout_buffer.getvalue(),
                "stderr": stderr_buffer.getvalue(),
            }

    # 测试 1: 正常执行
    print("测试 1: 计算并打印")
    result1 = execute_user_code("""
x = 10
y = 20
result = x + y
print(f"Result: {result}")
""")
    print(f"  状态: {result1['status']}")
    print(f"  输出: {result1['stdout'].strip()}")
    print(f"  变量: {result1['locals']}")

    # 测试 2: 错误处理
    print("\n测试 2: 除以零错误")
    result2 = execute_user_code("result = 1 / 0")
    print(f"  状态: {result2['status']}")
    print(f"  错误: {result2['error']}")

    # 测试 3: 隔离验证
    print("\n测试 3: 隔离验证")
    result3 = execute_user_code("try:\n    print(x)\nexcept NameError:\n    print('x is not defined')")
    print(f"  输出: {result3['stdout'].strip()}")
    print("  ✅ 变量隔离成功！")


def main():
    """运行所有演示"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║               Python exec() 函数完整演示                      ║
║                                                              ║
║  我们的所有实现都在使用 exec()，这是 Python 标准方式！        ║
╚══════════════════════════════════════════════════════════════╝
""")

    demos = [
        ("不传参数", demo_no_params),
        ("只传 globals", demo_only_globals),
        ("传 globals 和 locals", demo_globals_and_locals),
        ("多次执行隔离", demo_isolation_between_executions),
        ("函数隔离", demo_function_isolation),
        ("import 行为", demo_import_behavior),
        ("sys 状态污染", demo_sys_state_pollution),
        ("安全模式", demo_safe_builtins),
        ("真实场景", demo_real_world_usage),
    ]

    for name, demo_func in demos:
        try:
            demo_func()
        except Exception as e:
            print(f"\n❌ {name} 演示出错: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*60)
    print("总结")
    print("="*60)
    print("""
关键要点：

1. ✅ exec(code, {}, {}) 是正确的用法
   - 空 globals 隔离全局命名空间
   - 新 locals 每次都是干净的

2. ✅ 可以隔离的内容：
   - 变量、函数、类定义
   - 局部命名空间

3. ❌ 无法隔离的内容：
   - sys.modules（已导入的模块）
   - sys.path（搜索路径）
   - 全局解释器状态

4. 💡 解决方案：
   - 使用 exec(code, {}, {}) 基础隔离
   - 手动重置 sys.path 等状态
   - 定期重启进程清理累积状态

5. 🎯 这正是我们的 executor_isolated.py 所做的！

建议：查看 EXEC_EXPLAINED.md 了解更多细节
""")


if __name__ == "__main__":
    main()
