#!/bin/bash
# =============================================================================
# Script cài đặt một cú nhấp Termux MuMuAINovel
# =============================================================================
# 

set -e

# ── Cấu hình đường dẫn ──────────────────────────────────────────────────────────────────
INSTALL_DIR="$HOME/MuMuAINovel"                    # Thư mục cài đặt dự án
DATA_DIR="$HOME/mumuainovel/data"                   # Thư mục database
LOG_DIR="$HOME/mumuainovel/logs"                    # Thư mục log
REPO="https://ghfast.top/https://github.com/xiamuceer-j/MuMuAINovel.git"  # Mirror GitHub

# ── Hàm xuất ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
err()   { echo -e "${RED}[✗]${NC} $1"; }
step()  { echo -e "\n${CYAN}[$1/$2]${NC} $3"; }

# ── Hàm animation xoay ──────────────────────────────────────────────────────────────
# Cách dùng: SPIN <PID tiến trình nền> <chữ nhắc> <đường dẫn file log>
# Nguyên lý: kiểm tra tiến trình còn sống không, còn sống thì hiện animation xoay, xong hiện ✅ hoặc ❌
SPIN() {
    local PID=$1 MSG=$2 LOGF=$3
    echo -n "  $MSG"
    while kill -0 $PID 2>/dev/null; do
        for s in ⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏; do
            echo -ne "\r  $s $MSG"
            sleep 0.3
            kill -0 $PID 2>/dev/null || break 2
        done
    done
    wait $PID
    local RET=$?
    if [ $RET -eq 0 ]; then
        echo -e "\r  ✅ $MSG hoàn tất          "
    else
        echo -e "\r  ❌ $MSG thất bại          "
        if [ -n "$LOGF" ] && [ -f "$LOGF" ]; then
            echo -e "${RED}--- Log lỗi (20 dòng cuối) ---${NC}"
            tail -20 "$LOGF"
            echo -e "${RED}--- Kết thúc log ---${NC}"
        fi
        exit 1
    fi
}

# ── Nguồn mirror pip (tăng tốc) ──────────────────────────────────────────────────────
MIRROR="-i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com"

# =============================================================================
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   📚 MuMuAINovel Termux cài đặt một cú nhấp ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

TOTAL=9

# =============================================================================
# Bước 1: Kiểm tra môi trường Termux
# =============================================================================
step 1 $TOTAL "Kiểm tra môi trường"
if [ ! -d "/data/data/com.termux" ]; then
    err "Không phát hiện môi trường Termux, hãy chạy trong Termux"
    exit 1
fi
info "Phát hiện môi trường Termux thành công"

# =============================================================================
# Bước 2: Cài đặt dependency hệ thống (python/nodejs/git)
# Ghi chú: pkg install tự bỏ qua gói đã cài, chạy lại không tải lại
# =============================================================================
step 2 $TOTAL "Cài đặt dependency hệ thống"
LOG="$TMPDIR/pkg-install.log"
pkg install -y python nodejs git > "$LOG" 2>&1 &
SPIN $! "Đang cài đặt" "$LOG"

# =============================================================================
# Bước 3: Lấy/cập nhật mã nguồn dự án
# Ghi chú: đã có thư mục .git → git pull cập nhật tăng dần (giữ venv/.env/data)
#       chưa có → git clone tải đầy đủ
# =============================================================================
step 3 $TOTAL "Lấy/cập nhật mã nguồn dự án"
if [ -d "$INSTALL_DIR/.git" ]; then
    LOG="$TMPDIR/git-pull.log"
    (
        cd "$INSTALL_DIR"
        git fetch origin
        git reset --hard origin/main 2>/dev/null || git reset --hard origin/master
    ) > "$LOG" 2>&1 &
    SPIN $! "Đang lấy" "$LOG"
else
    # Thư mục tồn tại nhưng không phải repo git, dọn rồi clone lại
    if [ -d "$INSTALL_DIR" ]; then
        rm -rf "$INSTALL_DIR"
    fi
    LOG="$TMPDIR/git-clone.log"
    git clone "$REPO" "$INSTALL_DIR" > "$LOG" 2>&1 &
    SPIN $! "Đang clone" "$LOG"
