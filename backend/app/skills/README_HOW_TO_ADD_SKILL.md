# Hướng dẫn phát triển Skill: Cách thêm hoặc sửa Skill

## 1. Tổng quan kiến trúc hệ thống Skill

```
backend/app/skills/          ← Thư mục chứa mọi Skill
├── story-short-write/       ← Mỗi Skill một thư mục
│   ├── SKILL.md            ← Bắt buộc: metadata YAML + chỉ thị quy trình làm việc
│   └── references/         ← Tùy chọn: kho tri thức tham khảo (file .md)
│       ├── xxx.md
│       └── ...
├── story-long-write/
│   ├── SKILL.md
│   └── references/...
└── ...

backend/app/services/skill_loader.py   ← Bộ tải Skill (tự động quét thư mục skills/)
backend/app/api/skills.py              ← API endpoint (/api/skills/list)
backend/app/services/prompt_service.py ← Inject Skill vào system prompt
```

**Cơ chế cốt lõi**: Khi hệ thống khởi động, `skill_loader.py` tự động quét thư mục `skills/`, đọc `SKILL.md` của mỗi thư mục con, phân tích metadata YAML và chỉ thị quy trình làm việc, nối tài liệu tham khảo `references/` rồi cung cấp cho AI.

---

## 2. Thêm Skill mới (3 bước)

### Bước 1: Tạo thư mục Skill

Tạo thư mục mới trong `backend/app/skills/`, tên thư mục nên dùng chữ thường tiếng Anh + gạch ngang:

```bash
mkdir -p backend/app/skills/my-new-skill/references
```

### Bước 2: Tạo SKILL.md (bắt buộc)

Tạo `SKILL.md` trong thư mục, định dạng cố định là **YAML frontmatter + nội dung Markdown**:

```markdown
---
name: my-new-skill
description: |
  Mô tả một câu chức năng của Skill này. Đây là tên hiển thị trên UI.
  Cách kích hoạt: /my-new-skill, "giúp tôi làm xxx"
---

# my-new-skill: Tiêu đề hiển thị của Skill

Bạn là chuyên gia xxx. Nhiệm vụ của bạn là giúp người dùng hoàn thành xxx.

## Nguyên tắc cốt lõi

- Nguyên tắc 1...
- Nguyên tắc 2...

## Quy trình làm việc

### Phase 1: Xác nhận nhu cầu
...

### Phase 2: Thực hiện
...

### Phase 3: Xuất kết quả
...

## Định dạng xuất
...
```

**Giải thích trường YAML frontmatter**:

| Trường | Bắt buộc | Giải thích |
|------|------|------|
| `name` | ✅ | Tên định danh nội bộ của Skill, giữ nhất quán với tên thư mục |
| `description` | ✅ | Mô tả Skill. **Câu đầu tiên** (trước dấu chấm đầu tiên) sẽ làm tên hiển thị trong dropdown UI |

**Logic phân loại tự động** (trong `skill_loader.py`):

| name chứa | Phân loại hiển thị trên UI |
|-----------|-------------|
| `long` | Skill·Truyện dài |
| `short` | Skill·Truyện ngắn |
| `deslop` | Skill·Gọt giũa |
| `browser` | Skill·Công cụ |
| Khác | Skill |

### Bước 3: Thêm tài liệu tham khảo (tùy chọn)

Đặt file `.md` vào thư mục `references/`, mỗi file sẽ tự động được nối vào sau nội dung SKILL.md dưới dạng "tài liệu tham khảo":

```
references/
├── technique-a.md      ← Tự động tải, tiêu đề là "Tài liệu tham khảo: technique-a"
├── technique-b.md      ← Tự động tải, tiêu đề là "Tài liệu tham khảo: technique-b"
└── examples.md
```

**Hoàn tất!** Khởi động lại dịch vụ, Skill mới tự động xuất hiện trong dropdown UI, không cần sửa bất kỳ code nào.

---

## 3. Sửa Skill hiện có

### Sửa chỉ thị quy trình làm việc

Sửa trực tiếp phần Markdown phía dưới `---` trong file `SKILL.md` của thư mục Skill tương ứng.

### Sửa metadata (tên, mô tả)

Sửa YAML frontmatter ở đầu file `SKILL.md`:

```yaml
---
name: story-short-write          ← Sửa định danh nội bộ
description: |                   ← Sửa mô tả (câu đầu là tên hiển thị UI)
  Mô tả một câu mới. Giải thích chi tiết phía sau...
---
```

