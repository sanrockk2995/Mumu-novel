#!/usr/bin/env python3
"""
Script tự động migration database
Dùng để quản lý migration database cho môi trường phát triển và production
"""
import subprocess
import sys
import os
from pathlib import Path

# Thêm đường dẫn dự án
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.logger import get_logger

logger = get_logger(__name__)


def run_command(cmd: list, description: str) -> bool:
    """Chạy lệnh và trả về có thành công hay không"""
    try:
        logger.info(f"🚀 {description}...")
        result = subprocess.run(
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            logger.info(f"✅ {description} thành công")
            if result.stdout:
                print(result.stdout)
            return True
        else:
            logger.error(f"❌ {description} thất bại")
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            return False
    except Exception as e:
        logger.error(f"❌ {description} lỗi bất thường: {e}")
        return False


def create_migration(message: str = None):
    """Tạo phiên bản migration mới"""
    if not message:
        message = input("Vui lòng nhập mô tả migration: ").strip()
        if not message:
            message = "auto_migration"
    
    cmd = ["alembic", "revision", "--autogenerate", "-m", message]
    return run_command(cmd, f"Sinh migration: {message}")


def upgrade_database(revision: str = "head"):
    """Nâng cấp database tới phiên bản chỉ định"""
    cmd = ["alembic", "upgrade", revision]
    return run_command(cmd, f"Nâng cấp database tới: {revision}")


def downgrade_database(revision: str = "-1"):
    """Hạ cấp database tới phiên bản chỉ định"""
    cmd = ["alembic", "downgrade", revision]
    return run_command(cmd, f"Hạ cấp database tới: {revision}")


def show_current():
    """Hiển thị phiên bản database hiện tại"""
    cmd = ["alembic", "current"]
    return run_command(cmd, "Xem phiên bản hiện tại")


def show_history():
    """Hiển thị lịch sử migration"""
    cmd = ["alembic", "history", "--verbose"]
    return run_command(cmd, "Xem lịch sử migration")


def show_heads():
    """Hiển thị phiên bản mới nhất"""
    cmd = ["alembic", "heads"]
    return run_command(cmd, "Xem phiên bản mới nhất")


def stamp_database(revision: str = "head"):
    """Đánh dấu phiên bản database (không thực thi migration)"""
    cmd = ["alembic", "stamp", revision]
    return run_command(cmd, f"Đánh dấu phiên bản database: {revision}")


def auto_migrate():
    """Tự động migration: sinh và thực thi migration"""
    logger.info("=" * 60)
    logger.info("🔄 Bắt đầu quy trình tự động migration")
    logger.info("=" * 60)
    
    # 1. Tạo migration
    if not create_migration("auto_migration"):
        logger.error("❌ Tự động migration thất bại: không thể sinh migration")
        return False
    
    # 2. Thực thi migration
    if not upgrade_database():
        logger.error("❌ Tự động migration thất bại: không thể thực thi migration")
        return False
    
    logger.info("=" * 60)
    logger.info("✅ Tự động migration hoàn tất")
    logger.info("=" * 60)
    return True


def init_database():
    """Khởi tạo database (triển khai lần đầu)"""
    logger.info("=" * 60)
    logger.info("🔧 Khởi tạo database")
    logger.info("=" * 60)
    
    # Tạo migration ban đầu
    if not create_migration("initial_migration"):
        logger.warning("⚠️ Không thể tạo migration ban đầu, có thể đã tồn tại")
    
    # Thực thi migration
    if not upgrade_database():
        logger.error("❌ Khởi tạo thất bại")
        return False
    
    logger.info("=" * 60)
    logger.info("✅ Khởi tạo database hoàn tất")
    logger.info("=" * 60)
    return True


def main():
    """Hàm chính"""
    if len(sys.argv) < 2:
        print("Cách dùng:")
        print("  python migrate.py create [message]    - Tạo migration mới")
        print("  python migrate.py upgrade [revision]  - Nâng cấp database (mặc định: head)")
        print("  python migrate.py downgrade [revision] - Hạ cấp database (mặc định: -1)")
        print("  python migrate.py current            - Hiển thị phiên bản hiện tại")
        print("  python migrate.py history            - Hiển thị lịch sử migration")
        print("  python migrate.py heads              - Hiển thị phiên bản mới nhất")
        print("  python migrate.py stamp [revision]   - Đánh dấu phiên bản (mặc định: head)")
        print("  python migrate.py auto               - Tự động migration (sinh + thực thi)")
        print("  python migrate.py init               - Khởi tạo database")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "create":
        message = sys.argv[2] if len(sys.argv) > 2 else None
        success = create_migration(message)
    elif command == "upgrade":
        revision = sys.argv[2] if len(sys.argv) > 2 else "head"
        success = upgrade_database(revision)
    elif command == "downgrade":
        revision = sys.argv[2] if len(sys.argv) > 2 else "-1"
        success = downgrade_database(revision)
    elif command == "current":
        success = show_current()
    elif command == "history":
        success = show_history()
    elif command == "heads":
        success = show_heads()
    elif command == "stamp":
        revision = sys.argv[2] if len(sys.argv) > 2 else "head"
        success = stamp_database(revision)
    elif command == "auto":
        success = auto_migrate()
    elif command == "init":
        success = init_database()
    else:
        logger.error(f"❌ Lệnh không xác định: {command}")
        success = False
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()