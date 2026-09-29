import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  Button,
  Card,
  Col,
  Collapse,
  Empty,
  Input,
  InputNumber,
  List,
  message,
  Popconfirm,
  Progress,
  Row,
  Select,
  Space,
  Spin,
  Steps,
  Tag,
  Typography,
  Upload,
  theme,
} from 'antd';
import type { UploadFile } from 'antd/es/upload/interface';
import { InboxOutlined, PlayCircleOutlined, ReloadOutlined, StopOutlined, WarningOutlined, RedoOutlined } from '@ant-design/icons';
import { bookImportApi } from '../services/api';
import type {
  BookImportApplyPayload,
  BookImportExtractMode,
  BookImportPreview,
  BookImportStepFailure,
  BookImportTask,
} from '../types';

const { Text, Title } = Typography;
const { Dragger } = Upload;
const { TextArea } = Input;

const BOOK_IMPORT_CACHE_KEY = 'book_import_page_cache_v1';

type BookImportPageCache = {
  taskId: string | null;
  taskStatus: BookImportTask | null;
  preview: BookImportPreview | null;
  applyProgress: number;
  applyMessage: string;
  applyError: string | null;
  isApplyComplete: boolean;
  extractMode: BookImportExtractMode;
  tailChapterCount: number;
  cachedAt: number;
};

