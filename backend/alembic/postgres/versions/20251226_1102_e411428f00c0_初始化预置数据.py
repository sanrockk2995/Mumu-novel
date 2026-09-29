"""Khởi tạo dữ liệu preset

Revision ID: e411428f00c0
Revises: ee0a189f1532
Create Date: 2025-12-26 11:02:24.080526

"""
from typing import Sequence, Union
from datetime import datetime

from alembic import op
import sqlalchemy as sa
from sqlalchemy import table, column, String, Integer, Float, Text, Boolean, DateTime


# revision identifiers, used by Alembic.
revision: str = 'e411428f00c0'
down_revision: Union[str, None] = 'ee0a189f1532'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Chèn dữ liệu preset"""

    # ==================== 1. Chèn dữ liệu loại quan hệ ====================
    relationship_types_table = table(
        'relationship_types',
        column('name', String),
        column('category', String),
        column('reverse_name', String),
        column('intimacy_range', String),
        column('icon', String),
        column('description', Text),
    )

    relationship_types_data = [
        # Quan hệ gia đình
        {"name": "Cha", "category": "family", "reverse_name": "Con cái", "intimacy_range": "high", "icon": "👨", "description": "Quan hệ cha - con trai/cha - con gái"},
        {"name": "Mẹ", "category": "family", "reverse_name": "Con cái", "intimacy_range": "high", "icon": "👩", "description": "Quan hệ mẹ - con trai/mẹ - con gái"},
        {"name": "Anh em", "category": "family", "reverse_name": "Anh em", "intimacy_range": "high", "icon": "👬", "description": "Quan hệ anh em"},
        {"name": "Chị em", "category": "family", "reverse_name": "Chị em", "intimacy_range": "high", "icon": "👭", "description": "Quan hệ chị em"},
        {"name": "Con cái", "category": "family", "reverse_name": "Cha mẹ", "intimacy_range": "high", "icon": "👶", "description": "Quan hệ con cái"},
        {"name": "Vợ/Chồng", "category": "family", "reverse_name": "Vợ/Chồng", "intimacy_range": "high", "icon": "💑", "description": "Quan hệ vợ chồng"},
        {"name": "Người yêu", "category": "family", "reverse_name": "Người yêu", "intimacy_range": "high", "icon": "💕", "description": "Quan hệ yêu đương"},

        # Quan hệ xã hội
        {"name": "Sư phụ", "category": "social", "reverse_name": "Đồ đệ", "intimacy_range": "high", "icon": "🎓", "description": "Quan hệ thầy trò (góc nhìn sư phụ)"},
        {"name": "Đồ đệ", "category": "social", "reverse_name": "Sư phụ", "intimacy_range": "high", "icon": "📚", "description": "Quan hệ thầy trò (góc nhìn đồ đệ)"},
        {"name": "Bạn bè", "category": "social", "reverse_name": "Bạn bè", "intimacy_range": "medium", "icon": "🤝", "description": "Quan hệ bạn bè"},
        {"name": "Bạn học", "category": "social", "reverse_name": "Bạn học", "intimacy_range": "medium", "icon": "🎒", "description": "Quan hệ bạn học"},
        {"name": "Hàng xóm", "category": "social", "reverse_name": "Hàng xóm", "intimacy_range": "low", "icon": "🏘️", "description": "Quan hệ hàng xóm"},
        {"name": "Tri kỷ", "category": "social", "reverse_name": "Tri kỷ", "intimacy_range": "high", "icon": "💙", "description": "Bạn tri kỷ"},

        # Quan hệ nghề nghiệp
        {"name": "Cấp trên", "category": "professional", "reverse_name": "Cấp dưới", "intimacy_range": "low", "icon": "👔", "description": "Quan hệ cấp trên-cấp dưới (góc nhìn cấp trên)"},
        {"name": "Cấp dưới", "category": "professional", "reverse_name": "Cấp trên", "intimacy_range": "low", "icon": "💼", "description": "Quan hệ cấp trên-cấp dưới (góc nhìn cấp dưới)"},
        {"name": "Đồng nghiệp", "category": "professional", "reverse_name": "Đồng nghiệp", "intimacy_range": "medium", "icon": "🤵", "description": "Quan hệ đồng nghiệp"},
        {"name": "Đối tác", "category": "professional", "reverse_name": "Đối tác", "intimacy_range": "medium", "icon": "🤜🤛", "description": "Quan hệ hợp tác"},

        # Quan hệ địch đối
        {"name": "Kẻ địch", "category": "hostile", "reverse_name": "Kẻ địch", "intimacy_range": "low", "icon": "⚔️", "description": "Quan hệ địch đối"},
        {"name": "Kẻ thù", "category": "hostile", "reverse_name": "Kẻ thù", "intimacy_range": "low", "icon": "💢", "description": "Quan hệ thù hận"},
        {"name": "Đối thủ cạnh tranh", "category": "hostile", "reverse_name": "Đối thủ cạnh tranh", "intimacy_range": "low", "icon": "🎯", "description": "Quan hệ cạnh tranh"},
        {"name": "Kình địch", "category": "hostile", "reverse_name": "Kình địch", "intimacy_range": "low", "icon": "⚡", "description": "Kẻ thù định mệnh"},
    ]

    op.bulk_insert(relationship_types_table, relationship_types_data)
    print(f"✅ Đã chèn {len(relationship_types_data)} dữ liệu loại quan hệ")


    # ==================== 2. Chèn preset phong cách viết toàn cục ====================
    # Chú ý: cần lấy cấu hình preset từ WritingStyleManager
    # Để tránh import code ứng dụng, hardcode trực tiếp phong cách preset

    writing_styles_table = table(
        'writing_styles',
        column('user_id', String),
        column('name', String),
        column('style_type', String),
        column('preset_id', String),
        column('description', Text),
        column('prompt_content', Text),
        column('order_index', Integer),
    )

    writing_styles_data = [
        {
            "user_id": None,  # NULL nghĩa là preset toàn cục
            "name": "Tự nhiên lưu loát",
            "style_type": "preset",
            "preset_id": "natural",
            "description": "Phong cách kể chuyện tự nhiên lưu loát, hợp đề tài đô thị hiện đại, hiện thực",
            "prompt_content": """Yêu cầu phong cách viết:
