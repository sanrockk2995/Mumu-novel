import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams } from 'react-router-dom';
import {
  Card, Table, Button, Tag, Space, Modal, Form, Input, Select,
  InputNumber, Switch, message, Tooltip, Popconfirm, Statistic,
  Row, Col, Empty, Divider, Badge, Alert, Pagination, Dropdown, theme
} from 'antd';
import type { MenuProps } from 'antd';
import {
  PlusOutlined, SyncOutlined, EditOutlined, DeleteOutlined,
  CheckCircleOutlined, CloseCircleOutlined, ExclamationCircleOutlined,
  BulbOutlined, EyeOutlined, FlagOutlined, WarningOutlined,
  ClockCircleOutlined, MoreOutlined, ReloadOutlined, InfoCircleOutlined
} from '@ant-design/icons';
import { foreshadowApi, chapterApi, characterApi } from '../services/api';
import type {
  Foreshadow, ForeshadowCreate, ForeshadowUpdate, ForeshadowStats,
  ForeshadowStatus, ForeshadowCategory, Chapter, Character
} from '../types';
import { eventBus, EventNames } from '../store/eventBus';

const { TextArea } = Input;
const { Option } = Select;

// Cấu hình trạng thái
const STATUS_CONFIG: Record<ForeshadowStatus, { label: string; color: string; icon: React.ReactNode }> = {
  pending: { label: 'Chờ gieo', color: 'default', icon: <ClockCircleOutlined /> },
  planted: { label: 'Đã gieo', color: 'green', icon: <BulbOutlined /> },
  resolved: { label: 'Đã thu hồi', color: 'blue', icon: <CheckCircleOutlined /> },
  partially_resolved: { label: 'Thu hồi một phần', color: 'orange', icon: <ExclamationCircleOutlined /> },
  abandoned: { label: 'Đã loại bỏ', color: 'default', icon: <CloseCircleOutlined /> },
};

// Cấu hình phân loại
const CATEGORY_CONFIG: Record<string, { label: string; color: string }> = {
  identity: { label: 'Thân thế', color: 'purple' },
  mystery: { label: 'Huyền niệm', color: 'magenta' },
  item: { label: 'Vật phẩm', color: 'gold' },
  relationship: { label: 'Quan hệ', color: 'cyan' },
  event: { label: 'Sự kiện', color: 'blue' },
  ability: { label: 'Năng lực', color: 'green' },
  prophecy: { label: 'Lời tiên tri', color: 'volcano' },
};

