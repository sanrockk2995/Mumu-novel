import { useState, useEffect, useCallback } from 'react';
import {
  Card,
  Row,
  Col,
  Input,
  Select,
  Button,
  Tag,
  Space,
  Empty,
  Spin,
  Modal,
  Form,
  message,
  Tooltip,
  Badge,
  Tabs,
  Typography,
  Pagination,
  Alert,
  Statistic,
  theme,
} from 'antd';
import {
  SearchOutlined,
  DownloadOutlined,
  HeartOutlined,
  HeartFilled,
  CloudUploadOutlined,
  EyeOutlined,
  UserOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  DeleteOutlined,
  CloudOutlined,
  DisconnectOutlined,
  SettingOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import { promptWorkshopApi, authApi } from '../services/api';
import type {
  PromptWorkshopItem,
  PromptSubmission,
  PromptSubmissionCreate,
  User,
} from '../types';
import { PROMPT_CATEGORIES } from '../types';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

export default function PromptWorkshop() {
  const [items, setItems] = useState<PromptWorkshopItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState(12);
  
  // Điều kiện lọc
  const [category, setCategory] = useState<string>('');
  const [searchKeyword, setSearchKeyword] = useState('');
  const [sortBy, setSortBy] = useState<'newest' | 'popular' | 'downloads'>('newest');
  
  // Trạng thái dịch vụ
  const [serviceStatus, setServiceStatus] = useState<{
    mode: string;
    instance_id: string;
    cloud_connected?: boolean;
  } | null>(null);
  
  // Liên quan đến gửi
  const [isSubmitModalOpen, setIsSubmitModalOpen] = useState(false);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [submitForm] = Form.useForm();
  
  // Bài gửi của tôi
  const [mySubmissions, setMySubmissions] = useState<PromptSubmission[]>([]);
  const [submissionsLoading, setSubmissionsLoading] = useState(false);
  
  // Popup chi tiết
  const [detailItem, setDetailItem] = useState<PromptWorkshopItem | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  
  // Trạng thái nhập
  const [importingId, setImportingId] = useState<string | null>(null);
  
  // Người dùng hiện tại
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  
  // Liên quan đến duyệt của quản trị viên
  const [adminSubmissions, setAdminSubmissions] = useState<PromptSubmission[]>([]);
  const [adminSubmissionsLoading, setAdminSubmissionsLoading] = useState(false);
  const [adminPendingCount, setAdminPendingCount] = useState(0);
  const [adminStats, setAdminStats] = useState<{
    total_items: number;
    total_official: number;
    total_pending: number;
    total_downloads: number;
    total_likes: number;
  } | null>(null);
  const [reviewModalOpen, setReviewModalOpen] = useState(false);
  const [reviewingSubmission, setReviewingSubmission] = useState<PromptSubmission | null>(null);
  const [reviewForm] = Form.useForm();
  const [reviewLoading, setReviewLoading] = useState(false);
  const [addOfficialModalOpen, setAddOfficialModalOpen] = useState(false);
  const [addOfficialForm] = Form.useForm();
  const [addOfficialLoading, setAddOfficialLoading] = useState(false);
  
  // Quản lý prompt đã xuất bản
  const [publishedItems, setPublishedItems] = useState<PromptWorkshopItem[]>([]);
  const [publishedLoading, setPublishedLoading] = useState(false);
  const [editingItem, setEditingItem] = useState<PromptWorkshopItem | null>(null);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editForm] = Form.useForm();
  const [editLoading, setEditLoading] = useState(false);
  
  // Tab đang hoạt động
  const [activeTab, setActiveTab] = useState<string>('browse');
  
  const isMobile = window.innerWidth <= 768;
  const { token } = theme.useToken();
  
  // Xác định có phải quản trị viên server không
  const isServerAdmin = serviceStatus?.mode === 'server' && currentUser?.is_admin;

  // Cấu hình lưới thẻ - giữ nhất quán với WritingStyles
  const gridConfig = {
    gutter: isMobile ? 8 : 16,
    xs: 24,
    sm: 24,
    md: 12,
    lg: 8,
    xl: 6,
  };

  // Tải trạng thái dịch vụ và thông tin người dùng
  useEffect(() => {
    const init = async () => {
      try {
        const [status, user] = await Promise.all([
          promptWorkshopApi.getStatus(),
          authApi.getCurrentUser().catch(() => null),
        ]);
        setServiceStatus(status);
        setCurrentUser(user);
      } catch (error) {
        console.error('Failed to initialize:', error);
      }
    };
    init();
  }, []);

  // Tải danh sách workshop
  const loadItems = useCallback(async () => {
    setLoading(true);
    try {
      const response = await promptWorkshopApi.getItems({
        category: category || undefined,
        search: searchKeyword || undefined,
        sort: sortBy,
        page: currentPage,
        limit: pageSize,
      });
      setItems(response.data?.items || []);
      setTotal(response.data?.total || 0);
    } catch (error) {
      console.error('Failed to load workshop items:', error);
      message.error('Tải prompt workshop thất bại');
    } finally {
      setLoading(false);
    }
  }, [category, searchKeyword, sortBy, currentPage, pageSize]);

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  // Tải bài gửi của tôi
  const loadMySubmissions = async () => {
    setSubmissionsLoading(true);
    try {
      const response = await promptWorkshopApi.getMySubmissions();
      setMySubmissions(response.data?.items || []);
    } catch (error) {
      console.error('Failed to load submissions:', error);
    } finally {
      setSubmissionsLoading(false);
    }
  };

  // Nhập vào local
  const handleImport = async (item: PromptWorkshopItem) => {
    setImportingId(item.id);
    try {
      await promptWorkshopApi.importItem(item.id);
      message.success(`Đã nhập 「${item.name}」 vào phong cách viết local`);
      // Refresh danh sách để cập nhật số lượt tải
      loadItems();
    } catch (error) {
      console.error('Failed to import item:', error);
      message.error('Nhập thất bại');
    } finally {
      setImportingId(null);
    }
  };

  // Thích
  const handleLike = async (item: PromptWorkshopItem) => {
    try {
      const response = await promptWorkshopApi.toggleLike(item.id);
      // Cập nhật state local
      setItems(prev => prev.map(i => 
        i.id === item.id 
          ? { ...i, is_liked: response.liked, like_count: response.like_count }
          : i
      ));
    } catch (error) {
      console.error('Failed to toggle like:', error);
      message.error('Thao tác thất bại');
    }
  };

  // Gửi prompt mới
  const handleSubmit = async (values: PromptSubmissionCreate) => {
    setSubmitLoading(true);
    try {
      await promptWorkshopApi.submit({
        ...values,
        tags: values.tags ? (values.tags as unknown as string).split(',').map((t: string) => t.trim()).filter(Boolean) : [],
      });
      message.success('Gửi thành công, chờ quản trị viên duyệt');
      setIsSubmitModalOpen(false);
      submitForm.resetFields();
      loadMySubmissions();
      // Nếu là quản trị viên server, refresh danh sách chờ duyệt
      if (isServerAdmin) {
        loadAdminSubmissions();
      }
    } catch (error) {
      console.error('Failed to submit:', error);
      message.error('Gửi thất bại');
    } finally {
      setSubmitLoading(false);
    }
  };

  // Rút lại bài gửi (trạng thái pending)
  const handleWithdraw = async (submissionId: string) => {
    try {
      await promptWorkshopApi.withdrawSubmission(submissionId);
      message.success('Đã rút lại');
      loadMySubmissions();
      // Nếu là quản trị viên server, refresh danh sách chờ duyệt
      if (isServerAdmin) {
        loadAdminSubmissions();
      }
    } catch (error) {
      console.error('Failed to withdraw:', error);
      message.error('Rút lại thất bại');
    }
  };

  // Xóa bản ghi gửi (trạng thái đã duyệt)
  const handleDeleteSubmission = async (submission: PromptSubmission) => {
    Modal.confirm({
      title: 'Xóa bản ghi gửi',
      content: `Chắc chắn xóa bản ghi gửi của 「${submission.name}」 chứ? Thao tác này không thể khôi phục.`,
      okText: 'Xóa',
      okType: 'danger',
      cancelText: 'Hủy',
      centered: true,
      onOk: async () => {
        try {
          await promptWorkshopApi.deleteSubmission(submission.id);
          message.success('Xóa thành công');
          loadMySubmissions();
          // Nếu là quản trị viên server, refresh danh sách liên quan
          if (isServerAdmin) {
            loadAdminSubmissions();
          }
        } catch (error) {
          console.error('Failed to delete submission:', error);
          message.error('Xóa thất bại');
        }
      },
    });
  };

  // Xem chi tiết
  const handleViewDetail = async (item: PromptWorkshopItem) => {
    try {
      const response = await promptWorkshopApi.getItem(item.id);
      setDetailItem(response.data);
      setIsDetailModalOpen(true);
    } catch (error) {
      console.error('Failed to load detail:', error);
      message.error('Tải chi tiết thất bại');
    }
  };

  // Lấy màu nhãn phân loại
  const getCategoryColor = (cat: string) => {
    const colors: Record<string, string> = {
      general: 'blue',
      fantasy: 'purple',
      martial: 'orange',
      romance: 'pink',
      scifi: 'cyan',
      horror: 'red',
      history: 'gold',
      urban: 'green',
      game: 'magenta',
      other: 'default',
    };
    return colors[cat] || 'default';
  };

  // Lấy tên phân loại
  const getCategoryName = (cat: string) => {
    return PROMPT_CATEGORIES[cat] || cat;
  };
  
  // Lấy danh sách tùy chọn phân loại
  const categoryOptions = Object.entries(PROMPT_CATEGORIES).map(([value, label]) => ({
    value,
    label,
  }));

  // Lấy nhãn trạng thái gửi
  const getStatusTag = (status: string) => {
    const config: Record<string, { color: string; icon: React.ReactNode; text: string }> = {
      pending: { color: 'processing', icon: <ClockCircleOutlined />, text: 'Chờ duyệt' },
      approved: { color: 'success', icon: <CheckCircleOutlined />, text: 'Đã duyệt' },
      rejected: { color: 'error', icon: <CloseCircleOutlined />, text: 'Đã từ chối' },
    };
    const cfg = config[status] || config.pending;
    return <Tag color={cfg.color} icon={cfg.icon}>{cfg.text}</Tag>;
  };

  // Render khu vực lọc (cố định trên cùng)
  const renderFilterBar = () => (
    <div style={{ marginBottom: 16 }}>
      {/* Trạng thái dịch vụ */}
      {serviceStatus && !serviceStatus.cloud_connected && serviceStatus.mode === 'client' && (
        <Alert
          type="warning"
          message="Dịch vụ đám mây chưa kết nối"
          description="Không thể truy cập prompt workshop, vui lòng kiểm tra kết nối mạng hoặc thử lại sau"
          icon={<DisconnectOutlined />}
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}
      
      {/* Khu vực lọc */}
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: 12,
        alignItems: 'center',
      }}>
        <Input
          placeholder="Tìm kiếm prompt..."
          prefix={<SearchOutlined />}
          value={searchKeyword}
          onChange={e => setSearchKeyword(e.target.value)}
          onPressEnter={() => { setCurrentPage(1); loadItems(); }}
          style={{ width: isMobile ? '100%' : 200 }}
          allowClear
        />
        <Select
          placeholder="Chọn phân loại"
          value={category}
          onChange={v => { setCategory(v); setCurrentPage(1); }}
          style={{ width: isMobile ? '100%' : 150 }}
          allowClear
        >
          {categoryOptions.map(cat => (
            <Select.Option key={cat.value} value={cat.value}>{cat.label}</Select.Option>
          ))}
        </Select>
        <Select
          value={sortBy}
          onChange={v => { setSortBy(v); setCurrentPage(1); }}
          style={{ width: isMobile ? '100%' : 120 }}
        >
          <Select.Option value="newest">Mới nhất</Select.Option>
          <Select.Option value="popular">Phổ biến nhất</Select.Option>
          <Select.Option value="downloads">Tải nhiều nhất</Select.Option>
        </Select>
        <Button
          icon={<SyncOutlined />}
          onClick={() => { setCurrentPage(1); loadItems(); }}
        >
          Làm mới
        </Button>
      </div>
    </div>
  );

  // Render danh sách workshop (chỉ phần thẻ, dùng cho khu vực cuộn)
  const renderWorkshopList = () => (
    <div style={{ height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', paddingRight: 4 }}>
        <Spin spinning={loading}>
          {items.length === 0 ? (
            <Empty description="Chưa có prompt" />
          ) : (
              <Row
                gutter={[0, gridConfig.gutter]}
                style={{ marginLeft: 0, marginRight: 0 }}
              >
              {items.map(item => (
                <Col
                  key={item.id}
                  xs={gridConfig.xs}
                  sm={gridConfig.sm}
                  md={gridConfig.md}
                  lg={gridConfig.lg}
                  xl={gridConfig.xl}
                  style={{
                    paddingLeft: 0,
                    paddingRight: gridConfig.gutter / 2,
                    marginBottom: gridConfig.gutter
                  }}
                >
                  <Card
                    hoverable
                    style={{ 
                      height: '100%', 
                      borderRadius: 12,
                      display: 'flex',
                      flexDirection: 'column',
                      border: `1px solid ${token.colorBorderSecondary}`,
                    }}
                    bodyStyle={{ 
                      padding: 16, 
                      display: 'flex', 
                      flexDirection: 'column', 
                      flex: 1,
                    }}
                    actions={[
                      <Tooltip title="Xem chi tiết" key="view">
                        <EyeOutlined onClick={() => handleViewDetail(item)} />
                      </Tooltip>,
                      <Tooltip title={item.is_liked ? 'Bỏ thích' : 'Thích'} key="like">
                        <span onClick={() => handleLike(item)}>
                          {item.is_liked ? (
                            <HeartFilled style={{ color: token.colorError }} />
                          ) : (
                            <HeartOutlined />
                          )}
                          <span style={{ marginLeft: 4 }}>{item.like_count || 0}</span>
                        </span>
                      </Tooltip>,
                      <Tooltip title="Nhập vào local" key="import">
                        <Button
                          type="link"
                          size="small"
                          icon={<DownloadOutlined />}
                          loading={importingId === item.id}
                          onClick={() => handleImport(item)}
                        >
                          {item.download_count || 0}
                        </Button>
                      </Tooltip>,
                    ]}
                  >
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                      <Space style={{ marginBottom: 12 }} wrap>
                        <Text strong style={{ fontSize: 16 }}>{item.name}</Text>
                        <Tag color={getCategoryColor(item.category)}>
                          {getCategoryName(item.category)}
                        </Tag>
                      </Space>
                      
                      {item.description && (
                        <Paragraph
                          type="secondary"
                          style={{ fontSize: 13, marginBottom: 12 }}
                          ellipsis={{ rows: 2, tooltip: item.description }}
                        >
                          {item.description}
                        </Paragraph>
                      )}
                      
                      <Paragraph
                        type="secondary"
                        style={{
                          fontSize: 12,
                          marginBottom: 0,
                          backgroundColor: token.colorFillQuaternary,
                          padding: 8,
                          borderRadius: 4,
                          flex: 1,
                          minHeight: 60,
                        }}
                        ellipsis={{ rows: 3 }}
                      >
                        {item.prompt_content}
                      </Paragraph>
                      
                      {item.tags && item.tags.length > 0 && (
                        <Space size={4} wrap style={{ marginTop: 8 }}>
                          {item.tags.slice(0, 3).map(tag => (
                            <Tag key={tag} style={{ fontSize: 11 }}>{tag}</Tag>
                          ))}
                          {item.tags.length > 3 && (
                            <Tag style={{ fontSize: 11 }}>+{item.tags.length - 3}</Tag>
                          )}
                        </Space>
                      )}
                    </div>
                    
                    <div style={{ marginTop: 8, color: token.colorTextTertiary, fontSize: 12 }}>
                      <Space>
                        <span><UserOutlined /> {item.author_name || 'Ẩn danh'}</span>
                      </Space>
                    </div>
                  </Card>
                </Col>
              ))}
              </Row>
          )}
        </Spin>
      </div>

      {total > 0 && (
        <div
          style={{
            flexShrink: 0,
            textAlign: 'center',
            padding: '12px 0 0',
            marginTop: 12,
            borderTop: `1px solid ${token.colorBorderSecondary}`,
            background: token.colorBgContainer,
          }}
        >
          <Pagination
            current={currentPage}
            total={total}
            pageSize={pageSize}
            onChange={page => setCurrentPage(page)}
            showSizeChanger={false}
            showTotal={t => `Tổng ${t} prompt`}
          />
        </div>
      )}
    </div>
  );

  // Render bài gửi của tôi
  const renderMySubmissions = () => (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text>Xem prompt bạn đã gửi và trạng thái duyệt</Text>
        <Button icon={<SyncOutlined />} onClick={loadMySubmissions}>
          Làm mới
        </Button>
      </div>
      
      <Spin spinning={submissionsLoading}>
          {mySubmissions.length === 0 ? (
            <Empty description="Chưa có bản ghi gửi" />
          ) : (
            <Row gutter={[0, gridConfig.gutter]} style={{ marginLeft: 0, marginRight: 0 }}>
              {mySubmissions.map(sub => (
              <Col 
                key={sub.id} 
                xs={gridConfig.xs} 
                sm={gridConfig.sm} 
                md={gridConfig.md} 
                lg={gridConfig.lg}
                xl={gridConfig.xl}
                style={{
                  paddingLeft: 0,
                  paddingRight: gridConfig.gutter / 2,
                  marginBottom: gridConfig.gutter
                }}
              >
                <Card
                  style={{ borderRadius: 12, height: '100%', border: `1px solid ${token.colorBorderSecondary}` }}
                  bodyStyle={{ padding: 16 }}
                >
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Text strong>{sub.name}</Text>
                      {getStatusTag(sub.status)}
                    </div>
                    
                    <Tag color={getCategoryColor(sub.category)}>
                      {getCategoryName(sub.category)}
                    </Tag>
                    
                    <Paragraph
                      type="secondary"
                      style={{ fontSize: 12, marginBottom: 0 }}
                      ellipsis={{ rows: 2 }}
                    >
                      {sub.prompt_content}
                    </Paragraph>
                    
                    {sub.status === 'rejected' && sub.review_note && (
                      <Alert
                        type="error"
                        message="Lý do từ chối"
                        description={sub.review_note}
                        style={{ fontSize: 12 }}
                      />
                    )}
                    
                    <div style={{ fontSize: 12, color: token.colorTextTertiary }}>
                      Thời gian gửi: {sub.created_at ? new Date(sub.created_at).toLocaleDateString() : '-'}
                    </div>
                    
                    <Space>
                      {sub.status === 'pending' && (
                        <Button
                          type="link"
                          danger
                          size="small"
                          icon={<DeleteOutlined />}
                          onClick={() => handleWithdraw(sub.id)}
                        >
                          Rút lại
                        </Button>
                      )}
                      {sub.status !== 'pending' && (
                        <Button
                          type="link"
                          danger
                          size="small"
                          icon={<DeleteOutlined />}
                          onClick={() => handleDeleteSubmission(sub)}
                        >
                          Xóa bản ghi
                        </Button>
                      )}
                    </Space>
                  </Space>
                </Card>
              </Col>
            ))}
            </Row>
          )}
      </Spin>
    </div>
  );

  // Tải danh sách chờ duyệt của quản trị viên
  const loadAdminSubmissions = async () => {
    if (!isServerAdmin) return;
    
    setAdminSubmissionsLoading(true);
    try {
      const [subsResponse, statsResponse] = await Promise.all([
        promptWorkshopApi.adminGetSubmissions({ status: 'pending', limit: 50 }),
        promptWorkshopApi.adminGetStats(),
      ]);
      setAdminSubmissions(subsResponse.data?.items || []);
      setAdminPendingCount(subsResponse.data?.pending_count || 0);
      setAdminStats(statsResponse.data || null);
    } catch (error) {
      console.error('Failed to load admin submissions:', error);
    } finally {
      setAdminSubmissionsLoading(false);
    }
  };

  // Tải danh sách prompt đã xuất bản (dành cho quản trị viên)
  const loadPublishedItems = async () => {
    if (!isServerAdmin) return;
    
    setPublishedLoading(true);
    try {
      const response = await promptWorkshopApi.getItems({ limit: 100 });
      setPublishedItems(response.data?.items || []);
    } catch (error) {
      console.error('Failed to load published items:', error);
    } finally {
      setPublishedLoading(false);
    }
  };

  // Xóa prompt đã xuất bản
  const handleDeleteItem = async (item: PromptWorkshopItem) => {
    Modal.confirm({
      title: 'Xác nhận xóa',
      content: `Chắc chắn xóa 「${item.name}」 chứ? Thao tác này không thể khôi phục.`,
      okText: 'Xóa',
      okType: 'danger',
      cancelText: 'Hủy',
      centered: true,
      onOk: async () => {
        try {
          await promptWorkshopApi.adminDeleteItem(item.id);
          message.success('Xóa thành công');
          loadPublishedItems();
          loadAdminSubmissions();
          loadItems();
        } catch (error) {
          console.error('Failed to delete item:', error);
          message.error('Xóa thất bại');
        }
      },
    });
  };

  // Chỉnh sửa prompt đã xuất bản
  const handleEditItem = async (values: { name: string; category: string; description?: string; prompt_content: string; tags?: string }) => {
    if (!editingItem) return;
    
    setEditLoading(true);
    try {
      await promptWorkshopApi.adminUpdateItem(editingItem.id, {
        ...values,
        tags: values.tags ? values.tags.split(',').map(t => t.trim()).filter(Boolean) : undefined,
      });
      message.success('Sửa thành công');
      setEditModalOpen(false);
      setEditingItem(null);
      editForm.resetFields();
      loadPublishedItems();
      loadItems();
    } catch (error) {
      console.error('Failed to update item:', error);
      message.error('Sửa thất bại');
    } finally {
      setEditLoading(false);
    }
  };

  // Mở popup chỉnh sửa
  const openEditModal = (item: PromptWorkshopItem) => {
    setEditingItem(item);
    editForm.setFieldsValue({
      name: item.name,
      category: item.category,
      description: item.description,
      prompt_content: item.prompt_content,
      tags: item.tags?.join(', '),
    });
    setEditModalOpen(true);
  };

  // Duyệt bài gửi
  const handleReview = async (action: 'approve' | 'reject') => {
    if (!reviewingSubmission) return;
    
    setReviewLoading(true);
    try {
      const values = reviewForm.getFieldsValue();
      await promptWorkshopApi.adminReviewSubmission(reviewingSubmission.id, {
        action,
        review_note: values.review_note,
        category: values.category,
        tags: values.tags ? values.tags.split(',').map((t: string) => t.trim()).filter(Boolean) : undefined,
      });
      message.success(action === 'approve' ? 'Đã duyệt' : 'Đã từ chối');
      setReviewModalOpen(false);
      setReviewingSubmission(null);
      reviewForm.resetFields();
      // Refresh tất cả dữ liệu liên quan
      loadAdminSubmissions();
      loadItems();
      loadPublishedItems();  // Khi duyệt sẽ thêm vào danh sách đã xuất bản
    } catch (error) {
      console.error('Failed to review:', error);
      message.error('Duyệt thất bại');
    } finally {
      setReviewLoading(false);
    }
  };

  // Thêm prompt chính thức
  const handleAddOfficial = async (values: { name: string; category: string; description?: string; prompt_content: string; tags?: string }) => {
    setAddOfficialLoading(true);
    try {
      await promptWorkshopApi.adminCreateItem({
        ...values,
        tags: values.tags ? values.tags.split(',').map(t => t.trim()).filter(Boolean) : undefined,
      });
      message.success('Thêm thành công');
      setAddOfficialModalOpen(false);
      addOfficialForm.resetFields();
      loadItems();
      loadAdminSubmissions();
      loadPublishedItems();
    } catch (error) {
      console.error('Failed to add official item:', error);
      message.error('Thêm thất bại');
    } finally {
      setAddOfficialLoading(false);
    }
  };

  // Render bảng quản trị viên
  const renderAdminPanel = () => (
    <div>
      {/* Dữ liệu thống kê */}
      {adminStats && (
        <Row gutter={16} style={{ marginBottom: 24 }}>
          <Col span={4}>
            <Card size="small">
              <Statistic title="Tổng prompt" value={adminStats.total_items} />
            </Card>
          </Col>
          <Col span={4}>
            <Card size="small">
              <Statistic title="Prompt chính thức" value={adminStats.total_official} />
            </Card>
          </Col>
          <Col span={4}>
            <Card size="small">
              <Statistic title="Chờ duyệt" value={adminStats.total_pending} valueStyle={{ color: token.colorWarning }} />
            </Card>
          </Col>
          <Col span={4}>
            <Card size="small">
              <Statistic title="Tổng lượt tải" value={adminStats.total_downloads} />
            </Card>
          </Col>
          <Col span={4}>
            <Card size="small">
              <Statistic title="Tổng lượt thích" value={adminStats.total_likes} />
            </Card>
          </Col>
          <Col span={4}>
            <Card size="small" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
              <Button type="primary" icon={<PlusOutlined />} onClick={() => setAddOfficialModalOpen(true)}>
                Thêm chính thức
              </Button>
            </Card>
          </Col>
        </Row>
      )}
      
      {/* Danh sách chờ duyệt */}
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text strong>Bài gửi chờ duyệt ({adminPendingCount})</Text>
        <Button icon={<SyncOutlined />} onClick={loadAdminSubmissions}>
          Làm mới
        </Button>
      </div>
      
      <Spin spinning={adminSubmissionsLoading}>
        {adminSubmissions.length === 0 ? (
          <Empty description="Chưa có bài gửi chờ duyệt" />
        ) : (
          <Row gutter={[0, gridConfig.gutter]} style={{ marginLeft: 0, marginRight: 0 }}>
            {adminSubmissions.map(sub => (
              <Col 
                key={sub.id} 
                xs={gridConfig.xs} 
                sm={gridConfig.sm} 
                md={gridConfig.md} 
                lg={gridConfig.lg}
                xl={gridConfig.xl}
                style={{
                  paddingLeft: 0,
                  paddingRight: gridConfig.gutter / 2,
                  marginBottom: gridConfig.gutter
                }}
              >
                <Card
                  style={{ borderRadius: 12, border: `1px solid ${token.colorBorderSecondary}` }}
                  bodyStyle={{ padding: 16 }}
                  actions={[
                    <Button
                      key="approve"
                      type="link"
                      style={{ color: token.colorSuccess }}
                      onClick={() => {
                        setReviewingSubmission(sub);
                        reviewForm.setFieldsValue({
                          category: sub.category,
                          tags: sub.tags?.join(', '),
                        });
                        setReviewModalOpen(true);
                      }}
                    >
                      Duyệt
                    </Button>,
                  ]}
                >
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <Text strong>{sub.name}</Text>
                    <Tag color={getCategoryColor(sub.category)}>
                      {getCategoryName(sub.category)}
                    </Tag>
                    
                    <Paragraph
                      type="secondary"
                      style={{ fontSize: 12, marginBottom: 0 }}
                      ellipsis={{ rows: 3 }}
                    >
                      {sub.prompt_content}
                    </Paragraph>
                    
                    <div style={{ fontSize: 11, color: token.colorTextTertiary }}>
                      <div>Người gửi: {sub.submitter_name || 'Không rõ'}</div>
                      <div>Nguồn: {sub.source_instance}</div>
                      <div>Thời gian: {sub.created_at ? new Date(sub.created_at).toLocaleDateString() : '-'}</div>
                    </div>
                  </Space>
                </Card>
              </Col>
            ))}
          </Row>
        )}
      </Spin>
      
      {/* Quản lý prompt đã xuất bản */}
      <div style={{ marginTop: 32, marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text strong>Quản lý prompt đã xuất bản ({publishedItems.length})</Text>
        <Button icon={<SyncOutlined />} onClick={loadPublishedItems}>
          Làm mới
        </Button>
      </div>
      
      <Spin spinning={publishedLoading}>
        {publishedItems.length === 0 ? (
          <Empty description="Chưa có prompt đã xuất bản" />
        ) : (
          <Row gutter={[0, gridConfig.gutter]} style={{ marginLeft: 0, marginRight: 0 }}>
            {publishedItems.map(item => (
              <Col 
                key={item.id} 
                xs={gridConfig.xs} 
                sm={gridConfig.sm} 
                md={gridConfig.md} 
                lg={gridConfig.lg}
                xl={gridConfig.xl}
                style={{
                  paddingLeft: 0,
                  paddingRight: gridConfig.gutter / 2,
                  marginBottom: gridConfig.gutter
                }}
              >
                <Card
                  style={{ borderRadius: 12, border: `1px solid ${token.colorBorderSecondary}` }}
                  bodyStyle={{ padding: 16 }}
                  actions={[
                    <Tooltip title="Chỉnh sửa" key="edit">
                      <Button
                        type="link"
                        icon={<SettingOutlined />}
                        onClick={() => openEditModal(item)}
                      />
                    </Tooltip>,
                    <Tooltip title="Xóa" key="delete">
                      <Button
                        type="link"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={() => handleDeleteItem(item)}
                      />
                    </Tooltip>,
                  ]}
                >
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Text strong ellipsis style={{ maxWidth: 120 }}>{item.name}</Text>
                      {item.is_official && <Tag color="gold">Chính thức</Tag>}
                    </div>
                    <Tag color={getCategoryColor(item.category)}>
                      {getCategoryName(item.category)}
                    </Tag>
                    
                    <Paragraph
                      type="secondary"
                      style={{ fontSize: 12, marginBottom: 0 }}
                      ellipsis={{ rows: 2 }}
                    >
                      {item.prompt_content}
                    </Paragraph>
                    
                    <div style={{ fontSize: 11, color: token.colorTextTertiary }}>
                      <Space>
                        <span><HeartOutlined /> {item.like_count || 0}</span>
                        <span><DownloadOutlined /> {item.download_count || 0}</span>
                      </Space>
                    </div>
                  </Space>
                </Card>
              </Col>
            ))}
          </Row>
        )}
      </Spin>
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Khu vực cố định: tiêu đề + thanh chuyển Tabs + thanh lọc */}
      <div style={{ flexShrink: 0 }}>
        {/* Tiêu đề và khu vực thao tác */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: isMobile ? '12px 0' : '16px 0',
          marginBottom: isMobile ? 12 : 16,
          borderBottom: `1px solid ${token.colorBorderSecondary}`,
          flexWrap: 'wrap',
          gap: 12,
        }}>
          <h2 style={{ margin: 0, fontSize: isMobile ? 18 : 24, display: 'flex', alignItems: 'center', gap: 8 }}>
            <CloudOutlined />
            Prompt Workshop
            {serviceStatus?.mode === 'server' && (
              <Badge status="success" text="Chế độ server" style={{ marginLeft: 8, fontSize: 12 }} />
            )}
          </h2>
          <Button
            type="primary"
            icon={<CloudUploadOutlined />}
            onClick={() => setIsSubmitModalOpen(true)}
          >
            Chia sẻ prompt của tôi
          </Button>
        </div>

        {/* Thanh chuyển Tabs (không gồm nội dung) */}
        <Tabs
          activeKey={activeTab}
          onChange={key => {
            setActiveTab(key);
            if (key === 'submissions') loadMySubmissions();
            if (key === 'admin') {
              loadAdminSubmissions();
              loadPublishedItems();
            }
          }}
          items={[
            { key: 'browse', label: 'Duyệt workshop' },
            {
              key: 'submissions',
              label: (
                <Badge count={mySubmissions.filter(s => s.status === 'pending').length} size="small">
                  Bài gửi của tôi
                </Badge>
              ),
            },
            ...(isServerAdmin ? [{
              key: 'admin',
              label: (
                <Badge count={adminPendingCount} size="small">
                  <span><SettingOutlined /> Quản lý duyệt</span>
                </Badge>
              ),
            }] : []),
          ]}
          tabBarStyle={{ marginBottom: 16 }}
        />

        {/* Thanh lọc (chỉ hiển thị khi duyệt workshop) */}
        {activeTab === 'browse' && renderFilterBar()}
      </div>

      {/* Khu vực nội dung: duyệt workshop phân trang cố định bên trong, các Tab khác giữ cuộn riêng */}
      <div style={{ flex: 1, overflow: 'hidden', minHeight: 0 }}>
        {activeTab === 'browse' && renderWorkshopList()}
        {activeTab === 'submissions' && (
          <div style={{ height: '100%', overflowY: 'auto' }}>{renderMySubmissions()}</div>
        )}
        {activeTab === 'admin' && (
          <div style={{ height: '100%', overflowY: 'auto' }}>{renderAdminPanel()}</div>
        )}
      </div>

      {/* Popup gửi */}
      <Modal
        title="Chia sẻ prompt lên workshop"
        open={isSubmitModalOpen}
        onCancel={() => {
          setIsSubmitModalOpen(false);
          submitForm.resetFields();
        }}
        footer={null}
        width={isMobile ? '100%' : 600}
        centered
      >
        <Alert
          type="info"
          message="Lưu ý khi gửi"
          description="Prompt của bạn sẽ được gửi cho quản trị viên duyệt, sau khi duyệt sẽ hiển thị trong workshop. Vui lòng đảm bảo nội dung nguyên bản và không chứa thông tin nhạy cảm."
          style={{ marginBottom: 16 }}
          showIcon
        />
        
        <Form
          form={submitForm}
          layout="vertical"
          onFinish={handleSubmit}
        >
          <Form.Item
            name="name"
            label="Tên"
            rules={[{ required: true, message: 'Vui lòng nhập tên' }]}
          >
            <Input placeholder="Đặt tên cho prompt của bạn" maxLength={50} />
          </Form.Item>
          
          <Form.Item
            name="category"
            label="Phân loại"
            rules={[{ required: true, message: 'Vui lòng chọn phân loại' }]}
          >
            <Select placeholder="Chọn phân loại">
              {categoryOptions.map(cat => (
                <Select.Option key={cat.value} value={cat.value}>{cat.label}</Select.Option>
              ))}
            </Select>
          </Form.Item>
          
          <Form.Item name="description" label="Mô tả">
            <TextArea rows={2} placeholder="Mô tả ngắn gọn công dụng và hiệu quả của prompt này" maxLength={200} />
          </Form.Item>
          
          <Form.Item
            name="prompt_content"
            label="Nội dung prompt"
            rules={[{ required: true, message: 'Vui lòng nhập nội dung prompt' }]}
          >
            <TextArea rows={6} placeholder="Nhập đầy đủ nội dung prompt..." />
          </Form.Item>
          
          <Form.Item
            name="author_display_name"
            label="Tên tác giả"
            rules={[{ required: true, message: 'Vui lòng nhập tên tác giả' }]}
            tooltip="Tên tác giả hiển thị sau khi xuất bản"
          >
            <Input placeholder="Vui lòng nhập tên tác giả (bắt buộc)" maxLength={50} />
          </Form.Item>
          
          <Form.Item name="tags" label="Nhãn">
            <Input placeholder="Nhập nhãn, nhiều nhãn cách nhau bằng dấu phẩy, VD: võ hiệp,đối thoại,tinh tế" />
          </Form.Item>
          
          <Form.Item>
            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
              <Button onClick={() => {
                setIsSubmitModalOpen(false);
                submitForm.resetFields();
              }}>
                Hủy
              </Button>
              <Button type="primary" htmlType="submit" loading={submitLoading}>
                Gửi duyệt
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* Popup chi tiết */}
      <Modal
        title={detailItem?.name}
        open={isDetailModalOpen}
        onCancel={() => {
          setIsDetailModalOpen(false);
          setDetailItem(null);
        }}
        footer={[
          <Button key="close" onClick={() => setIsDetailModalOpen(false)}>
            Đóng
          </Button>,
          <Button
            key="import"
            type="primary"
            icon={<DownloadOutlined />}
            loading={importingId === detailItem?.id}
            onClick={() => detailItem && handleImport(detailItem)}
          >
            Nhập vào local
          </Button>,
        ]}
        width={isMobile ? '100%' : 700}
        centered
      >
        {detailItem && (
          <div>
            <Space style={{ marginBottom: 16 }} wrap>
              <Tag color={getCategoryColor(detailItem.category)}>
                {getCategoryName(detailItem.category)}
              </Tag>
              {detailItem.tags?.map(tag => (
                <Tag key={tag}>{tag}</Tag>
              ))}
            </Space>
            
            {detailItem.description && (
              <Paragraph style={{ marginBottom: 16 }}>
                {detailItem.description}
              </Paragraph>
            )}
            
            <div style={{
              backgroundColor: token.colorFillSecondary,
              padding: 16,
              borderRadius: 8,
              marginBottom: 16,
              maxHeight: 400,
              overflow: 'auto',
            }}>
              <Text strong style={{ display: 'block', marginBottom: 8 }}>Nội dung prompt</Text>
              <pre style={{
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                margin: 0,
                fontSize: 13,
              }}>
                {detailItem.prompt_content}
              </pre>
            </div>
            
            <Row gutter={16}>
              <Col span={8}>
                <Text type="secondary">Tác giả</Text>
                <div><UserOutlined /> {detailItem.author_name || 'Ẩn danh'}</div>
              </Col>
              <Col span={8}>
                <Text type="secondary">Lượt thích</Text>
                <div><HeartOutlined /> {detailItem.like_count || 0}</div>
              </Col>
              <Col span={8}>
                <Text type="secondary">Lượt tải</Text>
                <div><DownloadOutlined /> {detailItem.download_count || 0}</div>
              </Col>
            </Row>
          </div>
        )}
      </Modal>
      {/* Popup duyệt */}
      <Modal
        title={`Duyệt: ${reviewingSubmission?.name}`}
        open={reviewModalOpen}
        onCancel={() => {
          setReviewModalOpen(false);
          setReviewingSubmission(null);
          reviewForm.resetFields();
        }}
        footer={null}
        width={700}
        centered
      >
        {reviewingSubmission && (
          <div>
            <div style={{
              backgroundColor: token.colorFillSecondary,
              padding: 16,
              borderRadius: 8,
              marginBottom: 16,
              maxHeight: 300,
              overflow: 'auto',
            }}>
              <Text strong style={{ display: 'block', marginBottom: 8 }}>Xem trước nội dung prompt</Text>
              <pre style={{
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                margin: 0,
                fontSize: 13,
              }}>
                {reviewingSubmission.prompt_content}
              </pre>
            </div>
            
            <Form form={reviewForm} layout="vertical">
              <Form.Item name="category" label="Phân loại (có thể sửa)">
                <Select>
                  {categoryOptions.map(cat => (
                    <Select.Option key={cat.value} value={cat.value}>{cat.label}</Select.Option>
                  ))}
                </Select>
              </Form.Item>
              
              <Form.Item name="tags" label="Nhãn (có thể sửa, cách nhau bằng dấu phẩy)">
                <Input placeholder="võ hiệp, đối thoại, tinh tế" />
              </Form.Item>
              
              <Form.Item name="review_note" label="Ghi chú duyệt">
                <TextArea rows={2} placeholder="Khi từ chối vui lòng điền lý do..." />
              </Form.Item>
              
              <Form.Item>
                <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
                  <Button onClick={() => setReviewModalOpen(false)}>
                    Hủy
                  </Button>
                  <Button danger loading={reviewLoading} onClick={() => handleReview('reject')}>
                    Từ chối
                  </Button>
                  <Button type="primary" loading={reviewLoading} onClick={() => handleReview('approve')}>
                    Duyệt
                  </Button>
                </Space>
              </Form.Item>
            </Form>
          </div>
        )}
      </Modal>

      {/* Popup thêm prompt chính thức */}
      <Modal
        title="Thêm prompt chính thức"
        open={addOfficialModalOpen}
        onCancel={() => {
          setAddOfficialModalOpen(false);
          addOfficialForm.resetFields();
        }}
        footer={null}
        width={600}
        centered
      >
        <Form
          form={addOfficialForm}
          layout="vertical"
          onFinish={handleAddOfficial}
        >
          <Form.Item
            name="name"
            label="Tên"
            rules={[{ required: true, message: 'Vui lòng nhập tên' }]}
          >
            <Input placeholder="Tên prompt" maxLength={50} />
          </Form.Item>
          
          <Form.Item
            name="category"
            label="Phân loại"
            rules={[{ required: true, message: 'Vui lòng chọn phân loại' }]}
          >
            <Select placeholder="Chọn phân loại">
              {categoryOptions.map(cat => (
                <Select.Option key={cat.value} value={cat.value}>{cat.label}</Select.Option>
              ))}
            </Select>
          </Form.Item>
          
          <Form.Item name="description" label="Mô tả">
            <TextArea rows={2} placeholder="Mô tả ngắn gọn" maxLength={200} />
          </Form.Item>
          
          <Form.Item
            name="prompt_content"
            label="Nội dung prompt"
            rules={[{ required: true, message: 'Vui lòng nhập nội dung prompt' }]}
          >
            <TextArea rows={8} placeholder="Nhập đầy đủ nội dung prompt..." />
          </Form.Item>
          
          <Form.Item name="tags" label="Nhãn">
            <Input placeholder="Cách nhau bằng dấu phẩy, VD: võ hiệp,đối thoại,tinh tế" />
          </Form.Item>
          
          <Form.Item>
            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
              <Button onClick={() => {
                setAddOfficialModalOpen(false);
                addOfficialForm.resetFields();
              }}>
                Hủy
              </Button>
              <Button type="primary" htmlType="submit" loading={addOfficialLoading}>
                Thêm
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* Popup chỉnh sửa prompt */}
      <Modal
        title={`Chỉnh sửa: ${editingItem?.name}`}
        open={editModalOpen}
        onCancel={() => {
          setEditModalOpen(false);
          setEditingItem(null);
          editForm.resetFields();
        }}
        footer={null}
        width={600}
        centered
      >
        <Form
          form={editForm}
          layout="vertical"
          onFinish={handleEditItem}
        >
          <Form.Item
            name="name"
            label="Tên"
            rules={[{ required: true, message: 'Vui lòng nhập tên' }]}
          >
            <Input placeholder="Tên prompt" maxLength={50} />
          </Form.Item>
          
          <Form.Item
            name="category"
            label="Phân loại"
            rules={[{ required: true, message: 'Vui lòng chọn phân loại' }]}
          >
            <Select placeholder="Chọn phân loại">
              {categoryOptions.map(cat => (
                <Select.Option key={cat.value} value={cat.value}>{cat.label}</Select.Option>
              ))}
            </Select>
          </Form.Item>
          
          <Form.Item name="description" label="Mô tả">
            <TextArea rows={2} placeholder="Mô tả ngắn gọn" maxLength={200} />
          </Form.Item>
          
          <Form.Item
            name="prompt_content"
            label="Nội dung prompt"
            rules={[{ required: true, message: 'Vui lòng nhập nội dung prompt' }]}
          >
            <TextArea rows={8} placeholder="Nhập đầy đủ nội dung prompt..." />
          </Form.Item>
          
          <Form.Item name="tags" label="Nhãn">
            <Input placeholder="Cách nhau bằng dấu phẩy, VD: võ hiệp,đối thoại,tinh tế" />
          </Form.Item>
          
          <Form.Item>
            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
              <Button onClick={() => {
                setEditModalOpen(false);
                setEditingItem(null);
                editForm.resetFields();
              }}>
                Hủy
              </Button>
              <Button type="primary" htmlType="submit" loading={editLoading}>
                Lưu thay đổi
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
