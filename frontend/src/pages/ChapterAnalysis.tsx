import React, { useState, useEffect } from 'react';
import { Card, List, Button, Space, Empty, Tag, Spin, Alert, Switch, Drawer, message, theme } from 'antd';
import {
  EyeOutlined,
  EyeInvisibleOutlined,
  MenuOutlined,
  LeftOutlined,
  RightOutlined,
  UnorderedListOutlined,
  FundOutlined,
} from '@ant-design/icons';
import { useParams } from 'react-router-dom';
import api from '../services/api';
import AnnotatedText, { type MemoryAnnotation } from '../components/AnnotatedText';
import MemorySidebar from '../components/MemorySidebar';
import { eventBus, EventNames } from '../store/eventBus';

interface ChapterItem {
  id: string;
  chapter_number: number;
  title: string;
  content: string;
  word_count: number;
  status: string;
}

interface AnnotationsData {
  chapter_id: string;
  chapter_number: number;
  title: string;
  word_count: number;
  annotations: MemoryAnnotation[];
  has_analysis: boolean;
  summary: {
    total_annotations: number;
    hooks: number;
    foreshadows: number;
    plot_points: number;
    character_events: number;
  };
}

interface NavigationData {
  current: {
    id: string;
    chapter_number: number;
    title: string;
  };
  previous: {
    id: string;
    chapter_number: number;
    title: string;
  } | null;
  next: {
    id: string;
    chapter_number: number;
    title: string;
  } | null;
}

/**
 * Trang phân tích cốt truyện chương trong dự án
 * Hiển thị danh sách chương và nội dung chương có chú thích
 */
