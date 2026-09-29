"""Lớp công cụ xử lý JSON"""
import json
import re
from typing import Any, Dict, List, Union
from app.logger import get_logger, safe_preview
from app.utils.reasoning_text import strip_think_tags

try:
    import json5
    HAS_JSON5 = True
except ImportError:
    HAS_JSON5 = False

logger = get_logger(__name__)


# Ánh xạ dấu ngoặc kép/ngoặc đơn tiếng Trung sang ASCII
_QUOTE_MAP = {
    '\u201c': '"',  # " → "
    '\u201d': '"',  # " → "
    '\u2018': "'",  # ' → '
    '\u2019': "'",  # ' → '
    '\u300e': '"',  # 『 → "
    '\u300f': '"',  # 』 → "
    '\u300c': '"',  # 「 → "
    '\u300d': '"',  # 」 → "
}


def _is_content_quote(text: str, pos: int) -> bool:
    """
    Kiểm tra '"' trong giá trị chuỗi có phải là dấu ngoặc kép nội dung (cần escape)
    
    chứ không phải dấu ngoặc kép kết thúc JSON.
    ',' (phân tách giá trị) / '}' (đóng object) / ']' (đóng mảng)
    
    Nếu sau '"' không khớp các mẫu này, đó là dấu ngoặc kép nội dung do AI viết, cần escape.
    """
    j = pos + 1
    
    # Bỏ qua dấu cách và tab
    while j < len(text) and text[j] in ' \t':
        j += 1
    
    if j >= len(text):
        return False  # Cuối văn bản, coi như dấu ngoặc kép kết thúc
    
    ch = text[j]
    
    # } hoặc ] → dấu ngoặc kép kết thúc
    if ch in ('}', ']'):
        return False
    
    # Xuống dòng → kiểm tra đầu dòng tiếp theo để phán đoán
    if ch == '\n' or ch == '\r':
        k = j + (2 if (ch == '\r' and j + 1 < len(text) and text[j + 1] == '\n') else 1)
        while k < len(text) and text[k] in ' \t':
            k += 1
        if k >= len(text):
            return False
        # Dòng tiếp theo bắt đầu bằng " (JSON key) hoặc } hoặc ] → dấu ngoặc kép kết thúc
        if text[k] == '"' or text[k] in ('}', ']'):
            return False
        return True
    
    # , → cần kiểm tra sau dấu phẩy là gì
    if ch == ',':
        k = j + 1
        while k < len(text) and text[k] in ' \t':
            k += 1
        
        if k >= len(text):
            return False
        
        # Sau dấu phẩy là xuống dòng → kiểm tra dòng tiếp theo
        if text[k] in ('\n', '\r'):
            k2 = k + (2 if (text[k] == '\r' and k + 1 < len(text) and text[k + 1] == '\n') else 1)
            while k2 < len(text) and text[k2] in ' \t\n\r':
                k2 += 1
            if k2 >= len(text):
                return False
            if text[k2] == '"' or text[k2] in ('}', ']'):
                return False
            return True
        
        after_comma = text[k]
        
        # Sau dấu phẩy cấu trúc phải là đầu của giá trị JSON
        if after_comma == '"':
            return False  # Giá trị chuỗi hoặc key
        if after_comma.isdigit() or after_comma == '-':
            return False  # Số
        if after_comma in ('{', '['):
            return False  # Object/mảng
        if text[k:k+4] in ('true', 'null'):
            return False
        if text[k:k+5] == 'false':
            return False
        
        # Sau dấu phẩy không phải đầu giá trị JSON → dấu phẩy nội dung, dấu ngoặc kép là dấu ngoặc kép nội dung
        return True
    
    # : → thường không thể xuất hiện sau khi chuỗi kết thúc, xử lý thận trọng như dấu ngoặc kép kết thúc
    if ch == ':':
        return False
    
    # Ký tự khác (tiếng Trung, chữ cái, v.v.) → dấu ngoặc kép nội dung
    return True


