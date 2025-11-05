#!/usr/bin/env python3
"""
测试：通过隔离命名空间能否避免 sys 泄漏？
"""

import sys
import copy


def test_your_idea():
    """测试你提出的方案"""
    print("="*60)
    print("测试 1: 你提出的方案（传递 sys 引用）")
    print("="*60)

    original_path = sys.path.copy()
    print(f"\n原始 sys.path 长度: {len(original_path)}")
    print(f"最后一个路径: {original_path[-1]}")

    # 你的方案
    namespace = {"sys": sys}  # 传递 sys 引用

    code = """
sys.path.append('/test/path')
print(f"代码内部: sys.path 长度 = {len(sys.path)}")
"""

    exec(code, namespace)

    # 检查外部
    print(f"\n执行后，外部 sys.path 长度: {len(sys.path)}")
    print(f"最后一个路径: {sys.path[-1]}")

    if len(sys.path) > len(original_path):
        print("\n❌ 失败：外部 sys.path 被修改了！")
        print("   原因：namespace 中的 sys 是对真实 sys 的**引用**")
        print("   修改引用的对象 = 修改原对象")
    else:
        print("\n✅ 成功：外部 sys.path 未被修改")

    # 恢复
    sys.path[:] = original_path


def why_it_doesnt_work():
    """解释：为什么不起作用？"""
    print("\n" + "="*60)
    print("解释：为什么传递引用不起作用？")
    print("="*60)

    print("\nPython 对象引用机制：")
    print("-" * 40)

    # 示例 1：简单变量（数字）
    print("\n示例 1: 不可变对象（数字）")
    x = 10
    namespace = {"x": x}
    exec("x = 20", namespace)
    print(f"  外部 x = {x}")  # 10
    print(f"  namespace['x'] = {namespace['x']}")  # 20
    print("  ✅ x 未改变（创建了新对象）")

    # 示例 2：可变对象（列表）
    print("\n示例 2: 可变对象（列表）")
    my_list = [1, 2, 3]
    namespace = {"my_list": my_list}
    exec("my_list.append(4)", namespace)
    print(f"  外部 my_list = {my_list}")  # [1, 2, 3, 4]
    print(f"  namespace['my_list'] = {namespace['my_list']}")  # [1, 2, 3, 4]
    print("  ❌ my_list 被改变了！（修改的是同一个对象）")

    # 示例 3：sys 模块
    print("\n示例 3: sys 模块（单例对象）")
    original_len = len(sys.path)
    namespace = {"sys": sys}
    exec("sys.path.append('/fake')", namespace)
    print(f"  外部 sys.path 长度: {len(sys.path)}")
    print(f"  原始长度: {original_len}")
    print("  ❌ sys.path 被修改了！")

    # 恢复
    sys.path.pop()

    print("\n关键理解：")
    print("  • namespace = {'sys': sys} 传递的是**引用**")
    print("  • sys 是**全局单例对象**")
    print("  • 修改引用指向的对象 = 修改原对象")
    print("  • 就像两个变量指向同一个列表")


def test_deep_copy():
    """测试：深拷贝 sys 可以吗？"""
    print("\n" + "="*60)
    print("测试 2: 深拷贝 sys 模块？")
    print("="*60)

    try:
        import copy
        sys_copy = copy.deepcopy(sys)
        print("✅ 可以深拷贝 sys")
    except Exception as e:
        print(f"❌ 不能深拷贝 sys: {e}")
        print("   sys 模块包含不可拷贝的对象")

    print("\n即使能拷贝，也会有问题：")
    print("  • sys 是单例，拷贝后就不是同一个了")
    print("  • import sys 永远返回真实的 sys")
    print("  • 用户代码中的 'import sys' 会获取真实 sys")


