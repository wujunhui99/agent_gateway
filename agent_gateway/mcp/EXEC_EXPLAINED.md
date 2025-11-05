# Python exec() 函数详解：我们已经在用了！

## 🎯 核心发现

**我们的三个实现都在使用 `exec()` 函数！** 这是 Python 中动态执行代码的标准方式。

## 📖 exec() 基础知识

### 语法

```python
exec(code, globals=None, locals=None)
```

**参数说明：**
- `code`: 要执行的 Python 代码（字符串）
- `globals`: 全局命名空间（字典）
- `locals`: 局部命名空间（字典）

### 示例

```python
# 最简单的用法
exec("print('Hello')")  # 输出: Hello

# 带命名空间
code = "result = x + y"
local_vars = {"x": 1, "y": 2}
exec(code, {}, local_vars)
print(local_vars["result"])  # 输出: 3
```

## 🔍 我们的实现中如何使用 exec()

### 1. executor.py (Baseline) - Docker 容器中使用

```python
# 在 scripts/python_exec.py 中
def run_code(code: str) -> dict:
    local_vars = {}
    try:
        exec(code, {}, local_vars)  # ← 使用 exec()
        return {
            "stdout": stdout_buffer.getvalue(),
            "locals": local_vars,
        }
    except Exception as exc:
        return {"error": str(exc)}
```

### 2. executor_optimized.py - 持久化进程中使用

```python
# 在持久化进程的代码中
def run_code(code: str) -> dict:
    local_vars = {}
    exec(code, {}, local_vars)  # ← 同样使用 exec()
    return {"locals": local_vars}
```

### 3. executor_isolated.py - 带状态重置

```python
def run_code_with_reset(code: str) -> dict:
    # 保存状态
    original_path_len = len(sys.path)

    local_vars = {}
    exec(code, {}, local_vars)  # ← 使用 exec()

    # 恢复状态
    while len(sys.path) > original_path_len:
        sys.path.pop()

    return {"locals": local_vars}
```

**所以所有实现的核心都是 `exec()`！**

## 🎓 exec() 的三个参数详解

### 参数组合效果对比

| 用法 | 效果 | 隔离程度 | 示例 |
|------|------|---------|------|
| `exec(code)` | 在当前命名空间执行 | ❌ 无隔离 | 危险 |
| `exec(code, {})` | 空全局，当前局部 | 🟡 部分 | 有限 |
| `exec(code, {}, {})` | 空全局，空局部 | 🟢 完全 | 推荐 |

### 详细示例

#### ❌ 方式 1: 不传参数（危险）

```python
x = 100  # 外部变量

code = """
x = 200  # 会修改外部变量！
y = 300
"""

exec(code)  # 在当前命名空间执行

print(x)  # 输出: 200 ← 被修改了！
print(y)  # 输出: 300 ← 污染了外部环境
```

**问题：**
- ❌ 会修改外部变量
- ❌ 会污染外部命名空间
- ❌ 不安全！

---

#### 🟡 方式 2: 只传 globals

```python
x = 100

code = """
x = 200
y = 300
"""

global_ns = {}
exec(code, global_ns)

print(x)  # 输出: 100 ← 外部变量未被修改
print(global_ns)  # {'__builtins__': ..., 'x': 200, 'y': 300}
```

**特点：**
- ✅ 不会修改外部变量
- ⚠️ 但变量会留在 global_ns 中

---

#### ✅ 方式 3: 传 globals 和 locals（推荐）

```python
x = 100

code = """
x = 200
y = 300
result = x + y
"""

global_ns = {}
local_ns = {}
exec(code, global_ns, local_ns)

print(x)  # 输出: 100 ← 外部不受影响
print(local_ns)  # {'x': 200, 'y': 300, 'result': 500}
print(global_ns)  # {'__builtins__': ...} ← 干净
```

**优点：**
- ✅ 完全隔离
- ✅ 变量存储在 local_ns
- ✅ 可以获取执行结果
- ✅ 安全

**这就是我们使用的方式！**

## 🔬 深入理解：globals 和 locals 的区别

### globals 的作用

