# Phương pháp luận phân tách tư liệu truyện

## Mục lục

1. [Quy trình tách 5 giai đoạn](#quy-trình-tách-5-giai-đoạn)
2. [Sáu thiết luật trích xuất nguyên tử](#sáu-thiết-luật-trích-xuất-nguyên-tử)
3. [Cấu trúc thư mục đầu ra](#cấu-trúc-thư-mục-đầu-ra)
4. [Hệ thống ngưỡng chất lượng](#hệ-thống-ngưỡng-chất-lượng)
5. [Bao đáy tình tiết cô lập](#bao-đáy-tình-tiết-cô-lập)
6. [Hướng dẫn thực thi cho AI](#hướng-dẫn-thực-thi-cho-ai)

---

## Quy trình tách 5 giai đoạn

### Giai đoạn 1: Phân tích chương

- Nhận biết dấu phân cách chương (Chương X、Chapter X、đánh số thứ tự...)
- Trích tiêu đề chương, ghi số chữ mỗi chương

### Giai đoạn 2: Trích xuất nguyên tử (xử lý song song từng chương)

#### A. Tóm tắt chương

- Một câu tóm lược (100-300 chữ, kể theo chuỗi nhân quả)
- Sự kiện then chốt (3-5, theo thứ tự thời gian)
- Nhân vật xuất hiện, thẻ chủ đề, tông chương
- Độ thúc đẩy cốt truyện (bước ngoặt lớn/quá độ thường ngày/gợi mở mạch ngầm)

#### B. Trích điểm cốt truyện (mỗi chương 10-15 điểm)

Ghi vào tiểu chương điểm cốt truyện của file tóm tắt chương .md (không xuất riêng .json). Mỗi điểm cốt truyện:

| Trường | Giải thích |
|------|------|
| Số thứ tự | Thứ tự thời gian nghiêm ngặt |
| Loại | Điểm chuyển/tiết lộ thông tin/xung đột/giải quyết/mở đệm/hành động/hội thoại/thay đổi trạng thái |
| Miêu tả | Tả trực tiếp khách quan, chỉ ghi đã xảy ra gì |
| Trích dẫn nguyên văn | <=400 chữ trích trực tiếp |
| Nhân vật liên quan | Họ tên đầy đủ, không dùng đại từ |
| Địa điểm | Thông tin vị trí địa lý |
| Vật phẩm then chốt | Vật phẩm liên quan cốt truyện |
| Dấu thời gian | Thời gian tương đối (hôm sau, nửa tháng sau, đồng thời) |

#### C. Trích nhân vật

Mỗi nhân vật trích: biểu hiện bên ngoài (thân phận/lời nói hành vi/ngoại hình), phân tích bên trong (tính cách/mục tiêu/bí mật), chức năng chương này, bí danh. Chỉ ghi nhân vật mới xuất hiện hoặc phát triển mới của nhân vật đã có.

### Giai đoạn 3: Phân tích tổng hợp (liên chương)

#### A. Tổng hợp tuyến truyện

Tổng hợp điểm cốt truyện thành「tuyến truyện」theo đường cong kể chuyện:
- Mỗi tuyến truyện gồm 75-225 điểm cốt truyện
- Trích: tiêu đề, tóm tắt, mục tiêu cốt lõi, xung đột cốt lõi, loại (tuyến chính/tình cảm/trưởng thành/phục thù/tầm bảo/huyền nghi)
- Đánh dấu phân bố cấu trúc: kỳ mở đệm/kỳ phát triển/kỳ cao trào/kỳ kết mỗi kỳ gồm những chương nào

#### B. Trích tuyến câu chuyện

Tổng hợp nhiều tuyến truyện thành「tuyến câu chuyện」: tiêu đề, miêu tả, nhân vật chính, từ khóa chủ đề, danh sách tuyến truyện gồm.

#### C. Tạo tóm tắt truyện

Nhận biết khung câu chuyện tổng thể + một đoạn tóm tắt toàn truyện.

### Giai đoạn 4: Trích thế giới quan và thiết lập

#### Thế giới quan

| Trường | Giải thích |
|------|------|
| Loại | Huyền huyễn/hiện thực/thế giới song song |
| Hệ thống sức mạnh | Tên, cấp bậc, cách thăng tiến |
| Địa lý | Phân bố, khu vực chính, địa điểm then chốt |
| Thế lực | Môn phái/tổ chức/gia tộc/quốc gia |
| Quy tắc cốt lõi | Quy tắc cơ bản vận hành thế giới |
| Thiết lập đặc biệt | Thiết lập độc đáo khác hiện thực |

#### Bàn tay vàng

| Trường | Giải thích |
|------|------|
| Loại | Hệ thống/không gian/trọng sinh/xuyên không/thể chất đặc biệt/thần khí/huyết mạch/khác |
| Tên | Tên bàn tay vàng |
| Miêu tả | Năng lực, chức năng, giới hạn |
| Cách nhận | Nhận được thế nào |
| Cơ chế cốt lõi | Điều kiện kích hoạt, tài nguyên cốt lõi, cách dùng |
| Lịch sử tiến hóa | Quỹ đạo nâng cấp và biến hóa |
| Năng lực hiện tại | Danh sách năng lực đã mở khóa |

### Giai đoạn 5: Trích quan hệ nhân vật

Mỗi cặp quan hệ:

| Trường | Giải thích |
|------|------|
| Nhân vật A | Họ tên đầy đủ |
| Nhân vật B | Họ tên đầy đủ |
| Loại quan hệ | Gia đình/sư đồ/bạn bè/kẻ thù/người yêu/đồng nghiệp/cấp trên-dưới/thương mại/khác |
| Khuynh hướng tình cảm | Tích cực/tiêu cực/trung tính/phức tạp |
| Trạng thái | Mới thiết lập/quan hệ tiến hóa |
| Miêu tả | Miêu tả quan hệ |
| Tương tác then chốt | Sự kiện cụ thể dẫn đến thiết lập hoặc thay đổi quan hệ |
| Chi tiết tiến hóa | Từ trạng thái trước biến thành trạng thái hiện tại thế nào |

Mỗi 5 chương trích hàng loạt một lần, chỉ ghi quan hệ mới hoặc thay đổi quan hệ.

---

## Sáu thiết luật trích xuất nguyên tử

1. Tuyệt đối sắp theo thứ tự thời gian
2. Chỉ dùng tả trực tiếp khách quan, không dùng từ khung kể chuyện
3. Thông tin trung thực, không bỏ sót chi tiết làm đổi ngữ cảnh
4. Cô đọng cao độ, một điểm cốt truyện một câu
5. Hành động phức hợp phải gộp (chuỗi vi hành động liên tiếp phục vụ cùng một mục đích kịch)
6. Trích điểm thông tin là sự thật khách quan, không làm phân tích kể chuyện

**Tả trực tiếp khách quan vs từ khung kể chuyện**:
- Sai: 「Thông qua hội thoại, Trịnh Tùng biết Trương Tử Hào đang huấn luyện ở Hàn Quốc」(có từ khung kể chuyện)
- Đúng: 「Ngô Chí Bân nói với Trịnh Tùng, Trương Tử Hào đang huấn luyện ở Hàn Quốc」(trần thuật trực tiếp sự kiện)
- Sai: 「Lâm Phong thể hiện thực lực của mình」(tổng kết trừu tượng)
- Đúng: 「Lâm Phong ba chiêu đánh bại đối thủ, người vây xem hít một hơi lạnh」(miêu tả cụ thể kết quả)

---

## Cấu trúc thư mục đầu ra

```
{tên_truyện}/
  chương/        Chương_{N}_tách_sâu.md + Chương_{N}_tóm_tắt.md
  nhân_vật/     {tên_nhân_vật}.md + Quan_hệ_nhân_vật.md
  tuyến_truyện/ {tiêu_đề_tuyến}.md + Tuyến_câu_chuyện.md + Tình_tiết_rơi_rụng.md
  thiết_lập/    Thế_giới_quan.md + Bàn_tay_vàng.md
  Báo_cáo_tách_văn.md
  Tóm_tắt.md
  _progress.md
```

---

## Hệ thống ngưỡng chất lượng

Sau khi hoàn thành giai đoạn 3 và giai đoạn 4 tự kiểm:

| Chỉ số | Ngưỡng | Tính | Xử lý khi không đạt |
|------|------|------|------------|
| Độ tin cậy | >= 0.85 | Điểm cốt truyện quy thuộc rõ ràng / tổng số điểm cốt truyện trong tuyến | Dưới 0.85 đánh dấu「chờ phúc tra」 |
| Độ bao phủ | 85%-95% | Điểm cốt truyện đã phân loại / tổng số điểm cốt truyện | <85% kích hoạt phân loại lại tình tiết cô lập; >95% phúc tra ranh giới |
| Tỷ lệ chồng lấn | <= 35% | Điểm cốt truyện dùng chung liên tuyến / tổng số điểm cốt truyện | >35% nhắc ranh giới mơ hồ, đề nghị gộp |

---

## Bao đáy tình tiết cô lập

Sau khi tổng hợp giai đoạn 3 thực thi:

1. Lọc điểm cốt truyện chưa phân vào tuyến nào
2. Phân vào tuyến hiện có theo tương quan (độ tin cậy >= 0.7 có thể phân vào)
3. Tương quan không đủ thì phân cụm theo chủ đề thành tuyến ứng cử
4. Vẫn không phân được thì gom vào phụ lục「Tình tiết rơi rụng」(không vứt bỏ)

---

## Hướng dẫn thực thi cho AI

### Chiến lược phân khối

| Quy mô | Chiến lược | Kích thước khối |
|------|------|--------|
| <100 chương | Xử lý tổng thể theo giai đoạn | Không cần phân khối |
| 100-500 chương | Phân khối theo chương | 5-8 chương/khối |
| >500 chương | Chia theo quyển trước, trong quyển lại phân khối | 5-8 chương/khối |

Kích thước khối 6-8K token/khối, căn chỉnh ranh giới chương. Mỗi khối xong cập nhật _progress.md.

### Khôi phục liên phiên

- Tiến độ theo dõi qua _progress.md
- Phiên mới đọc _progress.md định vị điểm đứt
- Bắt đầu lại từ chương đầu khối chứa điểm đứt (ghi đè đầu ra đã có của khối đó)

### Quan hệ với SKILL.md

- SKILL.md = logic định tuyến + tóm tắt pipeline (tên giai đoạn/đầu vào/đầu ra)
- File này = chi tiết phương pháp luận (5 giai đoạn thao tác + sáu thiết luật + cấu trúc đầu ra + ngưỡng chất lượng)
- references/output-templates.md = mẫu định dạng đầu ra cụ thể