export default function Foreshadows() {
  const { projectId } = useParams<{ projectId: string }>();
  const [loading, setLoading] = useState(false);
  const [foreshadows, setForeshadows] = useState<Foreshadow[]>([]);
  const [stats, setStats] = useState<ForeshadowStats | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [total, setTotal] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  
  // Điều kiện lọc
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>(undefined);
  const [sourceFilter, setSourceFilter] = useState<string | undefined>(undefined);
  
  // Trạng thái modal
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [syncModalVisible, setSyncModalVisible] = useState(false);
  const [detailModalVisible, setDetailModalVisible] = useState(false);
  const [plantModalVisible, setPlantModalVisible] = useState(false);
  const [resolveModalVisible, setResolveModalVisible] = useState(false);
  
  const [currentForeshadow, setCurrentForeshadow] = useState<Foreshadow | null>(null);
  const [form] = Form.useForm();
  const [plantForm] = Form.useForm();
  const [resolveForm] = Form.useForm();
  const [syncing, setSyncing] = useState(false);
  
  // Ref container bảng, dùng để tính chiều cao cuộn
  const tableContainerRef = useRef<HTMLDivElement>(null);
  const [tableScrollY, setTableScrollY] = useState<number>(400);
  const { token } = theme.useToken();

  // Tải danh sách phục bút
  const loadForeshadows = useCallback(async () => {
    if (!projectId) return;
    
    setLoading(true);
    try {
      const response = await foreshadowApi.getProjectForeshadows(projectId, {
        status: statusFilter,
        category: categoryFilter,
        source_type: sourceFilter,
        page: currentPage,
        limit: pageSize,
      });
      
      setForeshadows(response.items);
      setTotal(response.total);
      if (response.stats) {
        setStats(response.stats);
      }
    } catch (error) {
      console.error('Tải danh sách phục bút thất bại:', error);
    } finally {
      setLoading(false);
    }
  }, [projectId, statusFilter, categoryFilter, sourceFilter, currentPage, pageSize]);

  // Tải danh sách chương (để chọn)
  const loadChapters = useCallback(async () => {
    if (!projectId) return;
    try {
      const chaptersData = await chapterApi.getChapters(projectId);
      setChapters(chaptersData);
    } catch (error) {
      console.error('Tải danh sách chương thất bại:', error);
    }
  }, [projectId]);

  // Tải danh sách nhân vật (để liên kết nhân vật)
  const loadCharacters = useCallback(async () => {
    if (!projectId) return;
    try {
      const charactersData = await characterApi.getCharacters(projectId);
      setCharacters(charactersData);
    } catch (error) {
      console.error('Tải danh sách nhân vật thất bại:', error);
    }
  }, [projectId]);

  // Tải thống kê
  const loadStats = useCallback(async () => {
    if (!projectId) return;
    try {
      // Lấy số chương lớn nhất hiện tại (chỉ tính chương có nội dung, đồng nhất với logic hiển thị bảng)
      const chaptersWithContent = chapters.filter(c => c.content);
      const maxChapter = chaptersWithContent.length > 0
        ? Math.max(...chaptersWithContent.map(c => c.chapter_number))
        : undefined;
      const statsData = await foreshadowApi.getForeshadowStats(projectId, maxChapter);
      setStats(statsData);
    } catch (error) {
      console.error('Tải thống kê thất bại:', error);
    }
  }, [projectId, chapters]);

  useEffect(() => {
    loadForeshadows();
    loadChapters();
    loadCharacters();
  }, [loadForeshadows, loadChapters, loadCharacters]);

  useEffect(() => {
    const handleTaskSettled = (payload?: unknown) => {
      if (!payload || typeof payload !== 'object') return;
      const data = payload as { projectId?: string; resources?: string[] };
      if (data.projectId && data.projectId !== projectId) return;
      if (!data.resources?.includes('foreshadows')) return;
      void loadForeshadows();
      void loadStats();
    };
    eventBus.on(EventNames.BACKGROUND_TASK_SETTLED, handleTaskSettled);
    return () => eventBus.off(EventNames.BACKGROUND_TASK_SETTLED, handleTaskSettled);
  }, [loadForeshadows, loadStats, projectId]);

  // Tính chiều cao cuộn của bảng
  useEffect(() => {
    const calculateTableHeight = () => {
      if (tableContainerRef.current) {
        // Lấy chiều cao container, trừ chiều cao header (khoảng 55px)
        const containerHeight = tableContainerRef.current.clientHeight;
        setTableScrollY(Math.max(containerHeight - 55, 200));
      }
    };
    
    calculateTableHeight();
    window.addEventListener('resize', calculateTableHeight);
    
    // Trì hoãn tính lại một lần để đảm bảo layout hoàn tất
    const timer = setTimeout(calculateTableHeight, 100);
    
    return () => {
      window.removeEventListener('resize', calculateTableHeight);
      clearTimeout(timer);
    };
  }, [stats]); // stats Tính lại khi thay đổi (vì chiều cao thẻ thống kê có thể thay đổi)

  useEffect(() => {
    if (chapters.length > 0) {
      loadStats();
    }
  }, [chapters, loadStats]);

  // Tạo/Chỉnh sửa phục bút
  const handleSave = async (values: ForeshadowCreate | ForeshadowUpdate) => {
    try {
      if (currentForeshadow) {
        await foreshadowApi.updateForeshadow(currentForeshadow.id, values as ForeshadowUpdate);
        message.success('Cập nhật phục bút thành công');
      } else {
        await foreshadowApi.createForeshadow({
          ...values,
          project_id: projectId!,
        } as ForeshadowCreate);
        message.success('Tạo phục bút thành công');
      }
      setEditModalVisible(false);
      form.resetFields();
      setCurrentForeshadow(null);
      loadForeshadows();
    } catch (error) {
      console.error('Lưu phục bút thất bại:', error);
    }
  };

  // Xóa phục bút
  const handleDelete = async (id: string) => {
    try {
      await foreshadowApi.deleteForeshadow(id);
      message.success('Xóa phục bút thành công');
      loadForeshadows();
    } catch (error) {
      console.error('Xóa phục bút thất bại:', error);
    }
  };

  // Đánh dấu gieo
  const handlePlant = async (values: { chapter_id: string; hint_text?: string }) => {
    if (!currentForeshadow) return;
    
    const chapter = chapters.find(c => c.id === values.chapter_id);
    if (!chapter) return;
    
    try {
      await foreshadowApi.plantForeshadow(currentForeshadow.id, {
        chapter_id: values.chapter_id,
        chapter_number: chapter.chapter_number,
        hint_text: values.hint_text,
      });
      message.success('Phục bút đã được đánh dấu là đã gieo');
      setPlantModalVisible(false);
      plantForm.resetFields();
      setCurrentForeshadow(null);
      loadForeshadows();
    } catch (error) {
      console.error('Đánh dấu gieo thất bại:', error);
    }
  };

  // Đánh dấu thu hồi
  const handleResolve = async (values: { chapter_id: string; resolution_text?: string; is_partial?: boolean }) => {
    if (!currentForeshadow) return;
    
    const chapter = chapters.find(c => c.id === values.chapter_id);
    if (!chapter) return;
    
    try {
      await foreshadowApi.resolveForeshadow(currentForeshadow.id, {
        chapter_id: values.chapter_id,
        chapter_number: chapter.chapter_number,
        resolution_text: values.resolution_text,
        is_partial: values.is_partial,
      });
      message.success('Phục bút đã được đánh dấu là đã thu hồi');
      setResolveModalVisible(false);
      resolveForm.resetFields();
      setCurrentForeshadow(null);
      loadForeshadows();
    } catch (error) {
      console.error('Đánh dấu thu hồi thất bại:', error);
    }
  };

  // Đánh dấu loại bỏ
  const handleAbandon = async (id: string) => {
    try {
      await foreshadowApi.abandonForeshadow(id);
      message.success('Phục bút đã được đánh dấu là đã loại bỏ');
      loadForeshadows();
    } catch (error) {
      console.error('Đánh dấu loại bỏ thất bại:', error);
    }
  };

  // Đồng bộ từ phân tích
  const handleSync = async () => {
    if (!projectId) return;
    
    setSyncing(true);
    try {
      const result = await foreshadowApi.syncFromAnalysis(projectId, {
        auto_set_planted: true,
      });
      message.success(`Đồng bộ xong: đã thêm ${result.synced_count} phục bút, bỏ qua ${result.skipped_count}`);
      setSyncModalVisible(false);
      loadForeshadows();
    } catch (error) {
      console.error('Đồng bộ thất bại:', error);
    } finally {
      setSyncing(false);
    }
  };

  // Mở modal chỉnh sửa
  const openEditModal = (foreshadow?: Foreshadow) => {
    setCurrentForeshadow(foreshadow || null);
    if (foreshadow) {
      // Đảm bảo trường kiểu mảng không phải null
      form.setFieldsValue({
        ...foreshadow,
        tags: foreshadow.tags || [],
        related_characters: foreshadow.related_characters || [],
      });
    } else {
      form.resetFields();
    }
    setEditModalVisible(true);
  };

  // Mở modal chi tiết
  const openDetailModal = (foreshadow: Foreshadow) => {
    setCurrentForeshadow(foreshadow);
    setDetailModalVisible(true);
  };

  // Mở modal gieo
  const openPlantModal = (foreshadow: Foreshadow) => {
    setCurrentForeshadow(foreshadow);
    plantForm.resetFields();
    setPlantModalVisible(true);
  };

  // Mở modal thu hồi
  const openResolveModal = (foreshadow: Foreshadow) => {
    setCurrentForeshadow(foreshadow);
    resolveForm.resetFields();
    setResolveModalVisible(true);
  };

  // Tính mức độ khẩn cấp
  const getUrgencyBadge = (foreshadow: Foreshadow) => {
    if (foreshadow.status !== 'planted' || !foreshadow.target_resolve_chapter_number) {
      return null;
    }
    
    const chaptersWithContent = chapters.filter(c => c.content);
    const currentMaxChapter = chaptersWithContent.length > 0
      ? Math.max(...chaptersWithContent.map(c => c.chapter_number))
      : 0;
    
    const remaining = foreshadow.target_resolve_chapter_number - currentMaxChapter;
    
    if (remaining < 0) {
      return <Badge status="error" text={`Đã quá hạn ${Math.abs(remaining)}`} />;
    } else if (remaining <= 3) {
      return <Badge status="warning" text={`Còn lại ${remaining}`} />;
    }
    return null;
  };

  // Thứ tự ưu tiên sắp xếp trạng thái
  const statusOrder: Record<ForeshadowStatus, number> = {
    planted: 1,      // Ưu tiên đã gieo (cần chú ý thu hồi)
    pending: 2,      // Chờ gieo tiếp theo
    partially_resolved: 3,
    resolved: 4,
    abandoned: 5,
  };

  // Định nghĩa cột bảng
  const columns = [
    {
      title: 'Trạng thái',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      sorter: (a: Foreshadow, b: Foreshadow) => statusOrder[a.status] - statusOrder[b.status],
      render: (status: ForeshadowStatus) => {
        const config = STATUS_CONFIG[status];
        return (
          <Tag color={config.color} icon={config.icon}>
            {config.label}
          </Tag>
        );
      },
    },
    {
      title: 'Tiêu đề',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
      sorter: (a: Foreshadow, b: Foreshadow) => a.title.localeCompare(b.title, 'zh-CN'),
      render: (title: string, record: Foreshadow) => (
        <Space direction="vertical" size={0}>
          <Space>
            <a onClick={() => openDetailModal(record)}>{title}</a>
            {record.is_long_term && (
              <Tag color="purple" style={{ marginLeft: 4 }}>Dài hạn</Tag>
            )}
          </Space>
          {getUrgencyBadge(record)}
        </Space>
      ),
    },
    {
      title: 'Phân loại',
      dataIndex: 'category',
      key: 'category',
      width: 80,
      sorter: (a: Foreshadow, b: Foreshadow) => {
        const catA = a.category || '';
        const catB = b.category || '';
        return catA.localeCompare(catB, 'zh-CN');
      },
      render: (category?: ForeshadowCategory) => {
        if (!category) return '-';
        const config = CATEGORY_CONFIG[category];
        return config ? <Tag color={config.color}>{config.label}</Tag> : category;
      },
    },
    {
      title: 'Chương gieo',
      dataIndex: 'plant_chapter_number',
      key: 'plant_chapter_number',
      width: 120,
      sorter: (a: Foreshadow, b: Foreshadow) => {
        const valA = a.plant_chapter_number ?? 999999;
        const valB = b.plant_chapter_number ?? 999999;
        return valA - valB;
      },
      defaultSortOrder: 'ascend' as const,
      render: (num?: number) => num ? `Chương ${num}` : '-',
    },
    {
      title: 'Dự kiến thu hồi',
      dataIndex: 'target_resolve_chapter_number',
      key: 'target_resolve_chapter_number',
      width: 120,
      sorter: (a: Foreshadow, b: Foreshadow) => {
        const valA = a.target_resolve_chapter_number ?? 999999;
        const valB = b.target_resolve_chapter_number ?? 999999;
        return valA - valB;
      },
      render: (num?: number) => num ? `Chương ${num}` : '-',
    },
    {
      title: 'Mức quan trọng',
      dataIndex: 'importance',
      key: 'importance',
      width: 100,
      sorter: (a: Foreshadow, b: Foreshadow) => a.importance - b.importance,
      render: (importance: number) => {
        const stars = Math.round(importance * 5);
        return '★'.repeat(stars) + '☆'.repeat(5 - stars);
      },
    },
    {
      title: 'Nguồn',
      dataIndex: 'source_type',
      key: 'source_type',
      width: 80,
      sorter: (a: Foreshadow, b: Foreshadow) => {
        const srcA = a.source_type || '';
        const srcB = b.source_type || '';
        return srcA.localeCompare(srcB);
      },
      render: (source?: string) => (
        <Tag color={source === 'analysis' ? 'blue' : 'green'}>
          {source === 'analysis' ? 'Phân tích' : 'Thủ công'}
        </Tag>
      ),
    },
    {
      title: 'Thao tác',
      key: 'actions',
      width: 200,
      render: (_: unknown, record: Foreshadow) => (
        <Space size="small">
          <Tooltip title="Xem chi tiết">
            <Button type="text" size="small" icon={<EyeOutlined />} onClick={() => openDetailModal(record)} />
          </Tooltip>
          <Tooltip title="Chỉnh sửa">
            <Button type="text" size="small" icon={<EditOutlined />} onClick={() => openEditModal(record)} />
          </Tooltip>
          {record.status === 'pending' && (
            <Tooltip title="Đánh dấu gieo">
              <Button type="text" size="small" icon={<FlagOutlined />} onClick={() => openPlantModal(record)} />
            </Tooltip>
          )}
          {record.status === 'planted' && (
            <Tooltip title="Đánh dấu thu hồi">
              <Button type="text" size="small" icon={<CheckCircleOutlined />} onClick={() => openResolveModal(record)} />
            </Tooltip>
          )}
          {record.status !== 'abandoned' && record.status !== 'resolved' && (
            <Popconfirm
              title="Bạn có chắc muốn loại bỏ phục bút này không?"
              onConfirm={() => handleAbandon(record.id)}
            >
              <Tooltip title="Loại bỏ">
                <Button type="text" size="small" danger icon={<CloseCircleOutlined />} />
              </Tooltip>
            </Popconfirm>
          )}
          <Popconfirm
            title="Bạn có chắc muốn xóa phục bút này không?"
            onConfirm={() => handleDelete(record.id)}
          >
            <Tooltip title="Xóa">
              <Button type="text" size="small" danger icon={<DeleteOutlined />} />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Thẻ thống kê */}
      {stats && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={3}>
            <Card size="small">
              <Statistic title="Tổng cộng" value={stats.total} />
            </Card>
          </Col>
          <Col span={3}>
            <Card size="small">
              <Statistic title="Chờ gieo" value={stats.pending} valueStyle={{ color: token.colorTextSecondary }} />
            </Card>
          </Col>
          <Col span={3}>
            <Card size="small">
              <Statistic title="Đã gieo" value={stats.planted} valueStyle={{ color: token.colorSuccess }} />
            </Card>
          </Col>
          <Col span={3}>
            <Card size="small">
              <Statistic title="Đã thu hồi" value={stats.resolved} valueStyle={{ color: token.colorPrimary }} />
            </Card>
          </Col>
          <Col span={3}>
            <Card size="small">
              <Statistic title="Phục bút dài hạn" value={stats.long_term_count} valueStyle={{ color: token.colorInfo }} />
            </Card>
          </Col>
          <Col span={3}>
            <Card size="small">
              <Statistic 
                title="Quá hạn chưa thu hồi" 
                value={stats.overdue_count} 
                valueStyle={{ color: stats.overdue_count > 0 ? token.colorError : token.colorTextSecondary }}
                prefix={stats.overdue_count > 0 ? <WarningOutlined /> : null}
              />
            </Card>
          </Col>
        </Row>
      )}

      {/* Nhắc nhở quá hạn */}
      {stats && stats.overdue_count > 0 && (
        <Alert
          message={`Có ${stats.overdue_count} phục bút đã quá hạn chưa thu hồi`}
          description="Vui lòng thu hồi các phục bút này trong các chương tiếp theo càng sớm càng tốt, hoặc điều chỉnh chương dự kiến thu hồi"
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {/* Gợi ý đồng bộ tự động */}
      <Alert
        message={
          <Space>
            <InfoCircleOutlined />
            <span>Dữ liệu phục bút sẽ tự động đồng bộ sau khi phân tích chương xong, không cần thao tác thủ công</span>
          </Space>
        }
        type="info"
        showIcon={false}
        style={{ marginBottom: 16 }}
        closable
      />

      {/* Thanh công cụ */}
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space>
          <Select
            placeholder="Lọc trạng thái"
            allowClear
            style={{ width: 120 }}
            value={statusFilter}
            onChange={setStatusFilter}
          >
            {Object.entries(STATUS_CONFIG).map(([key, config]) => (
              <Option key={key} value={key}>{config.label}</Option>
            ))}
          </Select>
          <Select
            placeholder="Lọc phân loại"
            allowClear
            style={{ width: 100 }}
            value={categoryFilter}
            onChange={setCategoryFilter}
          >
            {Object.entries(CATEGORY_CONFIG).map(([key, config]) => (
              <Option key={key} value={key}>{config.label}</Option>
            ))}
          </Select>
          <Select
            placeholder="Lọc nguồn"
            allowClear
            style={{ width: 100 }}
            value={sourceFilter}
            onChange={setSourceFilter}
          >
            <Option value="analysis">Phân tích</Option>
            <Option value="manual">Thủ công</Option>
          </Select>
        </Space>
        <Space>
          <Tooltip title="Refresh danh sách">
            <Button
              icon={<ReloadOutlined spin={loading} />}
              onClick={loadForeshadows}
            />
          </Tooltip>
          <Dropdown
            menu={{
              items: [
                {
                  key: 'sync',
                  icon: <SyncOutlined />,
                  label: 'Đồng bộ thủ công phục bút từ phân tích',
                  onClick: () => setSyncModalVisible(true),
                },
              ] as MenuProps['items'],
            }}
            placement="bottomRight"
          >
            <Button icon={<MoreOutlined />}>Thêm</Button>
          </Dropdown>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => openEditModal()}
          >
            Thêm phục bút
          </Button>
        </Space>
      </div>

      {/* Danh sách phục bút - Nội dung bảng cuộn được, header cố định */}
      <div
        ref={tableContainerRef}
        style={{
          flex: 1,
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          minHeight: 0, // Quan trọng: để  flex phần tử con có thể co lại
        }}
      >
        <Table
          dataSource={foreshadows}
          columns={columns}
          rowKey="id"
          loading={loading}
          pagination={false}
          scroll={{ y: tableScrollY }}
          locale={{
            emptyText: <Empty description="Chưa có phục bút, bấm góc trên bên phải để thêm" />,
          }}
        />
      </div>

      {/* Phân trang - Cố định ở dưới cùng, căn giữa */}
      <div style={{
        padding: '12px 0',
        borderTop: `1px solid ${token.colorBorderSecondary}`,
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        flexShrink: 0,
        background: token.colorBgContainer,
      }}>
        <Pagination
          current={currentPage}
          pageSize={pageSize}
          total={total}
          onChange={(page, size) => {
            setCurrentPage(page);
            if (size !== pageSize) {
              setPageSize(size);
            }
          }}
          showSizeChanger
          showTotal={(total) => `Tổng  ${total}  mục`}
          showQuickJumper
        />
      </div>

      {/* Tạo/Modal chỉnh sửa */}
      <Modal
        title={currentForeshadow ? 'Chỉnh sửa phục bút' : 'Thêm phục bút'}
        open={editModalVisible}
        centered
        onCancel={() => {
          setEditModalVisible(false);
          setCurrentForeshadow(null);
          form.resetFields();
        }}
        onOk={() => form.submit()}
        width={800}
        destroyOnClose
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSave}
          initialValues={{
            importance: 0.5,
            strength: 5,
            subtlety: 5,
            is_long_term: false,
            auto_remind: true,
            remind_before_chapters: 5,
            include_in_context: true,
          }}
        >
          <Row gutter={16}>
            <Col span={16}>
              <Form.Item name="title" label="Tiêu đề phục bút" rules={[{ required: true, message: 'Vui lòng nhập tiêu đề' }]}>
                <Input placeholder="Mô tả ngắn gọn nội dung phục bút" maxLength={200} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="category" label="Phân loại">
                <Select placeholder="Chọn phân loại" allowClear>
                  {Object.entries(CATEGORY_CONFIG).map(([key, config]) => (
                    <Option key={key} value={key}>{config.label}</Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>
          
          <Form.Item name="content" label="Nội dung phục bút" rules={[{ required: true, message: 'Vui lòng nhập nội dung' }]}>
            <TextArea rows={3} placeholder="Mô tả chi tiết nội dung và ý đồ của phục bút" />
          </Form.Item>
          
          <Row gutter={16}>
            <Col span={6}>
              <Form.Item name="plant_chapter_number" label="Dự kiến gieo">
                <InputNumber min={1} placeholder="Số chương" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="target_resolve_chapter_number" label="Dự kiến thu hồi">
                <InputNumber min={1} placeholder="Số chương" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="related_characters" label="Nhân vật liên quan">
                <Select
                  mode="multiple"
                  placeholder="Chọn nhân vật liên quan"
                  optionFilterProp="children"
                  maxTagCount={3}
                >
                  {characters
                    .filter(char => !char.is_organization)
                    .map(char => (
                      <Option key={char.name} value={char.name}>
                        {char.name} {char.role_type ? `(${char.role_type})` : ''}
                      </Option>
                    ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>
          
          <Row gutter={16}>
            <Col span={6}>
              <Form.Item name="importance" label="Mức quan trọng (0-1)">
                <InputNumber min={0} max={1} step={0.1} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="strength" label="Cường độ (1-10)">
                <InputNumber min={1} max={10} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="subtlety" label="Độ ẩn (1-10)">
                <InputNumber min={1} max={10} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="is_long_term" label="Phục bút dài hạn" valuePropName="checked">
                <Switch checkedChildren="Có" unCheckedChildren="Không" />
              </Form.Item>
            </Col>
          </Row>
          
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="hint_text" label="Văn bản gợi ý">
                <TextArea rows={2} placeholder="Miêu tả gợi ý dùng khi gieo phục bút" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="notes" label="Ghi chú">
                <TextArea rows={2} placeholder="Ghi chú sáng tác (chỉ tác giả thấy được)" />
              </Form.Item>
            </Col>
          </Row>
          
          <Divider style={{ margin: '12px 0' }}>AICài đặt hỗ trợ</Divider>
          
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="auto_remind" label="Nhắc tự động" valuePropName="checked" style={{ marginBottom: 0 }}>
                <Switch checkedChildren="Bật" unCheckedChildren="Tắt" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="include_in_context" label="Bao gồm trong ngữ cảnh sinh" valuePropName="checked" style={{ marginBottom: 0 }}>
                <Switch checkedChildren="Có" unCheckedChildren="Không" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="remind_before_chapters" label="Nhắc trước mấy chương" style={{ marginBottom: 0 }}>
                <InputNumber min={1} max={20} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>

      {/* Modal chi tiết */}
      <Modal
        title="Chi tiết phục bút"
        open={detailModalVisible}
        centered
        onCancel={() => {
          setDetailModalVisible(false);
          setCurrentForeshadow(null);
        }}
        footer={[
          <Button key="close" onClick={() => setDetailModalVisible(false)}>
            Đóng
          </Button>,
          <Button key="edit" type="primary" onClick={() => {
            setDetailModalVisible(false);
            openEditModal(currentForeshadow!);
          }}>
            Chỉnh sửa
          </Button>,
        ]}
        width={600}
      >
        {currentForeshadow && (
          <div>
            <Row gutter={[16, 16]}>
              <Col span={24}>
                <h3>{currentForeshadow.title}</h3>
                <Space>
                  <Tag color={STATUS_CONFIG[currentForeshadow.status].color}>
                    {STATUS_CONFIG[currentForeshadow.status].label}
                  </Tag>
                  {currentForeshadow.is_long_term && <Tag color="purple">Phục bút dài hạn</Tag>}
                  {currentForeshadow.category && CATEGORY_CONFIG[currentForeshadow.category] && (
                    <Tag color={CATEGORY_CONFIG[currentForeshadow.category].color}>
                      {CATEGORY_CONFIG[currentForeshadow.category].label}
                    </Tag>
                  )}
                </Space>
              </Col>
              
              <Col span={24}>
                <strong>Nội dung phục bút:</strong>
                <p style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}>{currentForeshadow.content}</p>
              </Col>
              
              {currentForeshadow.hint_text && (
                <Col span={24}>
                  <strong>Văn bản gợi ý:</strong>
                  <p style={{ marginTop: 8, whiteSpace: 'pre-wrap', color: token.colorTextSecondary }}>
                    {currentForeshadow.hint_text}
                  </p>
                </Col>
              )}
              
              {currentForeshadow.resolution_text && (
                <Col span={24}>
                  <strong>Văn bản hé lộ:</strong>
                  <p style={{ marginTop: 8, whiteSpace: 'pre-wrap', color: token.colorTextSecondary }}>
                    {currentForeshadow.resolution_text}
                  </p>
                </Col>
              )}
              
              <Col span={12}>
                <strong>Chương gieo:</strong> {currentForeshadow.plant_chapter_number ? `Chương ${currentForeshadow.plant_chapter_number}` : 'Chưa đặt'}
              </Col>
              <Col span={12}>
                <strong>Dự kiến thu hồi:</strong> {currentForeshadow.target_resolve_chapter_number ? `Chương ${currentForeshadow.target_resolve_chapter_number}` : 'Chưa đặt'}
              </Col>
              
              {currentForeshadow.actual_resolve_chapter_number && (
                <Col span={24}>
                  <strong>Thu hồi thực tế:</strong> Chương {currentForeshadow.actual_resolve_chapter_number}
                </Col>
              )}
              
              <Col span={8}>
                <strong>Mức quan trọng:</strong> {'★'.repeat(Math.round(currentForeshadow.importance * 5))}
              </Col>
              <Col span={8}>
                <strong>Cường độ:</strong> {currentForeshadow.strength}/10
              </Col>
              <Col span={8}>
                <strong>Độ ẩn:</strong> {currentForeshadow.subtlety}/10
              </Col>
              
              {currentForeshadow.related_characters && currentForeshadow.related_characters.length > 0 && (
                <Col span={24}>
                  <strong>Nhân vật liên quan:</strong>
                  <div style={{ marginTop: 4 }}>
                    {currentForeshadow.related_characters.map((name, idx) => (
                      <Tag key={idx}>{name}</Tag>
                    ))}
                  </div>
                </Col>
              )}
              
              {currentForeshadow.notes && (
                <Col span={24}>
                  <strong>Ghi chú:</strong>
                  <p style={{ marginTop: 8, color: token.colorTextSecondary }}>{currentForeshadow.notes}</p>
                </Col>
              )}
              
              <Col span={24}>
                <strong>Nguồn:</strong> {currentForeshadow.source_type === 'analysis' ? 'Trích xuất từ phân tích chương' : 'Thêm thủ công'}
              </Col>
            </Row>
          </div>
        )}
      </Modal>

      {/* Modal đánh dấu gieo */}
      <Modal
        title="Đánh dấu gieo phục bút"
        open={plantModalVisible}
        centered
        onCancel={() => {
          setPlantModalVisible(false);
          setCurrentForeshadow(null);
          plantForm.resetFields();
        }}
        onOk={() => plantForm.submit()}
        destroyOnClose
      >
        <Form form={plantForm} layout="vertical" onFinish={handlePlant}>
          <Form.Item name="chapter_id" label="Chọn chương gieo" rules={[{ required: true, message: 'Vui lòng chọn chương' }]}>
            <Select placeholder="Chọn chương">
              {chapters.map(chapter => (
                <Option key={chapter.id} value={chapter.id}>
                  Chương {chapter.chapter_number} - {chapter.title}
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="hint_text" label="Văn bản gợi ý (tùy chọn)">
            <TextArea rows={3} placeholder="Ghi lại miêu tả gợi ý dùng khi gieo phục bút" />
          </Form.Item>
        </Form>
      </Modal>

      {/* Modal đánh dấu thu hồi */}
      <Modal
        title="Đánh dấu thu hồi phục bút"
        open={resolveModalVisible}
        centered
        onCancel={() => {
          setResolveModalVisible(false);
          setCurrentForeshadow(null);
          resolveForm.resetFields();
        }}
        onOk={() => resolveForm.submit()}
        destroyOnClose
      >
        <Form form={resolveForm} layout="vertical" onFinish={handleResolve}>
          <Form.Item name="chapter_id" label="Chọn chương thu hồi" rules={[{ required: true, message: 'Vui lòng chọn chương' }]}>
            <Select placeholder="Chọn chương">
              {chapters.map(chapter => (
                <Option key={chapter.id} value={chapter.id}>
                  Chương {chapter.chapter_number} - {chapter.title}
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="resolution_text" label="Văn bản hé lộ (tùy chọn)">
            <TextArea rows={3} placeholder="Ghi lại nội dung hé lộ khi thu hồi phục bút" />
          </Form.Item>
          <Form.Item name="is_partial" label="Có phải thu hồi một phần không" valuePropName="checked">
            <Switch checkedChildren="Một phần" unCheckedChildren="Hoàn toàn" />
          </Form.Item>
        </Form>
      </Modal>

      {/* Modal đồng bộ */}
      <Modal
        title="Đồng bộ thủ công phục bút từ phân tích"
        open={syncModalVisible}
        centered
        onCancel={() => setSyncModalVisible(false)}
        onOk={handleSync}
        confirmLoading={syncing}
        okText="Bắt đầu đồng bộ"
      >
        <Alert
          message="Gợi ý"
          description="Thông thường, sau khi phân tích chương xong, phục bút sẽ tự động đồng bộ vào quản lý phục bút. Chức năng này dùng để bổ sung thủ công các phục bút có thể bị bỏ sót."
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />
        <p>Thao tác này sẽ trích xuất thông tin phục bút từ kết quả phân tích chương đã hoàn thành và đồng bộ vào bảng quản lý phục bút.</p>
        <ul>
          <li>Các bản ghi phục bút đã tồn tại sẽ không bị ghi đè</li>
          <li>Phục bút mới đồng bộ sẽ tự động được đặt thành trạng thái "Đã gieo"Trạng thái</li>
          <li>Sau khi đồng bộ xong có thể xem và chỉnh sửa trong danh sách</li>
        </ul>
      </Modal>
    </div>
  );
}