def _fix_json_string_values(text: str) -> str:
    """
    Sửa JSON có nhận thức ngữ cảnh, xử lý riêng trong/ngoài chuỗi.
    
    Trong giá trị chuỗi:
    1. Ký tự xuống dòng/tab trần → escape
    2. Dấu ngoặc kép tiếng Trung ("" v.v.) → escape thành \\"
    3. Dấu ngoặc kép ASCII chưa escape → phát hiện thông minh: dấu ngoặc kép nội dung thì escape, dấu ngoặc kép kết thúc thì giữ
    4. Dấu phẩy/hai chấm tiếng Trung → giữ nguyên (là ký tự nội dung)
    
    Vị trí cấu trúc (ngoài chuỗi):
    1. Dấu ngoặc kép tiếng Trung → dấu ngoặc kép ASCII
    2. Dấu phẩy tiếng Trung → dấu phẩy ASCII
    3. Dấu hai chấm tiếng Trung → dấu hai chấm ASCII
    """
    if not text or '"' not in text:
        return text
    
    result = []
    i = 0
    in_string = False
    fixed_count = 0
    
    while i < len(text):
        c = text[i]
        
        # === Ngoài chuỗi (vị trí cấu trúc) ===
        if not in_string:
            # Dấu câu tiếng Trung ở vị trí cấu trúc → ASCII
            if c == '\uff0c':  # ，→ ,
                result.append(',')
                fixed_count += 1
                i += 1
                continue
            if c == '\uff1a':  # ：→ :
                result.append(':')
                fixed_count += 1
                i += 1
                continue
            if c in _QUOTE_MAP:
                result.append(_QUOTE_MAP[c])
                fixed_count += 1
                i += 1
                continue
            
            # Dấu ngoặc kép ASCII → vào chuỗi
            if c == '"':
                in_string = True
                result.append(c)
                i += 1
                continue
            
            result.append(c)
            i += 1
            continue
        
        # === Trong giá trị chuỗi ===
        
        # Xử lý ký tự escape
        if c == '\\':
            if i + 1 < len(text):
                next_c = text[i + 1]
                if next_c in ('"', '\\', '/', 'b', 'f', 'n', 'r', 't'):
                    result.append(c)
                    result.append(next_c)
                    i += 2
                    continue
                elif next_c == 'u':
                    if i + 5 < len(text) and all(text[i+2+k] in '0123456789abcdefABCDEF' for k in range(4)):
                        result.append(text[i:i+6])
                        i += 6
                        continue
                    else:
                        result.append(next_c)
                        fixed_count += 1
                        i += 2
                        continue
                else:
                    result.append(next_c)
                    fixed_count += 1
                    i += 2
                    continue
            else:
                fixed_count += 1
                i += 1
                continue
        
        # Dấu ngoặc kép ASCII → phán đoán thông minh là dấu ngoặc kép kết thúc hay dấu ngoặc kép nội dung
        if c == '"':
            if _is_content_quote(text, i):
                # Dấu ngoặc kép nội dung, cần escape
                result.append('\\')
                result.append('"')
                fixed_count += 1
                i += 1
                continue
            else:
                # Dấu ngoặc kép kết thúc
                in_string = False
                result.append(c)
                i += 1
                continue
        
        # Ký tự xuống dòng trần → escape
        if c == '\n':
            result.append('\\')
            result.append('n')
            fixed_count += 1
            i += 1
            continue
        
        if c == '\r':
            if i + 1 < len(text) and text[i + 1] == '\n':
                result.append('\\')
                result.append('n')
                fixed_count += 1
                i += 2
            else:
                result.append('\\')
                result.append('n')
                fixed_count += 1
                i += 1
            continue
        
        if c == '\t':
            result.append('\\')
            result.append('t')
            fixed_count += 1
            i += 1
            continue
        
        # Xử lý dấu ngoặc kép tiếng Trung
        if c in _QUOTE_MAP:
            mapped = _QUOTE_MAP[c]
            if mapped == '"':
                # Dấu ngoặc kép đôi tiếng Trung trong chuỗi cần escape
                result.append('\\')
                result.append('"')
            else:
                # Dấu ngoặc đơn tiếng Trung trong chuỗi ngoặc kép đôi không cần escape, thay trực tiếp
                result.append(mapped)
            fixed_count += 1
            i += 1
            continue
        
        # Ký tự khác (gồm dấu phẩy, dấu hai chấm tiếng Trung) → giữ nguyên
        result.append(c)
        i += 1
    
    if fixed_count > 0:
        logger.debug(f"✅ Đã sửa {fixed_count} vấn đề JSON (dấu ngoặc kép/ký tự điều khiển/dấu câu tiếng Trung)")
    
    return ''.join(result)