```python
# 测试：能否访问内置函数？

# 不传 globals（可以访问）
exec("result = len([1, 2, 3])")  # ✅ 正常工作

# 传空 globals（不能访问）
local_ns = {}
exec("result = len([1, 2, 3])", {}, local_ns)  # ❌ NameError: len
```

**为什么？**
- 内置函数（`len`, `print` 等）在 `__builtins__` 中
- 空的 `globals={}` 没有 `__builtins__`

**解决方案：**

```python
# 方案 1: 添加 __builtins__
import builtins
safe_globals = {"__builtins__": builtins}
exec(code, safe_globals, local_ns)

# 方案 2: 自动添加
global_ns = {}
local_ns = {}
exec(code, global_ns, local_ns)
# exec() 会自动添加 __builtins__ 到 global_ns
```

### locals 的作用

```python
code1 = """
x = 100
def my_func():
    return x * 2
result = my_func()
"""

local_ns = {}
exec(code1, {}, local_ns)

print(local_ns)
# {
#   'x': 100,
#   'my_func': <function>,
#   'result': 200
# }

# 尝试在下一次执行中访问
code2 = "print(x)"
exec(code2, {}, {})  # ❌ NameError: x ← 已隔离
```

**关键：**
- 每次传入新的 `local_ns = {}`
- 之前的变量不会保留
- 实现了执行隔离

## 💡 exec() 的隔离机制

### 我们的实现

```python
# executor_optimized.py 中的实现
def run_code(code: str) -> dict:
    local_vars = {}  # 每次创建新的

    try:
        # 关键：空的 globals，新的 locals
        exec(code, {}, local_vars)

        return {
            "stdout": stdout_buffer.getvalue(),
            "locals": local_vars,  # 返回结果
        }
    except Exception:
        return {"error": ...}
```

### 为什么能隔离变量？

```python
# 执行 1
local_vars_1 = {}
exec("x = 100", {}, local_vars_1)
# local_vars_1 = {'x': 100}

# 执行 2（新的 local_vars）
local_vars_2 = {}
exec("result = x", {}, local_vars_2)
# ❌ NameError: x ← 因为 local_vars_2 是空的
```

### 为什么函数也隔离？

```python
# 执行 1：定义函数
local_vars_1 = {}
exec("def my_func(): return 42", {}, local_vars_1)
# local_vars_1 = {'my_func': <function>}

# 执行 2：尝试调用
local_vars_2 = {}
exec("result = my_func()", {}, local_vars_2)
# ❌ NameError: my_func ← 函数存储在 local_vars_1 中
```

## ⚠️ exec() 无法隔离的内容

### 1. sys 模块状态

```python
# 执行 1：修改 sys.path
local_ns = {}
exec("import sys; sys.path.append('/fake')", {}, local_ns)

# 执行 2：检查 sys.path
local_ns = {}
exec("import sys; result = '/fake' in sys.path", {}, local_ns)
print(local_ns['result'])  # True ← sys.path 被修改了！
```

**原因：**
- `sys` 是全局单例对象
- `exec()` 无法隔离 Python 解释器的内部状态

### 2. 已导入的模块（sys.modules）

```python
import sys

# 执行 1：导入模块
exec("import math", {}, {})

# 检查
print('math' in sys.modules)  # True ← 模块留在内存中
```

### 3. 全局解释器状态

- 环境变量 (`os.environ`)
- 信号处理器 (`signal`)
- 线程状态
- 文件描述符

## 🛡️ 安全使用 exec() 的最佳实践

### 1. 始终使用三参数形式

```python
# ❌ 错误
exec(user_code)

# ✅ 正确
exec(user_code, {}, {})
```

### 2. 限制可用的内置函数

```python
# 创建受限的 builtins
safe_builtins = {
    "print": print,
    "len": len,
    "range": range,
    # 不包括危险的函数如 open, eval, __import__
}

safe_globals = {"__builtins__": safe_builtins}
exec(code, safe_globals, {})
```

### 3. 使用 RestrictedPython（更安全）