### Thêm/xóa tài liệu tham khảo

Thêm/xóa file `.md` trong thư mục `references/` là được, khởi động lại tự có hiệu lực.

### Sửa phân loại tự động

Sửa logic phân loại trong `backend/app/services/skill_loader.py` (khoảng dòng 158-167):

```python
# Xác định phân loại con của Skill
sub_category = "Skill"
if "long" in name:
    sub_category = "Skill·Truyện dài"
elif "short" in name:
    sub_category = "Skill·Truyện ngắn"
# 👇 Thêm quy tắc phân loại mới tại đây
elif "my-keyword" in name:
    sub_category = "Skill·Phân loại mới"
```

---

## 4. Đường đi của Skill trong hệ thống

Hiểu Skill được dùng thế nào để tiện gỡ lỗi:

### 4.1 Trang SkillChat (hội thoại độc lập)

```
Người dùng chọn Skill trong SkillChat
  → Frontend gọi /api/skills/list lấy danh sách
  → Frontend gọi /api/skills/execute gửi tin nhắn
  → Backend skill_loader tải SKILL.md + references
  → Inject vào system prompt → gọi AI → trả kết quả
```

### 4.2 Sinh chương (chương đơn / hàng loạt)

```
Người dùng chọn dropdown Skill
  → Frontend truyền skill_key cho backend
  → Backend lấy nội dung Skill từ prompt_service
  → Inject vào system prompt sinh chương
  → AI sinh nội dung chương dưới sự hướng dẫn của Skill
```

Vị trí code then chốt:
- **Điểm inject backend**: phương thức `get_skill_content()` của `backend/app/services/prompt_service.py`
- **Sinh chương đơn**: `backend/app/store/hooks.ts` → `generateChapterContentStream()`
- **Sinh hàng loạt**: `backend/app/api/chapters.py` → `generate_single_chapter_for_batch()`

---

## 5. Ví dụ đầy đủ: thêm một Skill "kiểm tra nhịp điệu"

```bash
# 1. Tạo thư mục
mkdir -p backend/app/skills/story-pacing-check/references

# 2. Tạo SKILL.md
cat > backend/app/skills/story-pacing-check/SKILL.md << 'EOF'
---
name: story-pacing-check
description: |
  Chẩn đoán nhịp điệu. Phân tích nhịp kể chuyện của chương đã có, chỉ ra chỗ lê thê/vội vàng và đưa gợi ý sửa đổi.
  Cách kích hoạt: /story-pacing-check, "kiểm tra nhịp điệu", "nhịp điệu có vấn đề"
---

# story-pacing-check: Chẩn đoán nhịp kể chuyện

Bạn là chuyên gia phân tích nhịp kể chuyện. Nhiệm vụ của bạn là giúp người dùng phân tích vấn đề nhịp điệu của chương.

## Chiều phân tích

### 1. Mật độ thông tin
- Mỗi đoạn có thông tin mới đẩy tới không?
- Có diễn đạt trùng lặp không?

### 2. Đường cong cảm xúc
- Cảm xúc có lên xuống không?
- Trước cao trào đã lót đường đủ chưa?

### 3. Chuyển cảnh
- Chuyển cảnh có tự nhiên không?
- Dòng thời gian có rõ ràng không?

## Định dạng xuất

Đưa ra: vị trí vấn đề → phân tích nguyên nhân → gợi ý sửa đổi
EOF

# 3. Khởi động lại dịch vụ là xong!
```

---

## 6. Lưu ý

1. **Mã hóa SKILL.md**: phải là UTF-8
2. **Định dạng YAML**: nội dung sau `description: |` cần thụt đầu dòng
3. **Quy tắc đặt tên**: tên thư mục và trường `name` dùng chữ thường + gạch ngang (ví dụ `my-skill-name`)
4. **Cache**: Skill có cache bộ nhớ, sửa xong cần khởi động lại dịch vụ. Cũng có thể gọi `refresh_skills_cache()` để làm mới nóng
5. **Kích thước file tham khảo**: mọi file trong `references/` sẽ được nối vào prompt, chú ý tổng kích thước đừng vượt giới hạn ngữ cảnh của model
6. **Không cần sửa code**: thêm Skill chuẩn (chỉ SKILL.md + references) không cần sửa bất kỳ code Python/TypeScript nào
