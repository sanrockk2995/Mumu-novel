"""File cấu hình môi trường Alembic - PostgreSQL"""
import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Thêm thư mục gốc dự án vào Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import cấu hình ứng dụng
from app.config import settings

# Import Base và mọi model
from app.database import Base
from app.models import (
    Project, Outline, Character, Chapter, GenerationHistory,
    Settings, WritingStyle, ProjectDefaultStyle,
    RelationshipType, CharacterRelationship, Organization, OrganizationMember,
    StoryMemory, PlotAnalysis, AnalysisTask, BatchGenerationTask,
    RegenerationTask, Career, CharacterCareer, User, MCPPlugin, PromptTemplate,
    BackgroundTask
)

# Đối tượng Alembic Config
config = context.config

# Đặt chuỗi kết nối database (đọc từ biến môi trường)
config.set_main_option("sqlalchemy.url", settings.database_url)

# Cấu hình log
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Đặt target_metadata thành Base.metadata của ứng dụng
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Chạy migration ở chế độ 'offline'"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Hàm lõi thực thi migration - dành riêng cho PostgreSQL"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        render_as_batch=False,  # PostgreSQL không cần chế độ batch
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Chạy migration bất đồng bộ ở chế độ 'online'"""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = settings.database_url
    
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Chạy migration ở chế độ 'online'"""
    asyncio.run(run_async_migrations())


# Chọn chế độ chạy theo ngữ cảnh
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()