fi

BACKEND="$INSTALL_DIR/backend"
FRONTEND="$INSTALL_DIR/frontend"

# =============================================================================
# Bước 4: Áp dụng bản vá tương thích Termux
# Ghi chú: Termux không hỗ trợ chromadb/sentence-transformers, cần vá code để tránh crash
#   4a. memory_service.py — đổi import thành try/except, thiếu thì hạ cấp nhẹ nhàng
#   4b. File API — đổi import memory_service thành try/except
#   4c. .env — đã có thì bỏ qua, mới thì ghi cấu hình mặc định
# =============================================================================
step 4 $TOTAL "Áp dụng bản vá Termux"
LOG="$TMPDIR/patch.log"
(
# ── 4a. Vá memory_service.py ──────────────────────────────────────────────
python3 << 'PYEOF'
import os
f = os.path.expanduser("~/MuMuAINovel/backend/app/services/memory_service.py")
with open(f) as fh:
    c = fh.read()

# Đổi import tầng trên cùng thành try/except
c = c.replace(
    "import chromadb\\nfrom sentence_transformers import SentenceTransformer",
    """try:
    import chromadb
    from sentence_transformers import SentenceTransformer
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False
    chromadb = None
    SentenceTransformer = None"""
)

# Thêm kiểm tra MEMORY_AVAILABLE trong __init__, thiếu thì return thẳng không khởi tạo
old_init = '    def __init__(self):\n        \\\"\\\"\\\"Khởi tạo ChromaDB và model Embedding\\\"\\\"\\\"\n        if self._initialized:\n            return\n            \n        try:'
new_init = '    def __init__(self):\n        \\\"\\\"\\\"Khởi tạo ChromaDB và model Embedding\\\"\\\"\\\"\n        if self._initialized:\n            return\n\n        if not MEMORY_AVAILABLE:\n            self.client = None\n            self.model = None\n            self.collection = None\n            self._initialized = True\n            logger.warning("⚠️ Chức năng ký ức vector không khả dụng (thiếu chromadb/sentence-transformers)")\n            return\n\n        try:'
c = c.replace(old_init, new_init, 1)

with open(f, "w") as fh:
    fh.write(c)
print("  ✅ memory_service.py đã vá")
PYEOF

# ── 4b. Vá import memory_service của file API ──────────────────────────────────
python3 << 'PYEOF'
import os
home = os.path.expanduser("~")
files = [
    f"{home}/MuMuAINovel/backend/app/api/chapters.py",
    f"{home}/MuMuAINovel/backend/app/api/memories.py",
    f"{home}/MuMuAINovel/backend/app/api/outlines.py",
    f"{home}/MuMuAINovel/backend/app/api/projects.py",
    f"{home}/MuMuAINovel/backend/app/services/foreshadow_service.py",
]
old = 'from app.services.memory_service import memory_service'
new = 'try:\n    from app.services.memory_service import memory_service\nexcept ImportError:\n    memory_service = None'
count = 0
for f in files:
    if not os.path.exists(f): continue
    with open(f) as fh: c = fh.read()
    if old in c:
        c = c.replace(old, new)
        with open(f, 'w') as fh: fh.write(c)
        count += 1
print(f"  ✅ File API đã vá ({count} cái)")
PYEOF

# ── 4c. Tạo file cấu hình .env (đã có thì bỏ qua) ─────────────────────────────────────
mkdir -p "$DATA_DIR" "$LOG_DIR"
if [ ! -f "$BACKEND/.env" ]; then
cat > "$BACKEND/.env" << 'ENVEOF'
# Cấu hình Termux MuMuAINovel
APP_NAME=MuMuAINovel
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=false
TZ=Asia/Shanghai

# Database SQLite (thay PostgreSQL)
DATABASE_URL=sqlite+aiosqlite:///data/data/com.termux/files/home/mumuainovel/data/ai_story.db

# Log
LOG_LEVEL=INFO
LOG_TO_FILE=true
LOG_FILE_PATH=/data/data/com.termux/files/home/mumuainovel/logs/app.log
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5

# CORS
CORS_ORIGINS=["http://localhost:8000","http://127.0.0.1:8000"]

# ⚠️ Hãy điền API Key của bạn
OPENAI_API_KEY=***
OPENAI_BASE_URL=https://api.openai.com/v1

DEFAULT_AI_PROVIDER=openai
DEFAULT_MODEL=gpt-4o-mini
DEFAULT_TEMPERATURE=0.7
DEFAULT_MAX_TOKENS=4096

# Tài khoản đăng nhập cục bộ
LOCAL_AUTH_ENABLED=True
LOCAL_AUTH_USERNAME=admin
LOCAL_AUTH_PASSWORD=admin123
LOCAL_AUTH_DISPLAY_NAME=Admin
ENVEOF
# Thay đường dẫn placeholder bằng đường dẫn $HOME thực tế
sed -i "s|/data/data/com.termux/files/home|$HOME|g" "$BACKEND/.env"
sed -i "s|LOG_FILE_PATH=.*|LOG_FILE_PATH=$LOG_DIR/app.log|" "$BACKEND/.env"
echo "  ✅ .env đã tạo"
else
echo "  ✅ .env đã tồn tại, bỏ qua"
fi
) > "$LOG" 2>&1 &
SPIN $! "Đang vá" "$LOG"