1. Ngôn ngữ súc tích sáng sủa, gần với khẩu ngữ hiện đại
2. Dùng nhiều câu ngắn, nhịp điệu lưu loát
3. Chú trọng bộc lộ tự nhiên chi tiết cảm xúc
4. Tránh tô vẽ quá mức và cú pháp phức tạp""",
            "order_index": 1
        },
        {
            "user_id": None,
            "name": "Cổ điển thanh nhã",
            "style_type": "preset",
            "preset_id": "classical",
            "description": "Phong cách viết cổ điển thanh nhã, hợp đề tài cổ trang, tiên hiệp",
            "prompt_content": """Yêu cầu phong cách viết:
1. Dùng văn ngôn, bán văn ngôn hoặc bạch thoại điển nhã
2. Vận dụng thích hợp hình tượng thơ ca cổ điển
3. Chú trọng tạo ý cảnh và dư vị
4. Đối thoại và miêu tả giữ vẻ đẹp cổ điển""",
            "order_index": 2
        },
        {
            "user_id": None,
            "name": "Hiện đại tối giản",
            "style_type": "preset",
            "preset_id": "modern",
            "description": "Phong cách hiện đại tối giản, hợp kể chuyện nhịp nhanh kiểu light novel, truyện mạng",
            "prompt_content": """Yêu cầu phong cách viết:
1. Ngôn ngữ thẳng thắn súc tích, mật độ thông tin cao
2. Dùng nhiều đối thoại đẩy cốt truyện
3. Tránh miêu tả dài dòng, nổi bật động tác then chốt
4. Nhịp điệu sáng sủa, hợp đọc nhanh""",
            "order_index": 3
        },
        {
            "user_id": None,
            "name": "Văn nghệ tinh tế",
            "style_type": "preset",
            "preset_id": "literary",
            "description": "Phong cách văn nghệ tinh tế, chú trọng miêu tả tâm lý và tạo bầu không khí",
            "prompt_content": """Yêu cầu phong cách viết:
1. Chú trọng hoạt động tâm lý và chi tiết cảm xúc
2. Khéo dùng miêu tả môi trường để tô đậm bầu không khí
3. Ngôn ngữ đẹp, giàu tính văn học
4. Dùng thích hợp ẩn dụ, tượng trưng và các biện pháp tu từ""",
            "order_index": 4
        },
        {
            "user_id": None,
            "name": "Căng thẳng hồi hộp",
            "style_type": "preset",
            "preset_id": "suspense",
            "description": "Phong cách căng thẳng hồi hộp, hợp đề tài suy luận, kinh dị",
            "prompt_content": """Yêu cầu phong cách viết:
1. Tạo bầu không khí căng thẳng áp bức
2. Dùng nhiều câu ngắn đẩy nhanh nhịp điệu
3. Khéo đặt hồi hộp và phục bút
4. Chú trọng miêu tả chi tiết, gieo manh mối cho suy luận""",
            "order_index": 5
        },
        {
            "user_id": None,
            "name": "Hài hước dí dỏm",
            "style_type": "preset",
            "preset_id": "humorous",
            "description": "Phong cách hài hước dí dỏm, hợp đề tài nhẹ nhàng gây cười",
            "prompt_content": """Yêu cầu phong cách viết:
1. Ngôn ngữ sinh động dí dỏm, khéo dùng lời dí dỏm
2. Chú trọng hiệu quả hài hước của đối thoại
3. Phóng đại và bước ngoặt thích hợp để tạo điểm cười
4. Giữ tông nhẹ nhàng vui vẻ""",
            "order_index": 6
        },
    ]

    op.bulk_insert(writing_styles_table, writing_styles_data)
    print(f"✅ Đã chèn {len(writing_styles_data)} preset phong cách viết toàn cục")


def downgrade() -> None:
    """Xóa dữ liệu preset"""

    # Xóa preset phong cách viết (chỉ xóa preset toàn cục)
    op.execute("DELETE FROM writing_styles WHERE user_id IS NULL")
    print("✅ Đã xóa preset phong cách viết toàn cục")

    # Xóa loại quan hệ
    op.execute("DELETE FROM relationship_types")
    print("✅ Đã xóa dữ liệu loại quan hệ")
