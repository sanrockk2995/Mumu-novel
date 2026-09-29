import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { List, Button, Modal, Form, Input, Select, message, Empty, Space, Badge, Tag, Card, InputNumber, Alert, Radio, Descriptions, Collapse, Popconfirm, Pagination, theme } from 'antd';
import { EditOutlined, FileTextOutlined, ThunderboltOutlined, LockOutlined, DownloadOutlined, SettingOutlined, FundOutlined, SyncOutlined, CheckCircleOutlined, CloseCircleOutlined, RocketOutlined, StopOutlined, InfoCircleOutlined, CaretRightOutlined, DeleteOutlined, BookOutlined, FormOutlined, PlusOutlined, ReadOutlined } from '@ant-design/icons';
import { useStore } from '../store';
import { eventBus, EventNames } from '../store/eventBus';
import { useChapterSync } from '../store/hooks';
import { generateChapterBackground } from '../services/backgroundTaskService';
import { projectApi, writingStyleApi, chapterApi } from '../services/api';
import type { Chapter, ChapterUpdate, ApiError, WritingStyle, AnalysisTask, ExpansionPlanData } from '../types';
import type { TextAreaRef } from 'antd/es/input/TextArea';
import ChapterAnalysis from '../components/ChapterAnalysis';
import ExpansionPlanEditor from '../components/ExpansionPlanEditor';
import { SSELoadingOverlay } from '../components/SSELoadingOverlay';
import ChapterReader from '../components/ChapterReader';
import PartialRegenerateToolbar from '../components/PartialRegenerateToolbar';
import PartialRegenerateModal from '../components/PartialRegenerateModal';

const { TextArea } = Input;

// Tên key cache localStorage
const WORD_COUNT_CACHE_KEY = 'chapter_default_word_count';
const DEFAULT_WORD_COUNT = 3000;

// Đọc số từ đã cache từ localStorage
const getCachedWordCount = (): number => {
  try {
    const cached = localStorage.getItem(WORD_COUNT_CACHE_KEY);
    if (cached) {
      const value = parseInt(cached, 10);
      if (!isNaN(value) && value >= 500 && value <= 10000) {
        return value;
      }
    }
  } catch (error) {
    console.warn('Đọc cache số từ thất bại:', error);
  }
  return DEFAULT_WORD_COUNT;
};

// Lưu số từ vào localStorage
const setCachedWordCount = (value: number): void => {
  try {
    localStorage.setItem(WORD_COUNT_CACHE_KEY, String(value));
  } catch (error) {
    console.warn('Lưu cache số từ thất bại:', error);
  }
};

