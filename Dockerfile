FROM node:22-alpine AS web-builder

WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build


FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖（Pillow 需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
COPY packages/agent-core ./packages/agent-core
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .
COPY --from=web-builder /web/dist ./web/dist

# CloudBase 云托管使用 PORT 环境变量
EXPOSE 80

CMD gunicorn --bind "0.0.0.0:${PORT:-80}" --workers 2 --timeout 120 app:app
