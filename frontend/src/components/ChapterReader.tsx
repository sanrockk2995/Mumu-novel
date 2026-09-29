/**
 * Component đọc chương
 * Mang lại trải nghiệm đọc đắm chìm, hỗ trợ chuyển theme, chỉnh cỡ chữ, điều hướng lật trang, v.v.
 */
import { useState, useEffect, useCallback } from 'react';
import { Modal, Button, Slider, Radio, Space, Typography, Spin, message, theme } from 'antd';
import {
  LeftOutlined,
  RightOutlined,
  SettingOutlined,
  FontSizeOutlined,
  BgColorsOutlined,
  CloseOutlined,
  ColumnHeightOutlined
} from '@ant-design/icons';
import type { Chapter } from '../types';

// Interface cài đặt trình đọc
interface ReaderSettings {
  fontSize: number;       // Cỡ chữ
  theme: 'light' | 'sepia' | 'dark';  // Chế độ theme
  lineHeight: number;     // Chiều cao dòng
}

// Interface thuộc tính của component
interface ChapterReaderProps {
  visible: boolean;                           // Có hiển thị hay không
  chapter: Chapter;                           // Chương hiện tại
  onClose: () => void;                        // Callback khi đóng
  onChapterChange: (chapterId: string) => void;  // Callback chuyển chương
}

// Interface thông tin điều hướng
interface NavigationInfo {
  previous: { id: string; chapter_number: number; title: string } | null;
  next: { id: string; chapter_number: number; title: string } | null;
  current: { id: string; chapter_number: number; title: string };
}

interface ReaderThemeStyle {
  bg: string;
  text: string;
  headerBg: string;
  border: string;
}

// lưu trữ cục bộkey
const SETTINGS_STORAGE_KEY = 'chapter-reader-settings';

// Tải cài đặt từ lưu trữ cục bộ
const loadSettings = (): ReaderSettings => {
  try {
    const saved = localStorage.getItem(SETTINGS_STORAGE_KEY);
    if (saved) {
      return JSON.parse(saved);
    }
  } catch (e) {
    console.warn('Tải cài đặt trình đọc thất bại:', e);
  }
  return {
    fontSize: 18,
    theme: 'light',
    lineHeight: 1.8
  };
};

// Lưu cài đặt vào lưu trữ cục bộ
const saveSettings = (settings: ReaderSettings) => {
  try {
    localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(settings));
  } catch (e) {
    console.warn('Lưu cài đặt trình đọc thất bại:', e);
  }
};

