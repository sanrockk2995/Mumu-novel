"""Hằng số phân loại Xưởng prompt"""

PROMPT_CATEGORIES = {
    "general": "Chung",
    "fantasy": "Huyền huyễn/Tiên hiệp",
    "martial": "Võ hiệp",
    "romance": "Ngôn tình",
    "scifi": "Khoa học viễn tưởng",
    "horror": "Trinh thám/Kinh dị",
    "history": "Lịch sử",
    "urban": "Đô thị",
    "game": "Game/Esports",
    "other": "Khác",
}

CATEGORY_LIST = [
    {"id": k, "name": v} for k, v in PROMPT_CATEGORIES.items()
]

# Nhãn phổ biến (gợi ý)
POPULAR_TAGS = [
    "Huyền huyễn", "Tiên hiệp", "Tu chân", "Thăng cấp lưu", "Nhiệt huyết",
    "Võ hiệp", "Cổ phong", "Ngôn tình", "Ngọt sủng", "Ngược luyến",
    "Khoa huyễn", "Tinh tế", "Tận thế", "Trinh thám", "Suy luận",
    "Kinh dị", "Lịch sử", "Hư cấu", "Đô thị", "Công sở",
    "Game", "Esports", "Nhị thứ nguyên", "Light novel", "Hệ thống lưu",
    "Vô địch lưu", "Chậm nhiệt", "Đời thường", "Chữa lành"
]