function loadBookImportCache(): BookImportPageCache | null {
  try {
    const raw = sessionStorage.getItem(BOOK_IMPORT_CACHE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as BookImportPageCache;
  } catch (error) {
    console.warn('Đọc cache trang tách sách thất bại:', error);
    return null;
  }
}

function saveBookImportCache(cache: BookImportPageCache) {
  try {
    sessionStorage.setItem(BOOK_IMPORT_CACHE_KEY, JSON.stringify(cache));
  } catch (error) {
    const isQuotaExceeded =
      error instanceof DOMException &&
      (error.name === 'QuotaExceededError' || error.name === 'NS_ERROR_DOM_QUOTA_REACHED');

    if (isQuotaExceeded) {
      // Khi tràn dung lượng, hạ cấp sang cache nhẹ (không lưu nội dung xem trước), tránh báo lỗi liên tục
      try {
        const lightweightCache: BookImportPageCache = {
          ...cache,
          preview: null,
        };
        sessionStorage.setItem(BOOK_IMPORT_CACHE_KEY, JSON.stringify(lightweightCache));
        return;
      } catch (fallbackError) {
        console.warn('Ghi cache nhẹ trang tách sách thất bại:', fallbackError);
        try {
          sessionStorage.removeItem(BOOK_IMPORT_CACHE_KEY);
        } catch {
          // ignore
        }
      }
    }

    console.warn('Ghi cache trang tách sách thất bại:', error);
  }
}

function clearBookImportCache() {
  try {
    sessionStorage.removeItem(BOOK_IMPORT_CACHE_KEY);
  } catch (error) {
    console.warn('Dọn cache trang tách sách thất bại:', error);
  }
}

function isNotFoundError(error: unknown): boolean {
  if (!error || typeof error !== 'object') return false;
  const maybeError = error as { response?: { status?: number } };
  return maybeError.response?.status === 404;
}

export default function BookImport() {
  const navigate = useNavigate();
  const { token } = theme.useToken();
  const isMobile = window.innerWidth <= 768;
  const [file, setFile] = useState<File | null>(null);
  const [extractMode, setExtractMode] = useState<BookImportExtractMode>('tail');
  const [tailChapterCount, setTailChapterCount] = useState(10);

  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskStatus, setTaskStatus] = useState<BookImportTask | null>(null);
  const [preview, setPreview] = useState<BookImportPreview | null>(null);

  const [creatingTask, setCreatingTask] = useState(false);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [applying, setApplying] = useState(false);
  const [applyProgress, setApplyProgress] = useState(0);
  const [applyMessage, setApplyMessage] = useState('');
  const [applyError, setApplyError] = useState<string | null>(null);
  const [isApplyComplete, setIsApplyComplete] = useState(false);
  const [cacheReady, setCacheReady] = useState(false);

  // State liên quan đến thất bại và thử lại ở cấp bước
  const [failedSteps, setFailedSteps] = useState<BookImportStepFailure[]>([]);
  const [retrying, setRetrying] = useState(false);
  const [retryProgress, setRetryProgress] = useState(0);
  const [retryMessage, setRetryMessage] = useState('');
  const importedProjectId = useRef<string | null>(null);

  const isTaskTerminal = useMemo(() => {
    return !!taskStatus && ['completed', 'failed', 'cancelled'].includes(taskStatus.status);
  }, [taskStatus]);

  const currentStep = useMemo(() => {
    if (!taskId) return 0;
    if (taskStatus && ['pending', 'running'].includes(taskStatus.status)) return 1;
    if (applying || isApplyComplete) return 3; // Thêm bước tạo & nhập
    if (preview) return 2;
    return 1;
  }, [taskId, taskStatus, preview, applying, isApplyComplete]);

  const canRestart = useMemo(() => {
    return Boolean(
      file ||
      taskId ||
      taskStatus ||
      preview ||
      applyProgress > 0 ||
      applyMessage ||
      applyError ||
      isApplyComplete ||
      failedSteps.length > 0 ||
      retrying
    );
  }, [
    file,
    taskId,
    taskStatus,
    preview,
    applyProgress,
    applyMessage,
    applyError,
    isApplyComplete,
    failedSteps,
    retrying,
  ]);

  const normalizedTailChapterCount = useMemo(
    () => Math.max(5, Math.ceil(tailChapterCount / 5) * 5),
    [tailChapterCount]
  );
  const effectiveExtractMode = useMemo<BookImportExtractMode>(
    () => (normalizedTailChapterCount > 50 ? 'full' : extractMode),
    [extractMode, normalizedTailChapterCount]
  );
  const rangeLocked = Boolean(taskId || taskStatus || preview || creatingTask || applying || retrying);

  const stepItems = [
    { title: 'Tải file lên' },
    { title: 'Đang phân tích' },
    { title: 'Xem trước & chỉnh sửa' },
    { title: 'Tạo & nhập' },
  ];
  const currentStepText = stepItems[currentStep]?.title || 'Tải file lên';

  useEffect(() => {
    const cache = loadBookImportCache();
    if (cache) {
      const cacheAgeMs = typeof cache.cachedAt === 'number'
        ? Date.now() - cache.cachedAt
        : Number.POSITIVE_INFINITY;

      // Cache quá 6 giờ coi như hết hiệu lực, tránh dùng taskId cũ sau khi backend khởi động lại
      if (cacheAgeMs > 6 * 60 * 60 * 1000) {
        clearBookImportCache();
      } else {
        setTaskId(cache.taskId);
        setTaskStatus(cache.taskStatus);
        setPreview(cache.preview);
        setApplyProgress(cache.applyProgress);
        setApplyError(cache.applyError);
        setIsApplyComplete(cache.isApplyComplete);
        setExtractMode(cache.extractMode ?? 'tail');
        setTailChapterCount(cache.tailChapterCount ?? 10);
        setApplyMessage(
          cache.applyMessage || (cache.applyProgress > 0 && !cache.isApplyComplete
            ? 'Đã khôi phục cache trang, vui lòng nhấn lại "Xác nhận nhập" để tiếp tục.'
            : '')
        );
        message.info('Đã khôi phục cache trang nhập tách sách');
      }
    }
    setCacheReady(true);
  }, []);

  useEffect(() => {
    if (!cacheReady) return;

    // Sau khi nhập xong phải dọn cache, tránh quay lại trang khôi phục trạng thái task cũ
    if (isApplyComplete) {
      clearBookImportCache();
      return;
    }

    const hasCacheData = Boolean(
      taskId ||
      taskStatus ||
      preview ||
      applyError ||
      applyProgress > 0 ||
      applyMessage
    );

    if (!hasCacheData) {
      clearBookImportCache();
      return;
    }

    saveBookImportCache({
      taskId,
      taskStatus,
      // preview chứa toàn bộ nội dung chương, dung lượng lớn, dễ chạm giới hạn quota sessionStorage
      // Khi khôi phục trang có thể lấy lại preview theo taskId + taskStatus
      preview: null,
      applyProgress,
      applyMessage,
      applyError,
      isApplyComplete,
      extractMode,
      tailChapterCount,
      cachedAt: Date.now(),
    });
  }, [
    cacheReady,
    taskId,
    taskStatus,
    preview,
    applyProgress,
    applyMessage,
    applyError,
    isApplyComplete,
    extractMode,
    tailChapterCount,
  ]);

  useEffect(() => {
    if (!taskId) return;
    if (isTaskTerminal) return;

    const timer = setInterval(async () => {
      try {
        const status = await bookImportApi.getTaskStatus(taskId);
        setTaskStatus(status);
      } catch (error) {
        console.error('Poll trạng thái task thất bại:', error);
        if (isNotFoundError(error)) {
          clearBookImportCache();
          setTaskId(null);
          setTaskStatus(null);
          setPreview(null);
          setApplyProgress(0);
          setApplyMessage('');
          setApplyError(null);
          setIsApplyComplete(false);
          message.warning('Task tách sách đã hết hiệu lực (có thể do dịch vụ khởi động lại), vui lòng tải lại TXT và bắt đầu phân tích');
        }
      }
    }, 1500);

    return () => clearInterval(timer);
  }, [taskId, isTaskTerminal]);

  useEffect(() => {
    const fetchPreview = async () => {
      if (!taskId || !taskStatus) return;
      if (taskStatus.status !== 'completed' || preview) return;

      try {
        setLoadingPreview(true);
        const data = await bookImportApi.getPreview(taskId);
        setPreview(data);
      } catch (error) {
        console.error('Lấy bản xem trước thất bại:', error);
        if (isNotFoundError(error)) {
          clearBookImportCache();
          setTaskId(null);
          setTaskStatus(null);
          setPreview(null);
          setApplyProgress(0);
          setApplyMessage('');
          setApplyError(null);
          setIsApplyComplete(false);
          message.warning('Bản xem trước task tách sách không tồn tại (có thể do dịch vụ khởi động lại), đã xóa cache, vui lòng tải lại TXT');
        } else {
          message.error('Lấy bản xem trước thất bại');
        }
      } finally {
        setLoadingPreview(false);
      }
    };

    fetchPreview();
  }, [taskId, taskStatus, preview]);

  const startTask = async () => {
    if (!file) {
      message.warning('Vui lòng chọn file TXT trước');
      return;
    }

    try {
      setCreatingTask(true);
      setPreview(null);
      setTaskStatus(null);

      setExtractMode(effectiveExtractMode);
      setTailChapterCount(normalizedTailChapterCount);

      const response = await bookImportApi.createTask({
        file,
        extract_mode: effectiveExtractMode,
        tail_chapter_count: normalizedTailChapterCount,
      });

      setTaskId(response.task_id);
      message.success('Đã tạo task tách sách');
    } catch (error) {
      console.error('Tạo task thất bại:', error);
      message.error('Tạo task tách sách thất bại');
    } finally {
      setCreatingTask(false);
    }
  };

  const refreshStatus = async () => {
    if (!taskId) return;
    try {
      const status = await bookImportApi.getTaskStatus(taskId);
      setTaskStatus(status);
    } catch (error) {
      console.error('Refresh trạng thái thất bại:', error);
      if (isNotFoundError(error)) {
        clearBookImportCache();
        setTaskId(null);
        setTaskStatus(null);
        setPreview(null);
        setApplyProgress(0);
        setApplyMessage('');
        setApplyError(null);
        setIsApplyComplete(false);
        message.warning('Task không tồn tại, đã xóa cache cục bộ, vui lòng tạo lại task tách sách');
      }
    }
  };

  const cancelTask = async () => {
    if (!taskId) return;
    try {
      await bookImportApi.cancelTask(taskId);
      message.success('Đã hủy task');
      await refreshStatus();
    } catch (error) {
      console.error('Hủy task thất bại:', error);
      message.error('Hủy task thất bại');
    }
  };

  const applyImport = async () => {
    if (!taskId || !preview) return;

    const payload: BookImportApplyPayload = {
      project_suggestion: preview.project_suggestion,
      chapters: preview.chapters,
      outlines: preview.outlines,
      import_mode: 'append',
    };

    try {
      setApplying(true);
      setApplyProgress(0);
      setApplyMessage('Đang chuẩn bị nhập...');
      setApplyError(null);
      setIsApplyComplete(false);
      setFailedSteps([]);

      await bookImportApi.applyImportStream(
        taskId,
        payload,
        {
          onProgress: (msg, prog, status) => {
            // Kiểm tra có phải thông báo đặc biệt của bước thất bại không
            if (status === 'step_failures') {
              try {
                const parsed = JSON.parse(msg);
                if (parsed.failed_steps && Array.isArray(parsed.failed_steps)) {
                  setFailedSteps(parsed.failed_steps as BookImportStepFailure[]);
                }
              } catch {
                // Không phải JSON, bỏ qua
              }
              return;
            }
            setApplyProgress(prog);
            setApplyMessage(msg);
          },
          onResult: (result) => {
            importedProjectId.current = result.project_id;
            const generatedCareers = result.statistics?.generated_careers ?? 0;
            const generatedEntities = result.statistics?.generated_entities ?? 0;

            // Kiểm tra cuối cùng có bước thất bại không
            setIsApplyComplete(true);

            // Chỉ tự động chuyển khi không có bước thất bại
            // Lưu ý: ở đây cần delay một frame để chờ cập nhật failedSteps
            setTimeout(() => {
              setFailedSteps(prev => {
                if (prev.length === 0) {
                  message.success(`Nhập thành công: đã tạo ${generatedCareers} nghề nghiệp, ${generatedEntities} nhân vật/tổ chức`);
                  clearBookImportCache();
                  setTimeout(() => {
                    navigate(`/project/${result.project_id}/chapters`);
                  }, 1000);
                } else {
                  message.warning(`Nhập hoàn tất, nhưng có ${prev.length} bước tạo thất bại, có thể nhấn thử lại`);
                }
                return prev;
              });
            }, 100);
          },
          onError: (error) => {
            console.error('Quá trình nhập xảy ra lỗi:', error);
            setApplyError(`Nhập thất bại: ${error}`);
            message.error(`Nhập thất bại: ${error}`);
            setApplying(false);
          },
          onComplete: () => {
            setApplyProgress(100);
            setApplyMessage('Nhập hoàn tất!');
          }
        }
      );
    } catch (error) {
      console.error('Xác nhận nhập thất bại:', error);
      setApplyError('Xác nhận nhập thất bại, không thể kết nối đến máy chủ');
      message.error('Xác nhận nhập thất bại');
      setApplying(false);
    }
  };

  const retryFailedSteps = useCallback(async () => {
    if (!taskId || failedSteps.length === 0) return;

    const stepsToRetry = failedSteps.map(f => f.step_name);

    try {
      setRetrying(true);
      setRetryProgress(0);
      setRetryMessage('Đang thử lại các bước tạo thất bại...');

      await bookImportApi.retryFailedStepsStream(
        taskId,
        stepsToRetry,
        {
          onProgress: (msg, prog, status) => {
            if (status === 'step_failures') {
              try {
                const parsed = JSON.parse(msg);
                if (parsed.failed_steps && Array.isArray(parsed.failed_steps)) {
                  setFailedSteps(parsed.failed_steps as BookImportStepFailure[]);
                }
              } catch {
                // Không phải JSON, bỏ qua
              }
              return;
            }
            setRetryProgress(prog);
            setRetryMessage(msg);
          },
          onResult: (result) => {
            if (result.still_failed && result.still_failed.length > 0) {
              setFailedSteps(result.still_failed);
              message.warning(`Thử lại hoàn tất, vẫn còn ${result.still_failed.length} bước thất bại`);
            } else {
              setFailedSteps([]);
              message.success('Tất cả các bước thử lại thành công!');
              clearBookImportCache();
              const projectId = result.project_id || importedProjectId.current;
              if (projectId) {
                setTimeout(() => {
                  navigate(`/project/${projectId}/chapters`);
                }, 1000);
              }
            }
          },
          onError: (error) => {
            console.error('Thử lại thất bại:', error);
            message.error(`Thử lại thất bại: ${error}`);
          },
          onComplete: () => {
            setRetrying(false);
            setRetryProgress(100);
            setRetryMessage('Thử lại hoàn tất');
          }
        }
      );
    } catch (error) {
      console.error('Request thử lại thất bại:', error);
      message.error('Request thử lại thất bại, không thể kết nối đến máy chủ');
      setRetrying(false);
    }
  }, [taskId, failedSteps, navigate]);

  const skipFailedSteps = useCallback(() => {
    setFailedSteps([]);
    clearBookImportCache();
    const projectId = importedProjectId.current;
    if (projectId) {
      message.info('Đã bỏ qua bước thất bại, đang chuyển đến dự án...');
      navigate(`/project/${projectId}/chapters`);
    }
  }, [navigate]);

  const restartImport = useCallback(() => {
    clearBookImportCache();
    importedProjectId.current = null;

    setFile(null);
    setTaskId(null);
    setTaskStatus(null);
    setPreview(null);

    setCreatingTask(false);
    setLoadingPreview(false);
    setApplying(false);
    setApplyProgress(0);
    setApplyMessage('');
    setApplyError(null);
    setIsApplyComplete(false);

    setFailedSteps([]);
    setRetrying(false);
    setRetryProgress(0);
    setRetryMessage('');
    setExtractMode('tail');
    setTailChapterCount(10);

    message.success('Đã bắt đầu lại, vui lòng tải lại TXT và phân tích');
  }, []);

  const updateChapter = (index: number, patch: Partial<BookImportPreview['chapters'][number]>) => {
    setPreview(prev => {
      if (!prev) return prev;
      const next = [...prev.chapters];
      next[index] = { ...next[index], ...patch };
      return { ...prev, chapters: next };
    });
  };

  return (
    <div
      style={{
        minHeight: '90vh',
        overflow: 'auto',
        background: `linear-gradient(180deg, ${token.colorBgLayout} 0%, ${token.colorFillSecondary} 100%)`,
        padding: isMobile ? '20px 16px 70px' : '24px 24px 70px',
      }}
    >
      <div style={{ maxWidth: 1400, margin: '0 auto', width: '100%' }}>
        <Card
          variant="borderless"
          style={{
            background: `linear-gradient(135deg, ${token.colorPrimary} 0%, ${token.colorPrimaryHover} 100%)`,
            borderRadius: isMobile ? 16 : 20,
            boxShadow: token.boxShadowSecondary,
            marginBottom: isMobile ? 14 : 16,
            border: 'none',
            position: 'relative',
            overflow: 'hidden',
          }}
        >
          <div style={{ position: 'absolute', top: -48, right: -48, width: 160, height: 160, borderRadius: '50%', background: token.colorWhite, opacity: 0.08, pointerEvents: 'none' }} />
          <div style={{ position: 'absolute', bottom: -40, left: '26%', width: 110, height: 110, borderRadius: '50%', background: token.colorWhite, opacity: 0.05, pointerEvents: 'none' }} />

          <Row align="middle" justify="space-between" gutter={[16, 16]} style={{ position: 'relative', zIndex: 1 }}>
            <Col xs={24} sm={12}>
              <Space direction="vertical" size={4}>
                <Title level={isMobile ? 3 : 2} style={{ margin: 0, color: token.colorWhite, textShadow: `0 2px 4px ${token.colorBgMask}` }}>
                  <InboxOutlined style={{ color: token.colorWhite, opacity: 0.9, marginRight: 8 }} />
                  Nhập tách sách
                </Title>
                <Text style={{ fontSize: isMobile ? 12 : 14, color: token.colorTextLightSolid, opacity: 0.85, marginLeft: isMobile ? 40 : 48 }}>
                  Tải TXT lên, tự động phân tích thành chương, xem trước và nhập vào dự án
                </Text>
              </Space>
            </Col>
            <Col xs={24} sm={12}>
              <Space
                size={12}
                style={{
                  width: '100%',
                  display: 'flex',
                  justifyContent: isMobile ? 'flex-start' : 'flex-end',
                }}
              >
                <Tag
                  style={{
                    marginInlineEnd: 0,
                    background: token.colorWhite,
                    border: `1px solid ${token.colorWhite}`,
                    color: token.colorPrimary,
                    fontWeight: 600,
                    borderRadius: 8,
                    paddingInline: 10,
                  }}
                >
                  Tiến độ hiện tại: {currentStepText}
                </Tag>
                <Popconfirm
                  title="Xác nhận bắt đầu lại?"
                  description="Sẽ xóa task tách sách và cache hiện tại, quay về bước tải file lên."
                  onConfirm={restartImport}
                  okText="Bắt đầu lại"
                  cancelText="Hủy"
                  disabled={!canRestart}
                >
                  <Button
                    danger
                    type="primary"
                    icon={<ReloadOutlined />}
                    disabled={!canRestart}
                    style={{ boxShadow: '0 6px 16px rgba(0, 0, 0, 0.2)', borderRadius: 10 }}
                  >
                    Bắt đầu lại
                  </Button>
                </Popconfirm>
              </Space>
            </Col>
          </Row>

          <Card
            variant="borderless"
            style={{
              marginTop: isMobile ? 14 : 18,
              borderRadius: 12,
              background: token.colorBgContainer,
              border: `1px solid ${token.colorBorderSecondary}`,
              boxShadow: token.boxShadow,
            }}
            styles={{ body: { padding: isMobile ? '10px 12px' : '12px 16px' } }}
          >
            <Steps current={currentStep} size={isMobile ? 'small' : 'default'} items={stepItems} />
          </Card>
        </Card>

      {currentStep === 0 && (
      <Card title="Tải TXT lên và bắt đầu phân tích" style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }} size={16}>
          <Dragger
            accept=".txt"
            multiple={false}
            beforeUpload={(f) => {
              setFile(f);
              return false;
            }}
            onRemove={() => {
              setFile(null);
            }}
            fileList={
              file
                ? [
                    {
                      uid: 'selected-txt',
                      name: file.name,
                      status: 'done',
                    } as UploadFile,
                  ]
                : []
            }
            style={{ padding: '8px 0' }}
          >
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p className="ant-upload-text">Nhấn hoặc kéo thả file TXT vào khu vực này</p>
            <p className="ant-upload-hint">Bản đầu chỉ hỗ trợ .txt, nên không quá 50MB</p>
          </Dragger>

          <Card size="small" title="Thiết lập phạm vi phân tích">
            <Space direction="vertical" style={{ width: '100%' }} size={12}>
              {rangeLocked && (
                <Alert
                  type="warning"
                  showIcon
                  message="Phạm vi phân tích của task hiện tại đã bị khóa"
                  description="Task tách sách sẽ thực hiện theo phạm vi phân tích lúc tạo task. Nếu cần sửa phạm vi, vui lòng nhấn “Bắt đầu lại” phía trên rồi tải lại và phân tích."
                />
              )}
              <Select
                value={extractMode}
                onChange={(value) => setExtractMode(value)}
                options={[
                  { label: 'Lấy x chương cuối để tạo ngược', value: 'tail' },
                  { label: 'Tạo ngược toàn bộ sách', value: 'full' },
                ]}
                style={{ width: '100%' }}
                disabled={rangeLocked}
              />
              <InputNumber
                min={5}
                max={55}
                step={5}
                precision={0}
                value={tailChapterCount}
                disabled={rangeLocked || extractMode !== 'tail'}
                onChange={(value) => setTailChapterCount(typeof value === 'number' ? value : 10)}
                addonBefore="Số chương cuối"
                style={{ width: '100%' }}
              />
              <Text type="secondary">
                {effectiveExtractMode === 'tail'
                  ? `Hiện sẽ lấy ${normalizedTailChapterCount} chương cuối để tạo ngược; số chương phải là bội số của 5, tối đa 50 chương.`
                  : extractMode === 'tail' && tailChapterCount > 50
                    ? 'Số chương nhập hiện đã vượt quá 50, sẽ tự động xử lý tách toàn bộ sách.'
                    : 'Hiện sẽ tạo ngược dựa trên toàn bộ nội dung sách, phù hợp tách sách hoàn chỉnh nhưng có thể tốn thời gian hơn.'}
              </Text>
            </Space>
          </Card>

          <Alert
            type="info"
            showIcon
            message="Yêu cầu định dạng TXT tách sách được hỗ trợ"
            description={
              <div style={{ lineHeight: 1.8 }}>
                <div>1. Chỉ hỗ trợ file <strong>.txt</strong>, nên dùng dòng tiêu đề chương riêng cho mỗi chương.</div>
                <div>2. Định dạng đề xuất: <strong>第1章 标题</strong> (Chương 1 Tiêu đề), dòng tiếp theo bắt đầu viết nội dung chính.</div>
                <div>3. Nên xuống dòng nội dung theo đoạn tự nhiên, dòng đầu có thể thụt vào hai ký tự.</div>
                <div>4. Giữa các chương chỉ cần để dòng trống, không thêm đường phân cách thừa, “toàn văn hoàn”, thời gian xuất, v.v.</div>
                <div style={{ marginTop: 8 }}>
                  Ví dụ:
                  <pre style={{ margin: '8px 0 0', padding: 12, borderRadius: 8, background: token.colorFillAlter, whiteSpace: 'pre-wrap' }}>
{`第1章 初入江湖
这里是第1章正文第一段。
这里是第1章正文第二段。

第2章 雨夜追踪
这里是第2章正文内容。`}
                  </pre>
                </div>
              </div>
            }
          />
          
          <Space wrap>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              loading={creatingTask}
              onClick={startTask}
            >
              Bắt đầu phân tích
            </Button>
            {taskId && (
              <Tag color="blue">ID task: {taskId}</Tag>
            )}
          </Space>
        </Space>
      </Card>
      )}

      {currentStep === 1 && (
      <Card title="Trạng thái task phân tích" style={{ marginBottom: 16 }}>
        {!taskId ? (
          <Empty description="Chưa tạo task" />
        ) : (
          <div style={{ textAlign: 'center', padding: '24px 0' }}>
            <Progress
              type="circle"
              percent={taskStatus?.progress || 0}
              status={
                taskStatus?.status === 'failed' ? 'exception' :
                taskStatus?.status === 'completed' ? 'success' :
                'active'
              }
            />
            <div style={{ marginTop: 24 }}>
              <Text strong style={{ fontSize: 16 }}>
                {taskStatus?.status === 'pending' && 'Đang chờ điều phối...'}
                {taskStatus?.status === 'running' && 'Đang phân tích file TXT...'}
                {taskStatus?.status === 'completed' && 'Phân tích hoàn tất! Đang tạo bản xem trước...'}
                {taskStatus?.status === 'failed' && 'Phân tích thất bại'}
                {taskStatus?.status === 'cancelled' && 'Đã hủy'}
              </Text>
              {taskStatus?.message && (
                <div style={{ marginTop: 8 }}>
                  <Text type="secondary">{taskStatus.message}</Text>
                </div>
              )}
            </div>

            {taskStatus?.error && (
              <Alert type="error" message={taskStatus.error} showIcon style={{ marginTop: 16, textAlign: 'left' }} />
            )}

            <Space style={{ marginTop: 24 }}>
              <Button icon={<ReloadOutlined />} onClick={refreshStatus}>Làm mới trạng thái</Button>
              {taskStatus && ['pending', 'running'].includes(taskStatus.status) && (
                <Button danger icon={<StopOutlined />} onClick={cancelTask}>Hủy task</Button>
              )}
            </Space>
          </div>
        )}
      </Card>
      )}

      {currentStep === 2 && (
      <>
      <Card
        title="Xem trước & chỉnh sửa"
        extra={
          <Button
            type="primary"
            loading={applying}
            disabled={!preview}
            onClick={applyImport}
          >
            Xác nhận nhập
          </Button>
        }
        style={{ marginBottom: 16 }}
      >
        <Spin spinning={loadingPreview}>
          {!preview ? (
            <Empty description="Phân tích xong sẽ hiển thị dữ liệu xem trước" />
          ) : (
            <div style={{ maxHeight: '60vh', overflowY: 'auto', paddingRight: 8 }}>
              <Space direction="vertical" style={{ width: '100%' }} size={16}>
              {preview.warnings.length > 0 && (
                <Alert
                  type="warning"
                  showIcon
                  message="Phát hiện cảnh báo"
                  description={
                    <ul style={{ margin: 0, paddingLeft: 20 }}>
                      {preview.warnings.map((w, idx) => (
                        <li key={`${w.code}-${idx}`}>[{w.level}] {w.message}</li>
                      ))}
                    </ul>
                  }
                />
              )}

              <Card
                size="small"
                title="Thông tin dự án"
              >
                <Row gutter={12}>
                  <Col xs={24} md={12}>
                    <Text>Tiêu đề</Text>
                    <Input
                      value={preview.project_suggestion.title}
                      onChange={(e) =>
                        setPreview(prev => prev ? ({
                          ...prev,
                          project_suggestion: { ...prev.project_suggestion, title: e.target.value },
                        }) : prev)
                      }
                    />
                  </Col>
                  <Col xs={24} md={12}>
                    <Text>Thể loại</Text>
                    <Input
                      value={preview.project_suggestion.genre}
                      onChange={(e) =>
                        setPreview(prev => prev ? ({
                          ...prev,
                          project_suggestion: { ...prev.project_suggestion, genre: e.target.value },
                        }) : prev)
                      }
                    />
                  </Col>
                  <Col xs={24}>
                    <Text>Chủ đề</Text>
                    <TextArea
                      rows={3}
                      value={preview.project_suggestion.theme}
                      onChange={(e) =>
                        setPreview(prev => prev ? ({
                          ...prev,
                          project_suggestion: { ...prev.project_suggestion, theme: e.target.value },
                        }) : prev)
                      }
                    />
                  </Col>
                  <Col xs={24}>
                    <Text>Giới thiệu</Text>
                    <TextArea
                      rows={3}
                      value={preview.project_suggestion.description}
                      onChange={(e) =>
                        setPreview(prev => prev ? ({
                          ...prev,
                          project_suggestion: { ...prev.project_suggestion, description: e.target.value },
                        }) : prev)
                      }
                    />
                  </Col>
                  <Col xs={24} md={12}>
                    <Text>Góc nhìn kể chuyện</Text>
                    <Select
                      style={{ width: '100%' }}
                      value={preview.project_suggestion.narrative_perspective}
                      onChange={(v) =>
                        setPreview(prev => prev ? ({
                          ...prev,
                          project_suggestion: { ...prev.project_suggestion, narrative_perspective: v },
                        }) : prev)
                      }
                      options={[
                        { value: '第一人称', label: 'Ngôi thứ nhất' },
                        { value: '第三人称', label: 'Ngôi thứ ba' },
                        { value: '全知视角', label: 'Góc nhìn toàn tri' },
                      ]}
                    />
                  </Col>
                  <Col xs={24} md={12}>
                    <Text>Số chữ mục tiêu</Text>
                    <InputNumber
                      style={{ width: '100%' }}
                      min={1000}
                      step={1000}
                      value={preview.project_suggestion.target_words}
                      onChange={(v) =>
                        setPreview(prev => prev ? ({
                          ...prev,
                          project_suggestion: {
                            ...prev.project_suggestion,
                            target_words: Number(v || 100000),
                          },
                        }) : prev)
                      }
                    />
                  </Col>
                </Row>
              </Card>

              <Card size="small" title={`Chương (${preview.chapters.length})`}>
                <Collapse
                  items={preview.chapters.map((ch, idx) => ({
                    key: String(idx),
                    label: `Chương ${ch.chapter_number} · ${ch.title}`,
                    children: (
                      <Space direction="vertical" style={{ width: '100%' }}>
                        <Input
                          value={ch.title}
                          addonBefore="Tiêu đề"
                          onChange={(e) => updateChapter(idx, { title: e.target.value })}
                        />
                        <TextArea
                          rows={2}
                          value={ch.summary}
                          placeholder="Tóm tắt chương"
                          onChange={(e) => updateChapter(idx, { summary: e.target.value })}
                        />
                        <TextArea
                          rows={8}
                          value={ch.content}
                          placeholder="Nội dung chương"
                          onChange={(e) => updateChapter(idx, { content: e.target.value })}
                        />
                      </Space>
                    ),
                  }))}
                />
              </Card>

              </Space>
            </div>
          )}
        </Spin>
      </Card>

      </>
      )}

      {currentStep === 3 && (
      <Card title="Tiến độ tạo & nhập" style={{ marginBottom: 16 }}>
        <div style={{ textAlign: 'center', padding: '40px 20px', maxWidth: 600, margin: '0 auto' }}>
          <Typography.Title level={4} style={{ marginBottom: 32 }}>
            {retrying ? 'Đang thử lại các bước tạo thất bại' : (failedSteps.length > 0 && isApplyComplete ? 'Nhập hoàn tất, một số bước cần thử lại' : 'Đang tạo và nhập nội dung dự án cho bạn')}
          </Typography.Title>
          
          <Progress
            percent={retrying ? retryProgress : applyProgress}
            status={
              applyError ? 'exception' :
              (failedSteps.length > 0 && isApplyComplete && !retrying) ? 'exception' :
              (isApplyComplete && failedSteps.length === 0) ? 'success' :
              'active'
            }
            strokeColor={{
              '0%': 'var(--color-primary)',
              '100%': failedSteps.length > 0 ? '#faad14' : 'var(--color-primary-active)',
            }}
            style={{ marginBottom: 24 }}
          />
          
          <Typography.Paragraph
            style={{
              fontSize: 16,
              marginBottom: 32,
              color: applyError ? 'var(--color-error)' :
                (failedSteps.length > 0 && isApplyComplete && !retrying) ? '#faad14' :
                'var(--color-text-secondary)'
            }}
          >
            {retrying ? retryMessage : (applyError || applyMessage)}
          </Typography.Paragraph>
          
          {applyError && (
            <Alert
              type="error"
              message="Nhập bị lỗi"
              description={applyError}
              showIcon
              style={{ textAlign: 'left', marginBottom: 24 }}
            />
          )}

          {/* Nhắc nhở bước thất bại và UI thử lại */}
          {failedSteps.length > 0 && isApplyComplete && !retrying && (
            <div style={{ textAlign: 'left', marginBottom: 24 }}>
              <Alert
                type="warning"
                icon={<WarningOutlined />}
                showIcon
                message={`${failedSteps.length} bước tạo thất bại`}
                description={
                  <div>
                    <Typography.Paragraph style={{ marginBottom: 12, color: 'rgba(0,0,0,0.65)' }}>
                      Các bước tạo AI sau chưa hoàn tất, nhưng dữ liệu cơ bản (chương, đề cương) đã nhập thành công. Bạn có thể chọn thử lại hoặc bỏ qua.
                    </Typography.Paragraph>
                    <List
                      size="small"
                      bordered
                      dataSource={failedSteps}
                      renderItem={(item) => (
                        <List.Item
                          style={{ padding: '8px 12px' }}
                        >
                          <List.Item.Meta
                            title={
                              <Space>
                                <Tag color="error">{item.step_label}</Tag>
                                {(item.retry_count ?? 0) > 0 && (
                                  <Tag color="orange">Đã thử lại {item.retry_count} lần</Tag>
                                )}
                              </Space>
                            }
                            description={
                              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                                {item.error.length > 120 ? item.error.slice(0, 120) + '...' : item.error}
                              </Typography.Text>
                            }
                          />
                        </List.Item>
                      )}
                    />
                    <Space style={{ marginTop: 16, display: 'flex', justifyContent: 'center' }}>
                      <Button
                        type="primary"
                        icon={<RedoOutlined />}
                        onClick={retryFailedSteps}
                        loading={retrying}
                      >
                        Thử lại thông minh tất cả bước thất bại
                      </Button>
                      <Button onClick={skipFailedSteps}>
                        Bỏ qua, vào thẳng dự án
                      </Button>
                    </Space>
                  </div>
                }
                style={{ marginBottom: 16 }}
              />
            </div>
          )}

          {/* Đang thử lại */}
          {retrying && (
            <div style={{ marginBottom: 24 }}>
              <Spin spinning={retrying}>
                <Alert
                  type="info"
                  showIcon
                  message="Đang thử lại..."
                  description={retryMessage}
                  style={{ textAlign: 'left' }}
                />
              </Spin>
            </div>
          )}
          
          {!failedSteps.length && !retrying && (
            <div style={{
              background: 'var(--color-bg-layout)',
              padding: 16,
              borderRadius: 8,
              textAlign: 'left',
              marginTop: 32
            }}>
              <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                Trong quá trình nhập, AI sẽ tự động bổ sung giúp bạn: <br />
                • Thiết lập thế giới quan (thời gian, địa điểm, bầu không khí, quy tắc) <br />
                • Hệ thống nghề nghiệp (nghề chính và nghề phụ) <br />
                • Nhân vật cốt lõi và tổ chức liên quan <br />
                {isApplyComplete ? 'Tất cả các bước đã hoàn tất, sắp tự động chuyển.' : 'Vui lòng kiên nhẫn chờ, hoàn tất sẽ tự động chuyển.'}
              </Typography.Text>
            </div>
          )}
        </div>
      </Card>
      )}

      </div>
    </div>
  );
}