def _fix_all_invalid_escapes(text: str) -> str:
    """
    Sửa chữa dự phòng: quét toàn bộ văn bản để tìm các chuỗi escape JSON không hợp lệ.
    
    Khi _fix_json_string_values bỏ sót một số escape không hợp lệ do lỗi theo dõi biên chuỗi,
    hàm này đóng vai trò dự phòng, không phụ thuộc theo dõi trạng thái chuỗi, quét toàn bộ văn bản để sửa mọi escape không hợp lệ.
    
    Escape JSON hợp lệ: \\" \\\\ \\/ \\b \\f \\n \\r \\t \\uXXXX
    Các \\X đều là escape không hợp lệ, cách sửa là bỏ dấu backslash chỉ giữ ký tự.
    """
    if '\\' not in text:
        return text
    
    result = []
    i = 0
    fixed = 0
    
    while i < len(text):
        if text[i] == '\\' and i + 1 < len(text):
            next_c = text[i + 1]
            if next_c in ('"', '\\', '/', 'b', 'f', 'n', 'r', 't'):
                # Escape hợp lệ, giữ lại
                result.append(text[i])
                result.append(next_c)
                i += 2
                continue
            elif next_c == 'u':
                # Escape Unicode, kiểm tra có 4 ký tự hex không
                if i + 5 < len(text) and all(
                    text[i + 2 + k] in '0123456789abcdefABCDEF' 
                    for k in range(4)
                ):
                    result.append(text[i:i + 6])
                    i += 6
                    continue
                else:
                    # Escape unicode không đầy đủ, bỏ dấu backslash
                    result.append(next_c)
                    fixed += 1
                    i += 2
                    continue
            else:
                # Escape không hợp lệ, bỏ dấu backslash chỉ giữ ký tự
                result.append(next_c)
                fixed += 1
                i += 2
                continue
        else:
            result.append(text[i])
            i += 1
    
    if fixed > 0:
        logger.info(f"✅ Đã sửa dự phòng {fixed} chuỗi escape JSON không hợp lệ")
    
    return ''.join(result)


