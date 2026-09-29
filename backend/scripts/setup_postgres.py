#!/usr/bin/env python3
"""
Script tự động thiết lập database PostgreSQL

Chức năng:
1. Tự động kết nối tới máy chủ PostgreSQL
2. Tạo database và người dùng
3. Thiết lập quyền
4. Khởi tạo cấu trúc bảng

Cách dùng:
    python backend/scripts/setup_postgres.py

Điều kiện tiên quyết:
    - Dịch vụ PostgreSQL đã cài đặt và đang chạy
    - Biết mật khẩu superuser của PostgreSQL (thường là user postgres)
"""
import sys
import asyncio
from pathlib import Path
from getpass import getpass
import logging

# Thêm thư mục gốc dự án vào đường dẫn Python
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except ImportError:
    print("❌ Thiếu dependency psycopg2, đang cài đặt...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary"])
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Lưu ý: cấu trúc bảng nên do Alembic quản lý
from pathlib import Path

# Thiết lập log
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


class PostgreSQLSetup:
    """Tự động thiết lập database PostgreSQL"""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        admin_user: str = "postgres",
        admin_password: str = None,
        db_name: str = "mumuai_novel",
        db_user: str = "mumuai",
        db_password: str = "123456"
    ):
        """
        Khởi tạo tham số thiết lập

        Args:
            host: Địa chỉ host PostgreSQL
            port: Cổng PostgreSQL
            admin_user: Tên đăng nhập quản trị viên
            admin_password: Mật khẩu quản trị viên
            db_name: Tên database cần tạo
            db_user: Tên người dùng cần tạo
            db_password: Mật khẩu người dùng
        """
        self.host = host
        self.port = port
        self.admin_user = admin_user
        self.admin_password = admin_password
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
        self.conn = None
    
    def connect_as_admin(self) -> bool:
        """Kết nối tới PostgreSQL (dùng quyền quản trị viên)"""
        try:
            logger.info(f"🔌 Kết nối tới PostgreSQL ({self.host}:{self.port})...")
            
            self.conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                user=self.admin_user,
                password=self.admin_password,
                database="postgres"  # Kết nối tới database mặc định
            )
            self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            
            logger.info(f"✅ Đã kết nối tới PostgreSQL")
            return True
            
        except psycopg2.OperationalError as e:
            logger.error(f"❌ Kết nối thất bại: {e}")
            logger.error("\nNguyên nhân có thể:")
            logger.error("1. Dịch vụ PostgreSQL chưa khởi động")
            logger.error("2. Sai mật khẩu quản trị viên")
            logger.error("3. Sai địa chỉ host hoặc cổng")
            logger.error("4. Cấu hình pg_hba.conf không cho phép kết nối")
            return False
    
    def database_exists(self) -> bool:
        """Kiểm tra database đã tồn tại chưa"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (self.db_name,)
        )
        exists = cursor.fetchone() is not None
        cursor.close()
        return exists
    
    def user_exists(self) -> bool:
        """Kiểm tra người dùng đã tồn tại chưa"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT 1 FROM pg_user WHERE usename = %s",
            (self.db_user,)
        )
        exists = cursor.fetchone() is not None
        cursor.close()
        return exists
    
    def create_user(self) -> bool:
        """Tạo người dùng database"""
        try:
            if self.user_exists():
                logger.info(f"ℹ️  Người dùng '{self.db_user}' đã tồn tại")
                
                # Hỏi có đặt lại mật khẩu không
                response = input(f"Có đặt lại mật khẩu của người dùng '{self.db_user}' không? (yes/no): ")
                if response.lower() in ['yes', 'y']:
                    cursor = self.conn.cursor()
                    cursor.execute(
                        sql.SQL("ALTER USER {} WITH PASSWORD %s").format(
                            sql.Identifier(self.db_user)
                        ),
                        (self.db_password,)
                    )
                    cursor.close()
                    logger.info(f"✅ Mật khẩu người dùng đã được cập nhật")
                
                return True
            
            logger.info(f"👤 Tạo người dùng '{self.db_user}'...")
            cursor = self.conn.cursor()
            cursor.execute(
                sql.SQL("CREATE USER {} WITH PASSWORD %s").format(
                    sql.Identifier(self.db_user)
                ),
                (self.db_password,)
            )
            cursor.close()
            logger.info(f"✅ Tạo người dùng thành công")
            return True
            
        except Exception as e:
            logger.error(f"❌ Tạo người dùng thất bại: {e}")
            return False
    
    def create_database(self) -> bool:
        """Tạo database"""
        try:
            if self.database_exists():
                logger.info(f"ℹ️  Database '{self.db_name}' đã tồn tại")
                
                # Hỏi có xóa và tạo lại không
                response = input(f"Có xóa và tạo lại database '{self.db_name}' không? (yes/no): ")
                if response.lower() in ['yes', 'y']:
                    logger.warning(f"⚠️  Xóa database '{self.db_name}'...")
                    cursor = self.conn.cursor()
                    # Ngắt mọi kết nối
                    cursor.execute(
                        sql.SQL("""
                            SELECT pg_terminate_backend(pg_stat_activity.pid)
                            FROM pg_stat_activity
                            WHERE pg_stat_activity.datname = %s
                            AND pid <> pg_backend_pid()
                        """),
                        (self.db_name,)
                    )
                    cursor.execute(
                        sql.SQL("DROP DATABASE {}").format(
                            sql.Identifier(self.db_name)
                        )
                    )
                    cursor.close()
                    logger.info(f"✅ Database đã được xóa")
                else:
                    return True
            
            logger.info(f"🗄️  Tạo database '{self.db_name}'...")
            cursor = self.conn.cursor()
            cursor.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(self.db_name),
                    sql.Identifier(self.db_user)
                )
            )
            cursor.close()
            logger.info(f"✅ Tạo database thành công")
            return True
            
        except Exception as e:
            logger.error(f"❌ Tạo database thất bại: {e}")
            return False
    
    def grant_privileges(self) -> bool:
        """Cấp quyền cho người dùng"""
        try:
            logger.info(f"🔐 Cấp quyền cho người dùng...")
            cursor = self.conn.cursor()
            
            # Cấp mọi quyền trên database
            cursor.execute(
                sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
                    sql.Identifier(self.db_name),
                    sql.Identifier(self.db_user)
                )
            )
            
            cursor.close()
            logger.info(f"✅ Cấp quyền thành công")
            return True
            
        except Exception as e:
            logger.error(f"❌ Cấp quyền thất bại: {e}")
            return False
    
    def update_env_file(self) -> bool:
        """Cập nhật file .env"""
        try:
            env_file = Path(__file__).parent.parent / ".env"
            
            database_url = (
                f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
                f"@{self.host}:{self.port}/{self.db_name}"
            )
            
            if env_file.exists():
                # Đọc nội dung hiện có
                with open(env_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                # Cập nhật DATABASE_URL
                updated = False
                for i, line in enumerate(lines):
                    if line.startswith('DATABASE_URL='):
                        lines[i] = f"DATABASE_URL={database_url}\n"
                        updated = True
                        break
                
                if not updated:
                    lines.append(f"\nDATABASE_URL={database_url}\n")
                
                # Ghi lại file
                with open(env_file, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
            else:
                # Tạo file mới
                with open(env_file, 'w', encoding='utf-8') as f:
                    f.write(f"DATABASE_URL={database_url}\n")
            
            logger.info(f"✅ File .env đã được cập nhật")
            logger.info(f"   DATABASE_URL={database_url}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Cập nhật file .env thất bại: {e}")
            return False
    
    async def initialize_tables(self) -> bool:
        """Khởi tạo cấu trúc bảng database (dùng Alembic)"""
        try:
            import subprocess
            logger.info(f"📋 Khởi tạo cấu trúc bảng database bằng Alembic...")
            
            # Chạy migration Alembic
            result = subprocess.run(
                ["alembic", "upgrade", "head"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent
            )
            
            if result.returncode == 0:
                logger.info(f"✅ Khởi tạo cấu trúc bảng thành công")
                return True
            else:
                logger.error(f"❌ Migration Alembic thất bại: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Khởi tạo cấu trúc bảng thất bại: {e}")
            return False
    
    def close(self):
        """Đóng kết nối database"""
        if self.conn:
            self.conn.close()
            logger.info(f"🔌 Đã ngắt kết nối")
    
    async def setup(self) -> bool:
        """Thực thi quy trình thiết lập đầy đủ"""
        try:
            # 1. Kết nối
            if not self.connect_as_admin():
                return False
            
            # 2. Tạo người dùng
            if not self.create_user():
                return False
            
            # 3. Tạo database
            if not self.create_database():
                return False
            
            # 4. Cấp quyền
            if not self.grant_privileges():
                return False
            
            # 5. Cập nhật cấu hình
            if not self.update_env_file():
                return False
            
            # 6. Đóng kết nối quản trị viên
            self.close()
            
            # 7. Khởi tạo cấu trúc bảng
            if not await self.initialize_tables():
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Lỗi trong quá trình thiết lập: {e}")
            return False
        finally:
            if self.conn:
                self.close()


async def main():
    """Hàm chính"""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║          Công cụ tự động thiết lập database PostgreSQL       ║
║                                                               ║
║  Công cụ này sẽ tự động hoàn thành:                       ║
║  1. Kết nối tới máy chủ PostgreSQL                       ║
║  2. Tạo database và người dùng                           ║
║  3. Thiết lập quyền                                      ║
║  4. Khởi tạo cấu trúc bảng                               ║
║  5. Cập nhật file cấu hình .env                           ║
╚═══════════════════════════════════════════════════════════════╝
    """)
    
    # Lấy cấu hình
    print("Vui lòng nhập thông tin cấu hình PostgreSQL:\n")
    
    host = input("Địa chỉ host [localhost]: ").strip() or "localhost"
    port = input("Cổng [5432]: ").strip() or "5432"
    port = int(port)
    
    admin_user = input("Tên đăng nhập quản trị viên [postgres]: ").strip() or "postgres"
    admin_password = getpass(f"Mật khẩu quản trị viên: ")
    
    print("\nVui lòng nhập thông tin database cần tạo:\n")
    db_name = input("Tên database [mumuai_novel]: ").strip() or "mumuai_novel"
    db_user = input("Tên người dùng database [mumuai]: ").strip() or "mumuai"
    db_password = getpass("Mật khẩu người dùng database [mumuai123]: ") or "mumuai123"
    
    print(f"\n{'='*60}")
    print(f"Tóm tắt cấu hình:")
    print(f"  Máy chủ: {host}:{port}")
    print(f"  Database: {db_name}")
    print(f"  Người dùng: {db_user}")
    print(f"{'='*60}\n")
    
    response = input("Xác nhận bắt đầu thiết lập? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Đã hủy thiết lập")
        return
    
    # Thực thi thiết lập
    setup = PostgreSQLSetup(
        host=host,
        port=port,
        admin_user=admin_user,
        admin_password=admin_password,
        db_name=db_name,
        db_user=db_user,
        db_password=db_password
    )
    
    print(f"\n{'='*60}")
    success = await setup.setup()
    print(f"{'='*60}\n")
    
    if success:
        print("🎉 Thiết lập PostgreSQL hoàn tất!\n")
        print("Bước tiếp theo:")
        print("1. Khởi động ứng dụng: python -m app.main")
        print("2. Truy cập: http://localhost:8000")
        print("3. Xem tài liệu API: http://localhost:8000/docs")
    else:
        print("❌ Đã xảy ra lỗi trong quá trình thiết lập, vui lòng kiểm tra log")
        print("\nKhắc phục sự cố:")
        print("1. Xác nhận dịch vụ PostgreSQL đang chạy")
        print("2. Kiểm tra tên đăng nhập và mật khẩu quản trị viên")
        print("3. Xem log PostgreSQL")


if __name__ == "__main__":
    asyncio.run(main())