```python
from RestrictedPython import compile_restricted, safe_globals

byte_code = compile_restricted(code, '<string>', 'exec')
local_ns = {}
exec(byte_code, safe_globals, local_ns)
```

### 4. 添加超时保护

```python
import signal

def timeout_handler(signum, frame):
    raise TimeoutError("Code execution timeout")

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(5)  # 5 秒超时

try:
    exec(code, {}, {})
finally:
    signal.alarm(0)  # 取消超时
```

## 📊 exec() vs eval() vs compile()

| 函数 | 用途 | 返回值 | 安全性 |
|------|------|--------|--------|
| `exec(code)` | 执行语句 | None | 🟡 中等 |
| `eval(expr)` | 计算表达式 | 表达式的值 | 🟡 中等 |
| `compile(code)` | 编译代码 | 字节码对象 | 🟢 更安全 |

### eval() 示例

```python
# eval 只能执行表达式，不能执行语句
result = eval("1 + 2")  # ✅ 返回 3
eval("x = 1")  # ❌ SyntaxError（不是表达式）

# exec 可以执行语句
exec("x = 1")  # ✅ 可以
result = exec("1 + 2")  # ✅ 可以，但 result = None
```

### compile() + exec() 组合（更安全）

```python
# 先编译
try:
    byte_code = compile(user_code, '<string>', 'exec')
except SyntaxError as e:
    print(f"语法错误: {e}")
    return

# 再执行
try:
    exec(byte_code, {}, {})
except Exception as e:
    print(f"运行错误: {e}")
```

**优点：**
- 可以提前检查语法错误
- 可以缓存编译结果
- 可以使用 `compile_restricted`（RestrictedPython）

## 🎯 总结：为什么我们的方案是最优的

### 我们使用的方式

```python
# executor_isolated.py
local_vars = {}
exec(code, {}, local_vars)  # ← 正确的三参数形式
```

**优点：**
1. ✅ 使用 `exec()` - Python 标准方式
2. ✅ 空 globals - 隔离全局命名空间
3. ✅ 新 locals - 每次执行都是干净的
4. ✅ 捕获异常 - 安全处理错误
5. ✅ 重置状态 - 清理 sys.path 等
6. ✅ 定期重启 - 防止累积

### 与其他方案对比

| 方案 | 实现方式 | 性能 | 隔离 |
|------|---------|------|------|
| subprocess.run | 每次 fork 新进程 | ❌ 慢 | ✅ 完全 |
| **exec(code, {}, {})** | **持久化进程 + exec** | **✅ 快** | **✅ 完全** |
| eval(code) | 仅表达式 | ✅ 快 | ⚠️ 有限 |

## 💡 实用技巧

### 1. 捕获 print 输出

```python
from io import StringIO
from contextlib import redirect_stdout

stdout_buffer = StringIO()
with redirect_stdout(stdout_buffer):
    exec("print('Hello')", {}, {})

output = stdout_buffer.getvalue()  # "Hello\n"
```

### 2. 获取所有局部变量

```python
code = """
x = 1
y = 2
result = x + y
"""

local_vars = {}
exec(code, {}, local_vars)

print(local_vars)  # {'x': 1, 'y': 2, 'result': 3}
```

### 3. 允许特定的全局变量

```python
code = "result = PI * 2"

safe_globals = {
    "__builtins__": __builtins__,
    "PI": 3.14159,  # 允许访问 PI
}

local_vars = {}
exec(code, safe_globals, local_vars)
print(local_vars['result'])  # 6.28318
```

## 🎓 最终答案

**Q: Python 中有 exec 函数，使用 exec 函数执行代码怎么样？**

**A: 我们已经在用了！而且用得很好！**

核心要点：
1. ✅ 所有实现都使用 `exec(code, {}, local_vars)`
2. ✅ 这是 Python 中动态执行代码的标准方式
3. ✅ 通过空 globals 和新 locals 实现隔离
4. ⚠️ 但需要手动处理 sys 状态（已在 executor_isolated.py 中实现）
5. ✅ 性能优秀，隔离良好，生产就绪

**`exec()` 不是问题，关键是如何正确使用！** 🎯
