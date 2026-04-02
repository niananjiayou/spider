# 将基础镜像从 python:3.9-slim-buster 更改为 python:3.9-slim-bullseye
FROM python:3.9-slim-bullseye

# 设置工作目录
WORKDIR /app

# 安装 Chromium 及其依赖。
# 使用 --no-install-recommends 减少不必要的包。
RUN apt-get update && apt-get install -y \
    chromium \
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
    --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 设置 Chromium 的环境变量，确保 DrissionPage 能找到它
ENV CHROMIUM_BIN /usr/bin/chromium
ENV DRISSION_PAGE_BROWSER_PATH /usr/bin/chromium

# 复制 requirements.txt 并安装 Python 依赖
COPY requirements.txt .
# 升级 pip，然后安装所有依赖
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 复制您的应用代码
COPY . .

# 暴露 FastAPI 应用监听的端口
EXPOSE 8000

# 启动 Gunicorn 服务器来运行 FastAPI 应用
# 关键修改：将 workers 数量从 4 减少到 1
CMD ["/usr/local/bin/python", "-m", "gunicorn", "-w", "1", "-k", "uvicorn.workers.UvicornWorker", "app:app", "--bind", "0.0.0.0:8000", "--timeout", "120"]
