#!/bin/bash
# Script điểm vào khởi động container Docker
# Chức năng: chờ database sẵn sàng, chạy migration, khởi động ứng dụng

set -e  # Gặp lỗi thoát ngay

# Lấy thông tin phiên bản (từ file .env.example)
# Nếu biến môi trường chưa đặt, đọc từ .env.example
if [ -z "$APP_VERSION" ]; then
    if [ -f "/app/.env.example" ]; then
        APP_VERSION=$(grep "^APP_VERSION=" /app/.env.example | cut -d '=' -f2)
    fi
    APP_VERSION="${APP_VERSION:-1.5.6}"
fi

if [ -z "$APP_NAME" ]; then
    if [ -f "/app/.env.example" ]; then
        APP_NAME=$(grep "^APP_NAME=" /app/.env.example | cut -d '=' -f2)
    fi
    APP_NAME="${APP_NAME:-MuMuAINovel}"
fi

BUILD_TIME=$(date '+%Y-%m-%d %H:%M:%S')

echo "================================================"
echo "🚀 Đang khởi động ${APP_NAME}..."
echo "📦 Phiên bản: v${APP_VERSION}"
echo "🕐 Thời gian khởi động: ${BUILD_TIME}"
echo "================================================"

# Cấu hình database (đọc từ biến môi trường)
DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${POSTGRES_USER:-mumuai}"
DB_NAME="${POSTGRES_DB:-mumuai_novel}"

# Chờ database sẵn sàng
echo "⏳ Đang chờ database khởi động..."
MAX_RETRIES=30
RETRY_COUNT=0

while ! nc -z "$DB_HOST" "$DB_PORT" 2>/dev/null; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "❌ Lỗi: timeout kết nối database (${MAX_RETRIES} giây)"
        exit 1
    fi
    echo "   Đang chờ database... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 1
done

echo "✅ Kết nối database thành công"

# Chờ thêm, đảm bảo database hoàn toàn sẵn sàng
echo "⏳ Đang chờ database hoàn toàn sẵn sàng..."
sleep 3

# Kiểm tra database có nhận kết nối không
echo "🔍 Kiểm tra trạng thái database..."
if ! PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" > /dev/null 2>&1; then
    echo "❌ Database chưa sẵn sàng, tiếp tục chờ..."
    sleep 5
fi

echo "✅ Database đã sẵn sàng"

# Chạy migration database
echo "================================================"
echo "🔄 Thực hiện migration database..."
echo "================================================"

cd /app

# Thống nhất dùng alembic upgrade head
# Alembic tự xử lý triển khai lần đầu và migration tăng dần
echo "🔄 Nâng database lên phiên bản mới nhất..."
alembic upgrade head

if [ $? -eq 0 ]; then
    echo "✅ Migration database thành công"
else
    echo "❌ Migration database thất bại"
    exit 1
fi

echo "================================================"
echo "🎉 Khởi động dịch vụ ứng dụng..."
echo "================================================"

# Khởi động ứng dụng (dùng exec thay tiến trình hiện tại, đảm bảo signal truyền đúng)
cd /app
exec uvicorn app.main:app \
    --host "${APP_HOST:-0.0.0.0}" \
    --port "${APP_PORT:-8000}" \
    --log-level info \
    --access-log \
    --use-colors
