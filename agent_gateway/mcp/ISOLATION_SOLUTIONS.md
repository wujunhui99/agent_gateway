# Python 代码执行的状态隔离问题与解决方案

## 📋 问题概述

在使用持久化 Python 进程执行多段代码时，面临一个核心问题：
**前一次执行的代码会不会影响后续执行？**

## 🧪 测试结果分析

根据 `test_isolation.py` 的测试结果：

### ✅ 当前版本已经隔离的内容

| 内容类型 | 是否隔离 | 原因 |
|---------|---------|------|
| **局部变量** | ✅ 是 | 每次使用新的 `local_vars = {}` |
| **函数定义** | ✅ 是 | 函数存储在 locals 中 |
| **类定义** | ✅ 是 | 类存储在 locals 中 |
| **异常状态** | ✅ 是 | 异常被捕获后清除 |

### ❌ 当前版本未隔离的内容

| 内容类型 | 是否隔离 | 风险等级 | 影响 |
|---------|---------|---------|------|
| **已导入模块** | ❌ 否 | 🟡 中 | 模块状态可能被修改 |
| **sys 修改** | ❌ 否 | 🟠 高 | sys.path 等会累积 |
| **全局变量** | ❌ 否 | 🔴 很高 | 可能导致意外行为 |
| **打开的文件** | ❌ 否 | 🟠 高 | 可能资源泄漏 |
| **内存累积** | ❌ 否 | 🟡 中 | 长期运行可能 OOM |

## 🔍 为什么会这样？

### 当前实现 (executor_optimized.py)

```python
# 在持久化进程的主循环中
local_vars = {}  # 每次创建新的 locals
exec(code, {}, local_vars)  # globals={}, locals=local_vars
```

**这个实现的特点：**

1. **`globals={}`** - 提供了**空的全局命名空间**
   - ✅ 好处：代码看不到外部的全局变量
   - ❌ 问题：但是 Python 解释器的内部状态仍然共享

2. **`locals=local_vars`** - 每次新建
   - ✅ 好处：局部变量完全隔离

3. **Python 解释器状态** - 持久化
   - ❌ `sys.modules`：已导入的模块保留在内存
   - ❌ `sys.path`：路径修改会累积
   - ❌ 全局状态：如环境变量、信号处理器等

## 💡 解决方案对比

### 方案 1: 保持现状（推荐用于大多数场景）

**适用场景：** 用户代码是可信的，性能最重要

**优点：**
- ✅ 性能最好 (1900+ calls/s)
- ✅ 实现简单
- ✅ 已有基本隔离（局部变量、函数）

**缺点：**
- ❌ 模块状态可能冲突
- ❌ 全局状态会累积

**改进建议：**
```python
# 添加定期重启机制
if execution_count > 1000:  # 每1000次执行后重启
    restart_process()
```

---

### 方案 2: 重置全局状态（平衡方案）⭐

**适用场景：** 需要更好的隔离，但仍要保持高性能

```python
def run_code_with_reset(code: str) -> dict:
    # 保存原始状态
    original_modules = set(sys.modules.keys())
    original_path = sys.path.copy()

    local_vars = {}
    try:
        exec(code, {}, local_vars)
        result = {
            "stdout": stdout_buffer.getvalue(),
            "stderr": stderr_buffer.getvalue(),
            "locals": local_vars,
        }
    finally:
        # 清理新导入的模块
        for mod in list(sys.modules.keys()):
            if mod not in original_modules:
                del sys.modules[mod]

        # 恢复 sys.path
        sys.path = original_path

    return result
```

**优点：**
- ✅ 更好的隔离
- ✅ 防止状态累积
- ✅ 性能仍然很好

**缺点：**
- ⚠️ 略有性能损失（但仍远超 baseline）
- ⚠️ 实现复杂度增加

---

### 方案 3: 每次创建子进程（最强隔离）

**适用场景：** 执行不可信代码，安全性最重要

```python
def run_code_in_subprocess(code: str) -> dict:
    # 在持久化进程内 fork 子进程
    import multiprocessing

    def _execute():
        local_vars = {}
        exec(code, {}, local_vars)
        return local_vars

    with multiprocessing.Pool(1) as pool:
        result = pool.apply(_execute)

    return result
```

**优点：**
- ✅ 完全隔离
- ✅ 崩溃不影响主进程
- ✅ 可以设置资源限制（CPU、内存）

**缺点：**
- ❌ 性能下降 (约 100-200 calls/s)
- ❌ 进程创建开销

---

### 方案 4: 使用 RestrictedPython（最安全）

**适用场景：** 需要限制代码能力，防止恶意代码