def _fix_multiple_objects_as_value(text: str) -> str:
    """
    Sửa vấn đề trong JSON do AI sinh: nhiều object làm giá trị thuộc tính nhưng chưa được hợp nhất.
    
    Ví dụ:
        "key": {"a": "1"}, {"b": "2"}  →  "key": {"a": "1", "b": "2"}
    
    AI đôi khi khi xuất giá trị thuộc tính kiểu object lại xuất nhiều object độc lập thay vì hợp nhất thành một.
    Ví dụ khi field relationship_changes xuất nhiều thay đổi quan hệ nhân vật có thể gặp vấn đề này.
    Hàm này phát hiện và hợp nhất các object đó.
    """
    if '{' not in text or '}' not in text:
        return text
    
    # Khớp object có độ sâu lồng nhau không quá 2: { ... } trong đó ... không chứa { hoặc chỉ chứa một lớp lồng
    nested_obj = r'\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}'
    
    # Mẫu: sau dấu hai chấm của thuộc tính là một object, rồi dấu phẩy và một object khác (không có tên thuộc tính)
    # Tức là "key": {obj1}, {obj2} → "key": {obj1, obj2}
    pattern = r'(":)\s*(' + nested_obj + r')\s*,\s*(' + nested_obj + r')'
    
    def merge_objects(match):
        colon = match.group(1)
        obj1_content = match.group(2)[1:-1]  # Bỏ { } ở ngoài
        obj2_content = match.group(3)[1:-1]  # Bỏ { } ở ngoài
        # Hợp nhất thành một object
        return f'{colon} {{{obj1_content}, {obj2_content}}}'
    
    prev = None
    count = 0
    max_iterations = 10
    while prev != text and count < max_iterations:
        prev = text
        text = re.sub(pattern, merge_objects, text)
        count += 1
    
    if count > 1:
        logger.info(f"✅ Đã sửa {count - 1} chỗ hợp nhất giá trị thuộc tính nhiều object")
    
    return text