# =============================================================================
# Bước 5: Cài đặt dependency Python
# Ghi chú: venv chưa có thì tạo; pip tự bỏ qua gói đã cài, chỉ cài gói mới
# =============================================================================
step 5 $TOTAL "Cài đặt dependency Python"
if [ ! -d "$BACKEND/venv" ]; then
    python -m venv "$BACKEND/venv"
fi
PIP="$BACKEND/venv/bin/pip"

# Ghi danh sách dependency rút gọn (không gồm psutil/chromadb/sentence-transformers vốn không tương thích Termux)
cat > "$BACKEND/requirements-lite.txt" << 'REQEOF'
fastapi==0.121.0
uvicorn==0.38.0
python-multipart==0.0.20
sqlalchemy==2.0.36
alembic==1.14.0
aiosqlite==0.22.1
pydantic==2.12.4
pydantic-settings==2.11.0
openai==2.7.0
anthropic==0.72.0
httpx==0.28.1
python-dotenv==1.1.0
aiosmtplib==4.0.2
mcp==1.22.0
greenlet>=3.0
REQEOF

LOG="$TMPDIR/pip-install.log"
(
    $PIP install --upgrade pip setuptools wheel -q $MIRROR
    $PIP install -r "$BACKEND/requirements-lite.txt" $MIRROR
) > "$LOG" 2>&1 &
SPIN $! "Đang cài đặt" "$LOG"

# =============================================================================
# Bước 6: Migration database
# Ghi chú: cài lần đầu tạo mọi bảng; chạy lại tự bỏ qua migration đã chạy
# =============================================================================
step 6 $TOTAL "Migration database"
export DATABASE_URL="sqlite+aiosqlite:///$DATA_DIR/ai_story.db"
LOG="$TMPDIR/alembic.log"
(
    cd "$BACKEND"
    "$BACKEND/venv/bin/python" -m alembic -c alembic-sqlite.ini upgrade head
) > "$LOG" 2>&1 &
SPIN $! "Đang migration" "$LOG"

# =============================================================================
# Bước 7: Cài đặt dependency frontend
# Ghi chú: node_modules đã có thì bỏ qua; lần đầu chạy npm install
# =============================================================================
step 7 $TOTAL "Cài đặt dependency frontend"
cd "$FRONTEND"
if [ -d "node_modules" ] && [ -f "node_modules/.package-lock.json" ]; then
    info "Dependency frontend đã cài, bỏ qua"
else
    LOG="$TMPDIR/npm-install.log"
    npm install --include=dev --loglevel=silent > "$LOG" 2>&1 &
    SPIN $! "Đang cài đặt" "$LOG"
