# MCP Python Sandbox Performance Benchmark

## 概述

本性能测试套件用于对比当前实现和优化版本的性能差异。

## 测试架构

### 当前实现 (executor.py)
```
调用 → subprocess.run → docker compose exec → 新 Python 进程 → 执行代码 → 返回结果
```

**问题:**
- 每次调用都创建新的 subprocess
- 每次都执行 docker exec (有 Docker API 开销)
- 每次都启动新的 Python 解释器 (50-150ms)

### 优化实现 (executor_optimized.py)
```
首次调用 → 启动持久化 Python 进程
后续调用 → 通过 stdin/stdout 管道通信 → 执行代码 → 返回结果
```

**改进:**
- ✅ 进程复用 - 避免重复创建进程
- ✅ 解释器复用 - Python 解释器只启动一次
- ✅ 管道通信 - 避免 docker exec 开销
- ✅ 线程安全 - 使用锁保护并发访问

## 测试用例

1. **simple_calc**: 简单计算 (1+1)
2. **loop_calc**: 循环计算 (sum)
3. **string_ops**: 字符串操作
4. **list_comp**: 列表推导式
5. **dict_ops**: 字典操作
6. **json_parsing**: JSON 解析
7. **mixed_workload**: 混合负载

## 运行测试

### 前置条件

确保 Docker 容器正在运行:
```bash
cd agent_gateway/mcp
docker compose up -d
```

### 运行基准测试

```bash
cd agent_gateway/mcp
python benchmark.py
```

### 预期改进

根据架构分析，预期优化版本将实现:

| 指标 | 当前实现 | 优化版本 | 改进幅度 |
|------|----------|----------|----------|
| 平均延迟 | 100-300ms | 5-20ms | **85-95% ↓** |
| 吞吐量 | 3-10 calls/s | 50-200 calls/s | **5-20x ↑** |
| P95 延迟 | 200-400ms | 10-30ms | **85-92% ↓** |

## 输出

### 控制台输出
- 实时进度显示
- 详细的性能指标
- 对比分析表格

### 文件输出
- `benchmark_results.json`: 详细的性能数据(JSON 格式)

## 性能指标说明

- **Average time**: 平均执行时间
- **Median time**: 中位数执行时间
- **P95/P99 time**: 95%/99% 分位数延迟
- **Throughput**: 每秒可处理的请求数
- **Min/Max time**: 最小/最大执行时间

## 后续优化建议

如果性能仍不满足需求，可以考虑:

1. **预导入常用库**: 在启动时预导入 numpy, pandas 等
2. **进程池**: 维护多个 Python 进程处理并发请求
3. **结果缓存**: 对相同代码进行结果缓存
4. **Docker 优化**: 使用 Docker SDK 替代 CLI
5. **本地执行**: 在可信环境下直接执行而不用 Docker

## 安全性考虑

优化版本保持了与原版本相同的安全隔离:
- ✅ Docker 容器隔离
- ✅ network_mode: none (无网络访问)
- ✅ 只读卷挂载
- ✅ 执行超时保护
- ⚠️ 需要额外添加: 内存限制、CPU 限制

## 使用优化版本

要在生产环境使用优化版本，修改 `tools.py`:

```python
# 替换导入
from .mcp.executor_optimized import run_python_sandbox_optimized as run_python_sandbox

# 或者直接修改函数调用
def _python_execute_sync(code: str, input: Optional[str] = None):
    result = run_python_sandbox_optimized(code, input)  # 使用优化版本
    return {"status": "success", **result}
```

记得在应用关闭时清理资源:
```python
from .mcp.executor_optimized import cleanup_executor
atexit.register(cleanup_executor)
```
