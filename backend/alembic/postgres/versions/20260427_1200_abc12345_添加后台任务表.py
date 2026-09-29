"""Thêm bảng task nền

Revision ID: abc12345
Revises: 
Create Date: 2026-04-27 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, JSONB

# revision identifiers
revision = 'abc12345'
down_revision = '9a1b2c3d4e5f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'background_tasks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(100), nullable=False, index=True, comment='ID người dùng'),
        sa.Column('project_id', sa.String(36), nullable=False, index=True, comment='ID dự án'),
        sa.Column('task_type', sa.String(50), nullable=False, comment='Loại task'),
        sa.Column('status', sa.String(20), default='pending', comment='Trạng thái task'),
        sa.Column('progress', sa.Integer, default=0, comment='Phần trăm tiến độ'),
        sa.Column('status_message', sa.String(500), comment='Thông điệp trạng thái hiện tại'),
        sa.Column('task_input', JSON, comment='Tham số đầu vào task'),
        sa.Column('task_result', JSON, comment='Kết quả task'),
        sa.Column('error_message', sa.Text, comment='Thông tin lỗi'),
        sa.Column('progress_details', JSON, comment='Chi tiết tiến độ'),
        sa.Column('cancel_requested', sa.Boolean, default=False, comment='Có yêu cầu hủy không'),
        sa.Column('retry_count', sa.Integer, default=0, comment='Số lần đã thử lại'),
        sa.Column('max_retries', sa.Integer, default=3, comment='Số lần thử lại tối đa'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), comment='Thời gian tạo'),
        sa.Column('started_at', sa.DateTime, comment='Thời gian bắt đầu'),
        sa.Column('completed_at', sa.DateTime, comment='Thời gian hoàn thành'),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now(), comment='Thời gian cập nhật'),
    )
    # Thêm index hợp thành: truy vấn theo người dùng + dự án + trạng thái
    op.create_index('ix_background_tasks_user_project', 'background_tasks', ['user_id', 'project_id', 'status'])


def downgrade() -> None:
    op.drop_index('ix_background_tasks_user_project', table_name='background_tasks')
    op.drop_table('background_tasks')