export default function ChapterReader({ 
  visible, 
  chapter, 
  onClose, 
  onChapterChange 
}: ChapterReaderProps) {
  const { token } = theme.useToken();

  // Cài đặt trình đọc
  const [settings, setSettings] = useState<ReaderSettings>(loadSettings);
  
  // Thông tin điều hướng
  const [navigation, setNavigation] = useState<NavigationInfo | null>(null);
  
  // Trạng thái tải
  const [loading, setLoading] = useState(false);
  
  // Trạng thái hiển thị panel cài đặt
  const [showSettings, setShowSettings] = useState(false);
  
  // Phát hiện thiết bị di động
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);

  // Phát hiện responsive
  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth <= 768);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Lấy thông tin điều hướng chương
  useEffect(() => {
    if (visible && chapter?.id) {
      setLoading(true);
      fetch(`/api/chapters/${chapter.id}/navigation`)
        .then(res => {
          if (!res.ok) throw new Error('Lấy điều hướng thất bại');
          return res.json();
        })
        .then(data => {
          setNavigation(data);
          setLoading(false);
        })
        .catch(err => {
          console.error('Lấy thông tin điều hướng thất bại:', err);
          message.error('Lấy thông tin điều hướng chương thất bại');
          setLoading(false);
        });
    }
  }, [visible, chapter?.id]);

  // Lưu thay đổi cài đặt
  useEffect(() => {
    saveSettings(settings);
  }, [settings]);

  // Chương trước
  const handlePrevious = useCallback(() => {
    if (navigation?.previous) {
      setLoading(true);
      onChapterChange(navigation.previous.id);
    }
  }, [navigation?.previous, onChapterChange]);

  // Chương tiếp
  const handleNext = useCallback(() => {
    if (navigation?.next) {
      setLoading(true);
      onChapterChange(navigation.next.id);
    }
  }, [navigation?.next, onChapterChange]);

  // Phím tắt bàn phím
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!visible) return;
      
      // Bỏ qua phím nhấn trong ô nhập liệu
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }
      
      switch (e.key) {
        case 'ArrowLeft':
          handlePrevious();
          break;
        case 'ArrowRight':
          handleNext();
          break;
        case 'Escape':
          onClose();
          break;
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [visible, handlePrevious, handleNext, onClose]);

  // Tự động cuộn về đầu trang khi chương thay đổi
  useEffect(() => {
    if (chapter?.id) {
      setLoading(false);
      // Tìm container cuộn và cuộn lên đầu trang
      const scrollContainer = document.querySelector('.reader-scroll-container');
      if (scrollContainer) {
        scrollContainer.scrollTop = 0;
      }
    }
  }, [chapter?.id]);

  // Kiểu theme hiện tại
  const themeStyles: Record<ReaderSettings['theme'], ReaderThemeStyle> = {
    light: {
      bg: token.colorBgContainer,
      text: token.colorText,
      headerBg: token.colorBgElevated,
      border: token.colorBorderSecondary,
    },
    sepia: {
      bg: `color-mix(in srgb, ${token.colorWarningBg} 72%, ${token.colorBgContainer} 28%)`,
      text: `color-mix(in srgb, ${token.colorText} 85%, ${token.colorTextSecondary} 15%)`,
      headerBg: `color-mix(in srgb, ${token.colorWarningBg} 58%, ${token.colorBgElevated} 42%)`,
      border: `color-mix(in srgb, ${token.colorWarningBorder} 65%, ${token.colorBorder} 35%)`,
    },
    dark: {
      bg: `color-mix(in srgb, ${token.colorTextBase} 92%, ${token.colorBgContainer} 8%)`,
      text: `color-mix(in srgb, ${token.colorTextLightSolid} 82%, ${token.colorTextSecondary} 18%)`,
      headerBg: `color-mix(in srgb, ${token.colorTextBase} 84%, ${token.colorBgElevated} 16%)`,
      border: `color-mix(in srgb, ${token.colorTextBase} 60%, ${token.colorBorder} 40%)`,
    },
  };
  const currentTheme = themeStyles[settings.theme];

  // Hàm tiện ích cập nhật cài đặt
  const updateSettings = (key: keyof ReaderSettings, value: number | string) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };

  return (
    <Modal
      open={visible}
      onCancel={onClose}
      footer={null}
      width="100%"
      style={{
        maxWidth: '100vw',
        top: 0,
        margin: 0,
        padding: 0,
        height: '100vh',
        overflow: 'hidden'
      }}
      styles={{
        content: {
          height: '100vh',
          borderRadius: 0,
          boxShadow: 'none',
          padding: 0,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden'
        },
        body: {
          flex: 1,
          padding: 0,
          background: currentTheme.bg,
          overflow: 'hidden',
          height: '100%',
          scrollbarWidth: 'thin',
          display: 'flex',
          flexDirection: 'column'
        }
      }}
      closable={false}
      maskClosable={false}
    >
      {/* Thanh công cụ trên cùng */}
      <div style={{
        flex: 'none',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: isMobile ? '10px 12px' : '12px 20px',
        borderBottom: `1px solid ${currentTheme.border}`,
        background: currentTheme.headerBg,
        zIndex: 10
      }}>
        <Button 
          type="text" 
          icon={<CloseOutlined />} 
          onClick={onClose}
          style={{ color: currentTheme.text }}
        >
          {!isMobile && 'Đóng'}
        </Button>
        
        <Typography.Title 
          level={5} 
          style={{ 
            margin: 0, 
            color: currentTheme.text,
            maxWidth: isMobile ? '60%' : '70%',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            fontSize: isMobile ? 14 : 16
          }}
        >
          Chương {chapter.chapter_number}: {chapter.title}
        </Typography.Title>
        
        <Button
          type={showSettings ? 'primary' : 'text'}
          icon={<SettingOutlined />}
          onClick={() => setShowSettings(!showSettings)}
          style={{ color: showSettings ? undefined : currentTheme.text }}
          title="Cài đặt đọc"
        />
      </div>

      {/* Panel cài đặt */}
      {showSettings && (
        <div style={{
          padding: isMobile ? '12px 16px' : '16px 24px',
          borderBottom: `1px solid ${currentTheme.border}`,
          background: currentTheme.headerBg
        }}>
          <Space 
            direction={isMobile ? 'vertical' : 'horizontal'} 
            size="large"
            style={{ width: '100%' }}
            wrap
          >
            {/* Cỡ chữ */}
            <div style={{ minWidth: isMobile ? '100%' : 200 }}>
              <Space style={{ marginBottom: 8, color: currentTheme.text }}>
                <FontSizeOutlined />
                <span>Cỡ chữ: {settings.fontSize}px</span>
              </Space>
              <Slider
                min={14}
                max={28}
                value={settings.fontSize}
                onChange={v => updateSettings('fontSize', v)}
                style={{ margin: '8px 0' }}
              />
            </div>

            {/* Chiều cao dòng */}
            <div style={{ minWidth: isMobile ? '100%' : 200 }}>
              <Space style={{ marginBottom: 8, color: currentTheme.text }}>
                <ColumnHeightOutlined />
                <span>Chiều cao dòng: {settings.lineHeight}</span>
              </Space>
              <Slider
                min={1.4}
                max={2.5}
                step={0.1}
                value={settings.lineHeight}
                onChange={v => updateSettings('lineHeight', v)}
                style={{ margin: '8px 0' }}
              />
            </div>

            {/* Theme */}
            <div>
              <Space style={{ marginBottom: 8, color: currentTheme.text }}>
                <BgColorsOutlined />
                <span>Theme</span>
              </Space>
              <div>
                <Radio.Group
                  value={settings.theme}
                  onChange={e => updateSettings('theme', e.target.value)}
                  buttonStyle="solid"
                  size={isMobile ? 'small' : 'middle'}
                >
                  <Radio.Button value="light">Ban ngày</Radio.Button>
                  <Radio.Button value="sepia">Bảo vệ mắt</Radio.Button>
                  <Radio.Button value="dark">Ban đêm</Radio.Button>
                </Radio.Group>
              </div>
            </div>
          </Space>
        </div>
      )}

      {/* Khu vực nội dung chương */}
      <div
        className="reader-scroll-container"
        style={{
          flex: 1,
          overflowY: 'auto',
          position: 'relative',
          scrollBehavior: 'smooth'
        }}
      >
        <Spin spinning={loading} tip="Đang tải...">
          <div
            style={{
              maxWidth: 1000,
              margin: '0 auto',
              padding: isMobile ? '24px 16px 40px' : '40px 60px 40px',
              minHeight: '100%',
              fontSize: settings.fontSize,
            lineHeight: settings.lineHeight,
            color: currentTheme.text,
            whiteSpace: 'pre-wrap',
            textAlign: 'justify',
            wordBreak: 'break-word',
            overflowWrap: 'break-word'
          }}
        >
          {chapter.content ? (
            // Render nội dung theo từng đoạn để tối ưu trải nghiệm đọc
            chapter.content.split('\n').map((paragraph, index) => (
              paragraph.trim() ? (
                <p
                  key={index}
                  style={{
                    textIndent: '2em',
                    margin: 0,
                    marginBottom: '0.8em'
                  }}
                >
                  {paragraph}
                </p>
              ) : (
                <br key={index} />
              )
            ))
          ) : (
            <div style={{ 
              textAlign: 'center', 
              padding: '60px 20px',
              color: currentTheme.text,
              opacity: 0.6
            }}>
              Chưa có nội dung
            </div>
          )}
          </div>
        </Spin>
      </div>

      {/* Thanh điều hướng dưới cùng */}
      <div style={{
        flex: 'none',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: isMobile ? '12px 16px' : '16px 24px',
        borderTop: `1px solid ${currentTheme.border}`,
        background: currentTheme.headerBg,
        zIndex: 100
      }}>
        <Button
          type="primary"
          icon={<LeftOutlined />}
          disabled={!navigation?.previous || loading}
          onClick={handlePrevious}
          size={isMobile ? 'middle' : 'large'}
        >
          {!isMobile && 'Chương trước'}
        </Button>
        
        <div style={{ 
          textAlign: 'center',
          color: currentTheme.text,
          fontSize: isMobile ? 12 : 14
        }}>
          <div>{chapter.word_count || 0} ký tự</div>
          {navigation && (
            <div style={{ fontSize: isMobile ? 10 : 12, opacity: 0.7 }}>
              {navigation.previous ? `← ${navigation.previous.title}` : 'Đã là chương đầu tiên'}
              {' | '}
              {navigation.next ? `${navigation.next.title} →` : 'Đã là chương cuối cùng'}
            </div>
          )}
        </div>
        
        <Button
          type="primary"
          disabled={!navigation?.next || loading}
          onClick={handleNext}
          size={isMobile ? 'middle' : 'large'}
        >
          {!isMobile && 'Chương tiếp'}
          <RightOutlined />
        </Button>
      </div>
    </Modal>
  );
}