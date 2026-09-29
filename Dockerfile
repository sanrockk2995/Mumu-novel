# Dockerfile build đa giai đoạn cho AI Story Creator
# Hỗ trợ build đa kiến trúc: linux/amd64, linux/arm64

# Tham số build
ARG USE_CN_MIRROR=false
ARG EMBEDDING_MODEL_REVISION=60750e200f336606cdd1ecbda9bb33fbf4d5b2a1

# Giai đoạn 1: build frontend
FROM node:22-alpine AS frontend-builder

ARG USE_CN_MIRROR

WORKDIR /frontend

# Copy file dependency của frontend
COPY frontend/package*.json ./

# Quyết định có dùng npm mirror nội địa không theo tham số
RUN if [ "$USE_CN_MIRROR" = "true" ]; then \
        npm config set registry https://registry.npmmirror.com; \
    fi

# Xóa package-lock.json để tránh lỗi 404 do mirror source không nhất quán
RUN rm -f package-lock.json

# Cài đặt dependency
RUN npm install

# Copy mã nguồn frontend
COPY frontend/ ./

# Tạm thời sửa cấu hình vite để output ra thư mục dist (thay vì ../backend/static)
RUN sed -i "s|outDir: '../backend/static'|outDir: 'dist'|g" vite.config.ts

# Build frontend
RUN npm run build

# Giai đoạn 2: build image cuối cùng
FROM python:3.12-slim

ARG USE_CN_MIRROR
ARG TARGETPLATFORM
ARG TARGETARCH
ARG EMBEDDING_MODEL_REVISION

# Thiết lập thư mục làm việc
WORKDIR /app

# Quyết định có dùng mirror source nội địa không theo tham số
RUN if [ "$USE_CN_MIRROR" = "true" ]; then \
        sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
        sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources; \
    fi

# Cài đặt dependency hệ thống (thêm công cụ database)
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    postgresql-client \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Copy file dependency của backend
COPY backend/requirements.txt ./

# Cài đặt dependency runtime ONNX không kèm PyTorch/Transformers
RUN if [ "$USE_CN_MIRROR" = "true" ]; then \
        pip install --no-cache-dir -r requirements.txt -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple; \
    else \
        pip install --no-cache-dir -r requirements.txt; \
    fi

# Tải trực tiếp file triển khai ONNX đã chuyển đổi từ ModelScope, và kiểm tra manifest phát hành.
ENV ONNX_EMBEDDING_MODEL_DIR=/app/embedding/onnx/paraphrase-multilingual-MiniLM-L12-v2
RUN set -eu; \
    model_url="https://modelscope.cn/models/mumujie/paraphrase-multilingual-MiniLM-L12-v2-ONNX/resolve/${EMBEDDING_MODEL_REVISION}"; \
    mkdir -p "$ONNX_EMBEDDING_MODEL_DIR"; \
    curl --fail --location --retry 5 --retry-all-errors "$model_url/model.onnx" -o "$ONNX_EMBEDDING_MODEL_DIR/model.onnx"; \
    curl --fail --location --retry 5 --retry-all-errors "$model_url/tokenizer.json" -o "$ONNX_EMBEDDING_MODEL_DIR/tokenizer.json"; \
    curl --fail --location --retry 5 --retry-all-errors "$model_url/embedding_config.json" -o "$ONNX_EMBEDDING_MODEL_DIR/embedding_config.json"; \
    echo "e7515ed8b2f63e84f99dfed652b572e61a9a799f694a1c9399a7f3845b69cda5  $ONNX_EMBEDDING_MODEL_DIR/model.onnx" | sha256sum -c -; \
    echo "2c3387be76557bd40970cec13153b3bbf80407865484b209e655e5e4729076b8  $ONNX_EMBEDDING_MODEL_DIR/tokenizer.json" | sha256sum -c -; \
    echo "d9cfbb22ea59e66294db9bd5b35b452326658a2fe1580e409f0c806be01973c2  $ONNX_EMBEDDING_MODEL_DIR/embedding_config.json" | sha256sum -c -

# Copy code backend (không gồm embedding, vì đã tải về)
COPY backend/ ./

# Copy file tĩnh đã build từ giai đoạn build frontend
COPY --from=frontend-builder /frontend/dist ./static

# Copy cấu hình và script migration Alembic (PostgreSQL)
COPY backend/alembic-postgres.ini ./alembic.ini
COPY backend/alembic/postgres ./alembic
COPY backend/scripts/entrypoint.sh /app/entrypoint.sh
COPY backend/scripts/migrate.py ./scripts/migrate.py

# Cấp quyền thực thi
RUN chmod +x /app/entrypoint.sh

# Tạo các thư mục cần thiết
RUN mkdir -p /app/data /app/logs

# Expose cổng
EXPOSE 8000

# Thiết lập biến môi trường
ENV PYTHONUNBUFFERED=1
ENV APP_HOST=0.0.0.0
ENV APP_PORT=8000

# Kiểm tra sức khỏe
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Khởi động bằng script entrypoint (tự động chạy migration)
ENTRYPOINT ["/app/entrypoint.sh"]