def clean_json_response(text: str) -> str:
    """Làm sạch JSON do AI trả về (bản cải tiến - an toàn streaming)"""
    try:
        if not text:
            logger.warning("⚠️ clean_json_response: input rỗng")
            return text
        
        original_length = len(text)
        logger.debug(f"🔍 Bắt đầu làm sạch JSON, độ dài gốc: {original_length}")

        text = strip_think_tags(text)
        
        # Sửa có nhận thức ngữ cảnh: dấu ngoặc kép/phẩy/hai chấm tiếng Trung, ký tự điều khiển trần, dấu ngoặc kép nội dung chưa escape
        # (phân biệt trong/ngoài chuỗi: vị trí cấu trúc thay bằng ASCII, trong chuỗi giữ nguyên hoặc escape)
        text = _fix_json_string_values(text)
        
        # Loại bỏ code block markdown
        text = re.sub(r'^```json\s*\n?', '', text, flags=re.MULTILINE | re.IGNORECASE)
        text = re.sub(r'^```\s*\n?', '', text, flags=re.MULTILINE)
        text = re.sub(r'\n?```\s*$', '', text, flags=re.MULTILINE)
        text = text.strip()
        
        if len(text) != original_length:
            logger.debug(f"   Độ dài sau khi gỡ markdown: {len(text)}")
        
        # Thử parse trực tiếp (đường nhanh)
        try:
            json.loads(text)
            logger.debug(f"✅ Parse trực tiếp thành công, không cần làm sạch")
            return text
        except Exception:
            pass
        
        # Tìm { hoặc [ đầu tiên
        start = -1
        for i, c in enumerate(text):
            if c in ('{', '['):
                start = i
                break
        
        if start == -1:
            logger.warning(f"⚠️ Không tìm thấy ký tự bắt đầu JSON {{ hoặc [")
            logger.debug(f"   Xem trước văn bản: {safe_preview(text, 200)}")
            return text
        
        if start > 0:
            logger.debug(f"   Bỏ qua {start} ký tự đầu")
            text = text[start:]
        
        # Thuật toán khớp ngoặc cải tiến (xử lý chuỗi nghiêm ngặt hơn)
        stack = []
        i = 0
        end = -1
        in_string = False
        
        while i < len(text):
            c = text[i]
            
            # Xử lý trạng thái chuỗi
            if c == '"':
                if not in_string:
                    # Vào chuỗi
                    in_string = True
                else:
                    # Kiểm tra có phải dấu ngoặc kép đã escape không
                    num_backslashes = 0
                    j = i - 1
                    while j >= 0 and text[j] == '\\':
                        num_backslashes += 1
                        j -= 1
                    
                    # Số lượng backslash chẵn nghĩa là dấu ngoặc kép chưa bị escape, chuỗi kết thúc
                    if num_backslashes % 2 == 0:
                        in_string = False
                
                i += 1
                continue
            
            # Trong chuỗi, bỏ qua mọi ký tự
            if in_string:
                i += 1
                continue
            
            # Xử lý ngoặc (chỉ có hiệu lực ngoài chuỗi)
            if c == '{' or c == '[':
                stack.append(c)
            elif c == '}':
                if len(stack) > 0 and stack[-1] == '{':
                    stack.pop()
                    if len(stack) == 0:
                        end = i + 1
                        logger.debug(f"✅ Tìm thấy vị trí kết thúc JSON: {end}")
                        break
                elif len(stack) > 0:
                    # Ngoặc không khớp, có thể là JSON hỏng, thử tiếp tục
                    logger.warning(f"⚠️ Ngoặc không khớp: gặp }} nhưng đỉnh stack là {stack[-1]}")
                else:
                    # Stack rỗng gặp }, bỏ qua dấu đóng ngoặc thừa
                    logger.warning(f"⚠️ Gặp }} thừa, bỏ qua")
            elif c == ']':
                if len(stack) > 0 and stack[-1] == '[':
                    stack.pop()
                    if len(stack) == 0:
                        end = i + 1
                        logger.debug(f"✅ Tìm thấy vị trí kết thúc JSON: {end}")
                        break
                elif len(stack) > 0:
                    # Ngoặc không khớp, có thể là JSON hỏng, thử tiếp tục
                    logger.warning(f"⚠️ Ngoặc không khớp: gặp ] nhưng đỉnh stack là {stack[-1]}")
                else:
                    # Stack rỗng gặp ], bỏ qua dấu đóng ngoặc thừa
                    logger.warning(f"⚠️ Gặp ] thừa, bỏ qua")
            
            i += 1
        
        # Kiểm tra chuỗi chưa đóng
        if in_string:
            logger.warning(f"⚠️ Chuỗi chưa đóng, JSON có thể không đầy đủ")
        
        # Trích xuất kết quả
        if end > 0:
            result = text[:end]
            logger.debug(f"✅ Làm sạch JSON hoàn tất, độ dài kết quả: {len(result)}")
        else:
            result = text
            logger.warning(f"⚠️ Không tìm thấy vị trí kết thúc JSON, trả về toàn bộ nội dung (độ dài: {len(result)})")
            logger.debug(f"   Trạng thái stack: {stack}")
        
        # Xác minh kết quả sau khi làm sạch
        try:
            json.loads(result)
            logger.debug(f"✅ Xác minh JSON sau làm sạch thành công")
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ JSON sau làm sạch vẫn không hợp lệ: {e}, thử sửa vấn đề cấu trúc...")
            
            # Sửa 1: hợp nhất giá trị thuộc tính nhiều object (AI có thể xuất "key": {a:1}, {b:2} )
            result = _fix_multiple_objects_as_value(result)
            
            try:
                json.loads(result)
                logger.info(f"✅ Sửa giá trị thuộc tính nhiều object xong, xác minh JSON thành công")
            except json.JSONDecodeError:
                pass  # Tiếp tục thử cách sửa khác
            else:
                return result
            
            # Sửa 2: sửa dự phòng chuỗi escape không hợp lệ (không phụ thuộc theo dõi biên chuỗi)
            logger.warning(f"⚠️ Tiếp tục thử sửa dự phòng escape không hợp lệ...")
            result = _fix_all_invalid_escapes(result)
            try:
                json.loads(result)
                logger.info(f"✅ Sửa dự phòng xong, xác minh JSON thành công")
            except json.JSONDecodeError as e2:
                # Sửa 3: thử lại hợp nhất giá trị thuộc tính nhiều object (sau khi sửa escape có thể xuất hiện cơ hội hợp nhất mới)
                result = _fix_multiple_objects_as_value(result)
                try:
                    json.loads(result)
                    logger.info(f"✅ Sửa lần hai xong, xác minh JSON thành công")
                except json.JSONDecodeError as e3:
                    logger.error(f"❌ JSON vẫn không hợp lệ sau mọi cách sửa: {e3}")
                    logger.debug(f"   Xem trước kết quả: {safe_preview(result, 500)}")
                    logger.debug(f"   Độ dài phần cuối kết quả: {min(len(result), 200)}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ clean_json_response gặp lỗi: {e}")
        logger.error(f"   Độ dài văn bản: {len(text) if text else 0}")
        logger.error(f"   Xem trước văn bản: {safe_preview(text, 200)}")
        raise


