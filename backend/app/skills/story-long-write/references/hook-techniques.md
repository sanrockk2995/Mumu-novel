# Đại toàn kỹ thuật hook

## Mục lục

- [Hook cuối chương 13 thức](#章尾钩子-13-式)
  - [1. Hé lộ đột ngột](#1-突然揭示)
  - [2. Nguy cơ khẩn cấp](#2-紧急危机)
  - [3. Hành động dang dở](#3-未完成动作)
  - [4. Đảo ngược thân phận](#4-身份反转)
  - [5. Lựa chọn tiến thoái lưỡng nan](#5-两难抉择)
  - [6. Vật phẩm/manh mối bí ẩn](#6-神秘物品线索)
  - [7. Đếm ngược](#7-倒计时)
  - [8. Hứa hẹn/đe doạ](#8-承诺威胁)
  - [9. Biến mất kỳ lạ](#9-离奇消失)
  - [10. Ẩn ý](#10-隐藏含义)
  - [11. Hook hình tượng](#11-意象钩子)
  - [12. Hook hồi âm](#12-回声钩子)
  - [13. Hook bỏ trống](#13-留白钩子)
- [Hook đầu chương 7 thức](#章首钩子-7-式)
  - [1. Mở đầu bằng đối thoại hồi hộp](#1-悬念对话开局)
  - [2. Mảnh chớp tương lai](#2-闪前碎片)
  - [3. Mở đầu đếm ngược](#3-倒计时开局)
  - [4. Độc thoại bí ẩn](#4-神秘独白)
  - [5. Cảnh tương phản](#5-反差场景)
  - [6. Mở đầu hành động dang dở](#6-未完成动作开局)
  - [7. Hình tượng báo trước](#7-意象预示)
- [Mẫu hook cuối chương thực chiến](#实战章末钩子模板)
  - [I. Hook kiểu kích hoạt hệ thống](#一系统激活型钩子)
  - [II. Hook kiểu báo trước hồi hộp](#二悬念预知型钩子)
  - [III. Hook kiểu cắt ngang](#三截断型钩子)
  - [IV. Hook kiểu lựa chọn](#四选择型钩子)
  - [V. Hook kiểu nguy cơ leo thang](#五危机升级型钩子)
  - [VI. Hook kiểu thân phận sắp hé lộ](#六身份即将揭露型钩子)
  - [VII. Hook kiểu chuyển ngoặt tình cảm](#七情感转折型钩子)
  - [VIII. Hook kiểu chênh lệch thông tin](#八信息差型钩子)
  - [IX. Hook kiểu hồi hộp đối thoại](#九对话悬念型钩子)
  - [X. Hook kiểu nhảy thời gian](#十时间跳跃型钩子)
  - [Hướng dẫn chọn hook chương](#章节钩子选择指南)
  - [Ba cách viết hook cuối chương thực chiến](#章末钩子三种实战写法)
  - [Quy tắc cốt lõi xây dựng hồi hộp](#悬念构建核心法则)
  - [Bản chất của hồi hộp](#悬念的本质)
  - [Hồi hộp vs phục bút](#悬念-vs-伏笔)
  - [Bốn mẫu thứ tự thông tin hồi hộp](#四种悬念信息顺序模板)
  - [Hook kiểu kích hoạt (hook phân tầng)](#触发型钩子分层钩子)
- [Các loại hook cấp truyện ngắn/đoạn](#短篇段落级钩子类型)
  - [1. Hook chênh lệch thông tin (Information Gap)](#1-信息差钩子information-gap)
  - [2. Hook đếm ngược (Countdown)](#2-倒计时钩子countdown)
  - [3. Hook đảo ngược (Reversal)](#3-反转钩子reversal)
  - [4. Hook bài tẩy (Hidden Card)](#4-暗牌钩子hidden-card)
  - [5. Hook vả mặt (Face-slap)](#5-打脸钩子face-slap)
  - [6. Hook cái giá (Cost)](#6-代价钩子cost)
  - [7. Hook kẻ yếu/trẻ con (Vulnerable)](#7-弱者孩子钩子vulnerable)
  - [Kết hợp hook](#钩子组合)
  - [Checklist bóc truyện](#拆文检查清单)
  - [Ví dụ hook thực chiến](#实战钩子示例)
  - [Các loại hook mới](#新增钩子类型)
  - [8. Hook hồnbàng quan (Ghost POV)](#8-灵魂旁观钩子ghost-pov)
  - [9. Hook vật thể dị thường (Anomalous Object)](#9-异常物件钩子anomalous-object)
  - [10. Hook giả vờ phục tùng (Feigned Compliance)](#10-假意顺从钩子feigned-compliance)
  - [11. Hook phát hiện lạnh (Cold Discovery)](#11-冷发现钩子cold-discovery)
  - [Kết hợp hook mới](#新增钩子组合)
  - [Cảm xúc đối thoại tăng dần 5 cấp](#对话情绪五级递增)
  - [Hook tổn thương bất công](#不公平伤害钩子)
  - [Tầng cấp chất lượng người vây xem](#围观者质量层级)
  - [Phương pháp tiếp sức kỳ vọng](#期待接力法)
- [Sắp xếp hồi hộp](#悬念编排)
  - [Phân cấp cường độ](#强度分级)
  - [Chu kỳ hồi hộp đa tuyến](#多线悬念周期)
  - [Thiết kế hook 3 đoạn (trong một chương)](#三段钩子设计单章内)
- [Điều cấm kỵ của hook](#钩子禁忌)
- [Cách viết phân tầng chấn kinh](#震惊分层写法)
  - [Cấu trúc 3 tầng chấn kinh](#震惊三层结构)
  - [Cách thể hiện cụ thể chấn kinh tăng dần](#震惊递进的道具体现法)
  - [Nguyên tắc then chốt](#关键原则)
- [Luận 3 đời ngạnh cốt lõi](#核心梗三代论)
  - [Nguyên tắc then chốt](#关键原则-1)
  - [Bốn cách mở rộng ngạnh cốt lõi (lấy "hệ thống đến sớm" làm ví dụ)](#核心梗延伸四法以系统早到为例)
  - [Quy trình chuẩn công thức hoá giả heo ăn hổ](#公式化扮猪吃虎标准流程)
- [Bản chất kỳ vọng](#期待感本质)
  - [Quy tắc 3 búa kéo kỳ vọng](#三板斧拉期待法则)
  - [Cách thực hành duy trì kỳ vọng trăm vạn chữ](#维持百万字期待实操法)
  - [Tầng cấp chất lượng người vây xem](#围观者质量层级-1)
  - [Thiết kế tầng cấp chấn kinh](#震惊层级设计)
- [Mô hình cốt lõi kỳ vọng](#期待感核心模型)
  - [Cách viết hai dài một ngắn](#两长一短写法)
  - [Cách vận hành đa tuyến kỳ vọng (cách vẽ đường)](#期待感多线运行法画线法)
  - [Ba liên kết tiếp nối kỳ vọng khi đổi bản đồ](#换地图时期待感延续三链接)
  - [Đại cấu trúc kiểu Pinduoduo](#拼多多式大结构)
  - [Kỳ vọng không được đứt](#期待感不能断)
  - [Tuyến tình cảm làm tuyến kỳ vọng](#感情线作为期待线)
  - [Vận dụng chênh lệch thông tin](#信息差运用)
  - [Thủ pháp đưa kính viễn vọng](#递望远镜手法)
  - [Bài tẩy đặt trước](#底牌前置)
  - [Cách dùng ngạnh cốt lõi dẫn dắt](#核心梗驱动法)
- [Công thức thiết kế xung đột phản diện](#反派冲突设计公式)
  - [Ba kiểu xung đột phản diện](#反派冲突三型)
  - [Cấu trúc 5 yếu tố](#五要素结构)
  - [Cấu trúc 3 đoạn dục vọng-kỳ vọng-điểm sảng của phản diện](#反派欲望-期待-爽点三段结构)
- [Cách thao túng kỳ vọng tâm lý độc giả](#读者心理预期操控法)
  - [Nhận thức cốt lõi](#核心认知)
  - [Ví dụ thao túng kỳ vọng tâm lý](#心理预期操控示例)
  - [Hai trạng thái của hồi hộp](#悬念的两种状态)
  - [Thao tác đảo ngược](#反转操作)
  - [Điểm then chốt khi thao tác](#操作要点)
- [Cách kéo giằng đòn bẩy kỳ vọng](#期待感杠杆拉扯法)
  - [Sáu bước thực hành kéo giằng đòn bẩy](#杠杆拉扯六步实操)
  - [Nguyên tắc then chốt](#关键原则-2)
- [Cách phá cục phản dự đoán](#反预判破局法)
  - [Tầng cấp phá cục](#破局层次)
- [Điểm then chốt khi viết cao trào](#高潮写作要点)
- [Nhịp đường sóng cảm xúc](#情绪波浪线节奏)
  - [Bốn điều cốt lõi](#核心四条)
  - [Thực hành sóng cảm xúc](#情绪波浪实操)
- [Ví dụ tiếp nối kỳ vọng khi đổi bản đồ (bóc 《Quỷ Bí Chi Chủ》)](#换地图期待感衔接案例诡秘之主拆解)
  - [Ba liên kết tiếp nối (bóc cụ thể)](#衔接三链接具体拆解)
  - [Vòng tuần hoàn lưu phái nâng cấp ở bản đồ mới](#新地图升级流循环)
- [Cấu trúc hoàn chỉnh tuyến sự nghiệp](#事业线完整结构)
  - [Cách viết phản ứng nhân vật trong điểm sảng](#爽点中人物反应的写法)
- [Lỗi thường gặp về kỳ vọng](#期待感常见错误)
- [Cốt lõi đề tài & quản lý kỳ vọng độc giả](#题材核心与读者期待管理)
  - [Bảng tra nhanh cốt lõi đề tài](#题材核心速查表)
  - [Dấu hiệu lệch cốt lõi đề tài](#题材核心偏离的信号)
  - [Thực hành mở rộng ngạnh cốt lõi (lấy "hệ thống đến sớm" làm ví dụ)](#核心梗延伸实操以系统早到为例)
  - [Cách tự kiểm đứt gãy cảm xúc cốt lõi](#核心情绪断裂的自检方法)
- [Thiết kế vòng tuần hoàn cốt truyện tuyến sự nghiệp](#事业线剧情循环设计)
  - [Vòng tuần hoàn lưu phái nâng cấp chuẩn](#标准升级流循环)
  - [Điểm then chốt trong vòng tuần hoàn](#循环中的要点)
  - [Kho tình tiết dùng được cho đô thị cao võ](#都市高武可用情节库)
- [Nâng cấp hiệu quả chấn động: cách chấn惊 qua mạng quan hệ](#震动效果升级关系网震惊法)
  - [Tầng cấp chấn kinh mạng quan hệ](#关系网震惊层级)
  - [Nguyên lý nhân đôi khi làm người quen chấn kinh](#震惊熟人的倍增原理)
- [Nâng cao tiếp nối kỳ vọng khi đổi bản đồ](#换地图期待感衔接进阶)
  - [Ví dụ thất bại khi đổi bản đồ](#换地图失败案例)
  - [Cách làm đúng khi đổi bản đồ](#换地图正确做法)
  - [Lưu phái nhân tình thế sự (một ngạnh cốt lõi có thể tham khảo)](#人情世故流一种可参考的核心梗)
- [Lý thuyết hệ thống "đứt kỳ vọng"](#断期待系统理论)
  - [Sáu điều cấm kỵ đứt kỳ vọng](#六大断期待禁忌)
  - [Cách giải quyết tương ứng](#对应解决方法)
- [Cách kéo cảm xúc "lấy lui làm tiến"](#以退为进拉情绪法)
  - [Ba cách viết sai khi nhân vật chính trả giá](#主角付出的三种错误写法)
  - [Cốt lõi của cách lấy lui làm tiến](#以退为进法的核心)
- [Cách vận hành khác biệt hoá ngạnh cốt lõi](#核心梗差异化运行法)
  - [Ba cách vận hành khác biệt hoá](#三种差异化运行方法)
  - [Mô hình "tháp cao" chống đứt kỳ vọng](#防止断期待的高塔模型)
- [Cách thực hành kỳ vọng "hai dài một ngắn"](#两长一短期待感实操法)
  - [Cách thao tác kiểu Đại Phụng (khuyên người mới học)](#大奉式操作法推荐新手学习)
  - [Nguyên tắc quản lý kỳ vọng dài ngắn](#长短期待管理原则)
- [Nâng cao khoe mẽ: cách phóng đại cấu trúc cấp hai](#装逼进阶二级结构放大法)
  - [Ý tưởng cốt lõi](#核心思路)
  - [Nguyên tắc mở rộng phân tầng khán giả](#观众分层扩大原则)
  - [Cách tạo cảm giác chênh lệch](#落差感制造法)
  - [Chuyển mô thức khoe mẽ liên tục](#连续装逼的模式切换)
- [Cấu trúc ba lật bốn chấn](#三翻四震结构)
  - [Cấu trúc](#结构)
  - [Bóc ví dụ (nhân vật chính chọn học viện)](#实例拆解主角选择院校)
  - [Nguyên tắc then chốt](#关键原则-3)
- [Quy tắc 5 từ nguy cơ mở đầu](#开头危机五词法则)
  - [Tiêu chuẩn phán đoán](#判断标准)
  - [Tại sao quan trọng](#为什么重要)
- [Cách tạo điểm sảng "muốn trái trước phải"](#欲左先右爽点制造法)
  - [Công thức cốt lõi](#核心公式)
  - [Ba mô thức thao tác](#三种操作模式)
  - [Cách độc giả biết trước (đưa kính viễn vọng)](#读者预知法递望远镜)
  - [Cách đặt bài tẩy trước](#底牌前置法)
- [Cách thiết kế điểm lo (tạo lo âu)](#虑点设计法焦虑制造)
  - [Các bước thiết kế](#设计步骤)
  - [Nguyên tắc then chốt](#关键原则-4)
- [Cách thể hiện cụ thể chấn kinh tăng dần](#震惊递进的道具体现法-1)
  - [Điểm then chốt](#要点)
- [Cách đếm ngược kéo kính viễn vọng](#倒计时拉望远镜法)
- [Cách đòn bẩy kéo giằng cảm xúc](#情绪拉扯杠杆法)
- [Hai kênh tạo kỳ vọng](#期待感营造双通道)
  - [Tạo từ bên trong](#内部营造)
  - [Tạo từ bên ngoài](#外部营造)
  - [Quy tắc hai dài một ngắn](#两长一短法则)

## Hook cuối chương 13 thức

### 1. Hé lộ đột ngột
Ném ra thông tin thay đổi toàn cục.
- "Ngày trên thư, là ngày thứ bảy sau khi anh ta chết."
- "Mở két sắt, bên trong chỉ có một tấm ảnh — người trong ảnh, là chính cô ấy."

### 2. Nguy cơ khẩn cấp
Mối đe dọa cấp bách chương sau phải đáp lại.
- "Vết nứt đang mở rộng, linh thạch còn thiếu ba viên."
- "Đếm ngược hiển thị còn 180 giây, nhưng sợi dây đỏ còn chưa tìm thấy."

### 3. Hành động dang dở
Hành động bị biến số mới cắt ngang.
- "Anh ta vừa đưa tay ra — 'Đừng động.' Sau lưng vang lên một giọng nói."
- "Cửa đẩy được một nửa, một bàn tay từ bên trong thò ra, đóng cửa lại."

### 4. Đảo ngược thân phận
Ai đó không phải người chúng ta tưởng.
- "Anh ta tháo khẩu trang. Gương mặt đó, giống hệt Ma Vương."
- "Cô ấy nói mình tên Lâm Tiểu Nguyệt. Nhưng trên hồ sơ viết: Lâm Tiểu Nguyệt, đã mất."

### 5. Lựa chọn tiến thoái lưỡng nan
Bị ép chọn một trong hai lựa chọn tồi.
- "Thuyền cứu sinh chỉ ngồi được hai người, dưới nước có ba người."
- "Ký vào tài liệu này, công ty giữ được, nhưng anh ta phải vào tù."

### 6. Vật phẩm/manh mối bí ẩn
Đồ vật quan trọng nhưng ý nghĩa chưa rõ.
- "Một tấm ảnh chụp hôm qua, góc chụp — là chụp từ ngoài cửa sổ nhà cô ấy."
- "Trong bưu kiện là một chiếc chìa khoá, kèm mảnh giấy: 'Ngươi nợ ta.'"

### 7. Đếm ngược
Thời gian không đủ dùng.
- "Con số trên quả bom đang nhảy: 02:57."
- "Bác sĩ nói còn ba tháng. Đó là chuyện của hai tháng trước."

### 8. Hứa hẹn/đe doạ
Ai đó tuyên bố ý đồ hành động.
- "Trước mười hai giờ đêm nay, tôi sẽ nói cho mọi người biết anh đã làm gì."
- "Ngày mai, cả công ty sẽ biết bí mật này."

### 9. Biến mất kỳ lạ
Sự biến mất không thể nào.
- "Còng tay còn đó, người mất rồi. Cả căn phòng chỉ có một cánh cửa, cửa chưa từng mở."
- "Trong camera cô ấy bước vào thang máy, nhưng camera tầng dưới không quay được cảnh cô ấy đi ra."

### 10. Ẩn ý
Đối thoại nhìn bình thường, thật ra giấu thông tin.
- "Anh ta nói: 'Em với em gái giống nhau thật.' — Cô ấy là con một."
- "Cô ấy trong di chúc để lại nhà cho 'người bạn cũ trong nhà'. Cô ấy nuôi một con mèo."

### 11. Hook hình tượng
Hình tượng lặp đi lặp lại biến đổi ở cuối chương, ám chỉ chuyển ngoặt.
- "Chậu nhài trên bệ cửa sổ héo cả tháng, đột nhiên nhú nụ hoa."
- "Đèn lại tắt. Nhưng lần này, cô ấy ngửi thấy mùi khói."

### 12. Hook hồi âm
Câu cuối chương vang vọng câu đầu, chi tiết then chốt đổi rồi.
- Đầu: "Cô ấy nói cô ấy vĩnh viễn sẽ không tha thứ cho anh ta."
- Cuối: "Cô ấy nói cô ấy vĩnh viễn sẽ không tha thứ cho anh ta. Nhưng tay cô ấy, siết chặt hơn."

### 13. Hook bỏ trống
Cố ý không hé lộ đã xảy ra gì, chỉ cho thấy phản ứng.
- "Anh ta đọc thư. Sắc mặt đổi. Không nói gì, gấp thư bỏ vào túi."
- "Đầu dây bên kia im lặng rất lâu. Rồi cô ấy nói: 'Tôi biết rồi.' Cúp máy."

---

## Hook đầu chương 7 thức

### 1. Mở đầu bằng đối thoại hồi hộp
Bắt đầu thẳng từ một đoạn đối thoại đầy ẩn ý.
- "Anh chắc muốn làm vậy? / Chắc. / Vậy thì đừng hối hận."

### 2. Mảnh chớp tương lai
Cho trước một mảnh kết quả, rồi quay về kể bình thường.
- "Về sau anh ta mới biết, cú điện thoại đó đã thay đổi mọi chuyện. Nhưng lúc này anh ta còn chưa biết gì."

### 3. Mở đầu đếm ngược
Đầu chương đã dựng cảm giác cấp bách.
- "Còn 72 giờ nữa hợp đồng hết hạn."

### 4. Độc thoại bí ẩn
Độc thoại nội tâm kỳ dị ở ngôi thứ nhất.
- "Tôi cứ nghĩ mãi, hôm đó nếu tôi không quay đầu, mọi thứ có khác không."

### 5. Cảnh tương phản
Hai cảnh hoàn toàn khác nhau đặt cạnh nhau.
- "Một bên là hiện trường hôn lễ, tháp sâm panh chất cao ngất. Bên kia, đèn hành lang bệnh viện đang chớp."

### 6. Mở đầu hành động dang dở
Hành động đang tiến hành bị cắt ngang.
- "Anh ta vừa tra chìa vào ổ khoá —"

### 7. Hình tượng báo trước
Dùng hình tượng môi trường ám chỉ chuyện sắp xảy ra.
- "Chân trời cháy đỏ rực, như có thứ gì đang bốc cháy. Cô ấy ngẩng đầu nhìn một cái, tiếp tục đi."

---


---

## Mẫu hook cuối chương thực chiến

### I. Hook kiểu kích hoạt hệ thống

**Ví dụ thật**:
> Ngay lúc anh ta vạn niệm đều tan. Một giọng máy móc lạnh lẽo, đột nhiên vang lên trong đầu anh ta. Đinh!【Hệ thống Thiếu Niên Khinh Cuồng, chính thức khởi động.】

**Cấu trúc**: khoảnh khắc tuyệt vọng → âm thanh đột ngột → tên hệ thống

**Mẫu**:
```
Ngay lúc {nhân vật chính}{trạng thái đáy nhất}.
{Một miêu tả giác quan}.
Đinh!
【{Tên hệ thống}, chính thức khởi động.】
```

**Biến thể**:
- Ngay lúc anh ta chuẩn bị từ bỏ, trước mắt đột nhiên hiện ra một hàng chữ vàng.
- Trong đầu bỗng vang lên một giọng máy móc.
- Trên mu bàn tay hiện ra một hoa văn kỳ dị.

---

### II. Hook kiểu báo trước hồi hộp

**Ví dụ thật**:
> Tôi lạnh lùng nhìn đám người cười đến ngửa trước ngửa sau. Cười đi. Cười thêm lúc nữa. Qua hôm nay, các ngươi sẽ không bao giờ cười nổi nữa.

**Cấu trúc**: đối phương kiêu ngạo → nhân vật chính quan sát lạnh → báo trước đảo ngược

**Mẫu**:
```
{Nhân vật chính}{bình tĩnh/lạnh lùng} nhìn {hành vi kiêu ngạo của đối phương}.
{Một câu ngắn: cứ tiếp tục đi/từ từ/không vội}.
{Báo trước đảo ngược sắp xảy ra, không hé chi tiết}.
```

**Biến thể**:
- Điều anh ta không biết là, tai hoạ thật sự còn đang trên đường.
- Nhưng mọi người đều bỏ qua một chi tiết.
- Chỉ là cô ấy không biết, quyết định đó, sẽ thay đổi triệt để mọi thứ.

---

### III. Hook kiểu cắt ngang

**Ví dụ thật**:
> Chỉ một ngụm! Đồng tử của cô ấy đột ngột co thành đầu kim. Ầm! Một luồng nhiệt kinh khủng đến khó tả, trong nháy mắt trong bụng cô ấy nổ tung! Đây...... đây không phải cháo thường! Đây là gì?

**Cấu trúc**: hành động nhỏ → phản ứng lớn → câu hỏi (không trả lời)

**Mẫu**:
```
{Một hành động nhỏ}.
{Phản ứng dữ dội}.
{Kinh ngạc/câu hỏi —— chương kết thúc, không cho đáp án}.
```

**Biến thể**:
- Cô ấy mở cửa — người đàn ông nằm trên giường khiến máu cô ấy trong nháy mắt đông cứng.
- Trên bảng hệ thống nhảy ra một hàng chữ, anh ta nhìn rõ rồi, cả người sững lại.
- Đầu dây bên kia im lặng ba giây, rồi nói ra một cái tên anh ta nằm mơ cũng không nghĩ tới.

---

### IV. Hook kiểu lựa chọn

**Ví dụ thật**:
> Phần thưởng: Câu Ngọc Luân Hồi Nhãn, trái Chakra…… Cái giá: vô địch trăm năm xong lập tức chết bất đắc kỳ tử.
> Phần thưởng: vĩnh viễn bất tử! Cái giá: thực lực vĩnh viễn kẹt ở cấp Siêu Ảnh.

**Cấu trúc**: hai/nhiều lựa chọn + lợi hại mỗi bên → chương kết thúc

**Mẫu**:
```

Phần thưởng: {phần thưởng cực kỳ hấp dẫn}
Cái giá: {rủi ro ẩn}

Phần thưởng: {phần thưởng hấp dẫn khác}
Cái giá: {rủi ro khác}
```

**Biến thể**:
- Trước mắt xuất hiện hai con đường: một dẫn tới ánh sáng, một dẫn tới vực sâu.
- "Ngươi chỉ có một cơ hội." Anh ta nhìn hai cái nút trước mặt.

---

### V. Hook kiểu nguy cơ leo thang

**Ví dụ thật**:
> "Đều ra đây cho lão tử! Nhanh lên!" Rầm!!! Một chiếc ủng quân dính đầy bùn, thô bạo đá tung cửa lồng.

**Cấu trúc**: âm thanh đột ngột → mối đe dọa mới xuất hiện

**Mẫu**:
```
{Âm thanh/hành động đột ngột}!
{Mối đe dọa mới xuất hiện}.
{Phản ứng sợ hãi/cấp bách của nhân vật chính}.
```

**Biến thể**:
- Cuối hành lang vang lên tiếng bước chân. Càng lúc càng gần.
- Màn hình điện thoại đột nhiên sáng. Một tin nhắn từ số lạ.
- Tay nắm cửa đang xoay.

---

### VI. Hook kiểu thân phận sắp hé lộ

**Ví dụ thật**:
> Một phú thương nhìn chằm chằm tôi, ngập ngừng mở miệng: "Thẩm đại cô nương có từng đến Tây Vực không?" "Ta buôn bán bên đó, nghe nói bên Tây Vực có người phụ nữ, có dây dưa với hoàng thất, cũng tên Thẩm gì Nguyệt."

**Cấu trúc**: người bên cạnh phát hiện manh mối → nhân vật chính căng thẳng → tạm thời bị cắt ngang

**Mẫu**:
```
{Người chứng kiến} đột nhiên {đặt câu hỏi/phát hiện manh mối}.
"{Lời ám chỉ thân phận thật của nhân vật chính}"
{Người khác không để ý, nhân vật chính âm thầm căng thẳng}.
```

---

### VII. Hook kiểu chuyển ngoặt tình cảm

**Ví dụ thật**:
> Đúng lúc này, biểu cảm của Giang Diệc Dao đột nhiên đổi, hốc mắt đỏ lên, hai hàng lệ trong không hề báo trước lăn xuống. Cô mang giọng khóc: "Xin ngươi, Tô Mục, để ta đi đi……"

**Cấu trúc**: cảm xúc đột biến → tỏ yếu ngoài dự liệu → nhân vật chính dao động

**Mẫu**:
```
Đúng lúc này, {biểu cảm/thái độ} của {nhân vật} đột nhiên {đổi lớn}.
{Một hành động tỏ yếu/yêu cầu ngoài dự liệu}.
"{Lời đâm trúng điểm mềm của nhân vật chính}"
```

---

### VIII. Hook kiểu chênh lệch thông tin

**Ví dụ thật**:
> Hoa có ngày nở lại, người không có tuổi thiếu niên lần hai. Sao mình lại để cuộc sống thành bộ dạng cứt chó thế này?

**Cấu trúc**: nhân vật chính tự giễu/cảm khái → độc giả biết nhân vật chính sắpđón chuyển cơ → cuối chương đảo ngược

**Mẫu**:
```
{Tự nghi ngờ/cảm khái của nhân vật chính}.
{Một hình tượng/ví von}.
{Ám chỉ sắp thay đổi, nhưng không nói rõ}.
```

---

### IX. Hook kiểu hồi hộp đối thoại

**Ví dụ thật**:
> "Ta có một thỉnh cầu." Tô Mục chậm rãi nói.
> "Ngươi nói đi."
> "Trước khi ly hôn, ta muốn chứng minh mình một lần."

**Cấu trúc**: đưa ra thỉnh cầu → đối phương đồng ý → nói lời ngoài dự liệu

**Mẫu**:
```
"{Nửa đầu câu đưa ra thỉnh cầu}"
"{Đối phương đáp lại}"
"{Nửa sau ngoài dự liệu —— không phải điều độc giả mong đợi}"
```

---

### X. Hook kiểu nhảy thời gian

**Ví dụ thật**:
> Ba phút ba giây sau. Giang Diệc Dao thần sắc thong dong bước ra khỏi phòng, chỉnh lại quần áo hơi rối.

**Cấu trúc**: đánh dấu thời gian → cho thấy kết quả → bỏ trống quá trình ở giữa

**Mẫu**:
```
{Đánh dấu thời gian chính xác/mơ hồ}.
{Kết quả ngoài dự liệu}.
{Một câu ám chỉ quá trình}.
```

---

### Hướng dẫn chọn hook chương

| Giai đoạn truyện | Loại hook khuyên dùng | Tần suất |
|----------|-------------|------|
| Chương 1 | Kích hoạt hệ thống/cắt ngang/nguy cơ leo thang | Phải mạnh |
| Chương 2-3 | Lựa chọn/chênh lệch thông tin/chuyển ngoặt tình cảm | Mạnh |
| Thường nhật giữa truyện | Hồi hộp đối thoại/chênh lệch thông tin/thân phận sắp hé lộ | Trung |
| Trước cao trào | Nguy cơ leo thang/báo trước hồi hộp | Mạnh |
| Đại kết cục | Nhảy thời gian/chuyển ngoặt tình cảm | Thu lại |

---

### Ba cách viết hook cuối chương thực chiến

### Kiểu báo trước thu hoạch

```
{Hành động hiện tại gần hoàn thành}.
{Ám chỉ phần thưởng sắp có}.
{Một câu ám chỉ phần thưởng lớn hơn mong đợi}.
```

Hiệu quả: độc giả mong chờ chương sau thấy thu hoạch được thực hiện. Dùng khi phó bản/nhiệm vụ gần kết thúc.

### Kiểu phản diện áp sát

```
{Trạng thái hiện tại của nhân vật chính}.
{Trong tối/xa, một hành động nào đó của phản diện}.
{Ám chỉ hành động này sẽ ảnh hưởng nhân vật chính}.
```

Hiệu quả: độc giả lo cho an nguy của nhân vật chính, nóng lòng muốn thấy xung đột. Dùng ở cuối đoạn lót.

### Kiểu báo trước hành động

```
{Nhân vật chính đưa ra một quyết định}.
{Một động tác chuẩn bị}.
{Ám chỉ hành động sắp xảy ra} —— không viết kết quả.
```

Hiệu quả: độc giả mong chờ quá trình và kết quả hành động của nhân vật chính. Dùng trước khi nhân vật chính sắp khoe mẽ/vả mặt.

### Điểm then chốt khi thao tác

- Mỗi chương kết thúcbỏ thêm 100 chữ đặt hook, tỷ lệ đọc hết tăng rõ rệt
- Hook không cần phức tạp,điểm đến là dừng
- Mạng quan hệ càng phong phú, lựa chọn hook càng nhiều (có thể dùng kẻ thù của kẻ thù, nhân vật cũtrở lại v.v. làm hook)

---

### Quy tắc cốt lõi xây dựng hồi hộp

### Bản chất của hồi hộp

Khi kỳ vọng tâm lý của độc giả có hai hướng đi khác nhau trở lên, cốt truyện đã có hồi hộp —— vì anh ta thấy đều có thể.

### Hồi hộp vs phục bút

| Chiều | Hồi hộp | Phục bút |
|------|------|------|
| Mục đích | Để độc giả đoán tiếp theo sẽ thế nào | Chôn manh mối trước cho hé lộ sau |
| Vị trí | Thường ở cuối chương/đoạn | Thường tự nhiên đưa ra trong kể chuyện |
| Thời cơ hé lộ | Hé lộ ngắn hạn | Dài hạn mới hé lộ |
| Hiệu quả cảm xúc | Căng thẳng/tò mò/mong chờ | Chấn kinh/ngộ ra |

### Bốn mẫu thứ tự thông tin hồi hộp

| Loại | Cấu trúc | Dùng cho |
|------|------|------|
| Cốt truyệnthẳng thắn | Đặt câu hỏi → công bố đáp án | Kể cơ bản |
| Cốt truyện khám phá | Đặt câu hỏi → gợi ý bình thường → công bố đáp án | Đoạn lót |
| Cốt truyện bất ngờ | Đặt câu hỏi → gợi ý giả → công bố đáp án | Đoạn đảo ngược |
| Bất ngờ + đảo ngược | Đặt câu hỏi → gợi ý giả 1 → gợi ý giả đối lập 2 → công bố đáp án | Đoạn cao trào |

### Hook kiểu kích hoạt (hook phân tầng)

Trong một đoạn cốt truyện hoàn chỉnh, dùng nhiều tầng tạo hồi hộptăng dần：

```
Tầng 1: cho thấy thành quả bước đầu → khán giả phản ứng bước đầu
Tầng 2: hé lộ đây còn chưa phải kết quả cuối → kỳ vọng của khán giả nâng cấp
Tầng 3: cho thấy yếu tố vượt mong đợi → khán giả chấn kinh
Tầng 4: nhân vật chính còn nâng được nữa → để lại hook, mở đoạn tiếp theo
```

**Then chốt**: mỗi tầng đều phải có phản ứng của nhân vật đểkiểm chứngđộ mạnh của hồi hộp

---

## Các loại hook cấp truyện ngắn/đoạn

Truyện ngắn không có "ba chương vàng", dựa vào là hook của mỗi đoạn. Lúc bóc truyện trọng tâm xem mỗi chỗ chuyển ngoặt dùng hook gì, cường độ hook thế nào, độc giả có bị móc trúng không.

---

### 1. Hook chênh lệch thông tin (Information Gap)

**Định nghĩa**: độc giả biết một thông tin then chốt nào đó, nhưng nhân vật không biết. Độc giảthay nhân vật sốt ruột,thay nhân vật sợ hãi.

**Khi nào dùng**:
- Đoạn lót, dựng cảm giác ưu việt cho độc giả
- Tầng dìm cuối cùng trước đảo ngược
- Để độc giả đoán "bao giờ anh ta mới phát hiện"

**Ví dụ**:
> Anh ta cườinhận lấy cà phê, không biết cô ấy vừa mới bỏ vào đó một viên thuốc ngủ.

**Hiệu quả**: ★★★★★
- Hook dùng nhiều nhất truyện ngắn
- Không tốnchi phí tạo cảm giác căng thẳng
- Động lực cốt lõi của truyện trọng sinh, truyện báo thù
- Lưu ý: chênh lệch thông tin không thể kéo quá lâu, quá 3000 chữ độc giả sẽ bực

---

### 2. Hook đếm ngược (Countdown)

**Định nghĩa**: đặt áp lực thời gian rõ ràng. Đến một nút nào đó, chuyện gì đó sắp xảy ra.

**Khi nào dùng**:
- Đoạn phát triển, đẩy nhịp
- Trước cao trào thu lực căng
- Giữa truyện ngắnngăn nhịp sụp
**Ví dụ**:
> Thời gian suy nghĩ ly hôn còn ba ngày cuối cùng. Ba ngày sau, anh ta ký hay không đều không sao nữa.

**Hiệu quả**: ★★★★☆
- Tạo cảm giác cấp bách trực tiếp nhất
- Hợp đề tài hôn nhân, thế tình, huyền nghi
- Đếm ngược có thể là thời gian cụ thể, cũng có thể là nút sự kiện ("đợi anh ta về", "trước khi con ra đời")
- Lưu ý: đếm ngược một khi đã đặt, phải đến hạn thực hiện, không được bỏ lửng

---

### 3. Hook đảo ngược (Reversal)

**Định nghĩa**: kỳ vọng của độc giả đột nhiên bị phá vỡ. Tưởng là A, kết quả là B.

**Khi nào dùng**:
- Vị trí cốt lõi toàn truyện (60-75%)
- Cuối chương, ép độc giả lật chương sau
- Điểm ngoặt then chốt của cấu trúc

**Ví dụ**:
> Cô ấy mở di chúc, trên đó viết không phải tên cô ấy.
> Là của mẹ cô ấy.

**Hiệu quả**: ★★★★★
- Hook linh hồn của truyện ngắn
- Hook đảo ngược tốt khiến độc giả phải đọc lại phần trước
- Lưu ý: đảo ngược phải có lót, đảo ngược không lót là gian lận
- Lúc bóc truyện trọng tâm xem: lót mấy manh mối? Hướng đánh lạc là gì?

---

### 4. Hook bài tẩy (Hidden Card)

**Định nghĩa**: nhân vật chính giấu một lá bài chưa đánh ra, độc giả biết cô ấy có lá bài này, nhưng không biết khi nào đánh, đánh ra uy lực lớn bao nhiêu.

**Khi nào dùng**:
- Cuối đoạn lót, cho độc giả kỳ vọng
- Kỳ tích lực trước đảo ngược
- Phối với hook chênh lệch thông tin: độc giả biết bài tẩy, đối thủ không biết

**Ví dụ**:
> Mẹ chồng mắng suốt mười phút. Tôi một câu cũng không nói.
> Ghi âm điện thoại còn đang chạy.

**Hiệu quả**: ★★★★☆
- Kỳ vọng mạnh, độc giả chờ xem "lật bài"
- Hợp đề tài thế tình, hôn nhân, công sở
- Bài tẩy phải thực hiện, lúc thực hiện uy lực phải xứng với chờ đợi
- Lưu ý: bài tẩy không thể giấu quá lâu, trong truyện ngắn giấu tối đa 30% độ dài

---

### 5. Hook vả mặt (Face-slap)

**Định nghĩa**: nhân vật nào đó đang đắc ý/kiêu ngạo/chế nhạo nhân vật chính, nhưng độc giả biết hắn sắp bị vả mặt.

**Khi nào dùng**:
- Lúc cảm xúc cần kéo lên nhanh
- Giải toả cao trào sau đảo ngược
- Dùng cùng hook bài tẩy

**Ví dụ**:
> Cô ta cười đến ngửa trước ngửa sau.
> Tôi không nói gì. Chỉ lấy báo cáo xét nghiệm quan hệ cha con từ trong túi ra.

**Hiệu quả**: ★★★★★
- Sảng khoái cảm xúc cao nhất
- Trước vả mặt kiêu ngạo càng mạnh, lúc vả mặt càng sướng
- Hợp mọi đề tài
- Lưu ý: vả mặt phải dứt khoát gọn gàng, không đượckéo dài. Vả mặt một câu sướng hơn vả mặt một đoạn

---

### 6. Hook cái giá (Cost)

**Định nghĩa**: ám chỉ nhân vật chính sắp mất thứ gì đó, hoặc một lựa chọn phải trả giá thảm khốc. Độc giảthay nhân vật chính thắt lòng.

**Khi nào dùng**:
- Đoạn phát triển,tăng nặngđầu tư tình cảm
- Trước đảo ngược, để độc giả tưởng nhân vật chính sắp thua
- Lót cho kết BE

**Ví dụ**:
> Tôi biết tố cáo anh ta nghĩa là gì. Tố cáo anh ta, tôi cũng xong.
> Nhưng tôi vẫn nhấn nút gửi.

**Hiệu quả**: ★★★★☆
- Tạo đồng cảm hiệu quả nhất
- Độc giả sẽ nhập vào "nếu là tôi thì sao"
- Hợp đề tài thế tình, văn học u ám, hướng chữa lành
- Lưu ý: cái giá phải thật. Nếu nhân vật chính cuối cùng chẳng mất gì, hook cái giá sẽ mất hiệu lực

---

### 7. Hook kẻ yếu/trẻ con (Vulnerable)

**Định nghĩa**: đưa vào một kẻ yếu cần được bảo vệ (trẻ con, người già, bệnh nhân, động vật), ham muốn bảo vệ của độc giả bị khơi dậy.

**Khi nào dùng**:
- Mở đầu, nhanh dựng đồng cảm
- Giữa truyện, cho nhân vật chính một lý dobuộc phải hành động
- Tạo thêm căng thẳng tình cảm

**Ví dụ**:
> Con gáitrốn sau cửa, bịt tai.
> Con mới bốn tuổi, gì cũng không hiểu.
> Nhưng con biết không nên phát ra tiếng.

**Hiệu quả**: ★★★★☆
- Tốc độ đồng cảm nhanh nhất
- Một nhân vật yếu có thể khiếnphân lượng của toàn bộ xung đột tăng gấp đôi
- Hợp đề tài hôn nhân, thế tình, truy thê
- Lưu ý: kẻ yếu không thể chỉ là công cụ, phải có tuyến hành động riêng (dù rất nhỏ)

---

### Kết hợp hook

Truyện ngắn không dùng một hook, mà kết hợp dùng:

| Kết hợp | Hiệu quả | Đề tài hợp |
|------|------|----------|
| Chênh lệch thông tin + bài tẩy | Độc giả biết nhân vật chính đangnén đại chiêu | Báo thù, thế tình |
| Đếm ngược + cái giá | Thời gian cấp bách + chọn gì cũng lỗ | Huyền nghi, hôn nhân |
| Đảo ngược + vả mặt | Tàu lượn cảm xúc | Mọi truyện ngắn hướng sảng |
| Kẻ yếu + cái giá | Đồng cảm đầy | Truy thê, thế tình, văn học u ám |
| Bài tẩy + vả mặt | Sảng khoái mạnh nhất | Báo thù, nghịch tập |

### Checklist bóc truyện

Lúc bóc truyện với mỗi hook đánh giá:

1. Loại hook là gì?
2. Hook xuất hiện ở câu thứ mấy/chữ thứ mấy?
3. Cường độ hook (1-10)?
4. Hook có được thực hiện ở vị trí hợp lý không?
5. Khoảng cách giữa lót và thực hiện có hợp không?
6. Có hook nào chưa thực hiện (bỏ lửng)?

---

### Ví dụ hook thực chiến

1. **Sự thậtbất thường**: 'Anh ta chết một lần rồi, đây là lần thứ hai anh ta dự đám tang của chính mình.'
2. **Phản bội quan hệ**: 'Bạn thân nhất của cô ấy cưới chồng cũ của cô ấy, mà cô ấy là người cuối cùng biết.'
3. **Áp lực thời gian**: 'Còn hai tiếng nữa đến hạn, nhưng cô ấy vừa phát hiện số liệu trong phương án toàn là giả.'
4. **Bài tẩy giấu**: nhân vật chính biết gì đó, nhưng đối thủ/độc giả tạm thời không biết
5. **Sắp vả mặt**: phản diện đang đắc ý, độc giả biết nhân vật chính sắp lật kèo nhưng còn chưa lật bài
6. **Bẫythiện ý**: nhìn như quan tâm thật ra làm hại, kiểu thao túng "vì tốt cho ngươi"

---

### Các loại hook mới

### 8. Hook hồn bàng quan (Ghost POV)

**Định nghĩa**: nhân vật chính đã chết, lấy góc nhìn hồn phách lơ lửng giữa không trung kể chuyện. Toàn tri nhưng bất lực thay đổi.

**Ví dụ**:
> Hồn phách của tôitừ từ bay lên, nhìn gương mặttái mét của mẹ.
> Xin lỗi mẹ, con đã không thể đứng thẳng.

**Hiệu quả**: ★★★★★
- Câu đầu đã nói cho bạn nhân vật chính chết rồi — đây là bom thông tin mạnh nhất
- Tự nhiên tạo chênh lệch thông tin: hồn phách thấy đượcbộ mặt thật của mọi người
- Lúc bóc truyện chú ý: giới hạn kể chuyện của góc nhìn hồn phách (chỉ xem không động được) có bị tuân thủ nghiêm không

### 9. Hook vật thể dị thường (Anomalous Object)

**Định nghĩa**: một vật thể không nên xuất hiện ở đâygây ra toàn cục.

**Ví dụ**:
> Ngày trên bao cao su đột nhiên đổi，ngay cả mùi cũng thành mùi xoài mà trước đây tôi dị ứng.
> Tôi cười gật đầu.

**Hiệu quả**: ★★★★★
- Cảm giác nhập vai cực mạnh — ai cũng sẽ gặp dị thường thường ngày
- Bản thân vật thểmang lượng thông tin cực lớn (thương hiệu đổi = có người đến)
- Bốn chữ "cười gật đầu" tạo hồi hộp — nhân vật chính phát hiện gì? Cô ấy sẽ làm gì?

### 10. Hook giả vờ phục tùng (Feigned Compliance)

**Định nghĩa**: sau trọng sinh nhân vật chính chủ động đưa ra thứ kiếp trướcliều mạng bảo vệ. Độc giả biết nguyên nhân, đối thủ tưởng cô ấy điên rồi.

**Ví dụ**:
> "Ngươi đã muốn, thì đều cho ngươi."
> Dù sao ailấy được khoản di sản khổng lồ này người đóđại hoạ lâm đầu， đangsầu cáchgiữ mạng đây.

**Hiệu quả**: ★★★★☆
- Chênh lệch thông tin kép: đối thủ tưởng nhân vật chính ngốc rồi, độc giả biết cô ấy đang giăng bẫy
- Độc giả không biết cụ thể là bẫy gì — hồi hộp ba tầng

### 11. Hook phát hiện lạnh (Cold Discovery)

**Định nghĩa**: sau khi phát hiện dị thường phản ứng đầu không phải sụp đổ mà cực kỳ bình tĩnh. Bản thân bình tĩnh tạo hồi hộp.

**Ví dụ**:
> Trên móc khoá in "VIP Trung tâm ở cữ Duyệt An". Rõ ràng chúng tôi không có con.
> Tôi cười gật đầu. Hôm đóliền đến trung tâm ở cữghi lại đơn hẹn.
**Hiệu quả**: ★★★★★
- Càng bình tĩnh càng đáng sợ — độc giả mong chờ bùng nổ
- Tạo tương phản với mô thức truyền thống "khóc lóc → sụp đổ"

### Kết hợp hook mới

| Kết hợp | Hiệu quả | Ví dụ thật |
|------|------|----------|
| Vật thể dị thường + phát hiện lạnh | Hồi hộp thường ngày + nghiền ép IQ | 《Móc khoá》: móc khoá trung tâm ở cữ → cười điều tra |
| Hồn bàng quan + kẻ yếu | Bi kịch cực hạn + ham muốn bảo vệ | 《Phẫu thuật cột sống》: hồn xem bị ép → "chỉ muốn nghe một câu có đau không" |
| Giả vờ phục tùng + bài tẩy | Chênh lệch thông tin ba tầng + tích lực sảng khoái | 《Gió chiều gặp nắng mới》: cho di sản → thật ra là bẫy |
| Phản bội bậc thang + phát hiện lạnh | Tăng mức từng tầng + bình tĩnh toàn trình | 《Bao cao su》: ngoại tình → biển thủ → hại chết mẹ |

### Cảm xúc đối thoại tăng dần 5 cấp

Lúc viết mâu thuẫn xung đột, đối thoại càng bất lịch sự, cảm xúc càng mạnh:

1. **Trần thuật khách quan sự thật** — yếu nhất
2. **Trần thuật khách quan + đưa gợi ý** — lịch sự nhưng có lực
3. **Chỉ trích chủ quan** — bắt đầu có cảm giác xung đột
4. **Chỉ trích chủ quan + mệnh lệnh cưỡng chế** — cảm xúc mạnh
5. **Chỉ trích chủ quan + PUA nâng mình** — mạnh nhất

**Lời thoại mạnh nhất:** lấy cớ "vì tốt cho ngươi", câu nào cũng không rời quan tâm, nhưng câu nào cũng là chê bai, chỉ trích, ghét bỏ

---

### Hook tổn thương bất công

- Tổn thương bất công = bất công (nhân vật chính vô tội) + tổn thương (thể xác + tinh thần)
- Tổn thương tinh thần càng kéo được cảm xúc độc giả — đa số độc giả lúc chịu ấm ức thì nhiều
- "Không lo ít mà lo không đều": giảm tiền tháng ai cũng giảm (công bằng), nhưng chỉ dược liệu của nhân vật chính bị hạ một bậc (bất công)
- Tuỳ tiện chọn một loại viết tới nơi đều kéo được thù hận với phản diện

### Tầng cấp chất lượng người vây xem

Hiệu quả chấn kinh phụ thuộc vào tầng lớp của người vây xem:
1. Chất lượng thấp: quần chúng, tạp vụ, thực tập sinh
2. Chất lượng trung: kỹ thuật viên sành nghề, trợ thủ
3. Chất lượng cao: đại lão ngành, lãnh đạo

Người vây xem theo kinh nghiệm trước đây đối chiếu biểu hiện của nhân vật chính, biến đổi cảm xúc và khác biệt tâm thái càng vi tế, độc giả càng sướng.

### Phương pháp tiếp sức kỳ vọng

- Đảm bảo trong đầu độc giả có ba thứ tò mò: hai dài một ngắn
- Kỳ vọng dài thu về rồi thành bùng nổ ngắn, đồng thời kỳ vọng dài mới đã lót xong
- Trong truyện ngắn: một hồi hộp chính + một hồi hộp phụ, cuối cùng bùng nổ cùng lúc

---

## Sắp xếp hồi hộp

### Phân cấp cường độ
| Cấp | Tên | Hiệu quả | Dùng cho |
|------|------|------|------|
| 1 | Hồi hộp vi | Tò mò | Chương quá độ |
| 2 | Hồi hộp nhỏ | Muốn xem đoạn sau | Chương chính văn |
| 3 | Hồi hộp trung | Muốn xem chương sau | Chương then chốt |
| 4 | Hồi hộp lớn | Không buông sách được | Chương bùng nổ |
| 5 | Hồi hộp cực | Không ngủ được | Cao trào cuối tập |

### Chu kỳ hồi hộp đa tuyến
| Độ dài tuyến | Khoảng trải | Ví dụ |
|----------|------|------|
| Tuyến ngắn | 2-3 chương | Một trận đánh, một xung đột |
| Tuyến trung | 5-8 chương | Một đoạn biến đổi quan hệ, một câu đố nhỏ |
| Tuyến dài | Cả tập | Bí mật tối hậu, đảo ngược lớn tuyến chính |

### Thiết kế hook 3 đoạn (trong một chương)
1. **Gieo** (30% đầu): chôn hạt giống hook
2. **Nuôi** (50% giữa): tăng áp từng bước, để độc giả ý thức được không đúng
3. **Thu** (20% cuối): bùng nổ hoặc bùng nổ trì hoãn

---

## Điều cấm kỵ của hook

| Cấm kỵ | Giải thích |
|------|------|
| Hồi hộp giả | Mối đe dọa không tồn tại hoặc lập tức được gỡ bỏ, độc giả bị lừa một lần sẽ không tin nữa |
| Máy móc giáng thần | Cuối chương ném ra nguy cơ, đầu chương sau dùng trùng hợp giải quyết |
| Bỏ trống quá đà | Liên tục nhiều chương không hé lộ thông tin gì, độc giả mất kiên nhẫn |
| Hook rủi ro thấp | Dùng chuyện không quan trọng tạo hồi hộp ("ngày mai ăn gì nhỉ?") |
| Dùng liên tiếp cùng loại | Liên tục hơn 3 chương dùng cùng một loại hook |

---

## Cách viết phân tầng chấn kinh

Chấn kinh không phải một bước là xong, mà là tăng dần kiểu bậc thang. Đại thần viết 1500 chữ chấn kinh rất sướng, tiểu bạch chỉ viết được 150 chữ không sướng.

### Cấu trúc 3 tầng chấn kinh

1. **Chấn kinh điểm**: một người chấn kinh một cái (yếu nhất)
2. **Chấn kinh lưới**: chấn kinh mạng quan hệ, tức chiều rộng — không chỉ một người chấn kinh, người xung quanh đều có phản ứng
3. **Chấn kinh chiều sâu**: chấn kinh nhiều tầng chồng nhau — thành tựu 1 chấn kinh → thành tựu 2 chấn kinh → thành tựu 3 lợi hại hơn bùng nổ chấn kinh

### Cách thể hiện cụ thể chấn kinh tăng dần

Dùng biến đổi của đạo cụ cụ thể để thể hiện tăng dần mức độ chấn kinh:
- Thành tựu 1: đối phương bóp tay vịn ghế ra một vết nứt
- Thành tựu 2: ghế đầy vết nứt
- Thành tựu 3: đối phương bóp nát tay vịn ghế

### Nguyên tắc then chốt

> Lúc nên sướng mà không sướng tới nơi, cảm quan là rất độc. Vì cảm xúc trôi chảy, thậm chí có thể hy sinh tính hợp lý.

- Hiệu quả của bàn tay vàng với cốt truyện phải thể hiện rõ ràng rành mạch
- Đã lật bài tẩy, phản diện sẽ phải chịu đè ép tương ứng

---

## Luận 3 đời ngạnh cốt lõi

| Đời | Tên | Tác dụng | Ví dụ (Đấu Phá Thương Khung) |
|------|------|------|------------------|
| Đời 1 | Chủ đề | Cho mục tiêu vàý nghĩa | Thay đổi vận mệnh |
| Đời 2 | Cốt lõi đề tài | Sàng lọc độc giả,vạch rõ ranh giới, sinh cảm giác bầu không khí | Nâng cấp tu luyện |
| Đời 3 | Cảm xúc cốt lõi | Sàng lọc độc giả, nâng kịch tính | Chớ khinh thiếu niên nghèo |

### Nguyên tắc then chốt
- Cốt lõi một tiểu thuyết do mấy đời ngạnh cốt lõi dung hợp mà thành (thường 2-4 cái dung hợp)
- **Lệch cốt lõi đề tài = vứt bỏ chỗ dựa lớn nhất thu hút độc giả**, lượng đọc giảm thẳng
- Ngạnh cốt lõi = chuỗi cảm xúc cơ bản + cảm xúc cốt lõi cụ thể hơnlàm đầyđịnh hướng

### Bốn cách mở rộng ngạnh cốt lõi (lấy "hệ thống đến sớm" làm ví dụ)
1. Từ số lượng nhiệm vụquy hoạch kịch tính
2. Từ độ khó/số lượng phần thưởng nhiệm vụquy hoạch
3. Thông qua tầng cấp bậc kích hoạt kiểu ẩn
4. Thông qua phần thưởng hệ thống kích hoạt nhiệm vụ kịch tính mới (đối chiếu tương phản trước sau)

### Quy trình chuẩn công thức hoá giả heo ăn hổ
1. Đưa ra mục tiêu khó đạt + người qua đường có thực lực làm nổi bật độ khó
2. Nhân vật chính với thân phận tiểu trong suốt xuất hiện (khán giả biết thực lực thật) → sinh kỳ vọng
3. Nhân vật chính giả vờ tò mò xin thử → kéo cảm xúc
4. Người qua đường cười nhạo → cảm xúc bị dìm → mở rộngkhoảng trống cảm xúc
5. Nhân vật chính xin lỗi nhưng kiên trì → tiếp tục bị cười nhạo
6. Nhân vật chính đưa vật nặng cho người qua đường → người qua đườngđỡ không nổi → cảm xúc bắt đầu lên
7. Nhân vật chínhnhẹ nhàng hoàn thành → mọi người chấn kinh
8. Nhân vật chính khiêm tốn tỏ thái độ, giấu công giấudanh

---

## Bản chất kỳ vọng

Người đẹp, vật phẩm bản thân không phải kỳ vọng, cần lót trước để tạo. Lót vật nào đó là bảo khí,  nhưng thực lực/tài nguyên giai đoạn hiện tại của nhân vật chính chưa đủ không lấy được, thực lực đủ rồi hé lộ — kỳ vọng luôn ở đó.
Kỳ vọng tuyến tình cảm cần lót trước nam nữ chính có khả năng giao nhau, qua người qua đường đoán bên v.v. tạo kỳ vọng nội bộ. Không lót viết thẳng tiến triển tình cảm, độc giả tuyến nâng cấp sẽ thấykhó hiểu.

### Quy tắc ba búa kéo kỳ vọng
Viết xong một đoạn cao trào truyện thì lượng theo dõi ổn định, nhưng lúc bắt đầu truyện mới thì theo dõi/đặt mua sẽ giảm. Cần trước khi truyện cũ kết thúc đã vì truyện mới kéo lên tuyến kỳ vọng mới. Bản chất là "cách hai tuyến/cách nhiều tuyến" — để nhiều tuyến kỳ vọng chạy đan xen, đứt gãy sẽ không xảy ra.

### Cách thực hành duy trì kỳ vọng trăm vạn chữ
Dùng bút vẽ đường: một tuyến cốt truyện một đường ngang lớn, trên đường ngang quy hoạch nút cốt truyện (sự kiện cụ thể và kỳ vọng/thoả mãn). Tuyến kỳ vọng khác vẽ đường bên dưới, như trình diễn động quản lý nhiều tuyến. Nhân vật chính đến nơi mới tăng thông tin mới, lót phó bản tiếp theo, vạch trần phục bút cũ đồng thời kéo kỳ vọng dài mới.

---

### Tầng cấp chất lượng người vây xem

Hiệu quả chấn kinh phụ thuộc vào số lượng và chất lượng người vây xem:
1. **Chất lượng thấp**: quần chúng, tạp vụ, thực tập sinh, fan thuần
2. **Chất lượng trung**: quay phim sành nghề, thu âm, ánh sáng, phó đạo diễn,điều phối hiện trường
3. **Chất lượng cao**: cấp đạo diễn, nhà sản xuất, lãnh đạo nội bộ ngành

Để người vây xem theo kinh nghiệm trước đây đối chiếu biểu hiện của nhân vật chính, tạo đủ loại "chấn kinh". Càng thể hiện được vi tế biến đổi cảm xúc và tâm thái, độc giả càng sướng.

### Thiết kế tầng cấp chấn kinh
- Tầng lớp của đối tượng chấn kinh quyết định hiệu quả
- Chấn kinh của nhân vật phụ dùng một lầnlấy thoả mãn cảm xúc là chính
- "Phản ứng" của nhân vật phụ quan trọng có đất diễn sau phải đi kèmhé lộ thông tin, tiến triển quan hệ, biến đổi thái độ, mới kéo lên kỳ vọng được
- Mục đích cốt lõi của chấn kinh: qua phản ứng của nhân vật nổi tiếng/người địa vị cao một cách gián tiếp kéo lên kỳ vọng của độc giả
- Mỗi lần nhìn như cắt 99%, nhưng tổng còn lại 1% biến thành 100% mới, luôn treo độc giả
- Ví dụ: tuyến lộ áo choàng — nhân vật chính mỗi lần phá tan chất vấn đều suýt bị vạch trần một chút

### Kỳ vọng không được đứt
- Đứt kỳ vọng là đại kỵ số một khi viết truyện, kỳ vọng không còn độc giả sẽ không xem tiếp được
- Nhân vật chính nâng cấp xong nếu mất mục tiêu, mất cảm giác nguy cơ, kỳ vọng sẽ đứt
- Lúc đổi bản đồ dễ đứt kỳ vọng nhất, cần lót trước ở bản đồ mới tuyến kỳ vọng mới
- Lúc đổi bản đồ kỳ vọng nối dài ba liên kết: tuyến báo thù (mục tiêu chưa hoàn thành) + tuyến quan hệ ngày cũ (nhân vật cũ xuất hiện ở bản đồ mới) + chênh lệch thông tin

### Tuyến tình cảm làm tuyến kỳ vọng
- Tuyến tình cảm nam tần không phải là hợp tan dây dưa, mà là quan hệ tăng dần: xa lạ → quen biết → thân thuộc → ăn cơm riêng → nắm tay → ôm → hôn
- Cách dùng tốt nhất của tuyến tình cảm là treo độc giả: xây dựng nhân vật nữ độc giả thích, lấy việc có được cô ấy làm kỳ vọng
- Tuyến tình cảm có thể làm tuyến kỳ vọng dài, trong tiến triển tuyến nâng cấp xen kẽ tiến triển tình cảm, hai loại độc giả đều không ngán

### Vận dụng chênh lệch thông tin
- Độc giả biết nhân vật chính được vật phẩm mạnh nhưng nhân vật phụ không biết — chênh lệch thông tin tự nhiên sinh kỳ vọng
- Trên cơ sở chênh lệch thông tin, phản diện vừa vặn bị khắc chế — kỳ vọng chồng lên
- Người khác cầm trang bị tốt hơn đi lại thất bại — kỳ vọng lại nhân đôi
- Chênh lệch thông tin lúc cuối cùng được san bằng chính là điểm sảng bùng nổ
- Truyền đi chênh lệch thông tin bản thân không phải trọng điểm, trọng điểm là truyền đi mang lại đảo ngược cảm xúc trước sau của nhân vật mạng quan hệ
- Chấn kinh người quen sướng hơn chấn kinh người lạ, vì nhân vật cũ đã dựng quan hệ mang cảm xúc

### Thủ pháp đưa ống nhòm
- Nói trước với độc giả đại sự sắp xảy ra (như cửu long kéo quan tài đâm về phía nhân vật chính)
- Độc giả biết nhưng nhân vật chính không biết, tạo cảm giác căng thẳng và kỳ vọng
- Kỹ xảo "đếm ngược" của Thần Đông: biến một sự kiện thành đếm ngược không ngừng áp sát

### Bài tẩy đặt trước
- Thể hiện trước bài tẩy của nhân vật chính (thực lực/bàn tay vàng), rồi mới sắp xếp xung đột gây sự
- Độc giả biết nhân vật chính có bài tẩy nhưng phản diện không biết — kéo ra kỳ vọng tự nhiên
- Hai cặp thông tin kết hợp mới kéo ra kỳ vọng: bài tẩy + xung đột sắp xảy ra

### Phương pháp ngạnh cốt lõi dẫn động

Ngạnh cốt lõi = chuỗi cảm xúc hoàn chỉnh (kỳ vọng → thoả mãn)

**Ngạnh cốt lõi ba đời**:
- Đời một = chủ đề/tư tưởng trung tâm (như: thay đổi vận mệnh)
- Đời hai = cốt lõi đề tài (như: nâng cấp tu luyện)
- Đời ba = cảm xúc cốt lõi (như: chớ khinh thiếu niên nghèo)

**Thứ tự xây dựng cốt truyện**: điểm bán cốt lõi → mô-típ cảm xúc → cốt truyện cụ thể

---

## Công thức thiết kế xung đột phản diện

Phản diện là nhiên liệu của điểm sảng. Phản diện càng mạnh càng cuồng, nhân vật chính lúc phá cục càng sướng.

### Ba kiểu xung đột phản diện

| Kiểu | Cơ chế cốt lõi | Cảnh hợp |
|------|----------|----------|
| Kiểu chuyển lợi ích | Phản diện vì lợi ích bản thân cướp đoạt tài nguyên của nhân vật chính | Xung đột thường ngày, áp bức mở đầu |
| Kiểu chuyển giá | Phản diện đổ trừng phạt/tổn thất lên nhân vật chính | Tuyến âm mưu, tuyến dê tế thần |
| Kiểu giữ trật tự | Phản diện giữ trật tự hiện có, nhân vật chính đe doạ sự thống trị của hắn | Đối kháng tuyến chính, cục sinh tử |

### Cấu trúc năm yếu tố

Lúc thiết kế xung đột phản diện, điền đầy năm yếu tố này:

1. **Thiết lập phản diện**: địa vị, thực lực, nhãn tính cách
2. **Động cơ**: muốn có gì / muốn trốn gì (giá trị dương hoặc giá trị âm)
3. **Hành vi**: cướp đoạt, ép buộc, giăng bẫy, vu hãm — cụ thể đã làm gì
4. **Thái độ**: lẽ đương nhiên / vênh váo / vì tốt cho ngươi / đại nghĩa lẫm liệt (thái độ càng "chính đáng" càng tức)
5. **Mức độ nhân vật chính bị thương**: bảo vật gia truyền, 200 đồng cuối cùng, đạo cụ tốn bao công sức, có thể sẽ chết

> Then chốt: mức độ nhân vật chính bị thương càng cao, sức bùng nổ điểm sảng sau đó càng mạnh.

### Cấu trúc ba đoạn dục vọng - kỳ vọng - điểm sảng của phản diện

| Giai đoạn | Nội dung | Tỷ trọng |
|------|------|------|
| Lót | Dục vọng của phản diện cao ngất, sự tự tin khó hiểu | 20% |
| Kéo kỳ vọng | Hành động của phản diện điên cuồng, nhân vật chính bị động chịu đựng | **60%** |
| Điểm sảng | Nhân vật chính ra chiêu, một đòn tan vỡ | 20% |

> Giai đoạn kỳ vọng tỷ trọng lớn nhất. Phản diện càng điên cuồng, nhân vật chính càng bị động, cảm xúc độc giả tích tụ càng đầy.

---

## Cách thao túng kỳ vọng tâm lý độc giả

### Nhận thức cốt lõi

Mỗi dòng chữ bạn viết xuống đều đang thao túng kỳ vọng tâm lý độc giả. Bạn viết thế nào, độc giả sẽ nghĩ thế ấy. Nếu chưa tỉnh ra ý thức này, độc giả nghĩ thế nào bạn khống chế không được.

**Tâm pháp**: bạn nổ súng về hướng nào, độc giả sẽ vô thức nhìn về hướng đó. Nếu hắn không nhìn, tự hỏi có phải động tác nổ súng của mình không rõ ràng không.

### Ví dụ thao túng kỳ vọng tâm lý

Qua một ca suy luận giết người thể hiện cách thao túng độc giả:

```
Bước một — cấy sự kiện:
Bố bị không biết bị ai đâm chết.
→ Từ khoá "đâm" cấy vào đầu độc giả

Bước hai — cấy quan hệ nhân vật:
Em trai và bố quan hệ kém, và mẹ quan hệ rất tốt.
→ Độc giả bắt đầu dựng liên quan

Bước ba — tạo động cơ:
Đêm trước khi bố chết và mẹ cãi nhau to một trận, bị em trai thấy.
→ Kết hợp quan hệ nhân vật, độc giả càng nghi ngờ em trai

Bước bốn — tăng cường ám chỉ:
Em trai nhặt kéo lên, hung ác trừng bố.
→ "Kéo" + "đâm" = gần như mọi người đều cho là em trai
```

### Hai trạng thái của hồi hộp

| Số hướng kỳ vọng độc giả | Hiệu quả | Thao tác của bạn |
|---------------|------|----------|
| 0 hướng | Kẻ đố chữ, độc giả hoang mang | Đi giải thích thông tin |
| 1 hướng | Cảm giác nguy cơ/cảm giác căng thẳng/cảm giác kỳ vọng | Giữ, chuẩn bị đảo ngược |
| 2 hướng trở lên | Cảm giác hồi hộp — độc giả thấy đều có thể | Đây mới là hồi hộp thật |

### Thao tác đảo ngược

Trên cơ sở ví dụ trên thêm thông tin tạo đảo ngược:
- Thêm "trộm cầm dao lẻn vào" → sinh nghi phạm thứ hai → hồi hộp
- Thêm "tôi có chứng mộng du lại không uống thuốc" → nghi phạm thứ ba → hồi hộp nâng cấp

### Điểm thao tác

- Mỗi viết một dòng chữ đều phải hỏi: dòng chữ này dẫn độc giả về hướng nào?
- Kéo kỳ vọng, kéo cảm xúc, đảo ngược, quy luật nền tảng giống nhau: thao túng kỳ vọng tâm lý
- Nguồn gốc hỗn loạn truyền thông tin: tác giả chính mình cũng không ý thức được đang nổ súng về hướng nào

---

## Cách kéo đòn bẩy kỳ vọng

Sau khi thiết kế một điểm kỳ vọng, đừng thoả mãn trực tiếp, mà dùng **kéo cảm xúc** lặp đi lặp lại tăng đòn bẩy, mỗi lần kéo đều như gắn đòn bẩy nhân đôi kỳ vọng.

### Sáu bước thực hành kéo đòn bẩy

Lấy "nhân vật chính được bảo vật" làm ví dụ:

| Bước | Thao tác | Biến đổi kỳ vọng độc giả |
|------|------|-------------|
| 1 | Thể hiện bảo vật chức năng mạnh | Kỳ vọng dùng lên +1 |
| 2 | Nhân vật phụ thấy bảo vật cho là gân gà (chênh lệch thông tin) | Kỳ vọng vả mặt +1 |
| 3 | Phản diện xuất hiện, bảo vật vừa vặn khắc chế phản diện | Kỳ vọng xử phản diện +1 |
| 4 | Nhân vật phụ cầm trang bị mạnh hơn đi đánh phản diện, thất bại | Kỳ vọng vả mặt mọi người +1 |
| 5 | Nhân vật chính tối ưu hoá phương án có tính nhắm mục tiêu | Kỳ vọng tiếp tục +1 |
| 6 | Nhân vật chính lên sân, mọi người thấy "gân gà" không coi trọng | Kỳ vọng bùng nổ đến đỉnh |

> Cốt lõi: mỗi lần kéo đều sinh một lần **cảm xúc đi xuống** (lo lắng, chất vấn, coi thường), rồi lúc đi lên phóng thích càng mạnh.

### Nguyên tắc then chốt

- Xác định loại sảng cuối cùng muốn thể hiện: bảo vật khoe mẽ hay thực lực tổng thể nghiền ép? Lúc thiết kế xoay quanh một cốt lõi triển khai
- Phản ứng của các phe phải viết phân tầng: người qua đường, đồng hành, cao thủ, phản diện — mỗi tầng phản ứng khác nhau
- Được bảo vật xong đừng cách quá lâu mới dùng, trừ phi ở giữa lại kéo một tuyến lót làm sâu ấn tượng

---

## Cách phá cục phản phán đoán

Khi phản diện ứng đối dị thường mạnh, phá cục của nhân vật chính phải để độc giả thấy "đả kích hạ chiều".

### Tầng phá cục

| Tầng | Tên | Cách làm |
|------|------|------|
| 1 | Cứng đối cứng | Thực lực nghiền ép, đơn giản thô bạo |
| 2 | Phán đoán phản chế | Phản diện ra A, nhân vật chính sớm chuẩn bị B khắc chế A |
| 3 | Phản phán đoán | Phản diện chuẩn bị kỹ biện pháp nhắm vào A, nhân vật chính không chỉ tránh A, còn dùng A làm bẫy, dẫn phản diện rơi vào thủ đoạn phản chế đã đặt sẵn B |

> Điểm sảng cốt lõi: nhân vật chính ở tầng suy nghĩ, chuẩn bị và khả năng khống chế cao hơn. Mưu kế phải sớm hơn phản diện một tầng.

---

## Điểm viết cao trào

Trước khi viết cao trào phải làm rõ vấn đề:

1. **Nắm mâu thuẫn chính hiện tại**: tiểu cao trào ≠ mâu thuẫn chính cả sách, dễ quán tính tư duy chạy lệch. Phải làm rõ cao trào hiện tại giải quyết mâu thuẫn gì
2. **Kiểm tra lót trước văn có tới nơi không**: sắp xếp lại mọi lót trước văn, xác nhận cảm xúc độc giả đã tích đầy
3. **Đừng ở cao trào đưa vào thiết lập mới**: cao trào là thu lại và bùng nổ, không phải triển khai

---

## Nhịp sóng cảm xúc

Quy luật nhịp cảm xúc bóc ra từ video/phim ảnh:

### Bốn điều cốt lõi

1. **Cảm xúc phải không ngừng lên xuống**: cao thấp xen kẽ, đỉnh đáy rõ ràng, không được luôn phẳng
2. **Không ngừng cho kỳ vọng mới, không ngừng thoả mãn**: thoả mãn xong lập tức cho cái tiếp theo
3. **Lúc thoả mãn kỳ vọng đừng thoả mãn trực tiếp**: có thể đột nhiên gập ghềnh một cái, rồi mới thoả mãn thật
4. **Miêu tả bầu không khí theo cao trào cốt truyện đồng bộ lên xuống** (ví như nhạc nền)

### Thực hành sóng cảm xúc

```
↓ Hiện trạng sa sút (dựng đồng cảm)
↑ Cho hy vọng (kỳ vọng 1)
↓ Nhấn mạnh khó khăn/nguy cơ (kỳ vọng phóng to)
↑ Cho hy vọng mới (kỳ vọng 2)
↓ Tình hình xấu đi/bất ngờ (đáy cảm xúc)
↑ Tiến triển nhỏ bé (thoả mãn nhỏ + kỳ vọng mới)
↑↑ Đạt kỳ vọng (tiểu cao trào)
↓ Dừng đột ngột, cho khốn cảnh tiếp theo (cảm xúc lại kéo xuống)
↑ Cho kỳ vọng cao hơn (kỳ vọng 3)
↑↑↑ Hoàn thành mọi kỳ vọng (cao trào lớn bùng nổ)
```
> Then chốt: sau mỗi lần thoả mãn liền tiếp ngay đáy mới, không ngừng lặp lại nâng cấp, lúc bùng nổ cuối cùng cường độ cảm xúc = tổng mọi lần kéo trước đó.

---

## Ca nối kỳ vọng đổi bản đồ (bóc Quỷ Bí Chi Chủ)

Đổi bản đồ là lúc kỳ vọng dễ đứt gãy nhất. Cách xử lý của Quỷ Bí Chi Chủ:

### Ba liên kết nối tiếp (bóc cụ thể)

1. **Tuyến báo thù**: báo thù cho Đặng Ân → kéo dài qua bản đồ, thành mục tiêu đại cao trào của bản đồ mới
2. **Tuyến quan hệ ngày cũ**: Luân Nạp Đức gia nhập Hồng Thủ Sáo → nhân vật cũ xuất hiện ở bản đồ mới, quan hệ nối tiếp
3. **Chênh lệch thông tin**: người nhà/Luân Nạp Đức tưởng nhân vật chính đã chết → mong chờ phản ứng "hồi sinh hé lộ" (giống kỳ vọng truyện giả chết nữ tần)

### Vòng lặp lưu phái nâng cấp bản đồ mới

```
Sự kiện nhỏ → giải quyết → thu hoạch (tiền/tài liệu/công thức/đạo cụ)
→ Giao dịch qua hội Tarot/tụ hội → có thông tin nâng cấp
→ Nâng cấp bậc/lĩnh ngộ quy tắc → lặp lại
→ Cuối cùng thu về đại cao trào
```

> Lưu ý: sự kiện nhỏ quá nhiều, nhân vật ra sân quá nhiều dễ xuất hiện vấn đề vụn vặt, cần khống chế mật độ tuyến phụ.

---

## Cấu trúc đầy đủ tuyến sự nghiệp

Ba giai đoạn chuẩn của tuyến sự nghiệp nhân vật chính:

| Giai đoạn | Yếu tố |
|------|------|
| Lót | ① Khốn cảnh của nhân vật chính (cảm giác nhập vai thật) ② Nguy cơ của nhân vật phụ chính diện ③ Sự mạnh mẽ của nhân vật phản diện |
| Kéo kỳ vọng | ① Nhân vật chính dùng bàn tay vàng ② Nhân vật phụ chính diện thất bại ③ Nhân vật phản diện hoành hành |
| Điểm sảng | ① Nhân vật chính thắng ② Nhân vật phản diện: chất vấn→chấn kinh→hối hận ③ Nhân vật chính diện: chất vấn→chấn kinh→tâng bốc |

### Cách viết phản ứng nhân vật trong điểm sảng

- **Nhân vật phản diện** phải trải qua đầy đủ ba đoạn "chất vấn→chấn kinh→hối hận"
- **Nhân vật chính diện** trải qua ba đoạn "chất vấn→chấn kinh→tâng bốc"
- Phản ứng hai loại nhân vật đan xen viết ra, tạo **hiệu quả chấn kinh dạng lưới**

---

## Lỗi thường gặp về kỳ vọng

| Lỗi | Giải thích | Cách làm đúng |
|------|------|----------|
| Kỳ vọng chỉ sai mục tiêu | Lót "đánh lên trại nào đó" nhưng thực tế nên lót "nhân vật chính sinh tử giằng co" | Kỳ vọng nên nhắm **sinh tử nhân vật/lợi ích cốt lõi**, không phải mục tiêu trừu tượng |
| Phản diện lâu không xuất hiện | Đã cho mục tiêu nhưng phản diện giữa chừng biến mất hoàn toàn | Dùng mô thức "đánh nhỏ dẫn ra lớn", phản diện gây áp lực liên tục |
| Đứt tuyến kỳ vọng | Nhân vật chính nâng cấp xong mất mục tiêu, mất cảm giác nguy cơ | Nâng cấp xong lập tức đưa vào mối đe doạ mới, giữ kỳ vọng không đứt |
| Tăng trưởng thực lực bị phản diện bỏ qua | Nhân vật chính mạnh lên nhưng phản diện không hay biết, không xung đột | Phản diện lần lượt xung đột với nhân vật chính, lần lượt làm sâu mâu thuẫn, cuối cùng bị diệt |

---

## Cốt lõi đề tài và quản lý kỳ vọng độc giả

Độc giả đề tài khác nhau mang kỳ vọng cụ thể mà đến, làm trái những kỳ vọng này bằng chủ động đuổi độc giả.

### Bảng tra nhanh cốt lõi đề tài

| Đề tài | Kỳ vọng cốt lõi của độc giả | Việc tuyệt đối không được làm |
|------|-------------|---------------|
| Huyền nghi | Hồi hộp móc nối vòng vòng + bầu không khí kinh dị | Hậu kỳ xoá hồi hộp, kinh dị không lời giải |
| Truyện nâng cấp | Đánh quái nâng cấp + đối chiếu chấn kinh | Tuyến chính không rõ, nâng cấp lặp lại thuần tuý không mới |
| Tình yêu đô thị | Yêu đương trong đô thị | Xuyên đến thế giới huyền huyễn đánh quái nâng cấp |
| Truyện lịch sử | Thay đổi lịch sử, thay đổi vận mệnh nhân vật lịch sử | Hoàn toàn thoát ly bối cảnh lịch sử |
| Truyện game online | Tương tác người chơi, cơ chế game | Lâu dài đánh nhau qua lại với NPC |
| Đô thị cao võ | Đối chiếu siêu phàm + nâng cấp võ đạo | Đối tượng đối chiếu nhảy sang dị thế giới, mất cảm giác nhập vai |
| Lưu cực đạo | Áp bức giai cấp + phá cục bạo lực + nâng cao bạo lực | Giảm cảm giác áp bức hoặc cho nhân vật chính môi trường an nhàn |
| Đồng nhân | Va chạm với thế giới gốc, tương tác nhân vật gốc |thoát ly yếu tố nguyên tác viết thuần nguyên tác |

### Tín hiệu lệch cốt lõi đề tài

1. Khu bình luận độc giả xuất hiện "đổi vị rồi", "không phải mùi vị ban đầu"
2. Theo dõi/đang đọc ở nút nào đó giảm đột ngột (không phải suy giảm tự nhiên)
3. Cùng một sự kiện ở đề tài khác nhau phản ứng độc giả hoàn toàn khác nhau

### Thực hành mở rộng ngạnh cốt lõi (lấy "hệ thống đến sớm" làm ví dụ)

Khi kịch tính của ngạnh cốt lõi bắt đầu tiêu hao gần hết, cần mở rộng từ nhiều chiều:

| Chiều | Cách làm | Hiệu quả |
|------|------|------|
| Số lượng nhiệm vụ | Từ số lượng nhiệm vụ quy hoạch kịch tính | Biến đổi lượng sinh đối chiếu mới |
| Độ khó/số lượng phần thưởng | Từ thiết kế phần thưởng quy hoạch kịch tính | Biến đổi chất sinh kỳ vọng mới |
| Kích hoạt ẩn theo tầng cấp | Qua chênh lệch cấp bậc kích hoạt ẩn nhiệm vụ mới | Sinh kịch tính bất ngờ |
| Tương phản trước sau | Phần thưởng hệ thống kích hoạt nhiệm vụ kịch tính mới | Vòng chênh lệch mới |

> Then chốt: chỉ dùng hai điểm đầu sẽ khiến kịch tính tiêu hao nhanh chóng. Đối chiếu đồng chất lặp lại chỉ duy trì được hiệu quả ngắn hạn, phải qua điểm ba, bốn đưa vào biến đổi cấu trúc.

### Cách tự kiểm đứt gãy cảm xúc cốt lõi

Viết xong mỗi đoạn cốt truyện, dùng ba câu hỏi tự kiểm:

1. Cảm xúc cốt lõi của đoạn cốt truyện này là gì? (độc giả nên thấy gì)
2. Cảm xúc cốt lõi này có nhất quán với ngạnh cốt lõi cả sách không?
3. Nếu để độc giả chỉ xem đoạn này, họ có thấy được **cảm xúc tôi đang bán** không?

Nếu trong ba câu hỏi có bất kỳ câu nào trả lời không được, chứng tỏ đã lệch rồi.

---

## Thiết kế vòng lặp cốt truyện tuyến sự nghiệp

Cốt lõi của tuyến sự nghiệp nằm ở **biến đổi địa vị** và **biến đổi quan hệ người với người**, nâng cấp chỉ là thủ đoạn không phải mục đích.

### Vòng lặp lưu phái nâng cấp chuẩn

```
Sự kiện nhỏ → giải quyết → thu hoạch (tiền/tài liệu/công thức/đạo cụ/quan hệ)
→ Qua giao dịch/giao tiếp xã hội có thông tin nâng cấp
→ Nâng cấp → đối mặt thách thức tầng cao hơn → lặp lại
→ Cuối cùng thu về đại cao trào
```

### Điểm then chốt trong vòng lặp

- **Thu hoạch không thể chỉ có cấp bậc**: tiền, trang bị, nhân mạch, thông tin đều tính là thu hoạch
- **Nguồn thông tin nâng cấp đa dạng hoá**: giao dịch, giao tiếp xã hội, khám phá, phần thưởng nhiệm vụ đều được
- **Mỗi vòng lặp đưa vào ít nhất một biến số mới**: nhân vật mới, thế lực mới, quy tắc mới
- **Khống chế mật độ tuyến phụ**: sự kiện nhỏ quá nhiều, nhân vật ra sân quá nhiều dễ xuất hiện vấn đề vụn vặt

### Kho cốt truyện dùng được của đô thị cao võ

| Giai đoạn | Sự kiện dùng được |
|------|----------|
| Trường học | Lớp thiên tài, thi đấu ảo, lớp đánh thú triều, thi tháng, bá vương trường, thi liên trường, thi đại học |
| Võ quán | Được quán chủ coi trọng, truyền thừa võ học, sư huynh sư tỷ, giải đấu võ quán (thành phố→tỉnh→quốc gia) |
| Cục trị an | Đánh cướp, đánh tà ma, đánh phó bản, đánh boss trong thành |
| Cạnh tranh | Hợp đồng võ quán, học bổng trường, tuyển chọn võ đạo sảnh, quân bộ tuyển mộ, mạng thực chiến ảo, giải đấu ngôi sao |

> Mọi mục tiêu đều phải gắn với "tiền", lặp đi lặp lại gắn. Không tiềnnửa bước khó đi, có tiền đánh khắp thiên hạ — đây là cốt lõi cảm giác nhập vai của tiểu nhân vật.

---

## Nâng cấp hiệu quả chấn động: cách chấn kinh mạng quan hệ

Hiệu quả chấn kinh không chỉ phụ thuộc vào số lượng và chất lượng người vây xem, càng phụ thuộc vào **độ sâu quan hệ giữa người chấn kinh và nhân vật chính**.

### Tầng cấp chấn kinh mạng quan hệ

| Tầng | Đối tượng chấn kinh | Cường độ hiệu quả | Giá trị tiếp theo |
|------|----------|---------|---------|
| Người lạ chấn kinh | Người qua đường, quần chúng | Yếu | Thoả mãn cảm xúc thuần, không tiếp theo |
| Người quen chấn kinh | Nhân vật phụ từng tương tác | Trung | Có thể sinh biến đổi thái độ |
| Nhân vật quan trọng chấn kinh | Nhân vật có đất diễn tiếp theo | Mạnh | Đi kèm hé lộ thông tin, tiến triển quan hệ, kéo lên kỳ vọng |
| Người địa vị cao chấn kinh | Đại lão ngành, người địa vị cao | Mạnh nhất | Gián tiếp kéo lên kỳ vọng của độc giả với nhân vật chính |

### Nguyên lý nhân đôi chấn kinh người quen

- Chấn kinh người quen sướng hơn chấn kinh người lạ, vì nhân vật cũ đã dựng quan hệ mang cảm xúc
- Trọng điểm truyền chênh lệch thông tin không phải bản thân thông tin, mà là **đảo ngược cảm xúc trước sau của nhân vật mạng quan hệ** mà truyền thông tin mang lại
- Then chốt truyện đồng nhân dễ ra thành tích chính là ở đây — độc giả đã biết nhân vật nguyên tác, tầng cấp sảng khi chấn kinh nhân vật nguyên tác cao hơn

---

## Nối kỳ vọng đổi bản đồ nâng cao

Đổi bản đồ là lúc kỳ vọng dễ đứt gãy nhất, phải trước khi bản đồ cũ kết thúc đã vì bản đồ mới lót tuyến kỳ vọng.

### Ca đổi bản đồ thất bại

| Tác phẩm | Vấn đề | Hậu quả |
|------|------|------|
| 《Thập Phương Võ Thánh》 | Ở bản đồ gốc giết sạch mọi người rồi mới đổi bản đồ | Cảm xúc cốt lõi sụp đổ, đặt mua chém ngang lưng |
| 《Tuyệt Cảnh Hắc Dạ》 | Tông điệu từ sinh tồn cẩu đạo biến thành truyện đường bộ lưu vô hạn | Độc giả mất lượng lớn |

### Cách làm đúng khi đổi bản đồ

1. **Không cần thiết không đổi bản đồ**: địa vị của nhân vật chính ở bản đồ này đạt đỉnh, tiềm lực mạng quan hệcạn kiệt mới đổi
2. **Mang theo nhân vật phụ cốt lõi**: mang theo bạn đồng hành của nhân vật chính cùng đổi, giảm cảm giác cắt rời của bản đồ mới
3. **Đặt mục tiêu xuyên suốt cả sách**: như 《Già Thiên》 luôn viết Đại Đế
4. **Đặt nhân vật nối trên tiếp dưới**: nhân vật ở hai bản đồ đều có đất diễn
5. **Để lại hook**: làm động lực của nhân vật chính, đến khi tuyến cốt truyện mới mở ra mới giải quyết hook quá khứ
6. **Bản chất của nâng cấp không phải con sốto ra**： sảng đến từ nâng cao giai cấp và biến đổi quan hệ người với người

### Lưu phái nhân tình thế thái (một ngạnh cốt lõi có thể tham khảo)

Ngạnh cốt lõi: qua nhân tình thế thái để tiêu trừ đối kháng mạnh, đạt mục đích đi lên.

- Tài nguyên bàn tay vàng qua kinh doanh thế lực và mạng quan hệ người với người mà có (không phải giết giết giết)
- Biến đổi quan hệ của nhân vật chính với nhân vật khác là điểm xem chính
- Tông điệu: nhẹ nhàng thường ngày
- Tiền đề: phảilàm rõ đối tượng và điểm bán cốt lõi của mình

---

## Lý thuyết hệ thống "đứt kỳ vọng"

Đứt kỳ vọng là độc điểm lớn nhất của truyện mạng, hiểu công thức sinh điểm sảng mới phòng được:

**Công thức điểm sảng**: kéo cảm xúc → độc giả sinh kỳ vọng → cốt truyện phát triển thoả mãn kỳ vọng → đạt điểm sảng

Một khi chuỗi kỳ vọng sụp đổ toàn diện, độc giả sẽ bỏ sách.

### Sáu điều cấm kỵ đứt kỳ vọng lớn
| Cấm kỵ | Biểu hiện cụ thể | Hậu quả |
|------|----------|------|
| Chân không mục tiêu | Hoàn thành mục tiêu hiện tại rồi mới tìm mục tiêu mới | Cốt truyện đứt tầng, độc giả mất động lực đọc |
| Chân không nhân vật | Làm nhạt nhân vật cũ rồi mới đưa nhân vật mới | Mạng quan hệ đứt, đầu tư tình cảm về không |
| Chân không bản đồ | Đổi bản đồ không nối tiếp | Cảm giác cắt rời, bằng đổi một cuốn sách khác |
| Tuyến phụ tràn lan | Tuyến phụ không liên quan tuyến chính, dài dòng | Độc giả phân tán chú ý, kỳ vọng tuyến chính tan |
| Mục tiêu mơ hồ | Nhân vật chính không có mục tiêu rõ ràng và động lực đủ | Độc giả không biết đang theo đuổi cái gì |
| Cấp bậc không khác biệt | Trước sau nâng cấp chiến lực/quan hệ người với người không biến đổi | Nâng cấp mất ý nghĩa, kỳ vọng về không |

### Cách giải quyết tương ứng

**1. Nối mục tiêu**: trước khi hoàn thành mục tiêu hiện tại, cho trước manh mối phục bút của mục tiêu tiếp theo. Hoàn thành mục tiêu ngắn rồi, chuyển mục tiêu dài thành mục tiêu ngắn mới. Sau khi hoàn thành mục tiêu nhanh chóng cho đảo ngược gay gắt/bước ngoặt lớn/biến cố ngoài dự liệu, tạo kỳ vọng mới.

**2. Nối nhân vật**: trước khi làm nhạt nhân vật cũ thì đưa nhân vật mới vào trước. Đổi bản đồ để nhân vật cũ thú vị cùng nhân vật chính tiến vào thế giới mới. Trước khi đổi bản đồ để nhân vật bản đồ mới (hoặc truyền thuyết của hắn) tiếp xúc với nhân vật chính trước. Qua bàn tay vàng (nhóm chat, hội Tarot) ràng buộc mạng quan hệ người với người xuyên bản đồ.

**3. Tăng cường khác biệt hoá**: làm tốt kéo cảm xúc, viết tới nơi cảm xúc của nhân vật phụ các tầng. Làm đủ khác biệt hoá các cấp bậc/cảnh giới (phàm nhân thuần phế vật → Luyện Khí thả được pháp thuật → Trúc Cơ bay được → Kim Đan pháp thiên tượng địa). Làm đủ khác biệt hoá mạng quan hệ người với người ở các cấp bậc (thân bằng phàm nhân kiêu ngạo → Luyện Khí bình đẳng → Trúc Cơ sùng bái → Kim Đan hoá thành truyền thuyết).

**Then chốt**: kiên nhẫn của độc giả có hạn, một kỳ vọng có thể sinh ra động lực đọc là có hạn. Trì hoãn thoả mãn rồi cũng phải thoả mãn, tiêu dùng trước thì phải trả nợ.

---

## Cách kéo cảm xúc "lùi để tiến"

Kỹ pháp cốt lõi biến cốt truyện "nhân vật chính trả giá/hy sinh" từ điểm độc thành điểm sảng.

### Ba cách viết sai của việc nhân vật chính trả giá

| Sai | Biểu hiện | Phản ứng độc giả |
|------|------|----------|
| Không phân chính phụ | Để người được cứu biểu hiện cực thảm, đạo đức bắt cóc nhân vật chính | Chán ghét người được cứu, thấy cô ta tham không đáy |
| Không nhập vai được | Để nhân vật chính thương xuân buồn thu, miêu tả tâm lý đoạn dài | Thấy ẻo lả, đứt gãy tình cảm với nhân vật chính |
| Trốn tránh trả giá | Ám độ Trần Thương biến cốt truyện trả giá thành cốt truyện khoe mẽ | Độc giả thấy sự trả giá không được nhìn thẳng |

### Cốt lõi của cách lùi để tiến

**Nguyên lý then chốt**: tác giả muốn "nhân vật chính trả giá" thành điểm sảng, phải khiến độc giả sinh kỳ vọng với "nhân vật chính trả giá"; mà muốn độc giả sinh kỳ vọng này, phải có lót khoảng trống cảm xúc trước.

**Điểm thao tác**:
1. Không làm miêu tả tâm lý thừa — không kéo thảm trạng của tiểu sư muội, không để nhân vật chính thương xuân buồn thu
2. Chuyên chú lót khoảng trống cảm xúc — qua lời nhân vật phụ/cốt truyện thể hiện, để độc giả tự nhiên sinh kỳ vọng "nhân vật chính nên ra tay"
3. Hành vi trả giá bản thân gọn gàng có lực, không dây dưa
4. Hồi báo sau trả giá (phản ứng của người khác/thu hoạch của nhân vật chính) mới là điểm bùng nổ điểm sảng

**Hạn chế**: kiến nghị mạnh không dùng thủ pháp này ở mở đầu. Mở đầu quá quan trọng, dù không phải "sai lầm điểm độc" mà là "sai lầm cấu trúc/nhịp" cũng sẽ ảnh hưởng thành tích cực lớn.

**Tình huống cực đoan**: nếu muốn viết "tự hy sinh" kiểu trả giá chi phí cực lớn này, phải tốn công ở cấu trúc cấp hai, dùng rộng rãi "lùi để tiến" hợp lý hoá hy sinh lớn của nhân vật chính, phối hợp kỹ xảo "bi kịch sảng điểm hoá" và "bước ngoặt cốt truyện", mới miễn cưỡng biến điểm độc lớn thành cốt truyện chấp nhận được.

---

## Cách vận hành khác biệt hoá ngạnh cốt lõi

Cùng một ngạnh cốt lõi vận hành lặp lại sẽ khiến kịch tính tiêu hao hết, cần dùng cách khác biệt hoá giữ tươi mới.

### Ba cách vận hành khác biệt hoá

**1. Khác biệt hoá cách biểu đạt**: cùng một ngạnh cốt lõi vận hành ra cốt truyện không giống nhau. Tài liệu phản diện: lần một giết kẻ thù được oán niệm thưởng, lần hai lại giết kẻ thù được oán niệm, lần ba vẫn giết kẻ thù được oán niệm. Ca chính diện (đại thần Cổn Khai): lần một giết cả nhà kẻ thù được oán niệm thưởng; lần hai chủ động tham gia mâu thuẫn hai bên AB, giả làm thế lực A đến trước mặt B gây sự thu oán niệm, lại giả làm thế lực B đến trước mặt A giết đặc biệt giết thu oán niệm; lần ba bắt cóc toàn thành hắc đạo tống tiền, thu hoạch đầy thành oán niệm.

**2. Nhiều ngạnh cốt lõi luân phiên vận hành**: đặt nhiều ngạnh cốt lõi luân phiên dùng. Như Quỷ Bí Chi Chủ: hội Tarot Địch hoá là ngạnh cốt lõi A, siêu năng lực thám hiểm phá án là ngạnh cốt lõi B, đánh quái nâng cấp là ngạnh cốt lõi C, giải mã thế giới quan là ngạnh cốt lõi D — bốn loại ngạnh cốt lõi luân phiên vận hành, độc giả không đoán được cũng không phân biệt được.

**3. Cấu trúc cấp hai tạo hồi hộp**: thiết kế "bí mật" và "âm mưu" tầng thế giới quan, để cốt truyện không phải đồng bằng mà là mây che sương phủ, độc giả mãi mãi chỉ thấy rõ một đoạn đường nhỏ phía trước. Lưu ý quá cũng không được, không thể biến thành kẻ đố chữ và nhảy cấp thông tin.

### Mô hình "tháp cao" phòng đứt kỳ vọng

Ví tiểu thuyết như một toà tháp cao — nếu độc giả chỉ thấy cấu trúc bên ngoài, dễ bị sai lầm cấu trúc thu hút chú ý. Nhưng nếu dẫn độc giả đi vào bên trong tháp cao, chú ý của họ bị nội thất tinh mỹ cướp đi, bị cám dỗ lớn "tầng trên còn có gì" thu hút, không tự chủ đi kỳ vọng, đi leo.

Cốt lõi: tăng "kỳ vọng tuyến dài", chứ không phải mù quáng tăng "kỳ vọng ngắn hạn". Kỳ vọng tuyến dài bằng nhiệm vụ trong danh sách nhiệm vụ lúc nào cũng làm được, kỳ vọng ngắn hạn bằng hoạt động giới hạn thời gian — đồng thời tốt nhất chỉ có một.

---

## Cách thực hành kỳ vọng "hai dài một ngắn"

Đảm bảo trong đầu độc giả luôn có ba thứ tò mò: hai mục tiêu dài hạn + một mục tiêu ngắn hạn.

### Cách thao tác kiểu Đại Phụng (khuyên người mới học)

Chỉ dùng một cấu trúc cấp một, chỉ dùng một mục tiêu rõ ràng của nhân vật chính, lại kéo lên được nhiều tầng kỳ vọng, thoả mãn trực tiếp "hai dài một ngắn".

**Cách làm cốt lõi**:
1. Độ dài của cấu trúc cấp một đầu tiên mở đầu đừng quá ngắn — kéo dài cấu trúc cấp một mở đầu
2. Trong cấu trúc này, dùng mục tiêu rõ ràng của nhân vật chính đồng thời kéo lên: mục tiêu ngắn (giải quyết sự kiện hiện tại), mục tiêu dài 1 (hướng trưởng thành của nhân vật chính), mục tiêu dài 2 (hồi hộp lớn/bí mật thế giới quan)
3. Lúc cấu trúc cấp một đầu tiên kết thúc, kỳ vọng ngắn được thoả mãn, hai kỳ vọng dài tự nhiên thành động lực tiếp theo

### Nguyên tắc quản lý kỳ vọng dài ngắn

- Kỳ vọng dài = nhiệm vụ trong danh sách nhiệm vụ, lúc nào cũng làm được
- Kỳ vọng ngắn = hoạt động giới hạn thời gian, cùng lúc tốt nhất chỉ có một
- Dù đồng thời xuất hiện hai mục tiêu ngắn, nếu không liên quan nhau đều rơi vào hỗn loạn
- Sau khi dựng "hai dài một ngắn", cố tăng kỳ vọng tuyến dài, đừng mù quáng tăng kỳ vọng ngắn hạn
- Kỳ vọng dài thu về rồi thành bùng nổ ngắn, đồng thời kéo ra kỳ vọng dài mới

---

## Khoe mẽ nâng cao: cách phóng đại cấu trúc cấp hai

Phần cơ bản giải quyết "khoe thế nào, khoe với ai", phần nâng cao giải quyết "làm sao dùng khoe mẽ mở rộng sảng thêm".

### Ý tưởng cốt lõi

Trên cơ sở sự kiện khoe mẽ cơ bản, để hành vi của nhân vật chính với **mục đích hoặc lợi ích của nhiều phe người** sinh ảnh hưởng lớn thậm chí quyết định, thế là nhận được chú ý cực kỳ rộng rãi, nhất là chú ý của nhân vật kiểu "đại lão". Những người chú ý này sẽ vì thế đưa ra đủ loại phản ứng và sinh kỳ vọng cụ thể.

### Nguyên tắc mở rộng phân tầng khán giả

| Chiều | Nhiều > ít | Giải thích |
|------|---------|------|
| Loại nhân vật | Nhiều loại nhân vật > một loại nhân vật | Mỗi loại nhân vật khác nhau sinh phản ứng khác nhau, tăng sảng khác nhau |
| Số lượng nhân vật | Nhiều người > ít người | Lúc viết khoe mẽ chọn trường hợp được nhiều người ra sân |
| Tầng cấp nhân vật | Nhiều tầng > một tầng | Người qua đường, đồng hành, cao thủ, phản diện, mỗi tầng phản ứng khác nhau |
| Độ sâu quan hệ | Người quen > người lạ | Người quen chấn kinh sướng xa hơn người lạ chấn kinh |

### Cách tạo cảm giác chênh lệch

Cốt lõi sảng khi khoe mẽ thường nằm ở **có hay không cảm giác chênh lệch** — qua đối chiếu hai trạng thái/tâm thái khác nhau của nhân vật phụ, tăng cảm giácưu việt của độc giả.

- Có chênh lệch: nhân vật phụ cười nhạo trước chấn kinh sau >> nhân vật phụ chấn kinh trực tiếp
- Ở cùng một bản đồ càng lâu, thiết lập nhân vậtmở ra càng nhiều, sảng khi khoe mẽ càng cao (không gian chênh lệch tích luỹ càng lớn)

### Chuyển mô thức khoe mẽ liên tục

Lúc viết khoe mẽ liên tục, phải qua **mô thức khoe mẽ khác nhau** thể hiện mặt hơn người của nhân vật chính, độc giả mới không thấy lặp lại. Các mô thức có thể dung hợp dùng lẫn nhau gồm:

1. Nhiều người chấn kinh (A chấn kinh → B thân phận cao hơn cũng chấn kinh)
2. Giải thích chấn kinh (lời bình giải thích nguyên lý trước → nhân vật phụ lại chấn kinh)
3. Hình ảnh chấn kinh (miêu tả dị biến môi trường → nhân vật chấn động)
4. Đối chiếu chấn kinh (nhân vật phụ đối chiếu với mình → tự thấy xấu hổ)
5. Dấu hỏi chấn kinh (nhân vật phụ tự hỏi lòng làm không được → xác nhận khoảng cách)
6. Tương phản thiết lập chấn kinh (nhân vật phụ vốn coi thường nhân vật chính → đảo ngược chấn kinh)

---

## Cấu trúc ba lật bốn chấn

Một cách viết chấn kinh tăng dần, bản chất là "nâng cấp cảm xúc + gập ghềnh lên xuống".

### Cấu trúc

1. Nhân vật chính tuyên bố/thể hiện tầng một → mọi người phản ứng
2. Hé lộ tầng sâu hơn → phản ứng mọi người nâng cấp
3. Người địa vị cao can thiệp chất vấn → phản ứng mọi người lại nâng cấp
4. Hé lộ tối hậu + người có thẩm quyền bảo chứng → toàn trường chấn động

### Bóc ví dụ (nhân vật chính chọn trường)

```
Nhân vật chính nói đã có trường ưng ý → mọi người phản ứng
Nhân vật chính tuyên bố chọn Long Khoa Đại (không phải Thanh Bắc) → mọi người phản ứng
Giáo sư Thanh Bắc không hiểu truy hỏi → mọi người phản ứng!
Hiệu trưởng Long Khoa Đại đánh giá cao "quốc sĩ vô song" → mọi người phản ứng!
Chuyên gia rớt tuyển cúi đầu ủ rũ rời đi (dìm một cái)
```

### Nguyên tắc then chốt

- Mỗi lần lật đều phải có lượng thông tin mới, không phải lặp lại cùng thông tin
- Tầng cấp và phạm vi chấn kinh phải tăng dần: cá nhân → nhóm nhỏ → toàn trường → nhân vật có thẩm quyền
- Cuối cùng có thể dùng một "dìm một cái" kết thúc (nhân vật phụthất vọng rời đi), tránh cảm xúc quá đơn điệu

---

## Quy tắc năm từ nguy cơ mở đầu

Nguy cơ/sự kiện mở đầu phải đủ đơn giản, để độc giả liếc mắthiểu ngay. Tiêu chuẩn kiểm nghiệm: **dùng năm từtrở xuống**nói rõ với độc giả mục tiêu sự kiện là gì, đạt trạng thái gì, lại không cần giải thích thêm, độc giảlà có thể hoàn toàn hiểu thậm chí sinh cảm xúc.

### Tiêu chuẩnphán định

- Đạt: năm từnói rõ được "đây là nguy cơ gì" + "tại sao có nguy cơ này" + "không giải quyết sẽ thế nào"
- Không đạt: cần giải thích thêm lượng lớn độc giả mới hiểu →tất nhiên mang gánh nặng thông tin

### Tại sao quan trọng

Chú ý của độc giả có hạn, không thích suy nghĩ, vô cùng nóng nảy. Mở đầu nếu sự kiện phức tạp đến mức cần giải thích, độc giả chạy thẳng. Sự kiện thường ngày quen thuộc tự nhiên có cảm giác nhập vai (bị đuổi việc, bị lừa, bị bắt nạt), không cần giải thích là có thể sinh cảm xúc.

---

## Cách tạo điểm sảng "muốn trái trước phải"

### Công thức cốt lõi

Kỳ vọng của độc giả càng mạnh, lúc thoả mãn sảng càng mạnh. Cách tạo kỳ vọng không phải cho thẳng, mà là "muốn trái trước phải" — cho trước kỳ vọng hướng ngược lại.

### Ba mô thức thao tác

|Mô thức | Cách làm | Hiệu quả |
|------|------|------|
| Nhẫn nhịn rồi bùng nổ | Nhân vật chính có vốn lật kèo nhưng ngắn hạn bất động, độc giả biết nhưng nhân vật phụ không biết | Chênh lệch thông tin kéo đầy kỳ vọng |
| Lấy chính hợp lấy kỳ thắng | Thoả mãn trước kỳ vọng cơ bản của độc giả (chính), rồi cho bất ngờ thêm (kỳ) | Thoả mãn kép |
| Độc giả biết trước | Nói trước với độc giả đại sự sắp xảy ra, độc giả biết nhưng nhân vật chính không biết | Cảm giác căng thẳng + cảm giác kỳ vọng |

### Cách độc giả biết trước (đưa ống nhòm)

Để độc giả thấy trước nguy hiểm/đại sựáp sát (như cửu long kéo quan tài đâm về phía nhân vật chính), độc giả biết nhưng nhân vật chính không biết. Thần Đông hay dùng kỹ xảo "đếm ngược" — biến sự kiện thành đếm ngược không ngừngáp sát.

### Cách bài tẩy đặt trước

Thể hiện trước bài tẩy của nhân vật chính (thực lực/bàn tay vàng), rồi mới sắp xếp xung đột. Độc giả biết nhân vật chính có bài tẩy nhưng phản diện không biết — kéo ra kỳ vọng tự nhiên. Hai cặp thông tin kết hợp mới kéo ra kỳ vọng: **bài tẩy + xung đột sắp xảy ra**.

---

## Cách thiết kế điểm lo (tạo lo âu)

Để độc giả sinh "lo âu", qua giải quyết lo âu tạo sảng.
### Các bước thiết kế

1. Đặt một "điểm lo" hợp lý (như thiếu tiền, bị truy sát, thời gian không đủ)
2. Sau nâng cấp thể hiện nhiều mặt biến đổi của nâng cấp so với trước (chênh lệch đãi ngộ, khác biệt tài nguyên)
3. Trước nâng cấp lót thảm trạng lúc chưa nâng cấp, dựng cơ sở đối chiếu
4. Giữ điểm lo lâu dài — không phải giải quyết một lần là biến mất

### Nguyên tắc then chốt

- Điểm lo phải khiến độc giả thấy "hợp lý", như "thiếu tiền" kiểu đa số người đồng cảm được
- Thiết lập thế giới quan, cảnh giới, thiết lập nhân vật nhân vật phụ, đều phải suy nghĩ làm sao qua những thiết lập này khiến độc giả thấy lo âu
- Bản thân nâng cấp không phải điểm sảng cốt lõi nhất, **nâng cấp khác người thường mới phải**

---

## Cách thể hiện cụ thể chấn kinh tăng dần

Dùng biến đổi cụ thể của đạo cụ để thể hiện chấn kinh tăng dần, chứ không dùng miêu tả trừu tượng.

| Giai đoạn | Biểu hiện đạo cụ | Cường độ chấn kinh |
|------|----------|----------|
| Thành tựu 1 | Đối phương bóp tay vịn ghế ra một vết nứt | Nhẹ |
| Thành tựu 2 | Ghế đầy vết nứt | Trung |
| Thành tựu 3 | Đối phương bóp nát tay vịn ghế | Mạnh |

### Điểm then chốt

- Biến đổi đạo cụ có lực hơn "hắn chấn kinh rồi" một trăm lần
- Mỗi lần tăng dần đều phải có biến đổi thị giác/vật lý rõ ràng
- Dùng được cho mọi cảnh chấn kinh: cốc vỡ, bút rơi, trà đổ, sắc mặt biến đổi

---

## Cách đếm ngược đưa ống nhòm

Kỹ xảo Thần Đông dùng ở mở đầu 《Già Thiên》: biến "ống nhòm" thành "đếm ngược".

**Cách thao tác**:
1. Chương một cho một đại sự kiện (như cửu long kéo quan tài) miêu tả đẳng cấp cao
2. Sau đó cách 1-2 chươngthả một đoạn tiến triển nhỏ, như đếm ngược giảm dần
3. Theo đếm ngược đến gần, kỳ vọng độc giả không ngừng leo lên
4. Cuối cùngbùng nổ triệt để

**Ví dụ**: chương một xuất hiện sự kiện thần bí → cuối chương hai cập nhật tiến triển → đầu chương bốn cập nhật → chương sáubùng nổ

**Cảnh dùng**: mở đầu đưa vào đại sự kiện, lót trước bước ngoặt cốt truyện lớn

---

## Cách đòn bẩy kéo cảm xúc

Mỗi bước kéo đều như gắn đòn bẩy phóng to kỳ vọng:

| Bước | Thao tác | Biến đổi kỳ vọng độc giả |
|------|------|------------|
| 1 | Thể hiện vật phẩm/năng lực mạnh | Kỳ vọng dùng +1 |
| 2 | Nhân vật phụ vì chênh lệch thông tin cho là gân gà | Chênh lệch thông tin sinh, kỳ vọng vả mặt +1 |
| 3 | Thể hiện phản diện, vừa vặn bị vật phẩm này khắc chế | Kỳ vọng nhân vật chính ra tay +1 |
| 4 | Nhân vật phụ mạnh hơn cầm trang bị tốt hơn đánh phản diện thất bại | Kỳ vọng vả mặt mọi người +1 |
| 5 | Mọi người không coi trọng nhân vật chính lên sân | Kỳ vọng tiếp tục +1 |
| 6 | Nhân vật chínhnhẹ nhànggiây sát | Kỳ vọng thoả mãn |
| 7 | Mọi người chấn kinh + nhân vật phụmã hậu pháo phân tích | Kỳ vọng thoả mãn |
| 8 | Thu hoạch vòng mới | Thoả mãn + kỳ vọng mới sinh |

**Bản chất**: mỗi lần kéo đềuchồng lên kỳ vọng, lúc thoả mãn cuối cùng sảng nhân đôi.

---

## Kênh đôi tạo kỳ vọng

### Tạo trong

Qua tương tác nhân vật và lót trong cốt truyện để độc giả sinh kỳ vọng:
- Lótgián tiếp: người qua đường đoán nam nữ chính có thể xảy ra gì
- Độc giả hậu cung tự độngtự não bổ,  nhưng độc giả tuyến nâng cấp cần lót thêm
- Lóttới nơi rồi, độc giả hai tuyến đềuchăm sóc được được

### Tạo ngoài

Dùng nhận thức có sẵn của độc giả tạo kỳ vọng:
- Thiết lập nhân vật kiểu cụ thể (sát phạt quả đoán/vững vàng) độc giảvừa nhìn là đi theo
- Mô-típ quen thuộcgợi lên kỳ vọng với sảng cụ thể

### Quy tắc hai dài một ngắn

Đảm bảo mỗi chương trong đầu độc giả có ba thứ tò mò:
- Hai mục tiêu dài hạn (thân phận thần bí lão tổ, ước hẹn ba năm từ hôn v.v.)
- Một mục tiêu ngắn hạn (vả mặt/khoe mẽ hiện tại)
- Kỳ vọng dài thoả mãn xong lập tức kéo kỳ vọng dài mới
- Đừng vượt quá 4-5 tuyến, nhiều quáđiều khiển không được

---

## Công thức đặt tên sách

Tên sách là hook đầu tiên. Khống chế trong 15 chữ, 3 giây hiểu ngay điểm bán cốt lõi, từ khoákhớp chính xác độc giả mục tiêu.

### Loại công thức cốt lõi

| Loại | Công thức | Ví dụ |
|------|------|------|
| Tương phản thân phận | Thân phận yếu + hành vi mạnh | 《Ngày ra tù, tài phiệt nghìn tỷ xếp hàng đón tôi về nhà》 |
| Tương phản hành vi | Nhiệm vụ thường + thao tácvô lý | 《Cho ngươi đi lính cai nghiện game, ngươi thành tựu đế quốc hacker》 |
| Tương phản kết quả | Giai đoạn đầu bị ngược + giai đoạn sau vả mặt | 《Sau ly hôn, chồng cũ quỳ cầu tôiquay đầu》 |
| Đối chiếu số | Số cực đoan + kết quảtrái thường thức | 《1 giây lỗ sạch 5 triệu, tôinhờ bày sạp năm thu 300 triệu》 |
| Hồi hộp cảm xúc | Điểm đau + đảo ngược điểm sảng | 《Ăn cơm tất niên được một nửa, nhóm gia đìnhbật ra đếm ngược tử vong của tôi》 |
| Hệ thống bàn tay vàng | Thân phận thường + hệ thốngvô lý | 《Mỗi ngày điểm danh 1㎡, 90 ngày sau tôi mua cả toà nhà》 |
| Hỏi ngược nghi vấn | Trần thuật sự thật + hỏi ngược tạo xung đột | 《Nộp thuế trăm tỷ, ngươi gọi đây là doanh nghiệp siêu nhỏ?》 |
| Tiền tố chấn kinh | "Điên rồi à/vô lý" + sự kiện đảo ngược | 《Điên rồi à! Ngươi nói với ta đây là chương trình chạy trốn?》 |
| Thiết lập cực đoan | Thân phận cực đoan + năng lực cực đoan | 《Ta một người đọc sách, võ công sao thiên hạ vô địch rồi》 |
| Lệch góc nhìn | Phe ta biết thông tin vs mọi người không biết thông tin | 《Cả tông môn đều tưởng ta là phế vật, đến khi tiên tôn quỳ đất gọi sư tôn》 |
| Tương phản phật hệ | Môi trường áp lực cao + nhân vật chínhnằm ườn | 《Tận thế giáng lâm, ta chọn về nhà trồng trọt》 |
| Hạ chiều thân phận | Nghề nghiệp chiều cao + cảnh tầng thấp | 《Giáo sư vật lý hạt nhân, bị chủ nhiệm lớp của con gái gọi đi phạt đứng》 |
| Bị độngăn vạ | Ta chỉ muốn xx +không biết làm sao các ngươi cứ muốntự tìm chết | 《Ta chỉ muốn yên tĩnh trồng trọt, cứ bắt ta làm minh chủ võ lâm》 |

### Tránh hố
- Đừng học đại thần đặt tên sách cao thâm văn nghệ
- Đừng thuầntiêu đề đảng — hàng không đúngbản bỏ sách ngay
- Từ khoá hot (trọng sinh/hệ thống/chiến thần/ở rể/từ hôn/vả mặt) tiện nền tảngđề xuất

---

## Nguyên lý cốt lõi hút lượng và giữ chân

**Hai yếu tố lớn hút lượng**:
- **Bù đắp**： bù đắp thiếu sót hiện thực, độc giả qua nhập vai nhân vật chính có được thứ chưa từng có (an toàn, quyền lực, tình yêu)
- **Đường tắt**： nỗ lực nhỏ nhất lợi ích lớn nhất, dùng giá nhỏ nhất thoả mãnbù đắp

**Hai động cơ lớn giữ chân**:
- **Cảm xúc**: nhập vai nhanh + đắm chìm nhanh, tàu lượn cảm xúc phóng thích dopamine
- **Đói**: dùng chênh lệch thông tin cấy dấu hỏi trong đầu độc giả — não người trời sinh ghét trạng thái "chưa hoàn thành"

**Mở đầu 300-500 chữ phải đạt**:
- Tình cảnh hiện tại (không có gì hoặc vật trân quý sắp bị cướp đi)
- Nguồn nguy hiểm (nguy cơhình ảnh hoá, đồng cảm được)
- Hy vọng phá cục (liếc mắt là biết thứcó thể thay đổi tình cảnh)

**Xung đột dữ dội nhất của màn một là "cái chết"**: chết thể xác, chết xã hội, chết tinh thần. Tuyệt đại đa số truyện mạng thành công xung đột màn một đều liên quan trực tiếp với "cái chết".

---

## Mô hình nghiện Hook (lý thuyết bốn hook)

Áp dụng mô hình nghiện Hook (kích hoạt→hành động→thưởng→đầu tư), mỗi yếu tố sau lưng có một hook, câu ra một nguyên tội nhân tính:

| Yếu tố | Hook | Nguyên tội | Truyện mạngtương ứng |
|------|------|------|----------|
| Kích hoạt | Dục vọng | Vọng tưởng | Điểmcắt vào — nhắc độc giả hắn muốn gì, không phải ngươicứng nhét |
| Hành động | Đơn giản | Lười biếng | Tiêu chuẩnhành văn — mở đầu rườm rà = ngưỡng quá cao, đơn giản mới lặp lại nghiện được |
| Thưởng | Vận may | Tham lam | Kỳ vọng thu hoạch — thưởng đoán đượcnhạt nhẽo,  ngẫu nhiên không chắc mới khiến người mong "lần sau" |
| Đầu tư | Của cải | Si mê | Phát triển cao trào — trang bị cực phẩm/xếp hạng/tiểu đệ tông môn = chi phí chìm khóbỏ |

**Nguyên lý ngẫu nhiên của thưởng**:
- Cắn hạt dưa nghiện vì hạt dưa có to có nhỏ — hạt tiếp theo tốt xấu không chắc nhưng sẽ mong
- Cảm giác thu hoạch không chỉ phải có, còn phải ngoài dự liệu: dự kiến thu hoạch kinh nghiệm và tiền, kết quả trộm về một quả trứng rồng
- Truyện xây thành/truyệntrồng trọt mãi không suy: của cải do nâng cấp lãnh địa không ngừng mang lại = sức hút cốt lõi nhất

**Lệch cộng hưởng của khâu kích hoạt**:
- Điểm nóngthời sự có kiếm tiền được không phụ thuộc có nắm được cảm xúc độc giả thật muốn xem không
- Rõ ràng trong tin tức làcăm ghét chuyện nào đó, ngươilại viết quan điểm ngược → độc giả không đồng tình → lệch điểm cộng hưởng

---

## Lý thuyết còi chómánh lới

**Mánh lới = còi chó = từ khoá nhóm cụ thể nhận diện nhanh**:
- Hiệu ứng còi chó: chỉ nhóm cụ thể get được tín hiệu — như mắt Sharingan Naruto/mắt ác quỷ hải tặc/Cthulhu/quy tắckỳ đàm
- Tác dụng củamánh lới là sàng nhanh độc giả mục tiêu — liếc tên sách là biết "đây là món của ta"
- Khôngmánh lới = không tín hiệu = độc giả lướt qua, nội dung tốt nữa cũng vô dụng
- Mánh lới phảikhớp chính xác nhóm độc giả mục tiêu — dùng sai mánh lới còn tệ hơn không có mánh lới

**Bản chất ba chương vàng = định điệu = quản lý kỳ vọng = đáp ứng kỳ vọng**:
- Ba chương vàng không phải viết tốt ba chương đầu là xong, bản chất là truyền cho độc giả "sách nàycó thể cho ngươi gì"
- Định điệu = nói rõ với độc giả loại điểm sảng và nhịp của sách này
- Quản lý kỳ vọng = kỳ vọng ngươi dựng phải ở chương sau đáp ứng
- Không đáp ứng kỳ vọng =thất tín → độc giả bỏ sách → còn tệ hơn không có kỳ vọng

---

## Ba tầng định điệu và khống chế thông tin mở đầu

**Ba tầng định điệu**:
- Tầng một: bầu không khí cảm xúc (khổ đại thù sâu/nhẹ nhàng vui vẻ/hoa tiền nguyệthạ）
- Tầng hai: hướng đi truyện (trồng trọt/tranh bá/mạo hiểm/yêu đương)
- Tầng ba: khuynh hướng giá trị (nam tần/nữ tần/vịtrạch/vịthổ）
- Để độc giả thấy khí chất của truyện, xác nhận có phải truyện mình mong không

**Ba chương vàng = đáp ứng kỳ vọng**:
- Tên sách và giới thiệu đãcô đọng cao độ xung đột, hồi hộp, điểm bán
- Tác dụng cốt lõi của ba chương vàng là nhanh đáp ứng kỳ vọng của độc giảbấm vào sách này
- Đừng giấumánh lới ở rất sau — độc giả đợi không được
- Mở đầuxoay quanh tên sách và giới thiệu xây xung đột, mở đầuđiểm đề
- Công thức: tình cảnh bất an + địa vịgấp cần nâng + hack đầy hy vọng + tương lai tươi đẹpcó thể đượctriển vọng

**Nguyên tắc khống chế thông tin mở đầu**:
- Mở đầu cần sạch gọn,kiềm chế ham muốn biểu đạt
- Qua động tác đơn giản (mở mắt, tự nói, quan sát)tập trung tình cảnh hiện tại
- Dao cạo Occam: như không cần thiết chớ tăng thực thể — thiết lập cần lập tức dùng
---

## Năm yếu tố mở đầu và chọn điểm cắt vào

**Năm yếu tố mở đầu (chương một phảigiải thích)**:
- Ai → thông tin nhân vật chính
- Ở đâu → bối cảnh thế giới
- Có gì → bàn tay vàng
- Vì sao → mâu thuẫn xung đột
- Muốn làm gì → hướng tuyến chính

**Nămthiết luật mở đầu**:
1. **Đơn giản**: kỵlời dẫn mây mù, đánh đố
2. **Không lệch**: cốt truyện mở đầu phải hợp điểm bán cốt lõi tuyến chính
3. **Phải nhanh**: tốc độ cắt vào cốt truyện phải nhanh, phần nguyên nhân viết lướt
4. **Phải sướng**: trong năm chương không có chấn kinh là thất bại
5. **Không phẳng**: không có xung đột mâu thuẫn là thất bại

**Cách chọn điểm cắt vào (từ 0 đến e)**:

Một cốt truyện = nguyên nhân (không điểm sảng) →trải qua (sóng gió) → kết quả (khoe mẽ) → tiếp theo (thu hoạch/hook)

| Cách cắt vào | Tuyến truyện | Hiệu quả |
|----------|--------|------|
| 0 = xuyên việt | Viết xuôi toàn bộ | Chậm nhất,lề mề nhất |
| a = chuẩn bị dự thi | Viết xuôi | Chậm, nguyên nhân chiếm quá nhiềuđộ dài |
| b = hiện trường tuyển chọn sắp lên sân khấu | Kể ngược/nguyên nhân đặt sau | Khuyên dùng, cách viết đúng thường gặp nhất |
| c = trên sân khấu sắpmở hát | Gần kết quả hơn | Nhanh hơn, khuyên dùng mạnh |
| d = đang hát khán giả chấn kinh | Cao trào trực tiếp | Quá gấp |
| e = sau thi được thưởng | Bỏ lỡquá trình | Không khuyên |

**Điểm cắt vào tốt nhất = b hoặc c** — giữ không gian triển khai đầy đủ của quá trình và kết quả.

**Nghệ thuật viết lược**:
- Phần nguyên nhân phải gọn gàng súc tích, tuyệt đối không được kể lể chi li
- Một khi triển khai một khâu nhỏthì buộc phải luôn triển khai,  dừng không được
- Mẫu tham khảo: mở mắt xuyên việt → hai ba câu hồi tưởng → tình cảnh hiện tại (nguy cơ) → "ting" một tiếng hệ thống → chuẩn bị khoe mẽ
- Cực hạn của viết lược: chương một chỉ dùng hai ba trăm chữ nhảy qua mọi nguyên nhân

**Hiểu rộng mâu thuẫn xung đột**:
- Không nhất định cần kẻ địch và phản diện, bản chất là "xung đột giữa tình hình hiện thực và nhu cầu kỳ vọng"
- Kiểu nguy cơ khốn cảnh: bị vây giết/bị sỉ nhục/không tiền trả sính lễ
- Kiểu xung đột ẩn hình: nhân vật chính muốn khoe mẽ nhưng khoe mẽ không được → cần bàn tay vàng nên mới có "ting"
- Kiểu xung đột vĩ mô: quân công quốc gia lạc hậugấp cầnđuổi kịp

---

## Dựng sân khấu — độ lớn và độ cao

**Sân khấu = nơi cho nhân vật chính biểu diễn + dưới sân có khán giả**. Chênh lệch sảng đến từ hai chiều: và của sân khấu.

**Độ lớn sân khấu (số lượng khán giả)**:
- Solo lên đại sư (không khán giả) vs phòng livestream mấy vạn khán giả (có khán giả) vs Tổ Chim tám vạn hiện trường + mấy triệu khán giả mạng (toàn dân)
- Cách mở rộng: tăng nhân vật → tăng ngườimục kích và chứng kiến
- Đặt bạn cùng phòng/bạn học/đồng nghiệp xuất phát từ cùng vạch xuất phát → nhân vật chính một bước lên trời tạo "bức tường dày đángbuồn"

**Độ cao sân khấu (cường độ đối thủ)**:
- Giảithăng hạngđại sư thường vsvánvương giả vs chung kết giải S đối mặtđội tuyển số một lịch sử
- Cách nâng cao: tăng cốt truyện → lót sự mạnh của đối thủ, sứ mệnhgánh vác,  nhiều tầnggửi gắm
- Chồng lên ý nghĩa lót nhiều tuyến: đồng đội bị loạigiao phó + cha mẹ không coi trọng đến hiện trường + kỳ vọng của khán giả cả nước

**Nguyên tắc cốt lõi**:
- Lúc nhân vật chính có thể khoe mẽ → khán giả kéo được bao nhiêu kéo bấy nhiêu → ý nghĩagắn thêm được bao nhiêugắn thêm bấy nhiêu
- Nhưng tiền đề là không sụp →đường biên tính hợp lý không đượcvứt
- Kỵ nhất trận đấu nước lọc: ngủ dậy → đếnnhà thi đấu → thắng → về

---

## Cách mục tiêu cảnhdẫn động và kỹ xảo nhịp nhanh chậm

**Mục tiêu cảnh = cốt lõi cảm giác căng thẳng**:
- Một câu trần thuật mục tiêu nhân vật chính ở cảnh này muốn đạt → đặt sớm trong cảnh
- Độc giả truyện mạngđọc lướt mười dòng một mắt → dùng nhiều cách nhấn mạnh mục tiêu nhân vật chính → để nóin vào đầu độc giả
- Ví dụ: "Ta phải tìm được em gái, cứu cô ấy một mạng" / "Ta muốn giết quái vật, không thì liều chết một trận"

**Bốn yếu tố tăng cảm giác căng thẳng**:
1. **Động cơ**:Nói rõ nhân vật chính vì sao cần đạt mục tiêu, thất bại sẽ có hậu quả nghiêm trọng
2. **Giới hạn thời gian**: đặt cho nhân vật chính giới hạn thời gian thực hiện mục tiêu → cảm giác căng thẳng mạnh hơn
3. **Trở ngại**: trở ngạicản trở nhân vật chính thực hiện mục tiêu → phải nghiêm trọng hơn dự tính → đừng hé lộ chi tiết quá sớm
4. **Nguy hiểm tăng dần**: tưởng thoát hiểm → hung thủkhông ngờ giấu trong xe (ngoài dự liệu)

**Kỹ xảo viết nhịp nhanh**:
- Lúc động tác xảy ra nhanh dùng → đừng miêu tả quá nhiều → ít dùng tính từ phó từ → đoạn ngắn câu ngắn từ ngắn
- Câu ngắn truyền cảm giác thở gấp và tim đập nhanh → xoá mọi từ thừa → thậm chí dùng câu không hoàn chỉnh
- Ví dụ: "Bỗng, cô ấy cười" / "Đôi tay lạnh băng, nắm lấy cổ hắn"

**Kỹ xảo viết nhịp chậm**:
- Lúc nhân vật chính chờ đợi/không còn cách nào dùng → đoạn trung dài → độ dài câu không đều →huy động nhiều giác quan
- Miêu tả tiếng ồn nền = kỹ xảo nhịp chậm hiệu quả nhất → trong bóng tối truyền đến tiếng mài dao / hành lang yên tĩnh cửa bịđẩy ra từ từ
- Qualàm chậm nhịp tăng cảm giác huyền nghi → để độc giả lo âu hơn cả bản thân nhân vật chính

**Tâm lý học độc giả của nhịp nhanh chậm**:
- Chú ý của con ngườilấy 15-20 phútlàm chu kỳ → một chương truyện mạngvừa vặn trong phạm vi này
- Kỳ thư giãn sau căng thẳng liên tục không được vượt quá hai chương → vượt hai chương độc giảsẽ thấy "nước"
- Chức năng của kỳ thư giãn: tiêu hoá căng thẳng lần trước → lót căng thẳng lần sau → tương tác nhân vậtlàm sâu (không phải thật sự thả lỏng)

---

## Xây hồi hộp và chất kết dính của xung đột

**Công thức cốt lõi**: xung đột (khả năng đối mặt cái chết) + cốt truyện (biện pháp cụ thể tránh cái chết) + hồi hộp (sức căng chưa phóng thích) = trải nghiệm thoả mãn về tình cảm

**Ba loại "cái chết"**:
- Chết thể xác: kinh dị, mạo hiểm,đại đào sát v.v.
- Chết sự nghiệp: đấu đá công sở, cạnh tranh, khởi nghiệp v.v.
- Chết tâm lý: tình yêu, sụp đổ tín ngưỡng
- Xác định một loại chết chính xuyên suốt toàn cục, loại phụthúc đẩy cốt truyện nhưng khônglấn át chủ

**Chất kết dính của xung đột**:
- Chất kết dính = thiết lập khiến hai phe đối lập không thểdễ dàngthoát khỏi nhau
- Độc giả thấy nhân vật có thể lúc nào cũngthoát khỏi khốn cảnh → cảm giác căng thẳng của xung độttan thành mây khói
- Bốn chất kết dính thường gặp: lý do giết người (nâng cấp bậc chỉ một ngườilên đỉnh),  chức trách công việc (thám tử/Trừ Yêu Ty), trách nhiệm đạo đức (người thân gặp hiểm), nơi chốn thực thể (phó bản/quán cà phê)

**Kỹ xảo hồi hộp**:
- Bất ngờ vs hồi hộp: bất ngờ là bom dưới bànđột nhiên nổ; hồi hộp là khán giả nghe tiếng tích tắc của bom hẹn giờ nhưng không biết khi nào nổ
- Hồi hộp mạnh hơn bất ngờ xa → để độc giả chủ động tham gia → chứ không phải bị động phản ứng
- Treo vách đá =đứt chương: cuối mỗi chương để lại nguy hiểm chưa giải quyết
- Khoá thời gian: đặt sự kiện phải xảy ra trongkỳ hạn → nén thời gian → tăng cảm giác căng thẳng

---

## Hệ thống logic kép điểm xem điểm sảng

**Điểm xem = điểm treo kỳ vọng độc giả, điểm sảng = điểm thoả mãn kỳ vọng độc giả**. Nhất nhấttương ứng → trước lót bao nhiêu điểm sảngthì có bấy nhiêu.

**Công thức cốt lõi điểm sảng**:
- Điểm sảng = điểm xung đột của hai logic
- **Logic đại chúng** = nhận thức thường → với người thường đối thủ không thể chiến thắng → sợ hãi/tuyệt vọng
- **Logic nhân vật chính** = góc nhìn nhân vật chính →vừa vặn ngứa tay/nhẹmiêu tả hời hợt
- Chênh lệch hai logic càng lớn → điểm xem càng đủ → điểm sảng càng sướng

**Tam giác sắt ba yếu tố điểm sảng**: nhân vật chính + đối thủ + ăn dưa

- Ăn dưa tuyệt đối không phảinão tàn hô 6 → trong ba yếu tố trọng điểm thật ra ở ăn dưa
- Tác dụng ăn dưa ①: kéo cao kỳ vọng → dùng bàn tánđem hành vi đối thủ thổi rađẳng cấp → để điểm sảng sướng hơn
- Tác dụng ăn dưa ②: hoàn thành khoe mẽ vả mặt → phản ứng chấn kinh của ăn dưa bản thân là điểm sảng → đồng thời hoàn thànhthăng hoa điểm sảng
- Ăn dưa = nhân vật không lúc nào không nhắc độc giả logic đại chúng → tìm ra mỗi điểm tương phảnvà tiến hành phản ứng

**Tinh tuý truyện mạng = dựng tương phản + viết phản ứng**:
- Tương phản = điểm xem → độc giả mong không phải bản thân tương phản → mà là phản ứng sau tương phản → cái này mới là điểm sảng
- Phản ứng do ăn dưa cung cấp nhiều nhất → nên góc nhìn ăn dưa quan trọng nhất
- Phần điểm xemdốc hết sức lót → phần điểm sảngphải thu → cho ngọt nhưng không thoả mãn hoàn toàn → độc giả giữdục cầu bất mãn

---

## Cách viết lưu phái bất ngờ

**Kỹ pháp cốt lõi truyền thông mới**: hạ thấp giá trị kỳ vọng trước, rồikéo cao đẳng cấp giải quyết, tạo đảo ngược bất ngờ.

**Ba bước**:
1. Hạ thấp giá trị kỳ vọng trước: để độc giả thấy "giải quyết không được rồi"
2. Đường cùng lại thông: đột nhiên dùng cách đẳng cấp cao hơn giải quyết
3. Đánh một cái tát rồi cho táo ngọt: hạ thấp kỳ vọng = đánh tát, giải quyết đẳng cấp cao = táo ngọt

**Chênh lệch thông tin + lưu phái bất ngờ kết hợp**:
- Nhân viên bán hàng nhận điện thoại của sếp nói cóquý khách chí tôn → nhầm phản diện thành quý khách → sỉ nhục nhân vật chính → lộ thân phận →sợ chết
- Chênh lệch thông tin cực hạn = kỳ vọng mạnh → cảm giác đètăng vọt → lúc lộ thân phận càng sướng

**Độ đè — đè tự nhiên vs đè xã hội**:
- Đè tự nhiên: nhân vật chính rấttrâu bò nhưng người khác không biết (hướng Feilu, độc giả trẻ cảm giác nhập vai sâu, năng lực chịu đè yếu)
- Đè xã hội/đè đời sống: đến từ bất công của đời sống (hướng truyền thông mới, độc giả 30+ cầntăng lớn cường độ đè mới có cảm giác)
- Đè càngmạnh,  vả mặt càng sướng — nhưng phải phân rõ là "đè kiểu phẫn nộ" hay "đè kiểu coi thường", không được lẫn

---

## Công thức động lực

**Công thức cốt lõi**: sinhnhu cầu → cho hy vọng → nỗ lực giải quyết → được như ý

**Sinh nhu cầu (tạo khó chịu)**:
- Địa vị thấp/khốn cảnh/mối đe doạngay trước mắt/thứ chưa từng có
- Độc giả thấy vu cáo/bất công/ỷ mạnh hiếp yếu → trong lòng trời sinh nảy ra ý nghĩ "không nên như thế"
- Xung động "không nên như thế" này = động lực căn bản nhất
- Đề tài tốt cóđặc chấtgợi lên tiếc nuối, khao khát thay đổi của con người, không đơn là "thú vị"

**Cho hy vọng (bản chất của bàn tay vàng)**:
- Bản chất của bàn tay vàng =đặc chất/năng lực khó có được trong hiện thực
- Độc giả thấy khốn cảnh xong cần thấy hy vọng thay đổi → không có hy vọng → đau khổ của khốn cảnh khiến độc giả xem không nổi
- Thể hiện rõ bàn tay vàng = cho độc giả động lựcsẵn lòng xem tiếp

**Nỗ lực giải quyết và nhịp**:
- Không thể để độc giả quá nhanh được như ý → tâm khíbình ổn rồi động lực xem tiếplà hết
- Cách một "dần tốt lên": khốn cảnhchia thành nhiều tầng → tầng tầng tăng dần
- Cách hai "khốn cảnh mới": giải quyết một khốn cảnh → gặp khốn cảnh mới → tầng khốn cảnh không ngừng nâng
- Nhịp tốt: tầng khốn cảnh tầng tầng nâng cao, độ khó và độ phức tạptừng bước nâng, loại khônghếtgiống nhau

**Kỹ xảo "treo chưa quyết"**:
- Trạng thái "chưa giải quyết" liên tục = chú ý và kỳ vọng liên tục
- Đặt chênh lệch thông tin → độc giả biết nhưng nhân vật không biết / nhân vật biết nhưng độc giả không biết

---

## Chênh lệch thông tin ba tầng

| Tầng | Trạng thái thông tin | Hiệu quả |
|------|----------|------|
| Tầng một | Độc giả biết nhưng nhân vật chính không biết |Thay nhân vật chính toát mồ hôi (như phản diện đặt bẫy nhân vật chính đang đi vào) |
| Tầng hai | Nhân vật chính biết nhưng nhân vật khác không biết | Mong thời khắc hé lộ (như nhân vật chính đãnhìn thấu kế hoạch của phản diện) |
| Tầng ba | Hai bên đều không biết nhưng độc giả đoán có thể có nguy hiểm | Cảm giác hồi hộp (như phía trước nhìn bình yên thật raẩn giấu sát cơ) |
- Lúc chênh lệch thông tin được san bằng độc giả thở phào dài = điểm sảng phóng thích
- Kỹ pháp bóc hành tây: giới thiệu cấy hồi hộp cốt lõi → đầu mỗi chương cấy dấu hỏi nhỏ → cuối mỗi chương kẹt thông tin then chốt

---

## Kỳ vọng không gián đoạn và kỹ thuật chuỗi hook

**Nguyên lý cốt lõi: kỳ vọng > có được**:
- Lúc nhân vật chính sắp có được thứ gì đó nhưng chưa có được → kỳ vọng độc giả cao nhất → theo dõi tăng vùn vụt
- Nhân vật chính có được rồi → chương đó theo dõi cao → sau đó theo dõi rớt vùn vụt → vì kỳ vọng không còn
- Kết luận: trước khi nhân vật chính có được → phải gắn thêm một hook khác

**Cách thực hành chuỗi hook**:
- Nhân vật chính sắp làm minh chủ võ lâm → trước khi lên ngôi đột nhiên biết kẻ thù giết cha là ai → lên minh chủ xong có kỳ vọng mới = giết kẻ thù
- Trên đường giết kẻ thù quen cô gái → giết xong kẻ thù có kỳ vọng mới = chinh phục cô gái
- Kỳ vọng lớn (tuyến chính) + kỳ vọng nhỏ (tuyến phụ) xen kẽ qua lại → một cái móc một cái vòng lặp vô hạn
- Kiến nghị bất kể lúc nào cũng giữ hai tuyến kỳ vọng trở lên

**Thiết kế hook tuyến dài**:
- Trồng một cái cây → chín rồi có thể thế nào → cần thời gian → trồng xong nhân vật chính làm việc khác bình thường → rất lâu sau thu hoạch
- Trước khi mỗi mục tiêu nhỏ hoàn thành → tô đậm hoàn thành xong có thể thế nào → những người kia sẽ thế nào → được đặc quyền gì → rồi sắp xếp kỳ vọng mới

---

## Mẫu nhịp chương khoe mẽ vả mặt

**Công thức điểm sảng**: điểm sảng = (thiết lập nhân vật + lót) + va chạm đan xen của nhân vật

**Nguyên tắc vô địch nhỏ đặt trước**:
- Trước khi cảnh khoe mẽ bắt đầu, phải chuẩn bị xong đạo cụ/nhân vật/thực lực những thứ dùng để vả mặt
- Không có vô địch nhỏ đặt trước → độc giả thay nhân vật chính lo lắng sợ hãi → ngươi viết mỉa mai độc giả thấy là ngược chủ
- Có vô địch nhỏ đặt trước → độc giả nhẹ nhàng xem nhân vật chính khoe mẽ → mỉa mai chỉ là lót

**Lót quan trọng hơn vả mặt**:
- Khoe mẽ KTV tu tiên đô thị: cao trào vả mặt = nghìn chữ, lót = mấy vạn chữ
- Lót viết tốt rồi → đứng đó một lời không nói đều có thể khoe mẽ vả mặt

**Mẫu nhịp chương**:

| Giai đoạn | Kỳ công chúng (vòng 5 chương) | Kỳ VIP |
|------|------------------|-------|
| Thiết lập nhân vật | 1 chương | 1-2 chương |
| Lót | 2 chương | 5 chương |
| Vả mặt | 1 chương | 1-2 chương |
| Dọn dẹp hậu quả | 1 chương | 1 chương |

- Từ mẫu nhịp thấy: lót mới là phần cốt lõi nhất, đáng miêu tả chi tiết nhất của cả khoe mẽ vả mặt
- Vả mặt chỉ là kết thúc nghìn chữ

**Quản lý đẳng cấp khoe mẽ**:
- Thần hào không thể khoe mẽ với mèo chó linh tinh → đẳng cấp không tương xứng = ngượng
- Người qua đường A chấn kinh không gọi là sướng → độc giả muốn là người có phân lượng chấn kinh
- Tầng cấp của đối tượng vả mặt quyết định tầng cấp của sảng

---

## Năm mô thức thay thế bàn tay vàng

Xuất phát từ logic chung của truyện (sự kiện khích lệ→dục vọng→mục tiêu→hành động→trở ngại→vượt qua→thưởng), bàn tay vàng thay thế khâu nào:

| Mô thức | Khâu thay thế | Hiệu quả | Ví dụ |
|------|----------|------|------|
| Lưu phái hệ thống truyền thống | Dựng mục tiêu | Hệ thống phát hành nhiệm vụ→nhân vật chính hoàn thành→hệ thống thưởng | 《Đại Vương Tha Mạng》 |
| Hệ thống đổi vỏ | Vượt qua khó khăn | Hệ thống giúp nhân vật chính giải quyết vấn đề nhưng phải chịu giá/hạn chế | 《Cẩu Đạo Trung Nhân》 |
| Nhảy tài nguyên | Khâu chuẩn bị | Hệ thống cung cấp tài nguyên nhảy qua chuẩn bị, tua nhanh đến trở ngại và vượt qua | 《Khai Cục Tài Khoản Bị Trộm》 |
| Xuyên tương lai | Sự kiện khích lệ | Xuyên đến tương lai cung cấp động cơ thay đổi hiện tại | 《Thiên Niên Hồi Tố》 |
| Thay thế thưởng | Thu hoạch thưởng | Hệ thống cung cấp thưởng→nhân vật chính làm việc giá trị phổ thế công nhận nhưng không có hồi báo thế tục | Lưu Địch hoá/lưu cẩu đạo |

**Tại sao bàn tay vàng đóng gói thành hệ thống**:
- Bàn tay vàng kiểu đạo cụ truyền thống (như bình xanh nhỏ) chỉ đạt được nhu cầu một tầng
- Bàn tay vàng kiểu hệ thống có thể thoả mãn nhu cầu ngạnh cốt lõi phức tạp hơn
- Cốt lõi không phải hình thức "hệ thống", mà là **thiết kế hạn chế** của bàn tay vàng

**Hạn chế bàn tay vàng và cấu trúc truyện**:
- Bàn tay vàng có hạn chế → truyện mới có cấu trúc
- Không hạn chế = kể thẳng tuột = không phải truyện
- Hạn chế tốt = biến quá trình trở ngại thành một tuyến truyện khác (như phá án, tuyến hậu cung)

---

## Cách viết phó bản đấu trí và công thức giải mã

**Cách năm bước phó bản đấu trí**:
1. **Định quy tắc**: đặt quy tắc phó bản trước, bản thân quy tắc tạo hạn chế và áp lực
2. **Khám phá quy tắc**: trong khám phá thể hiện tính cách đồng đội, đồng thời làm nổi bật sức quan sát và lực quyết sách của nhân vật chính
3. **Tách tuyến trong ngoài**: đem đấu đá nội bộ người chơi và giải đố phó bản chia hai phần, giải quyết nội đấu trước rồi giải quyết phó bản
4. **Dùng lựa chọn phân phe**: qua lựa chọn khác nhau (có xuống tàu điện ngầm không/có ôm đoàn không/có khám phá không) sàng lọc địch bạn
5. **Giải mã kết thúc**: ghép đáp án đầy đủ → nghiệm chứng → đại chiến boss

**Công thức giải mã**:
Quy định quy tắc → khám phá quy tắc được thông tin và nghi hoặc → trao đổi tình hình được thông tin thêm → suy đoán thông tin được chân tướng gần đáp án → giải nghi hoặc ghép đáp án đầy đủ → nghiệm chứng quy tắc đại chiến

**Cách viết nhân vật chính làm nổi bật trí lực**:
- Trong thảo luận phát biểu ba ý kiến then chốt, mỗi câu đều thể hiện một chiều
- Giả vờ làm người chơi ăn thịt câu cá — tạo chênh lệch thông tin, để độc giả biết nhân vật chính đang giăng bẫy

**Công thức viết thường ngày**:
Thường ngày = thiết lập nhân vật + thường ngày có mục đích + thông tin
- Mỗi đoạn thường ngày phảithúc đẩy mục đích nào đó (kiểm tra năng lực bổ sung/lót manh mối/giải thích thiết lập)
- Thiết lập nhân vật là cốt lõi của thường ngày

---

## Bốn yếu tố xu hướng Feilu

**Xu hướng một: kỳ vọng (cốt lõi nhất)**
- Tính thực dụng sướng đơn thuần giảm rồi → kéo chậm kỳ vọng truyện mới là xu hướng cốt lõi
- Cảnh giác: giả vờ thần bí ≠ kỳ vọng → đáng giải thích không giải thích → độc giả xem không hiểu
- Ngạnh kỳ vọng hay dùng: loại lộ/ loại ngả bài/ loại di cô lịch sử

**Xu hướng hai: tuyến chính rõ ràng**
- Mấy năm trước Feilu không tuyến chính chỉ dựa vào sướng cũng ra được thành tích → giờ xác suất thấp đi N lần
- Tuyến chính rõ ràng + đủ hấp dẫn → dù sưu tầm không cao → lên kệ rồivững bước nâng

**Xu hướng ba: cảm giác thu hoạch**
- Cảm giác thu hoạch kiểu cuồng bạo = một trong cácchủ lưu Feilu → điểm danh/lựa chọn/tự động nâng cấp/treo máy
- Loại thu hoạch: thu hoạch vật phẩm + thực lực mạnh lên + thu hoạch tình cảm
- Nhân vật chính dùng hay không dùng thưởng không nhất định → nhưng để độc giả thấy cảm giác thu hoạch đầy ắp

**Xu hướng bốn: cảm giác xung đột**
- Mở đầu Feilu nổi bật hai điểm: kỳ vọng hoặc cảm giác xung đột
- Từ tên sách đã nổi bật xung đột → "dỡ XX của ta rồi còn muốn ta XX"
- Cảm giác xung đột → tạo kỳ vọng → độc giả mong thời khắc xung đột bùng nổ

---

