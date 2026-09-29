import { useState, useEffect, useRef } from 'react';
import { Modal, Spin, Alert, Tabs, Card, Tag, List, Empty, Statistic, Row, Col, Button, theme } from 'antd';
import {
  ThunderboltOutlined,
  BulbOutlined,
  FireOutlined,
  HeartOutlined,
  TeamOutlined,
  TrophyOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  ReloadOutlined,
  EditOutlined
} from '@ant-design/icons';
import type { AnalysisTask, ChapterAnalysisResponse } from '../types';
import ChapterRegenerationModal from './ChapterRegenerationModal';
import ChapterContentComparison from './ChapterContentComparison';

// Xác định có phải thiết bị di động không
const isMobileDevice = () => window.innerWidth < 768;

interface ChapterAnalysisProps {
  chapterId: string;
  visible: boolean;
  onClose: () => void;
}

export default function ChapterAnalysis({ chapterId, visible, onClose }: ChapterAnalysisProps) {
  const { token } = theme.useToken();
  const [task, setTask] = useState<AnalysisTask | null>(null);
  const [analysis, setAnalysis] = useState<ChapterAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isMobile, setIsMobile] = useState(isMobileDevice());
  const [regenerationModalVisible, setRegenerationModalVisible] = useState(false);
  const [comparisonModalVisible, setComparisonModalVisible] = useState(false);
  const [chapterInfo, setChapterInfo] = useState<{ title: string; chapter_number: number; content: string } | null>(null);
  const [newGeneratedContent, setNewGeneratedContent] = useState('');
  const [newContentWordCount, setNewContentWordCount] = useState(0);
  const pollTimerRef = useRef<number | null>(null);
  const requestGenerationRef = useRef(0);

  useEffect(() => {
    const generation = requestGenerationRef.current + 1;
    requestGenerationRef.current = generation;
    if (pollTimerRef.current !== null) {
      window.clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }

    if (visible && chapterId) {
      setTask(null);
      setAnalysis(null);
      setChapterInfo(null);
      setError(null);
      void fetchAnalysisStatus(chapterId, generation);
    }

    // Lắng nghe thay đổi kích thước cửa sổ
    const handleResize = () => {
      setIsMobile(isMobileDevice());
    };

    window.addEventListener('resize', handleResize);

    // Hàm dọn dẹp: xóa poll khi component unmount hoặc đóng
    return () => {
      window.removeEventListener('resize', handleResize);
      requestGenerationRef.current += 1;
      if (pollTimerRef.current !== null) {
        window.clearTimeout(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, chapterId]);

  // 🔧 Mới: hàm tải thông tin chương độc lập
  const loadChapterInfo = async (
    requestedChapterId = chapterId,
    generation = requestGenerationRef.current,
  ) => {
    try {
      const chapterResponse = await fetch(`/api/chapters/${requestedChapterId}`);
      if (chapterResponse.ok) {
        const chapterData = await chapterResponse.json();
        if (requestGenerationRef.current !== generation) return;
        setChapterInfo({
          title: chapterData.title,
          chapter_number: chapterData.chapter_number,
          content: chapterData.content || ''
        });
        console.log('✅ Đã refresh nội dung chương, số chữ:', chapterData.content?.length || 0);
      }
    } catch (error) {
      console.error('❌ Tải thông tin chương thất bại:', error);
    }
  };

  const fetchAnalysisStatus = async (
    requestedChapterId = chapterId,
    generation = requestGenerationRef.current,
  ) => {
    try {
      setLoading(true);
      setError(null);

      // 🔧 Dùng hàm tải chương độc lập
      await loadChapterInfo(requestedChapterId, generation);

      const response = await fetch(`/api/chapters/${requestedChapterId}/analysis/status`);
      if (requestGenerationRef.current !== generation) return;

      if (response.status === 404) {
        setTask(null);
        setError('Chương này chưa được phân tích');
        return;
      }

      if (!response.ok) {
        throw new Error('Lấy trạng thái phân tích thất bại');
      }

      const taskData: AnalysisTask = await response.json();

      // Nếu trạng thái là none (không có task), đặt task là null để frontend hiển thị nút "Bắt đầu phân tích"
      if (taskData.status === 'none' || !taskData.has_task) {
        setTask(null);
        setError(null); // Xóa lỗi, đây không phải trạng thái lỗi
        return;
      }

      setTask(taskData);

      if (taskData.status === 'completed') {
        await fetchAnalysisResult(requestedChapterId, generation);
      } else if (taskData.status === 'running' || taskData.status === 'pending') {
        startPolling(requestedChapterId, generation);
      }
    } catch (err) {
      if (requestGenerationRef.current === generation) {
        setError((err as Error).message);
      }
    } finally {
      if (requestGenerationRef.current === generation) {
        setLoading(false);
      }
    }
  };

  const fetchAnalysisResult = async (
    requestedChapterId = chapterId,
    generation = requestGenerationRef.current,
  ) => {
    try {
      const response = await fetch(`/api/chapters/${requestedChapterId}/analysis`);
      if (!response.ok) {
        throw new Error('Lấy kết quả phân tích thất bại');
      }
      const data: ChapterAnalysisResponse = await response.json();
      if (requestGenerationRef.current !== generation) return;
      setAnalysis(data);
    } catch (err) {
      if (requestGenerationRef.current === generation) {
        setError((err as Error).message);
      }
    }
  };

  const startPolling = (requestedChapterId: string, generation: number) => {
    const deadline = Date.now() + 11 * 60 * 1000;

    const poll = async (): Promise<void> => {
      if (requestGenerationRef.current !== generation) return;
      if (Date.now() >= deadline) {
        setError('Truy vấn trạng thái phân tích timeout, vui lòng đóng rồi mở lại');
        return;
      }

      try {
        const response = await fetch(`/api/chapters/${requestedChapterId}/analysis/status`);
        if (requestGenerationRef.current !== generation) return;
        if (!response.ok) throw new Error('Lấy trạng thái phân tích thất bại');

        const taskData: AnalysisTask = await response.json();
        setTask(taskData);

        if (taskData.status === 'completed') {
          await fetchAnalysisResult(requestedChapterId, generation);
          await loadChapterInfo(requestedChapterId, generation);
          return;
        } else if (taskData.status === 'failed') {
          setError(taskData.error_message || 'Phân tích thất bại');
          return;
        }
      } catch (err) {
        console.error('Lỗi poll:', err);
      }

      if (requestGenerationRef.current === generation) {
        pollTimerRef.current = window.setTimeout(() => {
          void poll();
        }, 2000);
      }
    };

    pollTimerRef.current = window.setTimeout(() => {
      void poll();
    }, 2000);
  };

  const triggerAnalysis = async () => {
    try {
      setLoading(true);
      setError(null);

      // 🔧 Refresh nội dung chương trước khi kích hoạt phân tích, đảm bảo phân tích nội dung mới nhất
      await loadChapterInfo();

      const response = await fetch(`/api/chapters/${chapterId}/analyze`, {
        method: 'POST'
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Kích hoạt phân tích thất bại');
      }

      // Đóng Modal ngay sau khi kích hoạt thành công, để quản lý state của component cha tiếp quản
      onClose();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };


  const renderStatusIcon = () => {
    if (!task) return null;

    switch (task.status) {
      case 'pending':
        return <ClockCircleOutlined style={{ color: 'var(--color-warning)' }} />;
      case 'running':
        return <Spin />;
      case 'completed':
        return <CheckCircleOutlined style={{ color: 'var(--color-success)' }} />;
      case 'failed':
        return <CloseCircleOutlined style={{ color: 'var(--color-error)' }} />;
      default:
        return null;
    }
  };

  const renderProgress = () => {
    if (!task || task.status === 'completed') return null;

    return (
      <div style={{
        padding: '40px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '300px'
      }}>
        {/* Tiêu đề và biểu tượng */}
        <div style={{
          textAlign: 'center',
          marginBottom: 32
        }}>
          {renderStatusIcon()}
          <div style={{
            fontSize: 20,
            fontWeight: 'bold',
            marginTop: 16,
            color: task.status === 'failed' ? 'var(--color-error)' : 'var(--color-text-primary)'
          }}>
            {task.status === 'pending' && 'Đang chờ phân tích...'}
            {task.status === 'running' && 'AI đang phân tích...'}
            {task.status === 'failed' && 'Phân tích thất bại'}
          </div>
        </div>

        {/* Thanh tiến độ */}
        <div style={{
          width: '100%',
          maxWidth: '500px',
          marginBottom: 16
        }}>
          <div style={{
            height: 12,
            background: 'var(--color-bg-layout)',
            borderRadius: 6,
            overflow: 'hidden',
            marginBottom: 12
          }}>
            <div style={{
              height: '100%',
              background: task.status === 'failed'
                ? 'var(--color-error)'
                : task.progress === 100
                  ? 'var(--color-success)'
                  : 'var(--color-primary)',
              width: `${task.progress}%`,
              transition: 'all 0.3s ease',
              borderRadius: 6,
              boxShadow: task.progress > 0 && task.status !== 'failed'
                ? `0 0 10px color-mix(in srgb, ${token.colorPrimary} 30%, transparent)`
                : 'none'
            }} />
          </div>

          {/* Phần trăm tiến độ */}
          <div style={{
            textAlign: 'center',
            fontSize: 32,
            fontWeight: 'bold',
            color: task.status === 'failed' ? 'var(--color-error)' :
              task.progress === 100 ? 'var(--color-success)' : 'var(--color-primary)',
            marginBottom: 8
          }}>
            {task.progress}%
          </div>
        </div>

        {/* Thông báo trạng thái */}
        <div style={{
          textAlign: 'center',
          fontSize: 16,
          color: 'var(--color-text-secondary)',
          minHeight: 24,
          marginBottom: 16
        }}>
          {task.status === 'pending' && 'Task phân tích đã được tạo, đang trong hàng đợi...'}
          {task.status === 'running' && 'Đang trích xuất thông tin quan trọng và đoạn ký ức...'}
        </div>

        {/* Thông tin lỗi */}
        {task.status === 'failed' && task.error_message && (
          <Alert
            message="Phân tích thất bại"
            description={task.error_message}
            type="error"
            showIcon
            style={{
              marginTop: 16,
              maxWidth: '500px',
              width: '100%'
            }}
          />
        )}

        {/* Chữ gợi ý */}
        {task.status !== 'failed' && (
          <div style={{
            textAlign: 'center',
            fontSize: 13,
            color: 'var(--color-text-tertiary)',
            marginTop: 16
          }}>
            Quá trình phân tích cần một khoảng thời gian, vui lòng kiên nhẫn chờ
          </div>
        )}
      </div>
    );
  };

  // Chuyển gợi ý phân tích thành định dạng component tạo lại cần
  const convertSuggestionsForRegeneration = () => {
    if (!analysis?.analysis?.suggestions) return [];

    return analysis.analysis.suggestions.map((suggestion, index) => ({
      category: 'Gợi ý cải tiến',
      content: suggestion,
      priority: index < 3 ? 'high' : 'medium'
    }));
  };

  const renderAnalysisResult = () => {
    if (!analysis) return null;

    const { analysis: analysis_data, memories, entity_changes } = analysis;
    const hasEntityChanges = Boolean(
      entity_changes && (
        (entity_changes.careers?.changes?.length || 0) > 0 ||
        (entity_changes.character_states?.changes?.length || 0) > 0 ||
        (entity_changes.organization_states?.changes?.length || 0) > 0
      )
    );

    return (
      <Tabs
        defaultActiveKey="overview"
        style={{ height: '100%' }}
        items={[
          {
            key: 'overview',
            label: 'Tổng quan',
            icon: <TrophyOutlined />,
            children: (
              <div style={{ height: isMobile ? 'calc(80vh - 180px)' : 'calc(90vh - 220px)', overflowY: 'auto', paddingRight: '8px' }}>
                {/* Nút tạo lại theo gợi ý */}
                {analysis_data.suggestions && analysis_data.suggestions.length > 0 && (
                  <Alert
                    message="Phát hiện gợi ý cải tiến"
                    description={
                      <div>
                        <p style={{ marginBottom: 12 }}>AI đã phân tích ra {analysis_data.suggestions.length} gợi ý cải tiến, bạn có thể tạo lại nội dung chương theo các gợi ý này.</p>
                        <Button
                          type="primary"
                          icon={<EditOutlined />}
                          onClick={() => setRegenerationModalVisible(true)}
                          size={isMobile ? 'small' : 'middle'}
                        >
                          Tạo lại theo gợi ý
                        </Button>
                      </div>
                    }
                    type="info"
                    showIcon
                    style={{ marginBottom: 16 }}
                  />
                )}

                <Card title="Điểm tổng thể" style={{ marginBottom: 16 }} size={isMobile ? 'small' : 'default'}>
                  <Row gutter={isMobile ? 8 : 16}>
                    <Col span={isMobile ? 12 : 6}>
                      <Statistic
                        title="Chất lượng tổng thể"
                        value={analysis_data.overall_quality_score || 0}
                        suffix="/ 10"
                        valueStyle={{ color: 'var(--color-success)' }}
                      />
                    </Col>
                    <Col span={isMobile ? 12 : 6}>
                      <Statistic
                        title="Kiểm soát nhịp độ"
                        value={analysis_data.pacing_score || 0}
                        suffix="/ 10"
                      />
                    </Col>
                    <Col span={isMobile ? 12 : 6}>
                      <Statistic
                        title="Sức hấp dẫn"
                        value={analysis_data.engagement_score || 0}
                        suffix="/ 10"
                      />
                    </Col>
                    <Col span={isMobile ? 12 : 6}>
                      <Statistic
                        title="Tính mạch lạc"
                        value={analysis_data.coherence_score || 0}
                        suffix="/ 10"
                      />
                    </Col>
                  </Row>
                </Card>

                {analysis_data.analysis_report && (
                  <Card title="Tóm tắt phân tích" style={{ marginBottom: 16 }} size={isMobile ? 'small' : 'default'}>
                    <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', fontSize: isMobile ? 13 : 14 }}>
                      {analysis_data.analysis_report}
                    </pre>
                  </Card>
                )}

                {hasEntityChanges && entity_changes && (
                  <Card title="Cập nhật liên động thực thể" style={{ marginBottom: 16 }} size={isMobile ? 'small' : 'default'}>
                    <Row gutter={isMobile ? 8 : 16} style={{ marginBottom: 16 }}>
                      <Col span={isMobile ? 24 : 8}>
                        <Statistic
                          title="Cập nhật nghề nghiệp"
                          value={entity_changes.careers?.updated_count || 0}
                        />
                      </Col>
                      <Col span={isMobile ? 24 : 8}>
                        <Statistic
                          title="Cập nhật trạng thái/quan hệ nhân vật"
                          value={
                            (entity_changes.character_states?.state_updated_count || 0) +
                            (entity_changes.character_states?.relationship_created_count || 0) +
                            (entity_changes.character_states?.relationship_updated_count || 0) +
                            (entity_changes.character_states?.org_updated_count || 0)
                          }
                        />
                      </Col>
                      <Col span={isMobile ? 24 : 8}>
                        <Statistic
                          title="Cập nhật trạng thái tổ chức"
                          value={entity_changes.organization_states?.updated_count || 0}
                        />
                      </Col>
                    </Row>

                    {entity_changes.careers?.changes?.length ? (
                      <div style={{ marginBottom: 12 }}>
                        <strong>Thay đổi nghề nghiệp:</strong>
                        <div style={{ marginTop: 8 }}>
                          {entity_changes.careers.changes.map((change, index) => (
                            <Tag key={`career-${index}`} color="blue" style={{ marginBottom: 8 }}>
                              {change}
                            </Tag>
                          ))}
                        </div>
                      </div>
                    ) : null}

                    {entity_changes.character_states?.changes?.length ? (
                      <div style={{ marginBottom: 12 }}>
                        <strong>Thay đổi nhân vật/quan hệ:</strong>
                        <List
                          size="small"
                          dataSource={entity_changes.character_states.changes}
                          renderItem={(item) => <List.Item>{item}</List.Item>}
                        />
                      </div>
                    ) : null}

                    {entity_changes.organization_states?.changes?.length ? (
                      <div>
                        <strong>Thay đổi trạng thái tổ chức:</strong>
                        <List
                          size="small"
                          dataSource={entity_changes.organization_states.changes}
                          renderItem={(item) => <List.Item>{item}</List.Item>}
                        />
                      </div>
                    ) : null}
                  </Card>
                )}

                {analysis_data.suggestions && analysis_data.suggestions.length > 0 && (
                  <Card title={<><BulbOutlined /> Gợi ý cải tiến</>} size={isMobile ? 'small' : 'default'}>
                    <List
                      dataSource={analysis_data.suggestions}
                      renderItem={(item, index) => (
                        <List.Item>
                          <span>{index + 1}. {item}</span>
                        </List.Item>
                      )}
                    />
                  </Card>
                )}
              </div>
            )
          },
          {
            key: 'hooks',
            label: `Hook (${analysis_data.hooks?.length || 0})`,
            icon: <ThunderboltOutlined />,
            children: (
              <div style={{ height: isMobile ? 'calc(80vh - 180px)' : 'calc(90vh - 220px)', overflowY: 'auto', paddingRight: '8px' }}>
                <Card size={isMobile ? 'small' : 'default'}>
                  {analysis_data.hooks && analysis_data.hooks.length > 0 ? (
                    <List
                      dataSource={analysis_data.hooks}
                      renderItem={(hook) => (
                        <List.Item>
                          <List.Item.Meta
                            title={
                              <div>
                                <Tag color="blue">{hook.type}</Tag>
                                <Tag color="orange">{hook.position}</Tag>
                                <Tag color="red">Cường độ: {hook.strength}/10</Tag>
                              </div>
                            }
                            description={hook.content}
                          />
                        </List.Item>
                      )}
                    />
                  ) : (
                    <Empty description="Chưa có hook" />
                  )}
                </Card>
              </div>
            )
          },
          {
            key: 'foreshadows',
            label: `Phục bút (${analysis_data.foreshadows?.length || 0})`,
            icon: <FireOutlined />,
            children: (
              <div style={{ height: isMobile ? 'calc(80vh - 180px)' : 'calc(90vh - 220px)', overflowY: 'auto', paddingRight: '8px' }}>
                <Card size={isMobile ? 'small' : 'default'}>
                  {analysis_data.foreshadows && analysis_data.foreshadows.length > 0 ? (
                    <List
                      dataSource={analysis_data.foreshadows}
                      renderItem={(foreshadow) => (
                        <List.Item>
                          <List.Item.Meta
                            title={
                              <div>
                                <Tag color={foreshadow.type === 'planted' ? 'green' : 'purple'}>
                                  {foreshadow.type === 'planted' ? 'Đã gieo' : 'Đã thu hồi'}
                                </Tag>
                                <Tag>Cường độ: {foreshadow.strength}/10</Tag>
                                <Tag>Độ ẩn: {foreshadow.subtlety}/10</Tag>
                                {foreshadow.reference_chapter && (
                                  <Tag color="cyan">Hồi ứng chương {foreshadow.reference_chapter}</Tag>
                                )}
                              </div>
                            }
                            description={foreshadow.content}
                          />
                        </List.Item>
                      )}
                    />
                  ) : (
                    <Empty description="Chưa có phục bút" />
                  )}
                </Card>
              </div>
            )
          },
          {
            key: 'emotion',
            label: 'Đường cong cảm xúc',
            icon: <HeartOutlined />,
            children: (
              <div style={{ height: isMobile ? 'calc(80vh - 180px)' : 'calc(90vh - 220px)', overflowY: 'auto', paddingRight: '8px' }}>
                <Card size={isMobile ? 'small' : 'default'}>
                  {analysis_data.emotional_tone ? (
                    <div>
                      <Row gutter={isMobile ? 8 : 16} style={{ marginBottom: isMobile ? 16 : 24 }}>
                        <Col span={isMobile ? 24 : 12}>
                          <Statistic
                            title="Cảm xúc chủ đạo"
                            value={analysis_data.emotional_tone}
                          />
                        </Col>
                        <Col span={isMobile ? 24 : 12}>
                          <Statistic
                            title="Cường độ cảm xúc"
                            value={(analysis_data.emotional_intensity * 10).toFixed(1)}
                            suffix="/ 10"
                          />
                        </Col>
                      </Row>
                      <Card type="inner" title="Giai đoạn cốt truyện" size="small">
                        <p><strong>Giai đoạn:</strong>{analysis_data.plot_stage}</p>
                        <p><strong>Mức độ xung đột:</strong>{analysis_data.conflict_level} / 10</p>
                        {analysis_data.conflict_types && analysis_data.conflict_types.length > 0 && (
                          <div style={{ marginTop: 8 }}>
                            <strong>Loại xung đột:</strong>
                            {analysis_data.conflict_types.map((type, idx) => (
                              <Tag key={idx} color="red" style={{ margin: 4 }}>
                                {type}
                              </Tag>
                            ))}
                          </div>
                        )}
                      </Card>
                    </div>
                  ) : (
                    <Empty description="Chưa có phân tích cảm xúc" />
                  )}
                </Card>
              </div>
            )
          },
          {
            key: 'characters',
            label: `Nhân vật (${analysis_data.character_states?.length || 0})`,
            icon: <TeamOutlined />,
            children: (
              <div style={{ height: isMobile ? 'calc(80vh - 180px)' : 'calc(90vh - 220px)', overflowY: 'auto', paddingRight: '8px' }}>
                <Card size={isMobile ? 'small' : 'default'}>
                  {analysis_data.character_states && analysis_data.character_states.length > 0 ? (
                    <List
                      dataSource={analysis_data.character_states}
                      renderItem={(char) => (
                        <List.Item>
                          <Card
                            type="inner"
                            title={char.character_name}
                            size="small"
                            style={{ width: '100%' }}
                          >
                            <p><strong>Thay đổi trạng thái:</strong>{char.state_before} → {char.state_after}</p>
                            <p><strong>Thay đổi tâm lý:</strong>{char.psychological_change}</p>
                            <p><strong>Sự kiện quan trọng:</strong>{char.key_event}</p>
                            {char.relationship_changes && Object.keys(char.relationship_changes).length > 0 && (
                              <div>
                                <strong>Thay đổi quan hệ:</strong>
                                {Object.entries(char.relationship_changes).map(([name, change]) => (
                                  <Tag key={name} color="blue" style={{ margin: 4 }}>
                                    Với {name}: {change}
                                  </Tag>
                                ))}
                              </div>
                            )}
                          </Card>
                        </List.Item>
                      )}
                    />
                  ) : (
                    <Empty description="Chưa có phân tích nhân vật" />
                  )}
                </Card>
              </div>
            )
          },
          {
            key: 'memories',
            label: `Ký ức (${memories?.length || 0})`,
            icon: <FireOutlined />,
            children: (
              <div style={{ height: isMobile ? 'calc(80vh - 180px)' : 'calc(90vh - 220px)', overflowY: 'auto', paddingRight: '8px' }}>
                <Card size={isMobile ? 'small' : 'default'}>
                  {memories && memories.length > 0 ? (
                    <List
                      dataSource={memories}
                      renderItem={(memory) => (
                        <List.Item>
                          <List.Item.Meta
                            title={
                              <div>
                                <Tag color="blue">{memory.type}</Tag>
                                <Tag color="orange">Mức quan trọng: {memory.importance.toFixed(1)}</Tag>
                                {memory.is_foreshadow === 1 && <Tag color="green">Đã gieo phục bút</Tag>}
                                {memory.is_foreshadow === 2 && <Tag color="purple">Đã thu hồi phục bút</Tag>}
                                <span style={{ marginLeft: 8 }}>{memory.title}</span>
                              </div>
                            }
                            description={
                              <div>
                                <p>{memory.content}</p>
                                <div>
                                  {memory.tags.map((tag, idx) => (
                                    <Tag key={idx} style={{ margin: 2 }}>{tag}</Tag>
                                  ))}
                                </div>
                              </div>
                            }
                          />
                        </List.Item>
                      )}
                    />
                  ) : (
                    <Empty description="Chưa có đoạn ký ức" />
                  )}
                </Card>
              </div>
            )
          }
        ]}
      />
    );
  };

  return (
    <Modal
      title="Phân tích chương"
      open={visible}
      onCancel={onClose}
      width={isMobile ? 'calc(100vw - 32px)' : '90%'}
      centered
      style={{
        maxWidth: isMobile ? 'calc(100vw - 32px)' : '1400px',
        margin: isMobile ? '0 auto' : undefined,
        padding: isMobile ? '0 16px' : undefined
      }}
      styles={{
        body: {
          padding: isMobile ? '12px' : '24px',
          paddingBottom: 0,
          maxHeight: isMobile ? 'calc(100vh - 200px)' : 'calc(90vh - 150px)',
          overflowY: 'auto'
        }
      }}
      footer={[
        <Button key="close" onClick={onClose} size={isMobile ? 'small' : 'middle'}>
          Đóng
        </Button>,
        !task && !loading && (
          <Button
            key="analyze"
            type="primary"
            icon={<ReloadOutlined />}
            onClick={triggerAnalysis}
            loading={loading}
            size={isMobile ? 'small' : 'middle'}
          >
            Bắt đầu phân tích
          </Button>
        ),
        task && (task.status === 'failed') && (
          <Button
            key="reanalyze"
            type="primary"
            icon={<ReloadOutlined />}
            onClick={triggerAnalysis}
            loading={loading}
            danger
            size={isMobile ? 'small' : 'middle'}
          >
            Phân tích lại
          </Button>
        ),
        task && task.status === 'completed' && (
          <Button
            key="reanalyze"
            type="default"
            icon={<ReloadOutlined />}
            onClick={triggerAnalysis}
            loading={loading}
            size={isMobile ? 'small' : 'middle'}
          >
            Phân tích lại
          </Button>
        )
      ].filter(Boolean)}
    >
      {loading && !task && (
        <div style={{ textAlign: 'center', padding: '48px' }}>
          <Spin size="large" />
          <p style={{ marginTop: 16 }}>Đang tải...</p>
        </div>
      )}

      {error && (
        <Alert
          message="Lỗi"
          description={error}
          type="error"
          showIcon
        />
      )}

      {task && task.status !== 'completed' && renderProgress()}
      {task && task.status === 'completed' && analysis && renderAnalysisResult()}

      {/* Modal tạo lại */}
      {chapterInfo && (
        <ChapterRegenerationModal
          visible={regenerationModalVisible}
          onCancel={() => setRegenerationModalVisible(false)}
          onSuccess={(newContent: string, wordCount: number) => {
            // Lưu nội dung mới tạo
            setNewGeneratedContent(newContent);
            setNewContentWordCount(wordCount);
            // Đóng hộp thoại tạo lại
            setRegenerationModalVisible(false);
            // Mở giao diện so sánh
            setComparisonModalVisible(true);
          }}
          chapterId={chapterId}
          chapterTitle={chapterInfo.title}
          chapterNumber={chapterInfo.chapter_number}
          suggestions={convertSuggestionsForRegeneration()}
          hasAnalysis={true}
        />
      )}

      {/* Component so sánh nội dung */}
      {chapterInfo && comparisonModalVisible && (
        <ChapterContentComparison
          visible={comparisonModalVisible}
          onClose={() => setComparisonModalVisible(false)}
          chapterId={chapterId}
          chapterTitle={chapterInfo.title}
          originalContent={chapterInfo.content}
          newContent={newGeneratedContent}
          wordCount={newContentWordCount}
          onApply={async () => {
            // Refresh thông tin chương và phân tích sau khi áp dụng nội dung mới
            setChapterInfo(null);
            setAnalysis(null);

            // Tải lại nội dung chương
            try {
              const chapterResponse = await fetch(`/api/chapters/${chapterId}`);
              if (chapterResponse.ok) {
                const chapterData = await chapterResponse.json();
                setChapterInfo({
                  title: chapterData.title,
                  chapter_number: chapterData.chapter_number,
                  content: chapterData.content || ''
                });
              }
            } catch (error) {
              console.error('Tải lại chương thất bại:', error);
            }

            // Refresh trạng thái phân tích
            await fetchAnalysisStatus();
          }}
          onDiscard={() => {
            // Bỏ nội dung mới, xóa state
            setNewGeneratedContent('');
            setNewContentWordCount(0);
          }}
        />
      )}
    </Modal>
  );
}
