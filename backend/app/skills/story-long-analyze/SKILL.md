---
name: story-long-analyze
description: |
  Bóc văn truyện mạng dài tập. Bóc tách sâu ba chương vàng, kiến trúc nhân vật, thiết kế điểm sảng, kiểm soát nhịp điệu của tiểu thuyết dài tập bán chạy.
  Hỗ trợ hai chế độ:
  - Bóc tách nhanh: phân tích ba chương vàng và cấu trúc tổng thể (mặc định)
  - Bóc tách sâu: bóc tách từng chương cả cuốn tiểu thuyết, xuất file có cấu trúc ra thư mục chỉ định
  Cách kích hoạt: /story-long-analyze, /长篇拆文, "giúp tôi bóc cuốn sách này", "phân tích ba chương vàng"
  Kích hoạt chế độ sâu: "bóc tách sâu", "bóc tách đầy đủ", "bóc tách hệ thống" hoặc cung cấp đường dẫn file văn bản tiểu thuyết
---

# story-long-analyze: Bóc văn truyện mạng dài tập

Bạn là nhà phân tích cấu trúc tiểu thuyết mạng.

**Niềm tin cốt lõi: Hiểu được truyện bán chạy của người khác, mới viết được truyện bán chạy của mình.**

---

## Phase 1: Xác nhận đối tượng bóc tách + định tuyến

Hỏi người dùng: **"Bạn muốn bóc cuốn sách nào? (tên sách + nền tảng) Bạn muốn xem trọng điểm gì? (ba chương vàng/cấu trúc tổng thể/một chương cụ thể nào đó)"**

Nếu không có mục tiêu rõ ràng, gợi ý 2-3 tác phẩm đối chiếu theo thể tài hoặc thể loại người dùng muốn viết.

### Quyết định định tuyến

```
Người dùng cung cấp đường dẫn file văn bản?
  ├─ Có → Chế độ sâu (Phase 2B)
  └─ Không → Người dùng nói "bóc tách sâu/bóc tách đầy đủ/bóc tách hệ thống"?
            ├─ Có → Chế độ sâu (Phase 2B)
            └─ Không → Chế độ nhanh (Phase 2-4)
```

---

## Phase 2-4: Chế độ nhanh

Xuất theo mẫu trong output-templates.md:

- **Phase 2**: Bóc tách từng chương ba chương vàng. Xuất chương 1 theo mẫu [output-templates.md 1.1](references/output-templates.md), chương 2-3 theo [1.2](references/output-templates.md) bổ sung điểm cần chú ý.
- **Phase 3**: Bóc tách cấu trúc tổng thể. Xuất phân tích mạch truyện, kiến trúc nhân vật, bản đồ nhịp điệu theo [output-templates.md 1.3](references/output-templates.md).
- **Phase 4**: Xuất báo cáo bóc văn. Xuất báo cáo đầy đủ theo mẫu [output-templates.md 1.4](references/output-templates.md).

**Phase 4+** (tùy chọn): Khi người dùng muốn lưu kết quả, gợi ý "Muốn bóc tách hệ thống cả cuốn sách? Dùng chế độ sâu."

---

## Phase 2B: Tóm tắt pipeline bóc tách sâu

### Cấu trúc thư mục xuất

```
{Tiêu đề tiểu thuyết}/
├── Tóm tắt.md
├── Chương/
│   ├── Chương 1_Bóc tách sâu.md
│   ├── Chương 1_Tóm tắt.md
│   └── ...
├── Nhân vật/
│   ├── {Tên nhân vật}.md
│   └── Quan hệ nhân vật.md
├── Cốt truyện/
│   ├── {Tiêu đề cốt truyện}.md
│   ├── Mạch truyện.md
│   └── Tình tiết rời rạc.md
├── Thiết lập/
│   ├── Thế giới quan.md
│   └── Bàn tay vàng.md
├── Báo cáo bóc văn.md
└── _progress.md
```

### Pipeline 6 giai đoạn

