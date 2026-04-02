# 使用一个包含 Python 和 Debian Buster 的基础镜像
# Debian Buster 提供了较好的 Chromium 包支持
FROM python:3.9-slim-buster

# 设置工作目录
WORKDIR /app

# 安装 Chromium 及其依赖。
# 这会增加镜像大小，但对于 DrissionPage 是必需的。
# --no-install-recommends 减少不必要的包
RUN apt-get update && apt-get install -y \
    chromium \
    # 某些字体库，避免 Chromium 在无头模式下字体渲染问题
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libcups2 \
    libgdk-pixbuf2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxss1 \
    xdg-utils \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# 设置 Chromium 的环境变量，确保 DrissionPage 能找到它
ENV CHROMIUM_BIN /usr/bin/chromium
ENV DRISSION_PAGE_BROWSER_PATH /usr/bin/chromium # 告诉 DrissionPage 浏览器路径

# 复制 requirements.txt 并安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制您的应用代码
COPY . .

# 暴露 FastAPI 应用监听的端口
EXPOSE 8000

# 启动 Gunicorn 服务器来运行 FastAPI 应用
# -w 4: 运行 4 个 worker 进程，可以根据 CPU 核心数调整
# -k uvicorn.workers.UvicornWorker: 使用 uvicorn worker 类型，以便兼容 ASGI 应用
# app:app: 指的是 app.py 文件中的 app 对象
CMD ["/usr/local/bin/python", "-m", "gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "app:app", "--bind", "0.0.0.0:8000"]
