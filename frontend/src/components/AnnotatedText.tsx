import React, { useMemo, useEffect, useRef } from 'react';
import { theme } from 'antd';

// Kiểu dữ liệu chú thích
export interface MemoryAnnotation {
  id: string;
  type: 'hook' | 'foreshadow' | 'plot_point' | 'character_event';
  title: string;
  content: string;
  importance: number;
  position: number;
  length: number;
  tags: string[];
  metadata: {
    strength?: number;
    foreshadowType?: 'planted' | 'resolved';
    relatedCharacters?: string[];
    [key: string]: unknown;
  };
}

// Kiểu đoạn văn bản
interface TextSegment {
  type: 'text' | 'annotated';
  content: string;
  annotation?: MemoryAnnotation;
  annotations?: MemoryAnnotation[]; // 🔧 Hỗ trợ nhiều chú thích
}

interface AnnotatedTextProps {
  content: string;
  annotations: MemoryAnnotation[];
  onAnnotationClick?: (annotation: MemoryAnnotation) => void;
  activeAnnotationId?: string;
  scrollToAnnotation?: string;
  style?: React.CSSProperties;
}

// Ánh xạ biểu tượng kiểu
const TYPE_ICONS = {
  hook: '🎣',
  foreshadow: '🌟',
  plot_point: '💎',
  character_event: '👤',
};

/**
 * Component văn bản kèm chú thích
 * Hiển thị trực quan chú thích ký ức trong văn bản chương
 */