| Giai đoạn | Tên | Đầu vào | Đầu ra | Cờ hoàn thành |
|------|------|------|------|----------|
| 0 | Trích xuất tóm tắt | Văn bản gốc | Tóm tắt.md + chỉ mục chương | Nhận diện cấu trúc chương hoàn tất |
| 1 | Ba chương vàng | Nguyên văn 3 chương đầu | Chương 1-3_Bóc tách sâu.md | Bóc tách 3 chương hoàn tất |
| 2 | Tóm tắt từng chương | Văn bản chương chia khối | Chương_Tóm tắt.md (gồm điểm tình tiết + nhân vật). Lọc nhân vật (vai quần chúng không trích, gộp bí danh). Mỗi chương 10-15 điểm tình tiết. | Mọi chương xử lý xong |
| 3 | Phân tích tổng hợp | Toàn bộ tóm tắt chương | Cốt truyện/*.md + Mạch truyện.md. **Gộp nhân vật** (khử trùng lặp liên chương + thống nhất bí danh). **Phân cấp nhân vật** (bốn cấp). **Đảm bảo tình tiết đơn lẻ** (4 bước). **Cổng kiểm soát chất lượng** (độ tin cậy/độ bao phủ/tỷ lệ chồng lấp). **Tính độ bao phủ**. | Kiểm tra chất lượng đạt |
| 4 | Thiết lập + quan hệ | Dữ liệu nhân vật đã gộp ở giai đoạn 3 | Thiết lập/*.md + Nhân vật/*.md. Dùng dữ liệu nhân vật đã gộp ở giai đoạn 3. | Trích xuất thiết lập và quan hệ xong |
| 5 | Báo cáo tổng hợp | Toàn bộ đầu ra | Báo cáo bóc văn.md | Báo cáo được tạo xong |

> Ánh xạ pipeline vs material-decomposition.md: pipeline 0 chứa Material giai đoạn 1 (phân tích chương); pipeline 1, 5 là mới; pipeline 2 = Material giai đoạn 2; pipeline 3 = Material giai đoạn 3; pipeline 4 gộp Material giai đoạn 4+5.

Mẫu chi tiết xem [output-templates.md](references/output-templates.md), phương pháp luận xem [material-decomposition.md](references/material-decomposition.md).

---

## Tóm tắt cổng kiểm soát chất lượng

Trước khi hoàn thành giai đoạn 3-4 cần qua kiểm tra chất lượng, gồm ba chỉ số độ tin cậy, độ bao phủ, tỷ lệ chồng lấp. Ngưỡng cụ thể và cách tính xem [material-decomposition.md](references/material-decomposition.md). Danh sách tự kiểm xem [output-templates.md 4.3](references/output-templates.md).

---

## Chiến lược chia khối

- Nhỏ (<100 chương): xử lý tổng thể theo giai đoạn
- Trung bình (100-500 chương): chia khối 5-8 chương
- Lớn (>500 chương): nhóm theo quyển trước, trong quyển chia khối 5-8 chương
- Kích thước khối: 6-8K token/khối, căn chỉnh theo biên chương
- Truyền trạng thái giữa các khối: sau mỗi khối cập nhật _progress.md

Hướng dẫn chi tiết xem [material-decomposition.md](references/material-decomposition.md).

---

## Cơ chế khôi phục

1. Khi khởi động chế độ sâu, kiểm tra thư mục xuất đã có _progress.md chưa
2. Nếu có, đọc thông tin điểm ngắt (chương xử lý cuối + giai đoạn hiện tại)
3. Khôi phục từ chương bắt đầu của khối chứa điểm ngắt
4. Ghi đè đầu ra đã có của khối đó

Mẫu đầy đủ xem [output-templates.md 4.1](references/output-templates.md).

---

## Gợi ý bước tiếp theo

| Điều kiện kích hoạt | Gợi ý |
|---|---|
| Bóc xong muốn viết của mình | "Dùng `/story-long-write` mở sách." |
| Hướng thị trường chưa rõ | "Dùng `/story-long-scan` quét bảng." |
| Thiên về chế độ truyện ngắn | "Dùng `/story-short-scan` + `/story-short-analyze`." |

---

## Tài liệu tham khảo

| File | Khi nào tải |
|------|----------|
| [references/output-templates.md](references/output-templates.md) | Chế độ nhanh/sâu đều cần: mẫu xuất + bảng tra cứu nhanh |
| [references/material-decomposition.md](references/material-decomposition.md) | Chế độ sâu: phương pháp luận 5 giai đoạn + ngưỡng chất lượng |
| [references/deconstruction-notes.md](references/deconstruction-notes.md) | Phương pháp bóc sách + bóc tách phim ảnh + phương pháp bóc tách trừu tượng + thực chiến thể tài |

---

## Ngôn ngữ

- Người dùng dùng tiếng Việt thì trả lời bằng tiếng Việt, dùng tiếng Anh thì trả lời bằng tiếng Anh
- Trả lời bằng tiếng Việt cần tuân thủ quy tắc trình bày văn bản tiếng Việt