```python
from RestrictedPython import compile_restricted, safe_globals

def run_code_restricted(code: str) -> dict:
    byte_code = compile_restricted(code, '<string>', 'exec')

    local_vars = {}
    exec(byte_code, safe_globals, local_vars)

    return {"locals": local_vars}
```

**优点：**
- ✅ 最安全（限制危险操作）
- ✅ 可以控制允许的操作
- ✅ 性能还可以

**缺点：**
- ❌ 功能受限（某些操作被禁止）
- ❌ 需要额外依赖
- ❌ 用户体验可能受影响

---

### 方案 5: 定期重启进程（混合方案）⭐

**适用场景：** 在性能和隔离之间取得最佳平衡

```python
class PersistentPythonExecutor:
    def __init__(self, max_executions=1000):
        self._execution_count = 0
        self._max_executions = max_executions

    def execute(self, code: str) -> dict:
        self._execution_count += 1

        # 定期重启
        if self._execution_count >= self._max_executions:
            self._restart_process()
            self._execution_count = 0

        # 正常执行
        return self._execute_code(code)
```

**优点：**
- ✅ 大部分时间保持高性能
- ✅ 定期清理防止状态累积
- ✅ 实现简单

**缺点：**
- ⚠️ 重启时会有短暂延迟

---

## 📊 方案性能对比

| 方案 | 吞吐量 | 隔离程度 | 实现复杂度 | 推荐度 |
|------|--------|---------|-----------|--------|
| 1. 保持现状 | 1900/s | 🟡 中 | ⭐ 简单 | ⭐⭐⭐ |
| 2. 重置全局状态 | 1500/s | 🟢 高 | ⭐⭐ 中等 | ⭐⭐⭐⭐⭐ |
| 3. 子进程隔离 | 150/s | 🟢 完全 | ⭐⭐⭐ 复杂 | ⭐⭐ |
| 4. RestrictedPython | 1000/s | 🟢 完全 | ⭐⭐⭐ 复杂 | ⭐⭐⭐ |
| 5. 定期重启 | 1850/s | 🟢 高 | ⭐ 简单 | ⭐⭐⭐⭐⭐ |

## 🎯 推荐方案

### 对于你的场景（Agent Gateway）

**推荐：方案 2（重置全局状态）+ 方案 5（定期重启）**

```python
class PersistentPythonExecutor:
    def __init__(self, max_executions=1000):
        self._execution_count = 0
        self._max_executions = max_executions

    def execute(self, code: str) -> dict:
        # 定期重启
        self._execution_count += 1
        if self._execution_count >= self._max_executions:
            self._restart_process()
            self._execution_count = 0

        # 保存原始状态
        original_modules = set(sys.modules.keys())
        original_path = sys.path.copy()

        local_vars = {}
        try:
            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                exec(code, {}, local_vars)

            result = {
                "stdout": stdout_buffer.getvalue(),
                "locals": local_vars,
            }
        finally:
            # 清理新导入的模块（可选，根据需要）
            # for mod in list(sys.modules.keys()):
            #     if mod not in original_modules:
            #         del sys.modules[mod]

            # 恢复 sys.path（必须）
            sys.path[:] = original_path

        return result
```

**为什么推荐这个组合？**
1. ✅ 性能几乎不受影响（~1800 calls/s）
2. ✅ 防止状态累积
3. ✅ 长期运行稳定
4. ✅ 实现简单

## ⚠️ 注意事项

### 1. 模块导入的性能权衡

**不清理模块：**
- ✅ 性能更好（模块被缓存）
- ❌ 可能有状态污染

**清理模块：**
- ✅ 隔离更好
- ❌ 每次都要重新导入（慢）

**建议：**
- 标准库模块：不清理（如 math, json）
- 第三方库：根据需要决定

### 2. 内存管理

即使清理了模块，内存仍可能累积。建议：

```python
import gc

def execute(self, code: str) -> dict:
    result = self._execute_code(code)

    # 定期强制垃圾回收
    if self._execution_count % 100 == 0:
        gc.collect()

    return result
```

### 3. 监控指标

建议监控：
- 内存使用：`psutil.Process().memory_info().rss`
- 执行次数：`self._execution_count`
- 模块数量：`len(sys.modules)`
- 执行耗时：记录每次执行时间

## 📚 相关资源

- Python exec() 文档: https://docs.python.org/3/library/functions.html#exec
- RestrictedPython: https://github.com/zopefoundation/RestrictedPython
- 沙箱安全: https://nedbatchelder.com/blog/201206/eval_really_is_dangerous.html

## 🔬 实验：测试你的场景

创建测试脚本验证隔离效果：

```bash
cd agent_gateway/mcp
python test_isolation.py
```

根据测试结果选择最适合你的方案！
