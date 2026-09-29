"""Dịch vụ phân tích TXT: nhận diện mã hóa, làm sạch văn bản và tách chương"""
from __future__ import annotations

import re
from typing import Optional

from app.logger import get_logger

logger = get_logger(__name__)


class TxtParserService:
    """Dịch vụ phân tích TXT (ưu tiên quy tắc)"""

    STRONG_CHAPTER_PATTERNS = [
        re.compile(r"^第[一二三四五六七八九十百千万零〇两\d]+[章节回卷集部篇].*$"),
        re.compile(r"^chapter\s*\d+.*$", re.IGNORECASE),
        re.compile(r"^chap\.\s*\d+.*$", re.IGNORECASE),
    ]

    def decode_bytes(self, content: bytes) -> tuple[str, str]:
        """
        Thử giải mã luồng byte TXT

        Returns:
            (text, encoding)
        """
        encodings = ["utf-8", "utf-8-sig", "gb18030", "gbk", "big5"]
        for enc in encodings:
            try:
                return content.decode(enc), enc
            except UnicodeDecodeError:
                continue

        # Dự phòng cuối cùng: không ném lỗi, cố gắng đọc nội dung
        logger.warning("Tự động nhận diện mã hóa TXT thất bại, dùng utf-8(ignore) dự phòng")
        return content.decode("utf-8", errors="ignore"), "utf-8(ignore)"

    def clean_text(self, text: str) -> str:
        """Làm sạch cơ bản: chuẩn hóa xuống dòng, loại bỏ khoảng trắng bất thường, nén các dòng trống thừa"""
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\ufeff", "")
        normalized = normalized.replace("\u3000", "  ")
        normalized = re.sub(r"[ \t]+\n", "\n", normalized)
        normalized = re.sub(r"\n{4,}", "\n\n\n", normalized)
        return normalized.strip()

    def split_chapters(self, text: str) -> list[dict]:
        """
        Tách chương (ưu tiên quy tắc, dự phòng khi thất bại)

        Returns:
            [{title, content, chapter_number}]
        """
        if not text.strip():
            return []

        lines = text.split("\n")
        heading_indexes: list[int] = []

        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            if self._is_strong_heading(stripped) or self._is_weak_heading(lines, idx):
                heading_indexes.append(idx)

        # Loại bỏ trùng lặp và sắp xếp
        heading_indexes = sorted(set(heading_indexes))

        # Nếu không nhận diện được tiêu đề nào, dùng cửa sổ cố định dự phòng
        if not heading_indexes:
            return self._fallback_split(text)

        # Nếu trước tiêu đề đầu tiên có chính văn dài, giữ lại làm chương mở đầu
        chapters: list[dict] = []
        chapter_no = 1

        first_heading = heading_indexes[0]
        if first_heading > 0:
            preface = "\n".join(lines[:first_heading]).strip()
            if len(preface) >= 200:
                chapters.append(
                    {
                        "title": "Mở đầu",
                        "content": preface,
                        "chapter_number": chapter_no,
                    }
                )
                chapter_no += 1

        for i, start_idx in enumerate(heading_indexes):
            end_idx = heading_indexes[i + 1] if i + 1 < len(heading_indexes) else len(lines)
            title = lines[start_idx].strip()[:200] or f"Chương {chapter_no}"
            body = "\n".join(lines[start_idx + 1 : end_idx]).strip()
            # Tránh mất/tiêu đề trống/chính văn trống
            if not body and i + 1 < len(heading_indexes):
                next_line = lines[start_idx + 1].strip() if start_idx + 1 < len(lines) else ""
                body = next_line

            chapters.append(
                {
                    "title": title,
                    "content": body,
                    "chapter_number": chapter_no,
                }
            )
            chapter_no += 1

        # Lọc bỏ các chương nhiễu rõ ràng
        filtered = [c for c in chapters if c["title"] or c["content"]]
        if filtered:
            return filtered

        return self._fallback_split(text)

    def _is_strong_heading(self, line: str) -> bool:
        return any(pattern.match(line) for pattern in self.STRONG_CHAPTER_PATTERNS)

    def _is_weak_heading(self, lines: list[str], idx: int) -> bool:
        """
        Chế độ yếu: dòng ngắn + dòng trống trước sau + tránh nhận nhầm câu thông thường
        """
        line = lines[idx].strip()
        if not line:
            return False
        if len(line) > 25:
            return False
        if re.search(r"[，。！？；：,.!?;:]", line):
            return False

        prev_blank = idx == 0 or not lines[idx - 1].strip()
        next_blank = idx == len(lines) - 1 or not lines[idx + 1].strip()
        return prev_blank and next_blank

    def _fallback_split(self, text: str, min_window: int = 3000, max_window: int = 5000) -> list[dict]:
        """
        Cửa sổ cố định + tách theo biên dấu câu
        """
        chapters: list[dict] = []
        n = len(text)
        start = 0
        chapter_no = 1
        boundary_punctuations = "。！？!?\n"

        while start < n:
            ideal_end = min(start + max_window, n)
            if ideal_end >= n:
                end = n
            else:
                search_from = min(start + min_window, n)
                segment = text[search_from:ideal_end]
                offset = max(segment.rfind(p) for p in boundary_punctuations)
                end = search_from + offset + 1 if offset >= 0 else ideal_end

            chunk = text[start:end].strip()
            if chunk:
                chapters.append(
                    {
                        "title": f"Chương {chapter_no}",
                        "content": chunk,
                        "chapter_number": chapter_no,
                    }
                )
                chapter_no += 1

            start = end

        return chapters


txt_parser_service = TxtParserService()