# 使用 Python 3.11 slim 镜像作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 创建非root用户
RUN useradd -m -u 1000 appuser

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 创建数据目录（用于 RAG 存储）
RUN mkdir -p /app/data && chown -R appuser:appuser /app

# 切换到非root用户
USER appuser

# 暴露应用端口
EXPOSE 8081

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8081/health')" || exit 1

# 启动应用
CMD ["python", "main.py"]