def parse_json(text: str) -> Union[Dict, List]:
    """Phân tích JSON, ưu tiên dùng json chuẩn, thất bại thì dùng json5 phân tích chịu lỗi"""
    cleaned = clean_json_response(text)
    
    # Ưu tiên dùng json chuẩn
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, Exception):
        pass
    
    # json5 phân tích chịu lỗi (xử lý dấu ngoặc đơn, dấu phẩy thừa, định dạng lỏng lẻo, v.v.)
    if HAS_JSON5:
        try:
            logger.info("🔄 Phân tích JSON chuẩn thất bại, dùng json5 phân tích chịu lỗi")
            result = json5.loads(cleaned)
            logger.info("✅ json5 phân tích chịu lỗi thành công")
            return result
        except Exception as e5:
            logger.error(f"❌ json5 phân tích chịu lỗi cũng thất bại: {e5}")
    
    # Thất bại hoàn toàn
    logger.error(f"❌ parse_json hoàn toàn thất bại")
    logger.error(f"   Độ dài văn bản gốc: {len(text) if text else 0}")
    logger.error(f"   Độ dài văn bản sau làm sạch: {len(cleaned) if cleaned else 0}")
    logger.debug(f"   Xem trước văn bản sau làm sạch: {safe_preview(cleaned, 500)}")
    raise json.JSONDecodeError("Phân tích JSON thất bại (cả json chuẩn và json5 đều thất bại)", cleaned, 0)


def loads_json(text: str) -> Any:
    """
    Thay thế chịu lỗi cho json.loads, có thể thay trực tiếp json.loads().
    Ưu tiên dùng json.loads chuẩn, thất bại thì tự động hạ cấp xuống json5.
    Dùng để phân tích JSON do AI trả về, có thể chứa định dạng không chuẩn.
    """
    # Ưu tiên dùng json chuẩn
    try:
        return json.loads(text)
    except (json.JSONDecodeError, Exception):
        pass
    
    # Sửa dự phòng chuỗi escape không hợp lệ rồi thử lại
    fixed_text = _fix_all_invalid_escapes(text)
    if fixed_text != text:
        try:
            result = json.loads(fixed_text)
            logger.info("✅ Sửa dự phòng escape không hợp lệ xong, json.loads thành công")
            return result
        except (json.JSONDecodeError, Exception):
            pass
    
    # json5 phân tích chịu lỗi
    if HAS_JSON5:
        try:
            logger.info("🔄 json.loads thất bại, dùng json5 phân tích chịu lỗi")
            result = json5.loads(text)
            logger.info("✅ json5 phân tích chịu lỗi thành công")
            return result
        except Exception as e5:
            # json5 cũng thất bại, thử dùng json5 với văn bản đã sửa
            if fixed_text != text:
                try:
                    result = json5.loads(fixed_text)
                    logger.info("✅ Sửa dự phòng escape không hợp lệ xong, json5 phân tích chịu lỗi thành công")
                    return result
                except Exception:
                    pass
            logger.error(f"❌ json5 phân tích chịu lỗi cũng thất bại: {e5}")
    
    # Thất bại hoàn toàn, ném ngoại lệ chuẩn
    raise json.JSONDecodeError("Phân tích JSON thất bại (cả json chuẩn và json5 đều thất bại)", text, 0)