export default function Chapters() {
  const { currentProject, chapters, outlines, setCurrentChapter, setCurrentProject } = useStore();
  const [modal, contextHolder] = Modal.useModal();
  const { token } = theme.useToken();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [isContinuing, setIsContinuing] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form] = Form.useForm();
  const [editorForm] = Form.useForm();
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);
  const contentTextAreaRef = useRef<TextAreaRef>(null);
  const [writingStyles, setWritingStyles] = useState<WritingStyle[]>([]);
  const [selectedStyleId, setSelectedStyleId] = useState<number | undefined>();
  const [targetWordCount, setTargetWordCount] = useState<number>(getCachedWordCount);
  const [availableModels, setAvailableModels] = useState<Array<{ value: string, label: string }>>([]);
  const [selectedModel, setSelectedModel] = useState<string | undefined>();
  const [batchSelectedModel, setBatchSelectedModel] = useState<string | undefined>(); // Lựa chọn mô hình cho sinh hàng loạt
  const [batchSelectedSkillKey, setBatchSelectedSkillKey] = useState<string | undefined>(); // Lựa chọn Skill cho sinh hàng loạt
  const [temporaryNarrativePerspective, setTemporaryNarrativePerspective] = useState<string | undefined>(); // Lựa chọn ngôi kể tạm thời
  const [availableSkills, setAvailableSkills] = useState<Array<{ template_key: string; template_name: string; description: string; category: string }>>([]);
  const [selectedSkillKey, setSelectedSkillKey] = useState<string | undefined>();
  const [analysisVisible, setAnalysisVisible] = useState(false);
  const [analysisChapterId, setAnalysisChapterId] = useState<string | null>(null);
  // Quản lý trạng thái task phân tích
  const [analysisTasksMap, setAnalysisTasksMap] = useState<Record<string, AnalysisTask>>({});
  const analysisPollingIntervalRef = useRef<number | null>(null);
  const activeAnalysisPollingIdsRef = useRef<Set<string>>(new Set());
  const analysisPollingInFlightRef = useRef(false);
  const analysisPollingRequestIdRef = useRef(0);
  const currentProjectIdRef = useRef<string | undefined>(currentProject?.id);
  currentProjectIdRef.current = currentProject?.id;
  const editingIdRef = useRef<string | null>(editingId);
  editingIdRef.current = editingId;

  // Trạng thái truy vấn danh sách và phân trang
  const [chapterSearchKeyword, setChapterSearchKeyword] = useState('');
  const [chapterPage, setChapterPage] = useState(1);
  const [chapterPageSize, setChapterPageSize] = useState(20);

  // Trạng thái trình đọc
  const [readerVisible, setReaderVisible] = useState(false);
  const [readingChapter, setReadingChapter] = useState<Chapter | null>(null);

  // Trạng thái chỉnh sửa kế hoạch
  const [planEditorVisible, setPlanEditorVisible] = useState(false);
  const [editingPlanChapter, setEditingPlanChapter] = useState<Chapter | null>(null);

  // Trạng thái viết lại cục bộ
  const [partialRegenerateToolbarVisible, setPartialRegenerateToolbarVisible] = useState(false);
  const [partialRegenerateToolbarPosition, setPartialRegenerateToolbarPosition] = useState({ top: 0, left: 0 });
  const [selectedTextForRegenerate, setSelectedTextForRegenerate] = useState('');
  const [selectionStartPosition, setSelectionStartPosition] = useState(0);
  const [selectionEndPosition, setSelectionEndPosition] = useState(0);
  const [partialRegenerateModalVisible, setPartialRegenerateModalVisible] = useState(false);

  // Trạng thái tiến trình sinh một chương
  const [singleChapterProgress, setSingleChapterProgress] = useState(0);
  const [singleChapterProgressMessage, setSingleChapterProgressMessage] = useState('');


  // Trạng thái liên quan sinh hàng loạt
  const [batchGenerateVisible, setBatchGenerateVisible] = useState(false);
  const [batchGenerating, setBatchGenerating] = useState(false);
  const [batchAnalyzingUnanalyzed, setBatchAnalyzingUnanalyzed] = useState(false);
  const [batchTaskId, setBatchTaskId] = useState<string | null>(null);
  const [batchForm] = Form.useForm();
  const [manualCreateForm] = Form.useForm();
  const [batchProgress, setBatchProgress] = useState<{
    status: string;
    total: number;
    completed: number;
    current_chapter_number: number | null;
    estimated_time_minutes?: number;
  } | null>(null);
  const batchPollingIntervalRef = useRef<number | null>(null);

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth <= 768);
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Đọc vùng chọn gốc của textarea. Vùng chọn của textarea không xuất hiện trong window.getSelection(), 
  // và sau khi mất focus selectionStart/selectionEnd vẫn được giữ lại, vì vậy có thể ổn định hỗ trợ kéo ra ngoài khung soạn thảo và bấm ra bên ngoài.
  const getTextAreaSelection = useCallback(() => {
    if (!isEditorOpen || isGenerating) return null;

    const textArea = contentTextAreaRef.current?.resizableTextArea?.textArea;
    if (!textArea) return null;

    const start = textArea.selectionStart;
    const end = textArea.selectionEnd;
    if (end <= start) return null;

    const selectedText = textArea.value.substring(start, end);
    if (selectedText.trim().length < 10) return null;

    return { textArea, start, end, selectedText };
  }, [isEditorOpen, isGenerating]);

  // Xử lý chọn văn bản - phát hiện văn bản được chọn và hiển thị thanh công cụ nổi
  const handleTextSelection = useCallback(() => {
    const currentSelection = getTextAreaSelection();
    if (!currentSelection) {
      setPartialRegenerateToolbarVisible(false);
      return;
    }

    const { textArea, start, end, selectedText: selectedInTextArea } = currentSelection;
    const textContent = textArea.value;

    // Tính vị trí thanh công cụ nổi
    const rect = textArea.getBoundingClientRect();
    const computedStyle = window.getComputedStyle(textArea);
    const lineHeight = parseFloat(computedStyle.lineHeight) || 24;
    const paddingTop = parseFloat(computedStyle.paddingTop) || 0;

    // Tính số dòng của vị trí bắt đầu văn bản được chọn
    const textBeforeSelection = textContent.substring(0, start);
    const startLine = textBeforeSelection.split('\n').length - 1;

    // Tính vị trí trực quan của văn bản được chọn trong textarea, có tính đến độ lệch cuộn bên trong
    const scrollTop = textArea.scrollTop;
    const visualTop = (startLine * lineHeight) + paddingTop - scrollTop;
    const toolbarTop = rect.top + visualTop - 45;
    const toolbarLeft = rect.right - 180;

    setSelectedTextForRegenerate(selectedInTextArea);
    setSelectionStartPosition(start);
    setSelectionEndPosition(end);

    // Nếu vị trí được chọn nằm ngoài vùng nhìn thấy, cố định ở mép textarea
    let finalTop = toolbarTop;
    if (visualTop < 0) {
      finalTop = rect.top + 10;
    } else if (visualTop > textArea.clientHeight) {
      finalTop = rect.bottom - 50;
    }

    setPartialRegenerateToolbarPosition({
      top: Math.max(rect.top + 10, Math.min(finalTop, rect.bottom - 50)),
      left: Math.min(Math.max(rect.left + 20, toolbarLeft), window.innerWidth - 200),
    });
    setPartialRegenerateToolbarVisible(true);
  }, [getTextAreaSelection]);
  // Hàm cập nhật vị trí thanh công cụ (không phát hiện vùng chọn, chỉ cập nhật vị trí)
  const updateToolbarPosition = useCallback(() => {
    if (!partialRegenerateToolbarVisible || !selectedTextForRegenerate) return;
    
    const textArea = contentTextAreaRef.current?.resizableTextArea?.textArea;
    if (!textArea) return;
    
    const rect = textArea.getBoundingClientRect();
    const computedStyle = window.getComputedStyle(textArea);
    const lineHeight = parseFloat(computedStyle.lineHeight) || 24;
    const paddingTop = parseFloat(computedStyle.paddingTop) || 0;
    
    const textContent = textArea.value;
    const textBeforeSelection = textContent.substring(0, selectionStartPosition);
    const startLine = textBeforeSelection.split('\n').length - 1;
    
    const scrollTop = textArea.scrollTop;
    const visualTop = (startLine * lineHeight) + paddingTop - scrollTop;
    
    const toolbarTop = rect.top + visualTop - 45;
    // Cố định ở góc trên bên phải textarea, không thay đổi theo vị trí được chọn
    const toolbarLeft = rect.right - 180;
    
    // Thanh công cụ cố định trong vùng nhìn thấy của textarea, vẫn hiển thị ngay cả khi văn bản được chọn cuộn ra khỏi tầm nhìn
    // Nếu vị trí được chọn trong vùng nhìn thấy, bám theo vị trí được chọn
    // Nếu cuộn ra khỏi tầm nhìn, cố định ở mép trên hoặc dưới
    let finalTop = toolbarTop;
    if (visualTop < 0) {
      // Vị trí được chọn ngoài tầm nhìn phía trên, thanh công cụ cố định ở trên cùng
      finalTop = rect.top + 10;
    } else if (visualTop > textArea.clientHeight) {
      // Vị trí được chọn ngoài tầm nhìn phía dưới, thanh công cụ cố định ở dưới cùng
      finalTop = rect.bottom - 50;
    }
    
    setPartialRegenerateToolbarPosition({
      top: Math.max(rect.top + 10, Math.min(finalTop, rect.bottom - 50)),
      left: Math.min(Math.max(rect.left + 20, toolbarLeft), window.innerWidth - 200),
    });
  }, [partialRegenerateToolbarVisible, selectedTextForRegenerate, selectionStartPosition]);

  // Lắng nghe sự kiện chọn
  useEffect(() => {
    if (!isEditorOpen) return;

    const textArea = contentTextAreaRef.current?.resizableTextArea?.textArea;
    if (!textArea) return;

    const handleMouseUp = (event: MouseEvent) => {
      const target = event.target;
      if (target instanceof Element && target.closest('[data-partial-regenerate-toolbar]')) return;

      // Lắng nghe ở cấp document, kéo ra ngoài textarea rồi thả chuột vẫn bắt được vùng chọn.
      window.setTimeout(handleTextSelection, 0);
    };

    const handleKeyUp = () => {
      // Mở rộng vùng chọn bằng bàn phím, thu hẹp và xóa vùng chọn đều xử lý bằng logic thống nhất.
      window.setTimeout(handleTextSelection, 0);
    };

    const handleSelect = () => {
      // Sự kiện select gốc của textarea đáng tin cậy hơn window.selection.
      handleTextSelection();
    };
    const handleScroll = () => {
      // Cập nhật vị trí khi cuộn (dùng requestAnimationFrame để tối ưu hiệu năng)
      requestAnimationFrame(updateToolbarPosition);
    };

    // Lắng nghe cuộn textarea
    document.addEventListener('mouseup', handleMouseUp, true);
    textArea.addEventListener('keyup', handleKeyUp);
    textArea.addEventListener('select', handleSelect);
    textArea.addEventListener('scroll', handleScroll);

    // Đồng thời lắng nghe cuộn Modal body (nội dung Modal có thể cuộn trong container ngoài)
    const modalBody = textArea.closest('.ant-modal-body');
    if (modalBody) {
      modalBody.addEventListener('scroll', handleScroll);
    }

    // Lắng nghe thay đổi kích thước cửa sổ
    window.addEventListener('resize', handleScroll);

    return () => {
      document.removeEventListener('mouseup', handleMouseUp, true);
      textArea.removeEventListener('keyup', handleKeyUp);
      textArea.removeEventListener('select', handleSelect);
      textArea.removeEventListener('scroll', handleScroll);
      if (modalBody) {
        modalBody.removeEventListener('scroll', handleScroll);
      }
      window.removeEventListener('resize', handleScroll);
    };
  }, [isEditorOpen, handleTextSelection, updateToolbarPosition]);



  const {
    refreshChapters,
    updateChapter,
    deleteChapter,
    generateChapterContentStream
  } = useChapterSync();

  useEffect(() => {
    if (currentProject?.id) {
      const projectId = currentProject.id;
      if (analysisPollingIntervalRef.current !== null) {
        clearInterval(analysisPollingIntervalRef.current);
        analysisPollingIntervalRef.current = null;
      }
      analysisPollingRequestIdRef.current += 1;
      analysisPollingInFlightRef.current = false;
      activeAnalysisPollingIdsRef.current.clear();
      setAnalysisTasksMap({});

      void refreshChapters(projectId).then((latestChapters) => {
        if (currentProjectIdRef.current === projectId) {
          void loadAnalysisTasks(latestChapters, projectId);
        }
      });
      loadWritingStyles();
      checkAndRestoreBatchTask();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentProject?.id]);

  // Dọn dẹp timer polling
  useEffect(() => {
    return () => {
      if (analysisPollingIntervalRef.current !== null) {
        clearInterval(analysisPollingIntervalRef.current);
        analysisPollingIntervalRef.current = null;
      }
      if (batchPollingIntervalRef.current !== null) {
        clearInterval(batchPollingIntervalRef.current);
        batchPollingIntervalRef.current = null;
      }
    };
  }, []);

  const clearAnalysisPollingIfIdle = useCallback(() => {
    if (activeAnalysisPollingIdsRef.current.size === 0 && analysisPollingIntervalRef.current) {
      clearInterval(analysisPollingIntervalRef.current);
      analysisPollingIntervalRef.current = null;
    }
  }, []);

  const pollActiveAnalysisTasks = useCallback(async () => {
    const projectId = currentProjectIdRef.current;
    if (!projectId || analysisPollingInFlightRef.current) return;

    const activeIds = Array.from(activeAnalysisPollingIdsRef.current);
    if (activeIds.length === 0) {
      clearAnalysisPollingIfIdle();
      return;
    }

    analysisPollingInFlightRef.current = true;
    const requestId = analysisPollingRequestIdRef.current + 1;
    analysisPollingRequestIdRef.current = requestId;

    try {
      const response = await chapterApi.getBatchAnalysisStatuses(projectId, activeIds);
      if (currentProjectIdRef.current !== projectId) return;

      const tasksMap = response.items || {};

      setAnalysisTasksMap(prev => ({
        ...prev,
        ...tasksMap,
      }));

      activeIds.forEach((chapterId) => {
        const task = tasksMap[chapterId];
        if (!task || task.status === 'completed' || task.status === 'failed' || task.status === 'none') {
          activeAnalysisPollingIdsRef.current.delete(chapterId);

          if (task?.status === 'completed') {
            message.success('Phân tích chương hoàn tất');
          } else if (task?.status === 'failed') {
            message.error(`Phân tích chương thất bại: ${task.error_message || 'Lỗi không xác định'}`);
          }
        }
      });

      clearAnalysisPollingIfIdle();
    } catch (error) {
      console.error('Polling hàng loạt task phân tích thất bại:', error);
    } finally {
      if (analysisPollingRequestIdRef.current === requestId) {
        analysisPollingInFlightRef.current = false;
      }
    }
  }, [clearAnalysisPollingIfIdle]);

  const ensureAnalysisPolling = useCallback(() => {
    if (analysisPollingIntervalRef.current) return;

    analysisPollingIntervalRef.current = window.setInterval(() => {
      void pollActiveAnalysisTasks();
    }, 2000);

    // Thực hiện ngay một lần
    void pollActiveAnalysisTasks();
  }, [pollActiveAnalysisTasks]);

  // Tải trạng thái task phân tích của mọi chương (API hàng loạt, tránh bão request từng chương)
  // Nhận tham số chaptersToLoad tùy chọn, giải quyết vấn đề trễ cập nhật state của React
  const loadAnalysisTasks = useCallback(async (
    chaptersToLoad?: typeof chapters,
    projectId?: string,
  ) => {
    const targetChapters = chaptersToLoad || chapters;
    const targetProjectId = projectId || currentProjectIdRef.current;
    if (!targetChapters || targetChapters.length === 0 || !targetProjectId) return;

    const chapterIds = targetChapters
      .filter(chapter => chapter.content && chapter.content.trim() !== '')
      .map(chapter => chapter.id);

    if (chapterIds.length === 0) {
      setAnalysisTasksMap({});
      activeAnalysisPollingIdsRef.current.clear();
      clearAnalysisPollingIfIdle();
      return;
    }

    try {
      const response = await chapterApi.getBatchAnalysisStatuses(targetProjectId, chapterIds);
      if (currentProjectIdRef.current !== targetProjectId) return;

      const tasksMap = response.items || {};
      setAnalysisTasksMap(tasksMap);

      activeAnalysisPollingIdsRef.current.clear();
      Object.entries(tasksMap).forEach(([chapterId, task]) => {
        if (task?.status === 'pending' || task?.status === 'running') {
          activeAnalysisPollingIdsRef.current.add(chapterId);
        }
      });

      if (activeAnalysisPollingIdsRef.current.size > 0) {
        ensureAnalysisPolling();
      } else {
        clearAnalysisPollingIfIdle();
      }
    } catch (error) {
      console.error('Tải hàng loạt trạng thái task phân tích thất bại:', error);
    }
  }, [chapters, clearAnalysisPollingIfIdle, ensureAnalysisPolling]);

  useEffect(() => {
    const handleTaskSettled = (payload?: unknown) => {
      if (!payload || typeof payload !== 'object') return;
      const data = payload as { projectId?: string; resources?: string[] };
      if (data.projectId && data.projectId !== currentProjectIdRef.current) return;
      if (!data.resources?.includes('analysis')) return;
      void refreshChapters().then(latestChapters => loadAnalysisTasks(latestChapters));
    };
    eventBus.on(EventNames.BACKGROUND_TASK_SETTLED, handleTaskSettled);
    return () => eventBus.off(EventNames.BACKGROUND_TASK_SETTLED, handleTaskSettled);
  }, [loadAnalysisTasks, refreshChapters]);

  // Khởi động polling task cho một chương (nội bộ gộp vào polling hàng loạt)
  const startPollingTask = (chapterId: string) => {
    activeAnalysisPollingIdsRef.current.add(chapterId);
    ensureAnalysisPolling();
  };

  const loadWritingStyles = async () => {
    if (!currentProject?.id) return;

    try {
      const response = await writingStyleApi.getProjectStyles(currentProject.id);
      setWritingStyles(response.styles);

      // Đặt phong cách mặc định làm lựa chọn ban đầu
      const defaultStyle = response.styles.find(s => s.is_default);
      if (defaultStyle) {
        setSelectedStyleId(defaultStyle.id);
      }
    } catch (error) {
      console.error('Tải phong cách viết thất bại:', error);
      message.error('Tải phong cách viết thất bại');
    }
  };

  // Tải danh sách Skill khả dụng
  const loadAvailableSkills = async () => {
    try {
      const response = await fetch('/api/skills/list');
      if (response.ok) {
        const data = await response.json();
        if (Array.isArray(data)) {
          setAvailableSkills(data);
        }
      }
    } catch (error) {
      console.error('Tải danh sách Skill thất bại:', error);
    }
  };

  const loadAvailableModels = async () => {
    try {
      // Lấy danh sách mô hình người dùng đã cấu hình từ API cài đặt
      const settingsResponse = await fetch('/api/settings');
      if (settingsResponse.ok) {
        const settings = await settingsResponse.json();
        const { api_key, api_base_url, api_provider } = settings;

        if (api_base_url) {
          try {
            const modelsResponse = await fetch(
              `/api/settings/models?api_key=${encodeURIComponent(api_key || '')}&api_base_url=${encodeURIComponent(api_base_url)}&provider=${api_provider}`
            );
            if (modelsResponse.ok) {
              const data = await modelsResponse.json();
              if (data.models && data.models.length > 0) {
                setAvailableModels(data.models);
                // Đặt mô hình mặc định thành mô hình đang cấu hình
                setSelectedModel(settings.llm_model);
                return settings.llm_model; // Trả về tên mô hình
              }
            }
          } catch {
            console.log('Lấy danh sách mô hình thất bại, sẽ dùng mô hình mặc định');
          }
        }
      }
    } catch (error) {
      console.error('Tải mô hình khả dụng thất bại:', error);
    }
    return null;
  };

  // Kiểm tra và khôi phục task sinh hàng loạt
  const checkAndRestoreBatchTask = async () => {
    if (!currentProject?.id) return;

    try {
      const response = await fetch(`/api/chapters/project/${currentProject.id}/batch-generate/active`);
      if (!response.ok) return;

      const data = await response.json();

      if (data.has_active_task && data.task) {
        const task = data.task;

        // Khôi phục trạng thái task (chỉ hiển thị trên thanh tiến trình trên cùng, không bật Modal)
        setBatchTaskId(task.batch_id);
        setBatchProgress({
          status: task.status,
          total: task.total,
          completed: task.completed,
          current_chapter_number: task.current_chapter_number,
        });
        setBatchGenerating(true);
        // Không đặt setBatchGenerateVisible(true) để tránh Modal bật lên che trang

        // Khởi động polling
        startBatchPolling(task.batch_id);

        message.info('Phát hiện task sinh hàng loạt chưa hoàn tất, vui lòng xem danh sách task');
      }
    } catch (error) {
      console.error('Kiểm tra task sinh hàng loạt thất bại:', error);
    }
  };

  // 🔔 Hiển thị thông báo trình duyệt
  const showBrowserNotification = (title: string, body: string, type: 'success' | 'error' | 'info' = 'info') => {
    // Kiểm tra trình duyệt có hỗ trợ thông báo không
    if (!('Notification' in window)) {
      console.log('Trình duyệt không hỗ trợ tính năng thông báo');
      return;
    }

    // Kiểm tra quyền thông báo
    if (Notification.permission === 'granted') {
      // Chọn icon
      const icon = type === 'success' ? '/logo.svg' : type === 'error' ? '/favicon.ico' : '/logo.svg';
      
      const notification = new Notification(title, {
        body,
        icon,
        badge: '/favicon.ico',
        tag: 'batch-generation', // tag giống nhau sẽ thay thế thông báo cũ
        requireInteraction: false, // Tự động đóng
        silent: false, // Phát âm báo
      });

      // Focus vào cửa sổ khi bấm thông báo
      notification.onclick = () => {
        window.focus();
        notification.close();
      };

      // Tự động đóng sau 5 giây
      setTimeout(() => {
        notification.close();
      }, 5000);
    } else if (Notification.permission !== 'denied') {
      // Nếu quyền chưa bị từ chối rõ ràng, thử yêu cầu quyền
      Notification.requestPermission().then(permission => {
        if (permission === 'granted') {
          showBrowserNotification(title, body, type);
        }
      });
    }
  };

  // Sắp xếp theo số chương và nhóm chương theo dàn ý (phải gọi trước early return để tránh vi phạm quy tắc Hooks)
  const { sortedChapters } = useMemo(() => {
    const sorted = [...chapters].sort((a, b) => a.chapter_number - b.chapter_number);

    const groups: Record<string, {
      outlineId: string | null;
      outlineTitle: string;
      outlineOrder: number;
      chapters: Chapter[];
    }> = {};

    sorted.forEach(chapter => {
      const key = chapter.outline_id || 'uncategorized';

      if (!groups[key]) {
        groups[key] = {
          outlineId: chapter.outline_id || null,
          outlineTitle: chapter.outline_title || 'Chương chưa phân loại',
          outlineOrder: chapter.outline_order ?? 999,
          chapters: []
        };
      }

      groups[key].chapters.push(chapter);
    });

    return { sortedChapters: sorted };
  }, [chapters]);

  // Lọc truy vấn chương (lọc ở frontend, giảm áp lực render)
  const filteredSortedChapters = useMemo(() => {
    const keyword = chapterSearchKeyword.trim().toLowerCase();
    if (!keyword) return sortedChapters;

    return sortedChapters.filter((chapter) => {
      return (
        String(chapter.chapter_number).includes(keyword) ||
        chapter.title.toLowerCase().includes(keyword) ||
        (chapter.outline_title || '').toLowerCase().includes(keyword)
      );
    });
  }, [sortedChapters, chapterSearchKeyword]);

  // Danh sách chương phẳng sau phân trang
  const pagedSortedChapters = useMemo(() => {
    const start = (chapterPage - 1) * chapterPageSize;
    return filteredSortedChapters.slice(start, start + chapterPageSize);
  }, [filteredSortedChapters, chapterPage, chapterPageSize]);

  // Chế độ one-to-many phân trang rồi mới nhóm theo dàn ý
  const pagedGroupedChapters = useMemo(() => {
    const groups: Record<string, {
      outlineId: string | null;
      outlineTitle: string;
      outlineOrder: number;
      chapters: Chapter[];
    }> = {};

    pagedSortedChapters.forEach(chapter => {
      const key = chapter.outline_id || 'uncategorized';
      if (!groups[key]) {
        groups[key] = {
          outlineId: chapter.outline_id || null,
          outlineTitle: chapter.outline_title || 'Chương chưa phân loại',
          outlineOrder: chapter.outline_order ?? 999,
          chapters: []
        };
      }
      groups[key].chapters.push(chapter);
    });

    return Object.values(groups).sort((a, b) => a.outlineOrder - b.outlineOrder);
  }, [pagedSortedChapters]);

  // Đặt lại về trang đầu khi từ khóa tìm kiếm hoặc kích thước trang thay đổi
  useEffect(() => {
    setChapterPage(1);
  }, [chapterSearchKeyword, chapterPageSize, currentProject?.outline_mode]);

  // Tự động sửa khi dữ liệu thay đổi khiến số trang vượt giới hạn
  useEffect(() => {
    const maxPage = Math.max(1, Math.ceil(filteredSortedChapters.length / chapterPageSize));
    if (chapterPage > maxPage) {
      setChapterPage(maxPage);
    }
  }, [filteredSortedChapters.length, chapterPage, chapterPageSize]);

  // Tính trước trạng thái có thể sinh của mỗi chương, tránh quét O(n²) lặp lại ở giai đoạn render
  const chapterGenerateGateMap = useMemo(() => {
    const gateMap: Record<string, { canGenerate: boolean; reason: string }> = {};
    const incompleteChapterNumbers: number[] = [];
    const unanalyzedChapters: Array<{ chapterNumber: number; reason: string }> = [];

    sortedChapters.forEach((chapter) => {
      if (incompleteChapterNumbers.length > 0) {
        gateMap[chapter.id] = {
          canGenerate: false,
          reason: `Cần hoàn thành chương tiền đề trước: chương ${incompleteChapterNumbers.join('、')}`
        };
      } else if (unanalyzedChapters.length > 0) {
        gateMap[chapter.id] = {
          canGenerate: false,
          reason: `Cần phân tích chương tiền đề trước: chương ${unanalyzedChapters.map(c => c.chapterNumber).join('、')} (${unanalyzedChapters.map(c => c.reason).join('、')})`
        };
      } else {
        gateMap[chapter.id] = { canGenerate: true, reason: '' };
      }

      // Đưa chương hiện tại vào điều kiện tiền đề của "các chương tiếp theo"
      if (!chapter.content || chapter.content.trim() === '') {
        incompleteChapterNumbers.push(chapter.chapter_number);
      }

      const task = analysisTasksMap[chapter.id];
      if (!task || !task.has_task) {
        unanalyzedChapters.push({ chapterNumber: chapter.chapter_number, reason: 'Chưa phân tích' });
      } else if (task.status === 'pending') {
        unanalyzedChapters.push({ chapterNumber: chapter.chapter_number, reason: 'Đang chờ phân tích' });
      } else if (task.status === 'running') {
        unanalyzedChapters.push({ chapterNumber: chapter.chapter_number, reason: 'Đang phân tích' });
      } else if (task.status === 'failed') {
        unanalyzedChapters.push({ chapterNumber: chapter.chapter_number, reason: 'Phân tích thất bại' });
      } else if (task.status !== 'completed') {
        unanalyzedChapters.push({ chapterNumber: chapter.chapter_number, reason: 'Trạng thái không xác định' });
      }
    });

    return gateMap;
  }, [sortedChapters, analysisTasksMap]);

  // Chương hiện có thể "phân tích một chạm" (có nội dung và chưa ở trạng thái hoàn tất/đang tiến hành)
  const batchAnalyzableChapterCount = useMemo(() => {
    return sortedChapters.filter((chapter) => {
      if (!chapter.content || chapter.content.trim() === '') return false;
      const task = analysisTasksMap[chapter.id];
      if (!task || !task.has_task) return true;
      return task.status !== 'completed' && task.status !== 'pending' && task.status !== 'running';
    }).length;
  }, [sortedChapters, analysisTasksMap]);

  if (!currentProject) return null;

  // Lấy text hiển thị ngôi kể (hỗ trợ cả giá trị Trung/Anh)
  const getNarrativePerspectiveText = (perspective?: string): string => {
    const texts: Record<string, string> = {
      // Ánh xạ giá trị tiếng Anh (tương thích ngược)
      'first_person': 'Ngôi thứ nhất (tôi)',
      'third_person': 'Ngôi thứ ba (anh ấy/cô ấy)',
      'omniscient': 'Góc nhìn toàn tri',
      // Ánh xạ giá trị tiếng Trung (cài đặt dự án dùng)
      '第一人称': 'Ngôi thứ nhất (tôi)',
      '第三人称': 'Ngôi thứ ba (anh ấy/cô ấy)',
      '全知视角': 'Góc nhìn toàn tri',
    };
    return texts[perspective || ''] || 'Ngôi thứ ba (mặc định)';
  };

  const canGenerateChapter = (chapter: Chapter): boolean => {
    return chapterGenerateGateMap[chapter.id]?.canGenerate ?? true;
  };

  const getGenerateDisabledReason = (chapter: Chapter): string => {
    return chapterGenerateGateMap[chapter.id]?.reason || '';
  };

  const handleOpenModal = (id: string) => {
    const chapter = chapters.find(c => c.id === id);
    if (chapter) {
      form.setFieldsValue(chapter);
      setEditingId(id);
      setIsModalOpen(true);
    }
  };

  const handleSubmit = async (values: ChapterUpdate) => {
    if (!editingId) return;

    try {
      await updateChapter(editingId, values);

      // Refresh danh sách chương để lấy dữ liệu chương đầy đủ (gồm các trường join như outline_title)
      await refreshChapters();

      message.success('Cập nhật chương thành công');
      setIsModalOpen(false);
      form.resetFields();
    } catch {
      message.error('Thao tác thất bại');
    }
  };

  const handleOpenEditor = (id: string) => {
    const chapter = chapters.find(c => c.id === id);
    if (chapter) {
      setCurrentChapter(chapter);
      editorForm.setFieldsValue({
        title: chapter.title,
        content: chapter.content,
      });
      setEditingId(id);
      setTemporaryNarrativePerspective(undefined); // Đặt lại lựa chọn ngôi kể
      setSelectedSkillKey(undefined); // Đặt lại lựa chọn Skill
      setIsEditorOpen(true);
      // Tải danh sách mô hình và danh sách Skill khi mở cửa sổ chỉnh sửa
      loadAvailableModels();
      loadAvailableSkills();
    }
  };

  const handleEditorSubmit = async (values: ChapterUpdate) => {
    if (!editingId || !currentProject) return;

    try {
      await updateChapter(editingId, values);

      // Refresh thông tin dự án để cập nhật thống kê tổng số từ
      const updatedProject = await projectApi.getProject(currentProject.id);
      setCurrentProject(updatedProject);

      message.success('Lưu chương thành công');
      setIsEditorOpen(false);
    } catch {
      message.error('Lưu thất bại');
    }
  };

  const handleGenerate = async () => {
    if (!editingId) return;

    try {
      setIsContinuing(true);
      setIsGenerating(true);
      setSingleChapterProgress(0);
      setSingleChapterProgressMessage('Chuẩn bị bắt đầu sinh...');

      const result = await generateChapterContentStream(
        editingId,
        (content) => {
          editorForm.setFieldsValue({ content });

          if (contentTextAreaRef.current) {
            const textArea = contentTextAreaRef.current.resizableTextArea?.textArea;
            if (textArea) {
              textArea.scrollTop = textArea.scrollHeight;
            }
          }
        },
        selectedStyleId,
        targetWordCount,
        (progressMsg, progressValue) => {
          // Callback tiến trình
          setSingleChapterProgress(progressValue);
          setSingleChapterProgressMessage(progressMsg);
        },
        selectedModel,  // Truyền mô hình đã chọn
        temporaryNarrativePerspective,  // Truyền tham số ngôi kể tạm thời
        selectedSkillKey  // Truyền Skill đã chọn
      );

      message.success('AI sáng tác thành công, đang phân tích nội dung chương...');

      // Nếu trả về ID task phân tích, khởi động polling
      if (result?.analysis_task_id) {
        const taskId = result.analysis_task_id;
        setAnalysisTasksMap(prev => ({
          ...prev,
          [editingId]: {
            has_task: true,
            task_id: taskId,
            chapter_id: editingId,
            status: 'pending',
            progress: 0
          }
        }));

        // Khởi động polling
        startPollingTask(editingId);
      }
    } catch (error) {
      const apiError = error as ApiError;
      message.error('AI sáng tác thất bại: ' + (apiError.response?.data?.detail || apiError.message || 'Lỗi không xác định'));
    } finally {
      setIsContinuing(false);
      setIsGenerating(false);
      setSingleChapterProgress(0);
      setSingleChapterProgressMessage('');
    }
  };

  const showGenerateModal = (chapter: Chapter) => {
    const previousChapters = chapters.filter(
      c => c.chapter_number < chapter.chapter_number
    ).sort((a, b) => a.chapter_number - b.chapter_number);

    const selectedStyle = writingStyles.find(s => s.id === selectedStyleId);

    const instance = modal.confirm({
      title: 'AI sáng tác nội dung chương',
      width: 700,
      centered: true,
      content: (
        <div style={{ marginTop: 16 }}>
          <p>AI sẽ sáng tác nội dung chương này dựa trên các thông tin sau:</p>
          <ul>
            <li>Dàn ý và yêu cầu của chương</li>
            <li>Thiết lập thế giới quan của dự án</li>
            <li>Thông tin nhân vật liên quan</li>
            <li><strong>Nội dung các chương đã hoàn thành trước đó (đảm bảo cốt truyện liền mạch)</strong></li>
            {selectedStyle && (
              <li><strong>Phong cách viết:{selectedStyle.name}</strong></li>
            )}
            <li><strong>Số từ mục tiêu:{targetWordCount} từ</strong></li>
          </ul>

          {previousChapters.length > 0 && (
            <div style={{
              marginTop: 16,
              padding: 12,
              background: token.colorInfoBg,
              borderRadius: token.borderRadius,
              border: `1px solid ${token.colorInfoBorder}`
            }}>
              <div style={{ marginBottom: 8, fontWeight: 500, color: token.colorPrimary }}>
                📚 Các chương tiền đề sẽ trích dẫn (tổng {previousChapters.length} chương):
              </div>
              <div style={{ maxHeight: 150, overflowY: 'auto' }}>
                {previousChapters.map(ch => (
                  <div key={ch.id} style={{ padding: '4px 0', fontSize: 13 }}>
                    ✓ Chương {ch.chapter_number}: {ch.title} ({ch.word_count || 0} từ)
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 8, fontSize: 12, color: token.colorTextSecondary }}>
                💡 AI sẽ tham khảo nội dung các chương này để đảm bảo tình tiết liền mạch, trạng thái nhân vật nhất quán
              </div>
            </div>
          )}

          <p style={{ color: token.colorError, marginTop: 16, marginBottom: 0 }}>
            ⚠️ Lưu ý: thao tác này sẽ ghi đè nội dung chương hiện tại
          </p>
        </div>
      ),
      okText: 'Bắt đầu sáng tác',
      okButtonProps: { danger: true },
      cancelText: 'Hủy',
      onOk: async () => {
        instance.update({
          okButtonProps: { danger: true, loading: true },
          cancelButtonProps: { disabled: true },
          closable: false,
          maskClosable: false,
          keyboard: false,
        });

        try {
          if (!selectedStyleId) {
            message.error('Vui lòng chọn phong cách viết trước');
            instance.update({
              okButtonProps: { danger: true, loading: false },
              cancelButtonProps: { disabled: false },
              closable: true,
              maskClosable: true,
              keyboard: true,
            });
            return;
          }
          await handleGenerate();
          instance.destroy();
        } catch {
          instance.update({
            okButtonProps: { danger: true, loading: false },
            cancelButtonProps: { disabled: false },
            closable: true,
            maskClosable: true,
            keyboard: true,
          });
        }
      },
      onCancel: () => {
        if (isGenerating) {
          message.warning('AI đang sáng tác, vui lòng chờ hoàn tất');
          return false;
        }
      },
    });
  };


  // Sinh chương trong nền (đóng trình duyệt cũng không ảnh hưởng)
  // Không còn bắt buộc hiển thị popup tiến trình, tiến độ task hiển thị trong khung task nổi ở góc dưới bên phải
  const handleBackgroundGenerate = async () => {
    if (!editingId) return;
    if (!selectedStyleId) {
      message.error("Vui lòng chọn phong cách viết trước");
      return;
    }

    try {
      const generatedChapterId = editingId;
      const generatedProjectId = currentProject?.id;
      let analysisTrackingStarted = false;

      const refreshGeneratedChapter = async () => {
        if (!generatedProjectId || currentProjectIdRef.current !== generatedProjectId) return [];

        const latestChapters = await refreshChapters(generatedProjectId);
        const latestChapter = latestChapters.find(chapter => chapter.id === generatedChapterId);
        if (latestChapter && editingIdRef.current === generatedChapterId) {
          setCurrentChapter(latestChapter);
          editorForm.setFieldsValue({
            title: latestChapter.title,
            content: latestChapter.content,
          });
        }

        projectApi.getProject(generatedProjectId).then(setCurrentProject).catch(console.error);
        return latestChapters;
      };

      await generateChapterBackground(
        generatedChapterId,
        {
          style_id: selectedStyleId,
          target_word_count: targetWordCount,
          model: selectedModel,
          narrative_perspective: temporaryNarrativePerspective,
        },
        async (status) => {
          if (status.progress_details?.stage !== 'analyzing' || analysisTrackingStarted) return;

          analysisTrackingStarted = true;
          const latestChapters = await refreshGeneratedChapter();
          await loadAnalysisTasks(latestChapters);
        },
        async () => {
          message.success("Sinh chương và phân tích trong nền hoàn tất!");
          const latestChapters = await refreshGeneratedChapter();
          await loadAnalysisTasks(latestChapters);
        },
        async (error) => {
          message.error("Task chương nền thất bại: " + error);
          const latestChapters = await refreshGeneratedChapter();
          await loadAnalysisTasks(latestChapters);
        }
      );

      message.info("Task sinh chương đã được gửi, có thể xem tiến độ trong panel task ở góc dưới bên phải");
      // Thông báo khung task nổi refresh
      eventBus.emit('background-task-created');
    } catch {
      message.error("Tạo task nền thất bại");
    }
  };
  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      'draft': 'default',
      'pending': 'warning',
      'writing': 'processing',
      'completed': 'success',
    };
    return colors[status] || 'default';
  };

  const getStatusText = (status: string) => {
    const texts: Record<string, string> = {
      'draft': 'Bản nháp',
      'pending': 'Đang chờ',
      'writing': 'Đang sáng tác',
      'completed': 'Đã hoàn thành',
    };
    return texts[status] || status;
  };

  const handleExport = () => {
    if (chapters.length === 0) {
      message.warning('Dự án hiện tại không có chương, không thể xuất');
      return;
    }

    modal.confirm({
      title: 'Xuất chương của dự án',
      content: `Bạn có chắc muốn xuất mọi chương của "${currentProject.title}" thành tệp TXT không?`,
      centered: true,
      okText: 'Xác nhận xuất',
      cancelText: 'Hủy',
      onOk: () => {
        try {
          projectApi.exportProject(currentProject.id);
          message.success('Bắt đầu tải tệp xuất');
        } catch {
          message.error('Xuất thất bại, vui lòng thử lại');
        }
      },
    });
  };

  const handleShowAnalysis = (chapterId: string) => {
    setAnalysisChapterId(chapterId);
    setAnalysisVisible(true);
  };

  // Phân tích một chạm các chương chưa phân tích theo thứ tự chương
  const handleBatchAnalyzeUnanalyzed = async () => {
    if (!currentProject?.id) return;

    try {
      setBatchAnalyzingUnanalyzed(true);
      const result = await chapterApi.batchAnalyzeUnanalyzed(currentProject.id);

      if (result.total_started > 0) {
        setAnalysisTasksMap((prev) => ({
          ...prev,
          ...result.started_tasks,
        }));

        Object.keys(result.started_tasks).forEach((chapterId) => {
          startPollingTask(chapterId);
        });

        message.success(
          `Đã thêm  ${result.total_started}  chương vào hàng đợi phân tích tuần tự (bỏ qua  ${result.total_already_completed}  chương đã phân tích, /đang xếp hàng ${result.total_skipped_running}  chương)`
        );
      } else {
        message.info('Không có chương nào để khởi động phân tích: chương hiện tại hoặc không có nội dung, hoặc đã phân tích xong, hoặc đang phân tích');
      }

      // Refresh trạng thái một lần để đảm bảo frontend và backend đồng nhất
      await loadAnalysisTasks();
    } catch (error: unknown) {
      const err = error as Error;
      message.error(`Phân tích một chạm thất bại: ${err.message || 'Lỗi không xác định'}`);
    } finally {
      setBatchAnalyzingUnanalyzed(false);
    }
  };

  // Hàm sinh hàng loạt
  const handleBatchGenerate = async (values: {
    startChapterNumber: number;
    count: number;
    enableAnalysis: boolean;
    styleId?: number;
    targetWordCount?: number;
    model?: string;
  }) => {
    if (!currentProject?.id) return;

    // Log gỡ lỗi
    console.log('[Sinh hàng loạt] giá trị form:', values);
    console.log('[Sinh hàng loạt] trạng thái batchSelectedModel:', batchSelectedModel);

    // Dùng phong cách và số từ đã chọn trong hộp thoại sinh hàng loạt, nếu không chọn thì dùng giá trị mặc định
    const styleId = values.styleId || selectedStyleId;
    const wordCount = values.targetWordCount || targetWordCount;

    // Dùng state mô hình chuyên cho sinh hàng loạt
    const model = batchSelectedModel;

    console.log('[Sinh hàng loạt] model dùng cuối cùng:', model);

    if (!styleId) {
      message.error('Vui lòng chọn phong cách viết');
      return;
    }

    try {
      setBatchGenerating(true);
      setBatchGenerateVisible(false); // Đóng hộp thoại cấu hình, tiến độ task hiển thị trong khung task nổi

      const requestBody: {
        start_chapter_number: number;
        count: number;
        enable_analysis: boolean;
        style_id: number;
        target_word_count: number;
        model?: string;
        skill_key?: string;
      } = {
        start_chapter_number: values.startChapterNumber,
        count: values.count,
        enable_analysis: values.enableAnalysis,
        style_id: styleId,
        target_word_count: wordCount,
      };

      // Nếu có tham số mô hình, thêm vào request body
      if (model) {
        requestBody.model = model;
        console.log('[Sinh hàng loạt] request body chứa model:', model);
      } else {
        console.log('[Sinh hàng loạt] request body không chứa model, dùng mô hình mặc định của backend');
      }

      // Nếu có tham số Skill, thêm vào request body
      if (batchSelectedSkillKey) {
        requestBody.skill_key = batchSelectedSkillKey;
        console.log('[Sinh hàng loạt] request body chứa skill_key:', batchSelectedSkillKey);
      }

      console.log('[Sinh hàng loạt] request body đầy đủ:', JSON.stringify(requestBody, null, 2));

      const response = await fetch(`/api/chapters/project/${currentProject.id}/batch-generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Tạo task sinh hàng loạt thất bại');
      }

      const result = await response.json();
      setBatchTaskId(result.batch_id);
      setBatchProgress({
        status: 'running',
        total: result.chapters_to_generate.length,
        completed: 0,
        current_chapter_number: values.startChapterNumber,
        estimated_time_minutes: result.estimated_time_minutes,
      });

      message.success(`Task sinh hàng loạt đã được tạo, dự kiến cần  ${result.estimated_time_minutes}  phút, có thể xem tiến độ trong panel task ở góc dưới bên phải`);
      // Thông báo khung task nổi refresh
      eventBus.emit('background-task-created');

      // 🔔 Kích hoạt thông báo trình duyệt (task bắt đầu)
      showBrowserNotification(
        'Sinh hàng loạt đã khởi động',
        `Bắt đầu sinh  ${result.chapters_to_generate.length}  chương, dự kiến cần  ${result.estimated_time_minutes}  phút`,
        'info'
      );

      // Bắt đầu polling trạng thái task
      startBatchPolling(result.batch_id);

    } catch (error: unknown) {
      const err = error as Error;
      message.error('Tạo task sinh hàng loạt thất bại: ' + (err.message || 'Lỗi không xác định'));
      setBatchGenerating(false);
      setBatchGenerateVisible(false);
    }
  };

  // Polling trạng thái task sinh hàng loạt
  const startBatchPolling = (taskId: string) => {
    if (batchPollingIntervalRef.current) {
      clearInterval(batchPollingIntervalRef.current);
    }

    const poll = async () => {
      try {
        const response = await fetch(`/api/chapters/batch-generate/${taskId}/status`);
        if (!response.ok) return;

        const status = await response.json();
        setBatchProgress({
          status: status.status,
          total: status.total,
          completed: status.completed,
          current_chapter_number: status.current_chapter_number,
        });

        // Mỗi lần polling refresh danh sách chương và trạng thái phân tích, hiển thị realtime chương mới sinh và tiến độ phân tích
        // Dùng await để đảm bảo lấy danh sách chương mới nhất rồi mới tải trạng thái task phân tích
        if (status.completed > 0) {
          const latestChapters = await refreshChapters();
          await loadAnalysisTasks(latestChapters);

          // Refresh thông tin dự án để cập nhật realtime thống kê tổng số từ
          if (currentProject?.id) {
            const updatedProject = await projectApi.getProject(currentProject.id);
            setCurrentProject(updatedProject);
          }
        }

        // Task hoàn tất hoặc thất bại thì dừng polling
        if (status.status === 'completed' || status.status === 'failed' || status.status === 'cancelled') {
          if (batchPollingIntervalRef.current) {
            clearInterval(batchPollingIntervalRef.current);
            batchPollingIntervalRef.current = null;
          }

          setBatchGenerating(false);

          // Refresh ngay danh sách chương và trạng thái task phân tích (trước khi hiển thị message)
          // Dùng danh sách chương mới nhất do refreshChapters trả về để truyền cho loadAnalysisTasks
          const finalChapters = await refreshChapters();
          await loadAnalysisTasks(finalChapters);

          // Refresh thông tin dự án để cập nhật thống kê tổng số từ
          if (currentProject?.id) {
            const updatedProject = await projectApi.getProject(currentProject.id);
            setCurrentProject(updatedProject);
          }

          if (status.status === 'completed') {
            message.success(`Sinh hàng loạt hoàn tất! Đã sinh thành công ${status.completed}`);
            // 🔔 Kích hoạt thông báo trình duyệt
            showBrowserNotification(
              'Sinh hàng loạt hoàn tất',
              `"${currentProject?.title || 'dự án'}" đã sinh thành công ${status.completed}  chương`,
              'success'
            );
          } else if (status.status === 'failed') {
            message.error(`Sinh hàng loạt thất bại: ${status.error_message || 'Lỗi không xác định'}`);
            // 🔔 Kích hoạt thông báo trình duyệt
            showBrowserNotification(
              'Sinh hàng loạt thất bại',
              status.error_message || 'Lỗi không xác định',
              'error'
            );
          } else if (status.status === 'cancelled') {
            message.warning('Đã hủy sinh hàng loạt');
          }

          // Trì hoãn đóng hộp thoại để người dùng thấy trạng thái cuối cùng
          setTimeout(() => {
            setBatchGenerateVisible(false);
            setBatchTaskId(null);
            setBatchProgress(null);
          }, 2000);
        }
      } catch (error) {
        console.error('Polling trạng thái sinh hàng loạt thất bại:', error);
      }
    };

    // Thực hiện ngay một lần
    poll();

    // Polling mỗi 2 giây một lần
    batchPollingIntervalRef.current = window.setInterval(poll, 2000);
  };

  // Hủy sinh hàng loạt
  const handleCancelBatchGenerate = async () => {
    if (!batchTaskId) return;

    try {
      const response = await fetch(`/api/chapters/batch-generate/${batchTaskId}/cancel`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Hủy thất bại');
      }

      message.success('Đã hủy sinh hàng loạt');

      // Hủy xong refresh ngay danh sách chương và task phân tích để hiển thị chương đã sinh
      await refreshChapters();
      await loadAnalysisTasks();

      // Refresh thông tin dự án để cập nhật thống kê tổng số từ
      if (currentProject?.id) {
        const updatedProject = await projectApi.getProject(currentProject.id);
        setCurrentProject(updatedProject);
      }
    } catch (error: unknown) {
      const err = error as Error;
      message.error('Hủy thất bại: ' + (err.message || 'Lỗi không xác định'));
    }
  };

  // Mở hộp thoại sinh hàng loạt
  const handleOpenBatchGenerate = async () => {
    // Tìm chương đầu tiên chưa được sinh
    const firstIncompleteChapter = sortedChapters.find(
      ch => !ch.content || ch.content.trim() === ''
    );

    if (!firstIncompleteChapter) {
      message.info('Mọi chương đều đã được sinh nội dung');
      return;
    }

    // Kiểm tra chương này có thể sinh không
    if (!canGenerateChapter(firstIncompleteChapter)) {
      const reason = getGenerateDisabledReason(firstIncompleteChapter);
      message.warning(reason);
      return;
    }

    // Tải danh sách mô hình và danh sách Skill khi mở hộp thoại, chờ hoàn tất
    const defaultModel = await loadAvailableModels();
    loadAvailableSkills();

    console.log('[Mở sinh hàng loạt] defaultModel:', defaultModel);
    console.log('[Mở sinh hàng loạt] selectedStyleId:', selectedStyleId);

    // Đặt state lựa chọn mô hình cho sinh hàng loạt
    setBatchSelectedModel(defaultModel || undefined);

    // Đặt lại form và đặt giá trị ban đầu (dùng số từ đã cache)
    batchForm.setFieldsValue({
      startChapterNumber: firstIncompleteChapter.chapter_number,
      count: 5,
      enableAnalysis: true,
      styleId: selectedStyleId,
      targetWordCount: getCachedWordCount(),
    });

    setBatchGenerateVisible(true);
  };

  // Tạo chương thủ công (chỉ chế độ one-to-many)
  const showManualCreateChapterModal = () => {
    // Tính số chương tiếp theo
    const nextChapterNumber = chapters.length > 0
      ? Math.max(...chapters.map(c => c.chapter_number)) + 1
      : 1;

    modal.confirm({
      title: 'Tạo thủ công chương',
      width: 600,
      centered: true,
      content: (
        <Form
          form={manualCreateForm}
          layout="vertical"
          initialValues={{
            chapter_number: nextChapterNumber,
            status: 'draft'
          }}
          style={{ marginTop: 16 }}
        >
          <Form.Item
            label="Số thứ tự chương"
            name="chapter_number"
            rules={[{ required: true, message: 'Vui lòng nhập số thứ tự chương' }]}
            tooltip="Nên tạo chương theo thứ tự để đảm bảo nội dung liền mạch"
          >
            <InputNumber min={1} style={{ width: '100%' }} placeholder="Số thứ tự tiếp theo được tính tự động" />
          </Form.Item>

          <Form.Item
            label="Tiêu đề chương"
            name="title"
            rules={[{ required: true, message: 'Vui lòng nhập tiêu đề' }]}
          >
            <Input placeholder="VD: Chương 1 - Lần đầu gặp gỡ" />
          </Form.Item>

          <Form.Item
            label="Dàn ý liên kết"
            name="outline_id"
            rules={[{ required: true, message: 'Vui lòng chọn dàn ý liên kết' }]}
            tooltip="Ở chế độ one-to-many, chương phải liên kết với dàn ý"
          >
            <Select placeholder="Vui lòng chọn dàn ý trực thuộc">
              {/* Dùng trực tiếp dữ liệu outlines trong store thay vì trích từ chương hiện có */}
              {[...outlines]
                .sort((a, b) => a.order_index - b.order_index)
                .map(outline => (
                  <Select.Option key={outline.id} value={outline.id}>
                    Tập {outline.order_index}: {outline.title}
                  </Select.Option>
                ))}
            </Select>
          </Form.Item>

          <Form.Item
            label="Tóm tắt chương (tùy chọn)"
            name="summary"
            tooltip="Mô tả ngắn gọn nội dung chính và diễn biến tình tiết của chương này"
          >
            <TextArea
              rows={4}
              placeholder="Mô tả ngắn gọn nội dung chương này..."
            />
          </Form.Item>

          <Form.Item
            label="Trạng thái"
            name="status"
          >
            <Select>
              <Select.Option value="draft">Bản nháp</Select.Option>
              <Select.Option value="pending">Đang chờ</Select.Option>
              <Select.Option value="writing">Đang sáng tác</Select.Option>
              <Select.Option value="completed">Đã hoàn thành</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      ),
      okText: 'Tạo',
      cancelText: 'Hủy',
      onOk: async () => {
        const values = await manualCreateForm.validateFields();

        // Kiểm tra số thứ tự chương đã tồn tại chưa
        const conflictChapter = chapters.find(
          ch => ch.chapter_number === values.chapter_number
        );

        if (conflictChapter) {
          // Hiển thị Modal gợi ý xung đột
          modal.confirm({
            title: 'Xung đột số thứ tự chương',
            icon: <InfoCircleOutlined style={{ color: token.colorError }} />,
            width: 500,
            centered: true,
            content: (
              <div>
                <p style={{ marginBottom: 12 }}>
                  Chương <strong>{values.chapter_number}</strong> đã tồn tại:
                </p>
                <div style={{
                  padding: 12,
                  background: token.colorWarningBg,
                  borderRadius: token.borderRadius,
                  border: `1px solid ${token.colorWarningBorder}`,
                  marginBottom: 12
                }}>
                  <div><strong>Tiêu đề:</strong>{conflictChapter.title}</div>
                  <div><strong>Trạng thái:</strong>{getStatusText(conflictChapter.status)}</div>
                  <div><strong>Số từ:</strong>{conflictChapter.word_count || 0} từ</div>
                  {conflictChapter.outline_title && (
                    <div><strong>Dàn ý trực thuộc:</strong>{conflictChapter.outline_title}</div>
                  )}
                </div>
                <p style={{ color: token.colorError, marginBottom: 8 }}>
                  ⚠️ Có xóa chương cũ và tạo chương mới không?
                </p>
                <p style={{ fontSize: 12, color: token.colorTextSecondary, marginBottom: 0 }}>
                  Sau khi xóa sẽ không thể khôi phục, nội dung chương và kết quả phân tích đều bị xóa.
                </p>
              </div>
            ),
            okText: 'Xóa và tạo',
            okButtonProps: { danger: true },
            cancelText: 'Hủy',
            onOk: async () => {
              try {
                // Xóa chương cũ trước
                await handleDeleteChapter(conflictChapter.id);

                // Chờ một lúc để đảm bảo xóa xong
                await new Promise(resolve => setTimeout(resolve, 300));

                // Tạo chương mới
                await chapterApi.createChapter({
                  project_id: currentProject.id,
                  ...values
                });

                message.success('Đã xóa chương cũ và tạo chương mới');
                await refreshChapters();

                // Refresh thông tin dự án để cập nhật thống kê số từ
                const updatedProject = await projectApi.getProject(currentProject.id);
                setCurrentProject(updatedProject);

                manualCreateForm.resetFields();
              } catch (error: unknown) {
                const err = error as Error;
                message.error('Thao tác thất bại：' + (err.message || 'Lỗi không xác định'));
                throw error;
              }
            }
          });

          // Ngăn Modal ngoài đóng lại
          return Promise.reject();
        }

        // Không có xung đột, tạo trực tiếp
        try {
          await chapterApi.createChapter({
            project_id: currentProject.id,
            ...values
          });
          message.success('Tạo chương thành công');
          await refreshChapters();

          // Refresh thông tin dự án để cập nhật thống kê số từ
          const updatedProject = await projectApi.getProject(currentProject.id);
          setCurrentProject(updatedProject);

          manualCreateForm.resetFields();
        } catch (error: unknown) {
          const err = error as Error;
          message.error('Tạo thất bại: ' + (err.message || 'Lỗi không xác định'));
          throw error;
        }
      }
    });
  };

  // Render tag trạng thái phân tích
  const renderAnalysisStatus = (chapterId: string) => {
    const task = analysisTasksMap[chapterId];

    if (!task) {
      return null;
    }

    switch (task.status) {
      case 'pending':
        return (
          <Tag icon={<SyncOutlined spin />} color="processing">
            Đang chờ phân tích
          </Tag>
        );
      case 'running': {
        // Kiểm tra có đang thử lại không (backend sẽ chứa "Đang thử lại" trong error_message)
        const isRetrying = task.error_message && task.error_message.includes('Đang thử lại');
        return (
          <Tag
            icon={<SyncOutlined spin />}
            color={isRetrying ? "warning" : "processing"}
            title={task.error_message || undefined}
          >
            {isRetrying ? `Đang thử lại ${task.progress}%` : `Đang phân tích ${task.progress}%`}
          </Tag>
        );
      }
      case 'completed':
        return (
          <Tag icon={<CheckCircleOutlined />} color="success">
            Đã phân tích
          </Tag>
        );
      case 'failed':
        return (
          <Tag icon={<CloseCircleOutlined />} color="error" title={task.error_message || undefined}>
            Phân tích thất bại
          </Tag>
        );
      default:
        return null;
    }
  };

  // Hiển thị chi tiết kế hoạch mở rộng
  const showExpansionPlanModal = (chapter: Chapter) => {
    if (!chapter.expansion_plan) return;

    try {
      const planData: ExpansionPlanData = JSON.parse(chapter.expansion_plan);

      modal.info({
        title: (
          <Space style={{ flexWrap: 'wrap' }}>
            <InfoCircleOutlined style={{ color: token.colorPrimary }} />
            <span style={{ wordBreak: 'break-word' }}>Kế hoạch mở rộng chương {chapter.chapter_number}</span>
          </Space>
        ),
        width: isMobile ? 'calc(100vw - 32px)' : 800,
        centered: true,
        style: isMobile ? {
          maxWidth: 'calc(100vw - 32px)',
          margin: '0 auto',
          padding: '0 16px'
        } : undefined,
        styles: {
          body: {
            maxHeight: isMobile ? 'calc(100vh - 200px)' : 'calc(80vh - 110px)',
            overflowY: 'auto'
          }
        },
        content: (
          <div style={{ marginTop: 16 }}>
            <Descriptions
              column={1}
              size="small"
              bordered
              labelStyle={{
                whiteSpace: 'normal',
                wordBreak: 'break-word',
                width: isMobile ? '80px' : '100px'
              }}
              contentStyle={{
                whiteSpace: 'normal',
                wordBreak: 'break-word',
                overflowWrap: 'break-word'
              }}
            >
              <Descriptions.Item label="Tiêu đề chương">
                <strong style={{
                  wordBreak: 'break-word',
                  whiteSpace: 'normal',
                  overflowWrap: 'break-word'
                }}>
                  {chapter.title}
                </strong>
              </Descriptions.Item>
              <Descriptions.Item label="Tông cảm xúc">
                <Tag
                  color="blue"
                  style={{
                    whiteSpace: 'normal',
                    wordBreak: 'break-word',
                    height: 'auto',
                    lineHeight: '1.5',
                    padding: '4px 8px'
                  }}
                >
                  {planData.emotional_tone}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Loại xung đột">
                <Tag
                  color="orange"
                  style={{
                    whiteSpace: 'normal',
                    wordBreak: 'break-word',
                    height: 'auto',
                    lineHeight: '1.5',
                    padding: '4px 8px'
                  }}
                >
                  {planData.conflict_type}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Số từ ước tính">
                <Tag color="green">{planData.estimated_words} từ</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Mục tiêu tự sự">
                <span style={{
                  wordBreak: 'break-word',
                  whiteSpace: 'normal',
                  overflowWrap: 'break-word'
                }}>
                  {planData.narrative_goal}
                </span>
              </Descriptions.Item>
              <Descriptions.Item label="Sự kiện then chốt">
                <Space direction="vertical" size="small" style={{ width: '100%' }}>
                  {planData.key_events.map((event, idx) => (
                    <div
                      key={idx}
                      style={{
                        padding: '4px 0',
                        wordBreak: 'break-word',
                        whiteSpace: 'normal',
                        overflowWrap: 'break-word'
                      }}
                    >
                      <Tag color="purple" style={{ flexShrink: 0 }}>{idx + 1}</Tag>{' '}
                      <span style={{
                        wordBreak: 'break-word',
                        whiteSpace: 'normal',
                        overflowWrap: 'break-word'
                      }}>
                        {event}
                      </span>
                    </div>
                  ))}
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="Nhân vật liên quan">
                <Space wrap style={{ maxWidth: '100%' }}>
                  {planData.character_focus.map((char, idx) => (
                    <Tag
                      key={idx}
                      color="cyan"
                      style={{
                        whiteSpace: 'normal',
                        wordBreak: 'break-word',
                        height: 'auto',
                        lineHeight: '1.5'
                      }}
                    >
                      {char}
                    </Tag>
                  ))}
                </Space>
              </Descriptions.Item>
              {planData.scenes && planData.scenes.length > 0 && (
                <Descriptions.Item label="Kế hoạch cảnh">
                  <Space direction="vertical" size="small" style={{ width: '100%' }}>
                    {planData.scenes.map((scene, idx) => (
                      <Card
                        key={idx}
                        size="small"
                        style={{
                          backgroundColor: token.colorFillQuaternary,
                          maxWidth: '100%',
                          overflow: 'hidden'
                        }}
                      >
                        <div style={{
                          marginBottom: 4,
                          wordBreak: 'break-word',
                          whiteSpace: 'normal',
                          overflowWrap: 'break-word'
                        }}>
                          <strong>📍 Địa điểm:</strong>
                          <span style={{
                            wordBreak: 'break-word',
                            whiteSpace: 'normal',
                            overflowWrap: 'break-word'
                          }}>
                            {scene.location}
                          </span>
                        </div>
                        <div style={{ marginBottom: 4 }}>
                          <strong>👥 Nhân vật:</strong>
                          <Space
                            size="small"
                            wrap
                            style={{
                              marginLeft: isMobile ? 0 : 8,
                              marginTop: isMobile ? 4 : 0,
                              display: isMobile ? 'flex' : 'inline-flex'
                            }}
                          >
                            {scene.characters.map((char, charIdx) => (
                              <Tag
                                key={charIdx}
                                style={{
                                  whiteSpace: 'normal',
                                  wordBreak: 'break-word',
                                  height: 'auto'
                                }}
                              >
                                {char}
                              </Tag>
                            ))}
                          </Space>
                        </div>
                        <div style={{
                          wordBreak: 'break-word',
                          whiteSpace: 'normal',
                          overflowWrap: 'break-word'
                        }}>
                          <strong>🎯 Mục đích:</strong>
                          <span style={{
                            wordBreak: 'break-word',
                            whiteSpace: 'normal',
                            overflowWrap: 'break-word'
                          }}>
                            {scene.purpose}
                          </span>
                        </div>
                      </Card>
                    ))}
                  </Space>
                </Descriptions.Item>
              )}
            </Descriptions>
            <Alert
              message="Gợi ý"
              description="Đây là thông tin kế hoạch do AI sinh khi mở rộng dàn ý, có thể dùng làm tham khảo khi sáng tác nội dung chương."
              type="info"
              showIcon
              style={{ marginTop: 16 }}
            />
          </div>
        ),
        okText: 'Đóng',
      });
    } catch (error) {
      console.error('Phân tích kế hoạch mở rộng thất bại:', error);
      message.error('Lỗi định dạng dữ liệu kế hoạch mở rộng');
    }
  };

  // Hàm xử lý xóa chương
  const handleDeleteChapter = async (chapterId: string) => {
    try {
      await deleteChapter(chapterId);

      // Refresh danh sách chương
      await refreshChapters();

      // Refresh thông tin dự án để cập nhật thống kê tổng số từ
      if (currentProject) {
        const updatedProject = await projectApi.getProject(currentProject.id);
        setCurrentProject(updatedProject);
      }

      message.success('Xóa chương thành công');
    } catch (error: unknown) {
      const err = error as Error;
      message.error('Xóa chương thất bại: ' + (err.message || 'Lỗi không xác định'));
    }
  };

  // Mở trình chỉnh sửa kế hoạch
  const handleOpenPlanEditor = (chapter: Chapter) => {
    // Mở trực tiếp trình chỉnh sửa, nếu không có dữ liệu kế hoạch thì tạo mới
    setEditingPlanChapter(chapter);
    setPlanEditorVisible(true);
  };

  // Lưu thông tin kế hoạch
  const handleSavePlan = async (planData: ExpansionPlanData) => {
    if (!editingPlanChapter) return;

    try {
      const response = await fetch(`/api/chapters/${editingPlanChapter.id}/expansion-plan`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(planData),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Cập nhật thất bại');
      }

      // Refresh danh sách chương
      await refreshChapters();

      message.success('Cập nhật thông tin kế hoạch thành công');

      // Đóng trình chỉnh sửa
      setPlanEditorVisible(false);
      setEditingPlanChapter(null);
    } catch (error: unknown) {
      const err = error as Error;
      message.error('Lưu kế hoạch thất bại: ' + (err.message || 'Lỗi không xác định'));
      throw error;
    }
  };

  // Mở trình đọc
  const handleOpenReader = (chapter: Chapter) => {
    setReadingChapter(chapter);
    setReaderVisible(true);
  };

  // Trình đọc chuyển chương
  const handleReaderChapterChange = async (chapterId: string) => {
    try {
      const response = await fetch(`/api/chapters/${chapterId}`);
      if (!response.ok) throw new Error('Lấy chương thất bại');
      const newChapter = await response.json();
      setReadingChapter(newChapter);
    } catch {
      message.error('Tải chương thất bại');
    }
  };

  // Mở popup viết lại cục bộ
  const handleOpenPartialRegenerate = () => {
    setPartialRegenerateToolbarVisible(false);
    setPartialRegenerateModalVisible(true);
  };

  // Áp dụng kết quả viết lại cục bộ
  const handleApplyPartialRegenerate = (newText: string, startPos: number, endPos: number) => {
    // Lấy nội dung hiện tại
    const currentContent = editorForm.getFieldValue('content') || '';
    
    // Thay thế phần được chọn
    const newContent = currentContent.substring(0, startPos) + newText + currentContent.substring(endPos);
    
    // Cập nhật form
    editorForm.setFieldsValue({ content: newContent });
    
    // Đóng popup
    setPartialRegenerateModalVisible(false);
    
    message.success('Đã áp dụng viết lại cục bộ');
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {contextHolder}
      <div style={{
        position: 'sticky',
        top: 0,
        zIndex: 10,
        backgroundColor: token.colorBgContainer,
        padding: isMobile ? '12px 0' : '16px 0',
        marginBottom: isMobile ? 12 : 16,
        borderBottom: `1px solid ${token.colorBorderSecondary}`,
        display: 'flex',
        flexDirection: isMobile ? 'column' : 'row',
        gap: isMobile ? 12 : 0,
        justifyContent: 'space-between',
        alignItems: isMobile ? 'stretch' : 'center'
      }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <h2 style={{ margin: 0, fontSize: isMobile ? 18 : 24 }}>
            <BookOutlined style={{ marginRight: 8 }} />
            Quản lý chương
          </h2>
          <Tag
            color={currentProject.outline_mode === 'one-to-one' ? 'blue' : 'green'}
            style={{ width: 'fit-content' }}
          >
            {currentProject.outline_mode === 'one-to-one'
              ? 'Chế độ truyền thống: chương do dàn ý quản lý, vui lòng thao tác ở trang dàn ý'
              : 'Chế độ chi tiết: chương có thể mở rộng ở trang dàn ý'}
          </Tag>
        </div>
        <Space direction={isMobile ? 'vertical' : 'horizontal'} style={{ width: isMobile ? '100%' : 'auto' }}>
          <Input.Search
            allowClear
            placeholder="Tìm kiếm chương (số thứ tự/tiêu đề/dàn ý)"
            value={chapterSearchKeyword}
            onChange={(e) => setChapterSearchKeyword(e.target.value)}
            style={{ width: isMobile ? '100%' : 280 }}
          />
          {currentProject.outline_mode === 'one-to-many' && (
            <Button
              icon={<PlusOutlined />}
              onClick={showManualCreateChapterModal}
              block={isMobile}
              size={isMobile ? 'middle' : 'middle'}
            >
              Tạo thủ công
            </Button>
          )}
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            onClick={handleBatchAnalyzeUnanalyzed}
            loading={batchAnalyzingUnanalyzed}
            disabled={chapters.length === 0 || batchAnalyzableChapterCount === 0}
            block={isMobile}
            size={isMobile ? 'middle' : 'middle'}
            style={{ background: token.colorWarning, borderColor: token.colorWarning }}
            title={batchAnalyzableChapterCount === 0 ? 'Chưa có chương nào để phân tích một chạm' : `Có thể phân tích một chạm ${batchAnalyzableChapterCount}`}
          >
            Phân tích một chạm{batchAnalyzableChapterCount > 0 ? ` (${batchAnalyzableChapterCount})` : ''}
          </Button>
          <Button
            type="primary"
            icon={<RocketOutlined />}
            onClick={handleOpenBatchGenerate}
            disabled={chapters.length === 0 || batchGenerating}
            loading={batchGenerating}
            block={isMobile}
            size={isMobile ? 'middle' : 'middle'}
            style={batchGenerating ? {} : { background: token.colorInfo, borderColor: token.colorInfo }}
          >
            {batchGenerating ? 'Đang sinh...' : 'Sinh hàng loạt'}
          </Button>
          <Button
            type="default"
            icon={<DownloadOutlined />}
            onClick={handleExport}
            disabled={chapters.length === 0}
            block={isMobile}
            size={isMobile ? 'middle' : 'middle'}
          >
            Xuất thành TXT
          </Button>
        </Space>
      </div>


      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
        {chapters.length === 0 ? (
          <Empty description="Chưa có chương nào, hãy bắt đầu sáng tác!" />
        ) : filteredSortedChapters.length === 0 ? (
          <Empty description="Không tìm thấy chương phù hợp" />
        ) : currentProject.outline_mode === 'one-to-one' ? (
          // Chế độ one-to-one: hiển thị trực tiếp danh sách phẳng
          <List
            dataSource={pagedSortedChapters}
            renderItem={(item) => (
              <List.Item
                id={`chapter-item-${item.id}`}
                style={{
                  padding: '16px',
                  marginBottom: 16,
                  background: token.colorBgContainer,
                  borderRadius: token.borderRadius,
                  border: `1px solid ${token.colorBorderSecondary}`,
                  flexDirection: isMobile ? 'column' : 'row',
                  alignItems: isMobile ? 'flex-start' : 'center',
                }}
                actions={isMobile ? undefined : [
                  <Button
                    type="text"
                    icon={<ReadOutlined />}
                    onClick={() => handleOpenReader(item)}
                    disabled={!item.content || item.content.trim() === ''}
                    title={!item.content || item.content.trim() === '' ? 'Chưa có nội dung' : 'Đọc đắm chìm'}
                  >
                    Đọc
                  </Button>,
                  <Button
                    type="text"
                    icon={<EditOutlined />}
                    onClick={() => handleOpenEditor(item.id)}
                  >
                    Chỉnh sửa
                  </Button>,
                  (() => {
                    const task = analysisTasksMap[item.id];
                    const isAnalyzing = task && (task.status === 'pending' || task.status === 'running');
                    const hasContent = item.content && item.content.trim() !== '';

                    return (
                      <Button
                        type="text"
                        icon={isAnalyzing ? <SyncOutlined spin /> : <FundOutlined />}
                        onClick={() => handleShowAnalysis(item.id)}
                        disabled={!hasContent || isAnalyzing}
                        loading={isAnalyzing}
                        title={
                          !hasContent ? 'Vui lòng sinh nội dung chương trước' :
                            isAnalyzing ? 'Đang phân tích, vui lòng chờ...' :
                              ''
                        }
                      >
                        {isAnalyzing ? 'Đang phân tích' : 'Phân tích'}
                      </Button>
                    );
                  })(),
                  <Button
                    type="text"
                    icon={<SettingOutlined />}
                    onClick={() => handleOpenModal(item.id)}
                  >
                    Sửa
                  </Button>,
                ]}
              >
                <div style={{ width: '100%' }}>
                  <List.Item.Meta
                    avatar={!isMobile && <FileTextOutlined style={{ fontSize: 32, color: token.colorPrimary }} />}
                    title={
                      <div style={{
                        display: 'flex',
                        flexDirection: isMobile ? 'column' : 'row',
                        alignItems: isMobile ? 'flex-start' : 'center',
                        gap: isMobile ? 6 : 12,
                        width: '100%'
                      }}>
                        <span style={{ fontSize: isMobile ? 14 : 16, fontWeight: 500, flexShrink: 0 }}>
                          Chương {item.chapter_number}: {item.title}
                        </span>
                        <Space wrap size={isMobile ? 4 : 8}>
                          <Tag color={getStatusColor(item.status)}>{getStatusText(item.status)}</Tag>
                          <Badge count={`${item.word_count || 0} từ`} style={{ backgroundColor: token.colorSuccess }} />
                          {renderAnalysisStatus(item.id)}
                          {!canGenerateChapter(item) && (
                            <Tag icon={<LockOutlined />} color="warning" title={getGenerateDisabledReason(item)}>
                              Cần chương tiền đề
                            </Tag>
                          )}
                        </Space>
                      </div>
                    }
                    description={
                      item.content ? (
                        <div style={{ marginTop: 8, color: token.colorTextSecondary, lineHeight: 1.6, fontSize: isMobile ? 12 : 14 }}>
                          {item.content.substring(0, isMobile ? 80 : 150)}
                          {item.content.length > (isMobile ? 80 : 150) && '...'}
                        </div>
                      ) : (
                        <span style={{ color: token.colorTextTertiary, fontSize: isMobile ? 12 : 14 }}>Chưa có nội dung</span>
                      )
                    }
                  />

                  {isMobile && (
                    <Space style={{ marginTop: 12, width: '100%', justifyContent: 'flex-end' }} wrap>
                      <Button
                        type="text"
                        icon={<ReadOutlined />}
                        onClick={() => handleOpenReader(item)}
                        size="small"
                        disabled={!item.content || item.content.trim() === ''}
                        title={!item.content || item.content.trim() === '' ? 'Chưa có nội dung' : 'Đọc'}
                      />
                      <Button
                        type="text"
                        icon={<EditOutlined />}
                        onClick={() => handleOpenEditor(item.id)}
                        size="small"
                        title="Chỉnh sửa"
                      />
                      {(() => {
                        const task = analysisTasksMap[item.id];
                        const isAnalyzing = task && (task.status === 'pending' || task.status === 'running');
                        const hasContent = item.content && item.content.trim() !== '';

                        return (
                          <Button
                            type="text"
                            icon={isAnalyzing ? <SyncOutlined spin /> : <FundOutlined />}
                            onClick={() => handleShowAnalysis(item.id)}
                            size="small"
                            disabled={!hasContent || isAnalyzing}
                            loading={isAnalyzing}
                            title={
                              !hasContent ? 'Vui lòng sinh nội dung chương trước' :
                                isAnalyzing ? 'Đang phân tích' :
                                  'Phân tích'
                            }
                          />
                        );
                      })()}
                      <Button
                        type="text"
                        icon={<SettingOutlined />}
                        onClick={() => handleOpenModal(item.id)}
                        size="small"
                        title="Sửa"
                      />
                    </Space>
                  )}
                </div>
              </List.Item>
            )}
          />
        ) : (
          // Chế độ one-to-many: hiển thị nhóm theo dàn ý
          <Collapse
            bordered={false}
            defaultActiveKey={pagedGroupedChapters.length > 0 ? ['0'] : []}
            destroyInactivePanel
            expandIcon={({ isActive }) => <CaretRightOutlined rotate={isActive ? 90 : 0} />}
            style={{ background: 'transparent' }}
          >
            {pagedGroupedChapters.map((group, groupIndex) => (
              <Collapse.Panel
                key={groupIndex.toString()}
                header={
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <Tag color={group.outlineId ? 'blue' : 'default'} style={{ margin: 0 }}>
                      {group.outlineId ? `📖 Dàn ý ${group.outlineOrder}` : '📝 Chưa phân loại'}
                    </Tag>
                    <span style={{ fontWeight: 600, fontSize: 16 }}>
                      {group.outlineTitle}
                    </span>
                    <Badge
                      count={`${group.chapters.length}`}
                      style={{ backgroundColor: token.colorSuccess }}
                    />
                    <Badge
                      count={`${group.chapters.reduce((sum, ch) => sum + (ch.word_count || 0), 0)}  từ`}
                      style={{ backgroundColor: token.colorPrimary }}
                    />
                  </div>
                }
                style={{
                  marginBottom: 16,
                  background: token.colorBgContainer,
                  borderRadius: token.borderRadius,
                  border: `1px solid ${token.colorBorderSecondary}`,
                }}
              >
                <List
                  dataSource={group.chapters}
                  renderItem={(item) => (
                    <List.Item
                      id={`chapter-item-${item.id}`}
                      style={{
                        padding: '16px 0',
                        borderRadius: 8,
                        transition: 'background 0.3s ease',
                        flexDirection: isMobile ? 'column' : 'row',
                        alignItems: isMobile ? 'flex-start' : 'center',
                      }}
                      actions={isMobile ? undefined : [
                        <Button
                          type="text"
                          icon={<ReadOutlined />}
                          onClick={() => handleOpenReader(item)}
                          disabled={!item.content || item.content.trim() === ''}
                          title={!item.content || item.content.trim() === '' ? 'Chưa có nội dung' : 'Đọc đắm chìm'}
                        >
                          Đọc
                        </Button>,
                        <Button
                          type="text"
                          icon={<EditOutlined />}
                          onClick={() => handleOpenEditor(item.id)}
                        >
                          Chỉnh sửa
                        </Button>,
                        (() => {
                          const task = analysisTasksMap[item.id];
                          const isAnalyzing = task && (task.status === 'pending' || task.status === 'running');
                          const hasContent = item.content && item.content.trim() !== '';

                          return (
                            <Button
                              type="text"
                              icon={isAnalyzing ? <SyncOutlined spin /> : <FundOutlined />}
                              onClick={() => handleShowAnalysis(item.id)}
                              disabled={!hasContent || isAnalyzing}
                              loading={isAnalyzing}
                              title={
                                !hasContent ? 'Vui lòng sinh nội dung chương trước' :
                                  isAnalyzing ? 'Đang phân tích, vui lòng chờ...' :
                                    ''
                              }
                            >
                              {isAnalyzing ? 'Đang phân tích' : 'Phân tích'}
                            </Button>
                          );
                        })(),
                        <Button
                          type="text"
                          icon={<SettingOutlined />}
                          onClick={() => handleOpenModal(item.id)}
                        >
                          Sửa
                        </Button>,
                        // Chỉ hiển thị nút xóa ở chế độ one-to-many
                        ...(currentProject.outline_mode === 'one-to-many' ? [
                          <Popconfirm
                            title="Bạn có chắc muốn xóa chương này không?"
                            description="Sau khi xóa sẽ không thể khôi phục, nội dung chương và kết quả phân tích đều bị xóa."
                            onConfirm={() => handleDeleteChapter(item.id)}
                            okText="Xác nhận xóa"
                            cancelText="Hủy"
                            okButtonProps={{ danger: true }}
                          >
                            <Button
                              type="text"
                              danger
                              icon={<DeleteOutlined />}
                            >
                              Xóa
                            </Button>
                          </Popconfirm>
                        ] : []),
                      ]}
                    >
                      <div style={{ width: '100%' }}>
                        <List.Item.Meta
                          avatar={!isMobile && <FileTextOutlined style={{ fontSize: 32, color: token.colorPrimary }} />}
                          title={
                            <div style={{
                              display: 'flex',
                              flexDirection: isMobile ? 'column' : 'row',
                              alignItems: isMobile ? 'flex-start' : 'center',
                              gap: isMobile ? 6 : 12,
                              width: '100%'
                            }}>
                              <span style={{ fontSize: isMobile ? 14 : 16, fontWeight: 500, flexShrink: 0 }}>
                                Chương {item.chapter_number}: {item.title}
                              </span>
                              <Space wrap size={isMobile ? 4 : 8}>
                                <Tag color={getStatusColor(item.status)}>{getStatusText(item.status)}</Tag>
                                <Badge count={`${item.word_count || 0} từ`} style={{ backgroundColor: token.colorSuccess }} />
                                {renderAnalysisStatus(item.id)}
                                {!canGenerateChapter(item) && (
                                  <Tag icon={<LockOutlined />} color="warning" title={getGenerateDisabledReason(item)}>
                                    Cần chương tiền đề
                                  </Tag>
                                )}
                                <Space size={4}>
                                  {item.expansion_plan && (
                                    <InfoCircleOutlined
                                      title="Xem chi tiết mở rộng"
                                      style={{ color: token.colorPrimary, cursor: 'pointer', fontSize: 16 }}
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        showExpansionPlanModal(item);
                                      }}
                                    />
                                  )}
                                  <FormOutlined
                                    title={item.expansion_plan ? "Chỉnh sửa thông tin kế hoạch" : "Tạo thông tin kế hoạch"}
                                    style={{ color: token.colorSuccess, cursor: 'pointer', fontSize: 16 }}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleOpenPlanEditor(item);
                                    }}
                                  />
                                </Space>
                              </Space>
                            </div>
                          }
                          description={
                            item.content ? (
                              <div style={{ marginTop: 8, color: token.colorTextSecondary, lineHeight: 1.6, fontSize: isMobile ? 12 : 14 }}>
                                {item.content.substring(0, isMobile ? 80 : 150)}
                                {item.content.length > (isMobile ? 80 : 150) && '...'}
                              </div>
                            ) : (
                              <span style={{ color: token.colorTextTertiary, fontSize: isMobile ? 12 : 14 }}>Chưa có nội dung</span>
                            )
                          }
                        />

                        {isMobile && (
                          <Space style={{ marginTop: 12, width: '100%', justifyContent: 'flex-end' }} wrap>
                            <Button
                              type="text"
                              icon={<ReadOutlined />}
                              onClick={() => handleOpenReader(item)}
                              size="small"
                              disabled={!item.content || item.content.trim() === ''}
                              title={!item.content || item.content.trim() === '' ? 'Chưa có nội dung' : 'Đọc'}
                            />
                            <Button
                              type="text"
                              icon={<EditOutlined />}
                              onClick={() => handleOpenEditor(item.id)}
                              size="small"
                              title="Chỉnh sửa"
                            />
                            {(() => {
                              const task = analysisTasksMap[item.id];
                              const isAnalyzing = task && (task.status === 'pending' || task.status === 'running');
                              const hasContent = item.content && item.content.trim() !== '';

                              return (
                                <Button
                                  type="text"
                                  icon={isAnalyzing ? <SyncOutlined spin /> : <FundOutlined />}
                                  onClick={() => handleShowAnalysis(item.id)}
                                  size="small"
                                  disabled={!hasContent || isAnalyzing}
                                  loading={isAnalyzing}
                                  title={
                                    !hasContent ? 'Vui lòng sinh nội dung chương trước' :
                                      isAnalyzing ? 'Đang phân tích' :
                                        'Phân tích'
                                  }
                                />
                              );
                            })()}
                            <Button
                              type="text"
                              icon={<SettingOutlined />}
                              onClick={() => handleOpenModal(item.id)}
                              size="small"
                              title="Sửa"
                            />
                            {/* Chỉ hiển thị nút xóa ở chế độ one-to-many */}
                            {currentProject.outline_mode === 'one-to-many' && (
                              <Popconfirm
                                title="Xác nhận xóa?"
                                description="Sau khi xóa không thể khôi phục"
                                onConfirm={() => handleDeleteChapter(item.id)}
                                okText="Xóa"
                                cancelText="Hủy"
                                okButtonProps={{ danger: true }}
                              >
                                <Button
                                  type="text"
                                  danger
                                  icon={<DeleteOutlined />}
                                  size="small"
                                  title="Xóa chương"
                                />
                              </Popconfirm>
                            )}
                          </Space>
                        )}
                      </div>
                    </List.Item>
                  )}
                />
              </Collapse.Panel>
            ))}
          </Collapse>
        )}
      </div>

      {filteredSortedChapters.length > 0 && (
        <div style={{ paddingTop: 12, display: 'flex', justifyContent: 'flex-end' }}>
          <Pagination
            current={chapterPage}
            pageSize={chapterPageSize}
            total={filteredSortedChapters.length}
            showSizeChanger
            pageSizeOptions={['10', '20', '50', '100']}
            onChange={(page, size) => {
              setChapterPage(page);
              if (size !== chapterPageSize) {
                setChapterPageSize(size);
                setChapterPage(1);
              }
            }}
            showTotal={(total) => `Tổng  ${total}  mục`}
            size={isMobile ? 'small' : 'default'}
          />
        </div>
      )}

      <Modal
        title={editingId ? 'Chỉnh sửa thông tin chương' : 'Thêm chương'}
        open={isModalOpen}
        onCancel={() => setIsModalOpen(false)}
        footer={null}
        centered
        width={isMobile ? 'calc(100vw - 32px)' : 520}
        style={isMobile ? {
          maxWidth: 'calc(100vw - 32px)',
          margin: '0 auto',
          padding: '0 16px'
        } : undefined}
        styles={{
          body: {
            maxHeight: isMobile ? 'calc(100vh - 200px)' : 'calc(80vh - 110px)',
            overflowY: 'auto'
          }
        }}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item
            label="Tiêu đề chương"
            name="title"
            tooltip={
              currentProject.outline_mode === 'one-to-one'
                ? "Tiêu đề chương do dàn ý quản lý, vui lòng sửa ở trang dàn ý"
                : "Ở chế độ một-nhiều có thể sửa tiêu đề chương"
            }
            rules={
              currentProject.outline_mode === 'one-to-many'
                ? [{ required: true, message: 'Vui lòng nhập tiêu đề chương' }]
                : undefined
            }
          >
            <Input
              placeholder="Nhập tiêu đề chương"
              disabled={currentProject.outline_mode === 'one-to-one'}
            />
          </Form.Item>

          <Form.Item
            label="Số thứ tự chương"
            name="chapter_number"
            tooltip="Không được sửa số thứ tự chương, vui lòng xóa dàn ý tương ứng rồi sinh lại"
          >
            <Input type="number" placeholder="Số thứ tự sắp xếp chương" disabled />
          </Form.Item>

          <Form.Item label="Trạng thái" name="status">
            <Select placeholder="Chọn trạng thái">
              <Select.Option value="draft">Bản nháp</Select.Option>
              <Select.Option value="pending">Đang chờ</Select.Option>
              <Select.Option value="writing">Đang sáng tác</Select.Option>
              <Select.Option value="completed">Đã hoàn thành</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item>
            <Space style={{ float: 'right' }}>
              <Button onClick={() => setIsModalOpen(false)}>Hủy</Button>
              <Button type="primary" htmlType="submit">
                Cập nhật
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="Chỉnh sửa nội dung chương"
        open={isEditorOpen}
        onCancel={() => {
          if (isGenerating) {
            message.warning('AI đang sáng tác, vui lòng chờ hoàn tất rồi mới đóng');
            return;
          }
          setIsEditorOpen(false);
        }}
        closable={!isGenerating}
        maskClosable={false}
        keyboard={!isGenerating}
        width={isMobile ? 'calc(100vw - 32px)' : '85%'}
        centered
        style={isMobile ? {
          maxWidth: 'calc(100vw - 32px)',
          margin: '0 auto',
          padding: '0 16px'
        } : undefined}
        styles={{
          body: {
            maxHeight: isMobile ? 'calc(100vh - 200px)' : 'calc(100vh - 110px)',
            overflowY: 'auto',
            padding: isMobile ? '16px 12px' : '8px'
          }
        }}
        footer={null}
      >
        <Form form={editorForm} layout="vertical" onFinish={handleEditorSubmit}>
          {/* Tiêu đề chương và nút AI sáng tác */}
          <Form.Item
            label="Tiêu đề chương"
            tooltip="(Chế độ 1-1 vui lòng sửa ở dàn ý, chế độ 1-N vui lòng dùng nút sửa để chỉnh sửa)"
            style={{ marginBottom: isMobile ? 16 : 12 }}
          >
            <Space.Compact style={{ width: '100%' }}>
              <Form.Item name="title" noStyle>
                <Input disabled style={{ flex: 1 }} />
              </Form.Item>
              {editingId && (() => {
                const currentChapter = chapters.find(c => c.id === editingId);
                const canGenerate = currentChapter ? canGenerateChapter(currentChapter) : false;
                const disabledReason = currentChapter ? getGenerateDisabledReason(currentChapter) : '';

                return (
                  <>
                  <Button
                    type="primary"
                    icon={canGenerate ? <ThunderboltOutlined /> : <LockOutlined />}
                    onClick={() => currentChapter && showGenerateModal(currentChapter)}
                    loading={isContinuing}
                    disabled={!canGenerate}
                    danger={!canGenerate}
                    style={{ fontWeight: 'bold' }}
                    title={!canGenerate ? disabledReason : 'Sáng tác dựa trên dàn ý và nội dung chương tiền đề (streaming)'}
                  >
                    {isMobile ? 'AI' : 'AI sáng tác'}
                  </Button>
                  <Button
                    icon={<RocketOutlined />}
                    onClick={handleBackgroundGenerate}
                    disabled={!canGenerate || isContinuing}
                    style={{ fontWeight: 'bold' }}
                    title={!canGenerate ? disabledReason : 'Sinh trong nền: đóng trình duyệt cũng không ảnh hưởng, xong sẽ tự động lưu'}
                  >
                    {isMobile ? 'Nền' : 'Sinh nền'}
                  </Button>
                  </>
                );
              })()}
            </Space.Compact>
          </Form.Item>


          {/* Hàng đầu: phong cách viết + góc kể chuyện */}
          <div style={{
            display: isMobile ? 'block' : 'flex',
            gap: isMobile ? 0 : 16,
            marginBottom: isMobile ? 0 : 12
          }}>
            <Form.Item
              label="Phong cách viết"
              tooltip="Chọn phong cách viết AI dùng khi sáng tác"
              required
              style={{ flex: 1, marginBottom: isMobile ? 16 : 0 }}
            >
              <Select
                placeholder="Vui lòng chọn phong cách viết"
                value={selectedStyleId}
                onChange={setSelectedStyleId}
                disabled={isGenerating}
                status={!selectedStyleId ? 'error' : undefined}
              >
                {writingStyles.map(style => (
                  <Select.Option key={style.id} value={style.id}>
                    {style.name}{style.is_default && ' (mặc định)'}
                  </Select.Option>
                ))}
              </Select>
              {!selectedStyleId && (
                <div style={{ color: token.colorError, fontSize: 12, marginTop: 4 }}>Vui lòng chọn phong cách viết</div>
              )}
            </Form.Item>

            <Form.Item
              label="Góc kể chuyện"
              tooltip="Ngôi thứ nhất (tôi) dễ đồng cảm; ngôi thứ ba (anh ấy/cô ấy) khách quan hơn; góc nhìn toàn tri thấu suốt mọi thứ"
              style={{ flex: 1, marginBottom: isMobile ? 16 : 0 }}
            >
              <Select
                placeholder={`Mặc định dự án: ${getNarrativePerspectiveText(currentProject?.narrative_perspective)}`}
                value={temporaryNarrativePerspective}
                onChange={setTemporaryNarrativePerspective}
                allowClear
                disabled={isGenerating}
              >
                <Select.Option value="第一人称">Ngôi thứ nhất (tôi)</Select.Option>
                <Select.Option value="第三人称">Ngôi thứ ba (anh ấy/cô ấy)</Select.Option>
                <Select.Option value="全知视角">Góc nhìn toàn tri</Select.Option>
              </Select>
              {temporaryNarrativePerspective && (
                <div style={{ color: token.colorSuccess, fontSize: 12, marginTop: 4 }}>
                  ✓ {getNarrativePerspectiveText(temporaryNarrativePerspective)}
                </div>
              )}
            </Form.Item>
          </div>

          {/* Hàng hai: số từ mục tiêu + mô hình AI + Skill */}
          <div style={{
            display: isMobile ? 'block' : 'flex',
            gap: isMobile ? 0 : 16,
            marginBottom: isMobile ? 16 : 12
          }}>
            <Form.Item
              label="Áp dụng Skill"
              tooltip="Chọn một workflow Skill để hướng dẫn AI sáng tác, không chọn thì dùng quy trình sáng tác chuẩn"
              style={{ flex: 1, marginBottom: isMobile ? 16 : 0 }}
            >
              <Select
                placeholder="Không dùng Skill (sáng tác chuẩn)"
                value={selectedSkillKey}
                onChange={setSelectedSkillKey}
                allowClear
                disabled={isGenerating}
                showSearch
                optionFilterProp="label"
              >
                {availableSkills.map(skill => (
                  <Select.Option key={skill.template_key} value={skill.template_key} label={skill.template_name}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span>{skill.template_name}</span>
                      <Tag style={{ fontSize: 11, lineHeight: '18px', padding: '0 4px' }}>{skill.category}</Tag>
                    </div>
                  </Select.Option>
                ))}
              </Select>
              {selectedSkillKey && (() => {
                const skill = availableSkills.find(s => s.template_key === selectedSkillKey);
                return skill ? (
                  <div style={{ color: token.colorSuccess, fontSize: 12, marginTop: 4 }}>
                    ✓ {skill.description}
                  </div>
                ) : null;
              })()}
            </Form.Item>

            <Form.Item
              label="Số từ mục tiêu"
              tooltip="Số từ mục tiêu khi AI sinh chương, thực tế có thể chênh lệch chút ít (sau khi sửa sẽ tự ghi nhớ)"
              style={{ flex: 1, marginBottom: isMobile ? 16 : 0 }}
            >
              <InputNumber
                min={500}
                max={10000}
                step={100}
                value={targetWordCount}
                onChange={(value) => {
                  const newValue = value || DEFAULT_WORD_COUNT;
                  setTargetWordCount(newValue);
                  setCachedWordCount(newValue);
                }}
                disabled={isGenerating}
                style={{ width: '100%' }}
                formatter={(value) => `${value}  từ`}
                parser={(value) => parseInt(value?.replace('  từ', '') || '0', 10) as unknown as 500}
              />
            </Form.Item>

            <Form.Item
              label="Mô hình AI"
              tooltip="Chọn mô hình AI dùng để sinh nội dung chương, không chọn thì dùng mô hình mặc định"
              style={{ flex: 1, marginBottom: isMobile ? 16 : 0 }}
            >
              <Select
                placeholder={selectedModel ? `Mặc định: ${availableModels.find(m => m.value === selectedModel)?.label || selectedModel}` : "Dùng mô hình mặc định"}
                value={selectedModel}
                onChange={setSelectedModel}
                allowClear
                disabled={isGenerating}
                showSearch
                optionFilterProp="label"
              >
                {availableModels.map(model => (
                  <Select.Option key={model.value} value={model.value} label={model.label}>
                    {model.label}
                  </Select.Option>
                ))}
              </Select>
            </Form.Item>
          </div>

          <Form.Item label="Nội dung chương" name="content">
            <TextArea
              ref={contentTextAreaRef}
              rows={isMobile ? 12 : 20}
              placeholder="Bắt đầu viết..."
              style={{ fontFamily: 'monospace', fontSize: isMobile ? 12 : 14 }}
              disabled={isGenerating}
            />
          </Form.Item>

          {/* Thanh công cụ nổi viết lại cục bộ */}
          <div data-partial-regenerate-toolbar>
            <PartialRegenerateToolbar
              visible={partialRegenerateToolbarVisible && !isGenerating}
              position={partialRegenerateToolbarPosition}
              selectedText={selectedTextForRegenerate}
              onRegenerate={handleOpenPartialRegenerate}
            />
          </div>

          <Form.Item>
            <Space style={{ width: '100%', justifyContent: 'flex-end', flexDirection: isMobile ? 'column' : 'row', alignItems: isMobile ? 'stretch' : 'center' }}>
              <Space style={{ width: isMobile ? '100%' : 'auto' }}>
                <Button
                  onClick={() => {
                    if (isGenerating) {
                      message.warning('AI đang sáng tác, vui lòng chờ hoàn tất rồi mới đóng');
                      return;
                    }
                    setIsEditorOpen(false);
                  }}
                  block={isMobile}
                  disabled={isGenerating}
                >
                  Hủy
                </Button>
                <Button
                  type="primary"
                  htmlType="submit"
                  block={isMobile}
                  disabled={isGenerating}
                >
                  Lưu chương
                </Button>
              </Space>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {analysisChapterId && (
        <ChapterAnalysis
          chapterId={analysisChapterId}
          visible={analysisVisible}
          onClose={() => {
            setAnalysisVisible(false);

            // Refresh danh sách chương để hiển thị nội dung mới nhất
            refreshChapters();

            // Refresh thông tin dự án để cập nhật thống kê số từ
            if (currentProject) {
              projectApi.getProject(currentProject.id)
                .then(updatedProject => {
                  setCurrentProject(updatedProject);
                })
                .catch(error => {
                  console.error('Refresh thông tin dự án thất bại:', error);
                });
            }

            // Trì hoãn 500ms rồi refresh hàng loạt trạng thái phân tích, tránh gọi API đơn chương tần suất cao
            setTimeout(() => {
              loadAnalysisTasks();
            }, 500);

            setAnalysisChapterId(null);
          }}
        />
      )}

      {/* Hộp thoại sinh hàng loạt */}
      <Modal
        title={
          <Space>
            <RocketOutlined style={{ color: token.colorInfo }} />
            <span>Sinh hàng loạt nội dung chương</span>
          </Space>
        }
        open={batchGenerateVisible}
        onCancel={() => {
          if (batchGenerating) {
            modal.confirm({
              title: 'Xác nhận hủy',
              content: 'Sinh hàng loạt đang tiến hành, bạn có chắc muốn hủy không?',
              okText: 'Xác nhận hủy',
              cancelText: 'Tiếp tục sinh',
              centered: true,
              onOk: () => {
                handleCancelBatchGenerate();
                setBatchGenerateVisible(false);
              },
            });
          } else {
            setBatchGenerateVisible(false);
          }
        }}
        footer={!batchGenerating ? (
          <Space style={{ width: '100%', justifyContent: 'flex-end', flexWrap: 'wrap' }}>
            <Button onClick={() => setBatchGenerateVisible(false)}>
              Hủy
            </Button>
            <Button type="primary" icon={<RocketOutlined />} onClick={() => batchForm.submit()}>
              Bắt đầu sinh hàng loạt
            </Button>
          </Space>
        ) : null}
        width={isMobile ? 'calc(100vw - 32px)' : 700}
        centered
        closable={!batchGenerating}
        maskClosable={!batchGenerating}
        style={isMobile ? {
          maxWidth: 'calc(100vw - 32px)',
          margin: '0 auto',
          padding: '0 16px'
        } : undefined}
        styles={{
          body: {
            maxHeight: isMobile ? 'calc(100vh - 200px)' : 'calc(100vh - 260px)',
            overflowY: 'auto',
            overflowX: 'hidden'
          }
        }}
      >
        {!batchGenerating ? (
          <Form
            form={batchForm}
            layout="vertical"
            onFinish={handleBatchGenerate}
            initialValues={{
              startChapterNumber: sortedChapters.find(ch => !ch.content || ch.content.trim() === '')?.chapter_number || 1,
              count: 5,
              enableAnalysis: true,
              styleId: selectedStyleId,
              targetWordCount: getCachedWordCount(),
              model: selectedModel,
            }}
          >
            <Alert
              message="Hướng dẫn sinh hàng loạt: sinh nghiêm ngặt theo thứ tự | thống nhất phong cách và số từ | bất kỳ lỗi nào cũng dừng"
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
            />

            {/* Hàng đầu: chương bắt đầu + số lượng sinh */}
            <div style={{ display: 'flex', flexDirection: isMobile ? 'column' : 'row', gap: isMobile ? 0 : 16 }}>
              <Form.Item
                label="Chương bắt đầu"
                name="startChapterNumber"
                rules={[{ required: true, message: 'Vui lòng chọn' }]}
                style={{ flex: 1, marginBottom: 12 }}
              >
                <Select placeholder="Chọn chương bắt đầu">
                  {sortedChapters
                    .filter(ch => !ch.content || ch.content.trim() === '')
                    .filter(ch => canGenerateChapter(ch))
                    .map(ch => (
                      <Select.Option key={ch.id} value={ch.chapter_number}>
                        Chương {ch.chapter_number}: {ch.title}
                      </Select.Option>
                    ))}
                </Select>
              </Form.Item>

              <Form.Item
                label="Số lượng sinh"
                name="count"
                rules={[{ required: true, message: 'Vui lòng chọn' }]}
                style={{ marginBottom: 12 }}
              >
                <Radio.Group buttonStyle="solid" size={isMobile ? 'small' : 'middle'}>
                  <Radio.Button value={5}>5 chương</Radio.Button>
                  <Radio.Button value={10}>10 chương</Radio.Button>
                  <Radio.Button value={15}>15 chương</Radio.Button>
                  <Radio.Button value={20}>20 chương</Radio.Button>
                </Radio.Group>
              </Form.Item>
            </div>

            {/* Hàng hai: phong cách viết + số từ mục tiêu */}
            <div style={{ display: 'flex', flexDirection: isMobile ? 'column' : 'row', gap: isMobile ? 0 : 16 }}>
              <Form.Item
                label="Phong cách viết"
                name="styleId"
                rules={[{ required: true, message: 'Vui lòng chọn' }]}
                style={{ flex: 1, marginBottom: 12 }}
              >
                <Select placeholder="Vui lòng chọn phong cách viết" showSearch optionFilterProp="children">
                  {writingStyles.map(style => (
                    <Select.Option key={style.id} value={style.id}>
                      {style.name}{style.is_default && ' (mặc định)'}
                    </Select.Option>
                  ))}
                </Select>
              </Form.Item>

              <Form.Item
                label="Số từ mục tiêu"
                name="targetWordCount"
                rules={[{ required: true, message: 'Vui lòng đặt' }]}
                tooltip="Sau khi sửa tự ghi nhớ"
                style={{ flex: 1, marginBottom: 12 }}
              >
                <InputNumber
                  min={500}
                  max={10000}
                  step={100}
                  style={{ width: '100%' }}
                  formatter={(value) => `${value}  từ`}
                  parser={(value) => parseInt(value?.replace('  từ', '') || '0', 10) as unknown as 500}
                  onChange={(value) => {
                    if (value) {
                      setCachedWordCount(value);
                    }
                  }}
                />
              </Form.Item>
            </div>

            {/* Hàng ba: mô hình AI + Skill */}
            <div style={{ display: 'flex', flexDirection: isMobile ? 'column' : 'row', gap: isMobile ? 0 : 16 }}>
              <Form.Item
                label="Mô hình AI"
                tooltip="Không chọn thì dùng mô hình mặc định"
                style={{ flex: 1, marginBottom: 12 }}
              >
                <Select
                  placeholder={batchSelectedModel ? `Mặc định: ${availableModels.find(m => m.value === batchSelectedModel)?.label || batchSelectedModel}` : "Dùng mô hình mặc định"}
                  value={batchSelectedModel}
                  onChange={setBatchSelectedModel}
                  allowClear
                  showSearch
                  optionFilterProp="label"
                >
                  {availableModels.map(model => (
                    <Select.Option key={model.value} value={model.value} label={model.label}>
                      {model.label}
                    </Select.Option>
                  ))}
                </Select>
              </Form.Item>

              <Form.Item
                label="Áp dụng Skill"
                tooltip="Chọn một workflow Skill để hướng dẫn sáng tác hàng loạt, không chọn thì dùng quy trình sáng tác chuẩn"
                style={{ flex: 1, marginBottom: 12 }}
              >
                <Select
                  placeholder="Không dùng Skill (sáng tác chuẩn)"
                  value={batchSelectedSkillKey}
                  onChange={setBatchSelectedSkillKey}
                  allowClear
                  showSearch
                  optionFilterProp="label"
                >
                  {availableSkills.map(skill => (
                    <Select.Option key={skill.template_key} value={skill.template_key} label={skill.template_name}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span>{skill.template_name}</span>
                        <Tag style={{ fontSize: 11, lineHeight: '18px', padding: '0 4px' }}>{skill.category}</Tag>
                      </div>
                    </Select.Option>
                  ))}
                </Select>
              </Form.Item>
            </div>

            {/* Đồng bộ phân tích (luôn bật) */}
            <Form.Item
              label="Đồng bộ phân tích"
              name="enableAnalysis"
              tooltip="Phải bật để đảm bảo cốt truyện liền mạch"
              style={{ marginBottom: 12 }}
            >
              <Radio.Group disabled>
                <Radio value={true}>
                  <span style={{ fontSize: 12, color: token.colorSuccess }}>✓ Tự động cập nhật trạng thái nhân vật</span>
                </Radio>
              </Radio.Group>
            </Form.Item>
          </Form>
        ) : (
          <div>
            <Alert
              message="Gợi ý thân thiện"
              description={
                <ul style={{ margin: '8px 0 0 0', paddingLeft: 20 }}>
                  <li>Sinh hàng loạt cần một khoảng thời gian, có thể chuyển sang trang khác</li>
                  <li>Đóng trang rồi mở lại sẽ tự khôi phục tiến độ task</li>
                  <li>Có thể bấm nút "Hủy task" bất cứ lúc nào để dừng sinh</li>
                  {batchProgress?.estimated_time_minutes && batchProgress.completed === 0 && (
                    <li>⏱️ Thời gian dự kiến: khoảng  {batchProgress.estimated_time_minutes}  phút</li>
                  )}
                </ul>
              }
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
            />

            <div style={{ textAlign: 'center' }}>
              <Button
                danger
                icon={<StopOutlined />}
                onClick={() => {
                  modal.confirm({
                    title: 'Xác nhận hủy',
                    content: 'Bạn có chắc muốn hủy sinh hàng loạt không? Các chương đã sinh sẽ được giữ lại.',
                    okText: 'Xác nhận hủy',
                    cancelText: 'Tiếp tục sinh',
                    okButtonProps: { danger: true },
                    onOk: handleCancelBatchGenerate,
                  });
                }}
              >
                Hủy task
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* Hiển thị tiến trình sinh một chương */}
      <SSELoadingOverlay
        loading={isGenerating}
        progress={singleChapterProgress}
        message={singleChapterProgressMessage}
      />

      {/* Trình đọc chương */}
      {readingChapter && (
        <ChapterReader
          visible={readerVisible}
          chapter={readingChapter}
          onClose={() => {
            setReaderVisible(false);
            setReadingChapter(null);
          }}
          onChapterChange={handleReaderChapterChange}
        />
      )}

      {/* Popup viết lại cục bộ */}
      {editingId && (
        <PartialRegenerateModal
          visible={partialRegenerateModalVisible}
          chapterId={editingId}
          selectedText={selectedTextForRegenerate}
          startPosition={selectionStartPosition}
          endPosition={selectionEndPosition}
          styleId={selectedStyleId}
          onClose={() => setPartialRegenerateModalVisible(false)}
          onApply={handleApplyPartialRegenerate}
        />
      )}

      {/* Trình chỉnh sửa kế hoạch */}
      {editingPlanChapter && currentProject && (() => {
        let parsedPlanData = null;
        try {
          if (editingPlanChapter.expansion_plan) {
            parsedPlanData = JSON.parse(editingPlanChapter.expansion_plan);
          }
        } catch (error) {
          console.error('Phân tích dữ liệu kế hoạch thất bại:', error);
        }

        return (
          <ExpansionPlanEditor
            visible={planEditorVisible}
            planData={parsedPlanData}
            chapterSummary={editingPlanChapter.summary || null}
            projectId={currentProject.id}
            onSave={handleSavePlan}
            onCancel={() => {
              setPlanEditorVisible(false);
              setEditingPlanChapter(null);
            }}
          />
        );
      })()}
    </div>
  );
}