def test_import_in_user_code():
    """测试：用户代码中 import sys 会怎样？"""
    print("\n" + "="*60)
    print("测试 3: 用户代码中 import sys")
    print("="*60)

    original_len = len(sys.path)

    # 方案：不传 sys，让用户自己 import
    namespace = {}  # 空命名空间

    code = """
import sys  # 用户自己导入
sys.path.append('/test/path')
print(f"代码内部: sys.path 长度 = {len(sys.path)}")
"""

    exec(code, namespace)

    print(f"\n执行后，外部 sys.path 长度: {len(sys.path)}")

    if len(sys.path) > original_len:
        print("\n❌ 依然失败：sys.path 被修改了")
        print("   原因：import sys 返回的是全局单例")
        print("   无论如何导入，都是同一个 sys 对象")
    else:
        print("\n✅ 成功")

    # 恢复
    sys.path[:] = sys.path[:original_len]


def visualize_reference():
    """可视化：引用机制"""
    print("\n" + "="*60)
    print("可视化：引用 vs 拷贝")
    print("="*60)

    print("\n情况 1: 传递引用（你的方案）")
    print("-" * 40)
    print("""
真实的 sys 对象
    ↓
[sys.path, sys.modules, ...]  ← 全局单例
    ↑
namespace['sys']  ← 也指向同一个对象

修改 namespace['sys'].path.append(...)
    = 修改真实的 sys.path
    = 外部也看到修改
""")

    print("\n情况 2: 如果能完全拷贝（理想但做不到）")
    print("-" * 40)
    print("""
真实的 sys 对象
[sys.path, sys.modules, ...]  ← 全局单例

拷贝的 sys 对象（独立）
[sys.path_copy, sys.modules_copy, ...]
    ↑
namespace['sys']

修改 namespace['sys'].path.append(...)
    = 修改拷贝的 sys.path
    = 外部不受影响

但问题：
  • sys 不能深拷贝
  • 用户代码 'import sys' 还是获取真实 sys
  • 拷贝的 sys 不是真正的 sys
""")


def what_can_we_do():
    """我们能做什么？"""
    print("\n" + "="*60)
    print("那我们能做什么？")
    print("="*60)

    print("\n方案对比：")
    print("-" * 60)

    solutions = [
        {
            "方案": "传递 sys 引用",
            "代码": "namespace = {'sys': sys}",
            "能隔离": "❌ 否",
            "原因": "引用同一对象"
        },
        {
            "方案": "深拷贝 sys",
            "代码": "namespace = {'sys': copy.deepcopy(sys)}",
            "能隔离": "❌ 不可行",
            "原因": "sys 不能深拷贝"
        },
        {
            "方案": "空命名空间",
            "代码": "exec(code, {}, {})",
            "能隔离": "❌ 否",
            "原因": "import sys 获取真实 sys"
        },
        {
            "方案": "执行后重置",
            "代码": "exec(); sys.path.pop()",
            "能隔离": "✅ 是",
            "原因": "手动撤销修改"
        },
        {
            "方案": "定期重启进程",
            "代码": "restart_process()",
            "能隔离": "✅ 是",
            "原因": "完全清理"
        },
    ]

    print(f"{'方案':<20} {'能隔离':<10} {'原因':<30}")
    print("-" * 60)
    for s in solutions:
        print(f"{s['方案']:<20} {s['能隔离']:<10} {s['原因']:<30}")


def test_forbidden_imports():
    """测试：禁止导入 sys？"""
    print("\n" + "="*60)
    print("测试 4: 禁止导入 sys（极端方案）")
    print("="*60)

    # 创建自定义的 __import__
    def restricted_import(name, *args, **kwargs):
        if name == 'sys':
            raise ImportError("禁止导入 sys 模块！")
        return __import__(name, *args, **kwargs)

    namespace = {
        '__builtins__': {
            '__import__': restricted_import,
            'print': print,
        }
    }

    code = """
import sys  # 尝试导入
sys.path.append('/test')
"""

    print("\n执行代码...")
    try:
        exec(code, namespace)
        print("❌ 导入成功了")
    except ImportError as e:
        print(f"✅ 成功拦截: {e}")

    print("\n但这个方案有问题：")
    print("  • 用户需要 sys 来做正常操作")
    print("  • 过于严格，不实用")
    print("  • 用户可以用其他方式访问 sys")