const AnnotatedText: React.FC<AnnotatedTextProps> = ({
  content,
  annotations,
  onAnnotationClick,
  activeAnnotationId,
  scrollToAnnotation,
  style,
}) => {
  const annotationRefs = useRef<Record<string, HTMLSpanElement | null>>({});

  const { token } = theme.useToken();
  const typeColors: Record<MemoryAnnotation['type'], string> = {
    hook: token.colorError,
    foreshadow: token.colorInfo,
    plot_point: token.colorSuccess,
    character_event: token.colorWarning,
  };

  // Khi cần cuộn đến chú thích cụ thể
  useEffect(() => {
    if (scrollToAnnotation && annotationRefs.current[scrollToAnnotation]) {
      const element = annotationRefs.current[scrollToAnnotation];
      element?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }
  }, [scrollToAnnotation]);
  // Xử lý chú thích chồng lấn và sắp xếp
  const processedAnnotations = useMemo(() => {
    if (!annotations || annotations.length === 0) {
      console.log('AnnotatedText: không có dữ liệu chú thích');
      return [];
    }
    
    console.log(`AnnotatedText: nhận ${annotations.length} chú thích, độ dài nội dung ${content.length}`);
    
    // Lọc bỏ chú thích vị trí không hợp lệ
    const validAnnotations = annotations.filter(
      (a) => a.position >= 0 && a.position < content.length
    );
    
    const invalidCount = annotations.length - validAnnotations.length;
    if (invalidCount > 0) {
      console.warn(`AnnotatedText: ${invalidCount} chú thích vị trí không hợp lệ, chú thích hợp lệ ${validAnnotations.length}`);
      console.log('Chú thích không hợp lệ:', annotations.filter(a => a.position < 0 || a.position >= content.length));
    }
    
    // Sắp xếp theo vị trí
    return validAnnotations.sort((a, b) => a.position - b.position);
  }, [annotations, content]);

  // Chia văn bản thành các đoạn kèm chú thích
  const segments = useMemo(() => {
    if (processedAnnotations.length === 0) {
      return [{ type: 'text' as const, content }];
    }

    const result: TextSegment[] = [];
    let lastPos = 0;

    // 🔧 Nhóm thông minh: phát hiện chú thích chồng lấn và kề nhau
    const annotationRanges: Array<{
      start: number;
      end: number;
      annotations: MemoryAnnotation[];
    }> = [];

    for (const annotation of processedAnnotations) {
      const { position, length } = annotation;
      const actualLength = length > 0 ? length : 30;
      const start = position;
      const end = position + actualLength;

      // Tìm có phạm vi chồng lấn hoặc sát nhau không
      const overlappingRange = annotationRanges.find(
        (range) =>
          (start >= range.start && start <= range.end) || // Điểm bắt đầu trong phạm vi
          (end >= range.start && end <= range.end) || // Điểm kết thúc trong phạm vi
          (start <= range.start && end >= range.end) || // Bao trọn hoàn toàn
          Math.abs(start - range.end) <= 5 || // Sát nhau (dung sai 5 ký tự)
          Math.abs(end - range.start) <= 5
      );

      if (overlappingRange) {
        // Gộp vào phạm vi hiện có
        overlappingRange.start = Math.min(overlappingRange.start, start);
        overlappingRange.end = Math.max(overlappingRange.end, end);
        overlappingRange.annotations.push(annotation);
      } else {
        // Tạo phạm vi mới
        annotationRanges.push({
          start,
          end,
          annotations: [annotation],
        });
      }
    }

    // Sắp xếp theo vị trí bắt đầu
    annotationRanges.sort((a, b) => a.start - b.start);

    // 🔧 Chia mảnh thông minh: chia vùng chồng lấn thành nhiều đoạn nhỏ
    for (const range of annotationRanges) {
      // Thêm văn bản thường phía trước
      if (range.start > lastPos) {
        result.push({
          type: 'text',
          content: content.slice(lastPos, range.start),
        });
      }

      if (range.annotations.length === 1) {
        // Một chú thích, thêm trực tiếp
        result.push({
          type: 'annotated',
          content: content.slice(range.start, range.end),
          annotation: range.annotations[0],
          annotations: range.annotations,
        });
      } else {
        // 🔧 Nhiều chú thích: chia văn bản thành nhiều đoạn nhỏ
        const totalLength = range.end - range.start;
        const segmentLength = Math.max(1, Math.floor(totalLength / range.annotations.length));

        // Sắp xếp chú thích theo mức quan trọng
        const sortedAnnotations = [...range.annotations].sort((a, b) => b.importance - a.importance);

        for (let i = 0; i < sortedAnnotations.length; i++) {
          const segmentStart = range.start + i * segmentLength;
          const segmentEnd = i === sortedAnnotations.length - 1
            ? range.end
            : range.start + (i + 1) * segmentLength;

          result.push({
            type: 'annotated',
            content: content.slice(segmentStart, segmentEnd),
            annotation: sortedAnnotations[i],
            annotations: sortedAnnotations, // Giữ tất cả thông tin chú thích
          });
        }
      }

      lastPos = range.end;
    }

    // Thêm văn bản còn lại
    if (lastPos < content.length) {
      result.push({
        type: 'text',
        content: content.slice(lastPos),
      });
    }

    console.log(`AnnotatedText: xử lý ${processedAnnotations.length} chú thích, tạo ${result.length} đoạn`);
    return result;
  }, [content, processedAnnotations]);

  // Render đoạn chú thích
  const renderAnnotatedSegment = (segment: TextSegment, index: number) => {
    if (segment.type === 'text') {
      return <span key={index}>{segment.content}</span>;
    }

    const { annotation, annotations } = segment;
    if (!annotation) return null;

    const color = typeColors[annotation.type];
    const icon = TYPE_ICONS[annotation.type];
    const isActive = activeAnnotationId === annotation.id;

    // Đơn giản hóa nội dung tooltip, không dùng phần tử React phức tạp nữa, đổi sang văn bản thuần hoặc gỡ Tooltip
    const tooltipText = annotations && annotations.length > 1
      ? `Ở đây có ${annotations.length} chú thích`
      : `${annotation.title}: ${annotation.content.slice(0, 100)}${annotation.content.length > 100 ? '...' : ''}`;

    return (
      <span
        key={index}
        title={tooltipText}
        ref={(el) => {
          if (annotation) {
            annotationRefs.current[annotation.id] = el;
          }
        }}
        data-annotation-id={annotation?.id}
        className={`annotated-text ${isActive ? 'active' : ''}`}
        style={{
          position: 'relative',
          borderBottom: `2px solid ${color}`,
          cursor: 'pointer',
          backgroundColor: isActive ? `color-mix(in srgb, ${color} 13%, transparent)` : 'transparent',
          transition: 'all 0.2s',
          padding: '2px 0',
        }}
        onClick={() => onAnnotationClick?.(annotation)}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = `color-mix(in srgb, ${color} 20%, transparent)`;
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = isActive
            ? `color-mix(in srgb, ${color} 13%, transparent)`
            : 'transparent';
        }}
      >
        {segment.content}
        <span
          style={{
            position: 'absolute',
            top: -20,
            left: '50%',
            transform: 'translateX(-50%)',
            fontSize: 14,
            pointerEvents: 'none',
          }}
        >
          {icon}
        </span>
      </span>
    );
  };

  return (
    <div
      style={{
        lineHeight: 2,
        fontSize: 16,
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        ...style,
      }}
    >
      {segments.map((segment, index) => renderAnnotatedSegment(segment, index))}
    </div>
  );
};

export default AnnotatedText;