const ChapterAnalysis: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  
  const [chapters, setChapters] = useState<ChapterItem[]>([]);
  const [selectedChapter, setSelectedChapter] = useState<ChapterItem | null>(null);
  const [annotationsData, setAnnotationsData] = useState<AnnotationsData | null>(null);
  const [navigation, setNavigation] = useState<NavigationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [contentLoading, setContentLoading] = useState(false);
  const [showAnnotations, setShowAnnotations] = useState(true);
  const [activeAnnotationId, setActiveAnnotationId] = useState<string | undefined>();
  const [sidebarVisible, setSidebarVisible] = useState(false);
  const [chapterListVisible, setChapterListVisible] = useState(false);
  const [scrollToContentAnnotation, setScrollToContentAnnotation] = useState<string | undefined>();
  const [scrollToSidebarAnnotation, setScrollToSidebarAnnotation] = useState<string | undefined>();
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const { token } = theme.useToken();

  // Lắng nghe thay đổi kích thước cửa sổ
  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth < 768);
    };
    
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Tải danh sách chương
  useEffect(() => {
    const loadChapters = async () => {
      if (!projectId) return;
      
      try {
        setLoading(true);
        const response = await api.get(`/chapters/project/${projectId}`);
        // Interceptor API đã phân tích response.data nên dùng trực tiếp
        const data = response.data || response;
        const chapterList = data.items || [];
        setChapters(chapterList);
        
        // Tự động chọn chương đầu tiên có nội dung
        const firstChapterWithContent = chapterList.find((ch: ChapterItem) => ch.content && ch.content.trim() !== '');
        if (firstChapterWithContent) {
          loadChapterContent(firstChapterWithContent.id);
        }
      } catch (error) {
        console.error('Tải danh sách chương thất bại:', error);
        message.error('Tải danh sách chương thất bại');
      } finally {
        setLoading(false);
      }
    };

    loadChapters();
  }, [projectId]);

  // Tải nội dung chương và chú thích
  const loadChapterContent = async (chapterId: string) => {
    try {
      setContentLoading(true);
      
      const [chapterResponse, annotationsResponse, navigationResponse] = await Promise.all([
        api.get(`/chapters/${chapterId}`),
        api.get(`/chapters/${chapterId}/annotations`).catch(() => null),
        api.get(`/chapters/${chapterId}/navigation`).catch(() => null),
      ]);

      // Trích xuất thuộc tính data
      setSelectedChapter(chapterResponse.data || chapterResponse);
      setAnnotationsData(annotationsResponse ? (annotationsResponse.data || annotationsResponse) : null);
      setNavigation(navigationResponse ? (navigationResponse.data || navigationResponse) : null);
    } catch (error) {
      console.error('Tải nội dung chương thất bại:', error);
      message.error('Tải nội dung chương thất bại');
    } finally {
      setContentLoading(false);
    }
  };

  useEffect(() => {
    const handleTaskSettled = (payload?: unknown) => {
      if (!payload || typeof payload !== 'object') return;
      const data = payload as { projectId?: string; resources?: string[] };
      if (data.projectId && data.projectId !== projectId) return;
      if (data.resources?.includes('analysis') && selectedChapter?.id) {
        void loadChapterContent(selectedChapter.id);
      }
    };
    eventBus.on(EventNames.BACKGROUND_TASK_SETTLED, handleTaskSettled);
    return () => eventBus.off(EventNames.BACKGROUND_TASK_SETTLED, handleTaskSettled);
  }, [projectId, selectedChapter?.id]);

  const handleChapterSelect = (chapterId: string) => {
    loadChapterContent(chapterId);
    if (isMobile) {
      setChapterListVisible(false);
    }
  };

  const handlePreviousChapter = () => {
    if (navigation?.previous) {
      loadChapterContent(navigation.previous.id);
    }
  };

  const handleNextChapter = () => {
    if (navigation?.next) {
      loadChapterContent(navigation.next.id);
    }
  };

  const handleAnnotationClick = (annotation: MemoryAnnotation, source: 'content' | 'sidebar' = 'content') => {
    setActiveAnnotationId(annotation.id);
    
    if (source === 'content') {
      // Click từ khu vực nội dung để cuộn đến sidebar
      setScrollToSidebarAnnotation(annotation.id);
      // Xóa trạng thái cuộn
      setTimeout(() => setScrollToSidebarAnnotation(undefined), 100);
      
      if (isMobile) {
        setSidebarVisible(true);
      }
    } else {
      // Click từ sidebar để cuộn đến khu vực nội dung
      setScrollToContentAnnotation(annotation.id);
      // Xóa trạng thái cuộn
      setTimeout(() => setScrollToContentAnnotation(undefined), 100);
    }
  };

  const hasAnnotations = annotationsData && annotationsData.annotations.length > 0;

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0' }}>
        <Spin size="large" tip="Đang tải chương..." />
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Tiêu đề trang - chỉ hiển thị trên desktop */}
      {!isMobile && (
        <div style={{
          padding: '16px 0',
          marginBottom: 16,
          borderBottom: `1px solid ${token.colorBorderSecondary}`
        }}>
          <h2 style={{ margin: 0, fontSize: 24 }}>
            <FundOutlined style={{ marginRight: 8 }} />
            Phân tích cốt truyện
          </h2>
        </div>
      )}
      
      <div style={{
        flex: 1,
        display: 'flex',
        gap: isMobile ? 0 : 16,
        flexDirection: isMobile ? 'column' : 'row',
        overflow: 'hidden'
      }}>
        {/* Danh sách chương bên trái - desktop */}
        {!isMobile && (
        <Card
          title="Danh sách chương"
          style={{ width: 280, height: '100%', overflow: 'hidden' }}
          bodyStyle={{ padding: 0, height: 'calc(100% - 57px)', overflow: 'auto' }}
        >
          {chapters.length === 0 ? (
            <Empty description="Chưa có chương" style={{ marginTop: 60 }} />
          ) : (
            <List
              dataSource={chapters}
              renderItem={(chapter) => (
                <List.Item
                  key={chapter.id}
                  onClick={() => handleChapterSelect(chapter.id)}
                  style={{
                    cursor: 'pointer',
                    padding: '12px 16px',
                    background: selectedChapter?.id === chapter.id ? token.colorPrimaryBg : 'transparent',
                    borderLeft: selectedChapter?.id === chapter.id ? `3px solid ${token.colorPrimary}` : '3px solid transparent',
                  }}
                >
                  <List.Item.Meta
                    title={
                      <span style={{ fontSize: 14, fontWeight: selectedChapter?.id === chapter.id ? 600 : 400 }}>
                        Chương {chapter.chapter_number}: {chapter.title}
                      </span>
                    }
                    description={
                      <Space size={4}>
                        <Tag color={chapter.content && chapter.content.trim() !== '' ? 'success' : 'default'}>
                          {chapter.word_count || 0} ký tự
                        </Tag>
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          )}
        </Card>
        )}

        {/* Ngăn kéo danh sách chương trên di động */}
      {isMobile && (
        <Drawer
          title="Danh sách chương"
          placement="left"
          onClose={() => setChapterListVisible(false)}
          open={chapterListVisible}
          width="85%"
          styles={{ body: { padding: 0 } }}
        >
          {chapters.length === 0 ? (
            <Empty description="Chưa có chương" style={{ marginTop: 60 }} />
          ) : (
            <List
              dataSource={chapters}
              renderItem={(chapter) => (
                <List.Item
                  key={chapter.id}
                  onClick={() => handleChapterSelect(chapter.id)}
                  style={{
                    cursor: 'pointer',
                    padding: '12px 16px',
                    background: selectedChapter?.id === chapter.id ? token.colorPrimaryBg : 'transparent',
                    borderLeft: selectedChapter?.id === chapter.id ? `3px solid ${token.colorPrimary}` : '3px solid transparent',
                  }}
                >
                  <List.Item.Meta
                    title={
                      <span style={{ fontSize: 14, fontWeight: selectedChapter?.id === chapter.id ? 600 : 400 }}>
                        Chương {chapter.chapter_number}: {chapter.title}
                      </span>
                    }
                    description={
                      <Space size={4}>
                        <Tag color={chapter.content && chapter.content.trim() !== '' ? 'success' : 'default'}>
                          {chapter.word_count || 0} ký tự
                        </Tag>
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          )}
        </Drawer>
        )}

        {/* Khu vực nội dung bên phải */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
        {!selectedChapter ? (
          <Card style={{ height: '100%' }}>
            <Empty description="Vui lòng chọn một chương từ bên trái để xem" style={{ marginTop: 100 }} />
          </Card>
        ) : (
          <>
            {/* Thanh công cụ */}
            <Card size="small" style={{ marginBottom: isMobile ? 8 : 16 }}>
              {isMobile ? (
                // Layout di động: hiển thị hai dòng
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {/* Dòng đầu: tiêu đề và nút chuyển trang */}
                  <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 8
                  }}>
                    <Button
                      icon={<LeftOutlined />}
                      onClick={handlePreviousChapter}
                      disabled={!navigation?.previous}
                      title={navigation?.previous ? `Chương trước: ${navigation.previous.title}` : 'Đã là chương đầu tiên'}
                      size="small"
                    />
                    <span style={{
                      fontSize: 14,
                      fontWeight: 600,
                      flex: 1,
                      textAlign: 'center',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      padding: '0 8px'
                    }}>
                      Chương {selectedChapter.chapter_number}: {selectedChapter.title}
                    </span>
                    <Button
                      icon={<RightOutlined />}
                      onClick={handleNextChapter}
                      disabled={!navigation?.next}
                      title={navigation?.next ? `Chương tiếp: ${navigation.next.title}` : 'Đã là chương cuối cùng'}
                      size="small"
                    />
                  </div>

                  {/* Dòng hai: chương, công tắc, nút phân tích */}
                  <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 8
                  }}>
                    <Button
                      icon={<UnorderedListOutlined />}
                      onClick={() => setChapterListVisible(true)}
                      size="small"
                    >
                      Chương
                    </Button>

                    {hasAnnotations && (
                      <>
                        <Switch
                          checked={showAnnotations}
                          onChange={setShowAnnotations}
                          checkedChildren={<EyeOutlined />}
                          unCheckedChildren={<EyeInvisibleOutlined />}
                          size="small"
                          style={{
                            flexShrink: 0,
                            height: 16,
                            minHeight: 16,
                            lineHeight: '16px'
                          }}
                        />
                        <Button
                          icon={<MenuOutlined />}
                          onClick={() => setSidebarVisible(true)}
                          size="small"
                        >
                          Phân tích
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              ) : (
                // Layout desktop: giữ nguyên
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}>
                  <Space>
                    <Button
                      icon={<LeftOutlined />}
                      onClick={handlePreviousChapter}
                      disabled={!navigation?.previous}
                      title={navigation?.previous ? `Chương trước: ${navigation.previous.title}` : 'Đã là chương đầu tiên'}
                    >
                      Chương trước
                    </Button>
                    <span style={{ fontSize: 16, fontWeight: 600 }}>
                      Chương {selectedChapter.chapter_number}: {selectedChapter.title}
                    </span>
                    <Button
                      icon={<RightOutlined />}
                      onClick={handleNextChapter}
                      disabled={!navigation?.next}
                      title={navigation?.next ? `Chương tiếp: ${navigation.next.title}` : 'Đã là chương cuối cùng'}
                    >
                      Chương tiếp
                    </Button>
                  </Space>

                  <Space>
                    {hasAnnotations && (
                      <>
                        <Switch
                          checked={showAnnotations}
                          onChange={setShowAnnotations}
                          checkedChildren={<EyeOutlined />}
                          unCheckedChildren={<EyeInvisibleOutlined />}
                        />
                        <span style={{ fontSize: 13, color: token.colorTextSecondary }}>Hiển thị chú thích</span>
                      </>
                    )}
                  </Space>
                </div>
              )}

              {hasAnnotations && annotationsData && (
                <div style={{
                  marginTop: 12,
                  fontSize: isMobile ? 11 : 12,
                  color: token.colorTextTertiary,
                  lineHeight: 1.5
                }}>
                  Tổng cộng {annotationsData.summary.total_annotations}  chú thích:
                  {annotationsData.summary.hooks > 0 && ` 🎣${annotationsData.summary.hooks} hook`}
                  {annotationsData.summary.foreshadows > 0 &&
                    ` 🌟${annotationsData.summary.foreshadows} foreshadow`}
                  {annotationsData.summary.plot_points > 0 &&
                    ` 💎${annotationsData.summary.plot_points} plot point`}
                  {annotationsData.summary.character_events > 0 &&
                    ` 👤${annotationsData.summary.character_events} sự kiện nhân vật`}
                </div>
              )}
            </Card>

            {/* Khu vực nội dung */}
            <div style={{
              flex: 1,
              display: 'flex',
              gap: isMobile ? 0 : 16,
              overflow: 'hidden'
            }}>
              {/* Nội dung chương */}
              <Card
                style={{ flex: 1, overflow: 'auto' }}
                bodyStyle={{ padding: isMobile ? '12px' : '24px' }}
                loading={contentLoading}
              >
                {!contentLoading && (
                  <>
                    {!hasAnnotations && (
                      <Alert
                        message="Chưa có dữ liệu phân tích"
                        description="Chương này chưa được phân tích bằng AI nên không thể hiển thị chú thích ký ức."
                        type="info"
                        showIcon
                        style={{ marginBottom: 24 }}
                      />
                    )}

                    {showAnnotations && hasAnnotations && annotationsData ? (
                      <AnnotatedText
                        content={selectedChapter.content}
                        annotations={annotationsData.annotations}
                        onAnnotationClick={(annotation) => handleAnnotationClick(annotation, 'content')}
                        activeAnnotationId={activeAnnotationId}
                        scrollToAnnotation={scrollToContentAnnotation}
                        style={{
                          lineHeight: isMobile ? 1.8 : 2,
                          fontSize: isMobile ? 14 : 16,
                        }}
                      />
                    ) : (
                      <div
                        style={{
                          lineHeight: isMobile ? 1.8 : 2,
                          fontSize: isMobile ? 14 : 16,
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                        }}
                      >
                        {selectedChapter.content}
                      </div>
                    )}
                  </>
                )}
              </Card>

              {/* Sidebar ký ức bên phải (desktop) */}
              {hasAnnotations && annotationsData && !isMobile && (
                <Card
                  style={{ width: 400, overflow: 'auto' }}
                  bodyStyle={{ padding: 0 }}
                >
                  <MemorySidebar
                    annotations={annotationsData.annotations}
                    activeAnnotationId={activeAnnotationId}
                    onAnnotationClick={(annotation) => handleAnnotationClick(annotation, 'sidebar')}
                    scrollToAnnotation={scrollToSidebarAnnotation}
                  />
                </Card>
              )}
            </div>

            {/* Ngăn kéo di động */}
            {hasAnnotations && annotationsData && (
              <Drawer
                title="Phân tích chương"
                placement="right"
                onClose={() => setSidebarVisible(false)}
                open={sidebarVisible}
                width={isMobile ? '90%' : '80%'}
              >
                <MemorySidebar
                  annotations={annotationsData.annotations}
                  activeAnnotationId={activeAnnotationId}
                  onAnnotationClick={(annotation) => {
                    handleAnnotationClick(annotation, 'sidebar');
                    setSidebarVisible(false);
                  }}
                  scrollToAnnotation={scrollToSidebarAnnotation}
                />
              </Drawer>
            )}
          </>
        )}
        </div>
      </div>
    </div>
  );
};

export default ChapterAnalysis;