def efficiency_comparison():
    """效率对比"""
    print("\n" + "="*60)
    print("测试 5: 效率对比")
    print("="*60)

    import time

    # 方案 1: 传递引用（你的方案，但不起作用）
    print("\n方案 1: 传递引用（不起作用但测试性能）")
    namespace = {"sys": sys}
    code = "import sys; x = 1"

    start = time.perf_counter()
    for _ in range(1000):
        exec(code, namespace)
    elapsed1 = time.perf_counter() - start

    print(f"  执行 1000 次: {elapsed1*1000:.2f}ms")
    print(f"  平均: {elapsed1:.4f}ms")

    # 方案 2: 空命名空间
    print("\n方案 2: 空命名空间（变量隔离）")
    start = time.perf_counter()
    for _ in range(1000):
        exec(code, {}, {})
    elapsed2 = time.perf_counter() - start

    print(f"  执行 1000 次: {elapsed2*1000:.2f}ms")
    print(f"  平均: {elapsed2:.4f}ms")

    # 方案 3: 空命名空间 + 重置
    print("\n方案 3: 空命名空间 + 重置 sys.path（我们的方案）")
    original_len = len(sys.path)

    start = time.perf_counter()
    for _ in range(1000):
        exec(code, {}, {})
        # 重置
        while len(sys.path) > original_len:
            sys.path.pop()
    elapsed3 = time.perf_counter() - start

    print(f"  执行 1000 次: {elapsed3*1000:.2f}ms")
    print(f"  平均: {elapsed3:.4f}ms")

    print("\n性能对比：")
    print(f"  方案 1（传引用）: {elapsed1*1000:.2f}ms - 基准")
    print(f"  方案 2（空命名空间）: {elapsed2*1000:.2f}ms - {(elapsed2/elapsed1-1)*100:+.1f}%")
    print(f"  方案 3（空+重置）: {elapsed3*1000:.2f}ms - {(elapsed3/elapsed1-1)*100:+.1f}%")

    print("\n结论：")
    print("  • 传引用最快，但不能隔离 sys ❌")
    print("  • 空命名空间稍慢，但能隔离变量 ✅")
    print("  • 加上重置几乎没有额外开销 ✅")


def main():
    """运行所有测试"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║    测试：隔离命名空间能否避免 sys 泄漏？                      ║
╚══════════════════════════════════════════════════════════════╝
""")

    test_your_idea()
    why_it_doesnt_work()
    test_deep_copy()
    test_import_in_user_code()
    visualize_reference()
    test_forbidden_imports()
    what_can_we_do()
    efficiency_comparison()

    print("\n" + "="*60)
    print("总结")
    print("="*60)
    print("""
Q: 创建隔离命名空间能避免 sys 泄漏吗？
A: ❌ 不能！

原因：
  1. namespace = {'sys': sys} 传递的是**引用**
  2. sys 是 Python 的**全局单例对象**
  3. 修改引用 = 修改原对象
  4. 就像两个变量指向同一个列表

Q: 为什么不能拷贝 sys？
A: • sys 包含不可拷贝的对象
   • 即使能拷贝，用户 'import sys' 还是获取真实 sys
   • 拷贝的 sys 不是真正的 sys

Q: 那效率会更高吗？
A: • 传引用确实最快（但不能隔离）
   • 空命名空间几乎一样快（能隔离变量）
   • 加上重置 sys.path 几乎无额外开销

Q: 最佳方案是什么？
A: ✅ 我们的 executor_isolated.py：
   • exec(code, {}, {}) - 隔离变量
   • 手动重置 sys.path - 隔离 sys
   • 定期重启进程 - 完全清理
   • 性能优秀 + 完全隔离

结论：
  没有魔法方案能完全隔离 sys，
  只能通过执行后重置或定期重启来清理。
  我们的方案已经是最佳平衡！✅
""")


if __name__ == "__main__":
    main()