fi

# =============================================================================
# Bước 8: Build frontend
# Ghi chú: mỗi lần đều build lại, đảm bảo code mới nhất có hiệu lực
# =============================================================================
step 8 $TOTAL "Build frontend"
node "$FRONTEND/node_modules/typescript/bin/tsc" -b 2>/dev/null || true
LOG="$TMPDIR/vite-build.log"
node "$FRONTEND/node_modules/vite/bin/vite.js" build > "$LOG" 2>&1 &
SPIN $! "Đang build" "$LOG"
grep -E "built in" "$LOG" | sed 's/^/    /'

# =============================================================================
# Bước 9: Tạo script khởi động
# Ghi chú: tạo ~/mumuainovel-start.sh, hỗ trợ chạy foreground/nền
# =============================================================================
step 9 $TOTAL "Tạo script khởi động"
cat > "$HOME/mumuainovel-start.sh" << STARTEOF
#!/bin/bash
# Script khởi động Termux MuMuAINovel
set -e

BACKEND="$BACKEND"
PYTHON="\$BACKEND/venv/bin/python"
DATA_DIR="$DATA_DIR"
LOG_DIR="$LOG_DIR"

mkdir -p "\$DATA_DIR" "\$LOG_DIR"
export DATABASE_URL="sqlite+aiosqlite:///\$DATA_DIR/ai_story.db"
cd "\$BACKEND"

if [ "\$1" = "--bg" ]; then
    echo "🚀 Khởi động nền MuMuAINovel (cổng 8000)..."
    nohup "\$PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 \\
        > "\$LOG_DIR/app.log" 2>&1 &
    echo \$! > "$HOME/mumuainovel.pid"
    sleep 2
    if kill -0 \$(cat "$HOME/mumuainovel.pid") 2>/dev/null; then
        echo "✅ Đã khởi động, PID: \$(cat $HOME/mumuainovel.pid)"
    else
        echo "❌ Khởi động thất bại, xem log: \$LOG_DIR/app.log"
        exit 1
    fi
else
    echo "🚀 Khởi động MuMuAINovel (cổng 8000, Ctrl+C để dừng)..."
    exec "\$PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
fi
STARTEOF
chmod +x "$HOME/mumuainovel-start.sh"
info "Đã tạo script khởi động: ~/mumuainovel-start.sh"

# =============================================================================
# Cài đặt hoàn tất
# =============================================================================
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  🎉 Cài đặt MuMuAINovel hoàn tất!               ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║                                              ║${NC}"
echo -e "${GREEN}║  Chạy foreground (Ctrl+C để dừng):            ║${NC}"
echo -e "${GREEN}║    bash ~/mumuainovel-start.sh                ║${NC}"
echo -e "${GREEN}║                                              ║${NC}"
echo -e "${GREEN}║  Chạy nền:                                   ║${NC}"
echo -e "${GREEN}║    bash ~/mumuainovel-start.sh --bg           ║${NC}"
echo -e "${GREEN}║                                              ║${NC}"
echo -e "${GREEN}║  Dừng chạy nền:                               ║${NC}"
echo -e "${GREEN}║    kill \$(cat ~/mumuainovel.pid)              ║${NC}"
echo -e "${GREEN}║                                              ║${NC}"
echo -e "${GREEN}║  Xem log:                                     ║${NC}"
echo -e "${GREEN}║    tail -f ~/mumuainovel/logs/app.log         ║${NC}"
echo -e "${GREEN}║                                              ║${NC}"
echo -e "${GREEN}║  🌐 Truy cập: http://127.0.0.1:8000            ║${NC}"
echo -e "${GREEN}║  🔑 Tài khoản: admin / admin123               ║${NC}"
echo -e "${GREEN}║                                              ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}  ⚠️  Trước khi dùng lần đầu hãy sửa API Key:${NC}"
echo -e "     nano $BACKEND/.env"
echo -e "     Sửa OPENAI_API_KEY và OPENAI_BASE_URL"
echo ""
