import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Table,
  Button,
  Modal,
  Form,
  Input,
  Switch,
  Space,
  Tag,
  Popconfirm,
  message,
  Card,
  Typography,
  Badge,
  InputNumber,
  Row,
  Col,
  Pagination,
  Dropdown,
  theme,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  KeyOutlined,
  StopOutlined,
  CheckCircleOutlined,
  ArrowLeftOutlined,
  TeamOutlined,
  UserOutlined,
  SearchOutlined,
  MoreOutlined,
} from '@ant-design/icons';
import { adminApi } from '../services/api';
import type { User } from '../types';
import UserMenu from '../components/UserMenu';

const { Title, Text } = Typography;

interface UserWithStatus extends User {
  is_active?: boolean;
}

type SortField =
  | 'username'
  | 'display_name'
  | 'is_active'
  | 'is_admin'
  | 'trust_level'
  | 'created_at'
  | 'last_login';

type SortOrder = 'ascend' | 'descend' | null;

export default function UserManagement() {
  const navigate = useNavigate();
  const [users, setUsers] = useState<UserWithStatus[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [resetPasswordModalVisible, setResetPasswordModalVisible] = useState(false);
  const [currentUser, setCurrentUser] = useState<UserWithStatus | null>(null);
  const [newPassword, setNewPassword] = useState('');
  const [pageSize, setPageSize] = useState(20);
  const [currentPage, setCurrentPage] = useState(1);
  const [searchText, setSearchText] = useState('');
  const [sortField, setSortField] = useState<SortField | null>('created_at');
  const [sortOrder, setSortOrder] = useState<SortOrder>('descend');

  const [form] = Form.useForm();
  const [editForm] = Form.useForm();
  const [modal, contextHolder] = Modal.useModal();
  const { token } = theme.useToken();
  const alphaColor = (color: string, alpha: number) => `color-mix(in srgb, ${color} ${(alpha * 100).toFixed(0)}%, transparent)`;

  // Lọc danh sách người dùng
  const filteredUsers = users.filter(user => {
    if (!searchText) return true;
    const searchLower = searchText.toLowerCase();
    return (
      user.username?.toLowerCase().includes(searchLower) ||
      user.display_name?.toLowerCase().includes(searchLower) ||
      user.user_id?.toLowerCase().includes(searchLower)
    );
  });

  // Danh sách người dùng đã sắp xếp
  const sortedUsers = useMemo(() => {
    if (!sortField || !sortOrder) {
      return filteredUsers;
    }

    const compareValues = (
      a: string | number | boolean | null | undefined,
      b: string | number | boolean | null | undefined
    ) => {
      // Giá trị rỗng luôn xếp cuối
      if (a == null && b == null) return 0;
      if (a == null) return 1;
      if (b == null) return -1;

      if (typeof a === 'string' && typeof b === 'string') {
        return a.localeCompare(b, 'vi-VN');
      }

      if (typeof a === 'boolean' && typeof b === 'boolean') {
        return Number(a) - Number(b);
      }

      return Number(a) - Number(b);
    };

    const getSortValue = (user: UserWithStatus) => {
      switch (sortField) {
        case 'username':
          return user.username ?? null;
        case 'display_name':
          return user.display_name ?? null;
        case 'is_active':
          return user.is_active !== false;
        case 'is_admin':
          return user.is_admin;
        case 'trust_level':
          return user.trust_level ?? null;
        case 'created_at':
          return user.created_at ? new Date(user.created_at).getTime() : null;
        case 'last_login':
          return user.last_login ? new Date(user.last_login).getTime() : null;
        default:
          return null;
      }
    };

    const sorted = [...filteredUsers].sort((a, b) => {
      const result = compareValues(getSortValue(a), getSortValue(b));
      return sortOrder === 'ascend' ? result : -result;
    });

    return sorted;
  }, [filteredUsers, sortField, sortOrder]);

  // Tải danh sách người dùng
  const loadUsers = async () => {
    setLoading(true);
    try {
      const res = await adminApi.getUsers();
      setUsers(res.users);
    } catch (error) {
      console.error('Tải danh sách người dùng thất bại:', error);
      message.error('Tải danh sách người dùng thất bại');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  // Thêm người dùng
  interface CreateUserValues {
    username: string;
    display_name: string;
    password?: string;
    avatar_url?: string;
    trust_level?: number;
    is_admin?: boolean;
  }

  const handleCreate = async (values: CreateUserValues) => {
    try {
      const res = await adminApi.createUser(values);
      message.success('Tạo người dùng thành công');

      // Nếu có mật khẩu mặc định, hiển thị cho quản trị viên
      if (res.default_password) {
        modal.info({
          title: 'Tạo người dùng thành công',
          content: (
            <div>
              <p>Tên đăng nhập:<Text strong>{values.username}</Text></p>
              <p>Mật khẩu ban đầu:<Text strong copyable>{res.default_password}</Text></p>
              <p style={{ color: token.colorError, marginTop: 16 }}>
                ⚠️ Vui lòng sao chép mật khẩu và thông báo cho người dùng, mật khẩu này chỉ hiển thị một lần!
              </p>
            </div>
          ),
          width: 500,
          centered: true,
        });
      }

      setModalVisible(false);
      form.resetFields();
      loadUsers();
    } catch (error) {
      console.error('Tạo người dùng thất bại:', error);
      message.error('Tạo người dùng thất bại');
    }
  };

  // Chỉnh sửa người dùng
  const handleEdit = (user: UserWithStatus) => {
    setCurrentUser(user);
    editForm.setFieldsValue({
      display_name: user.display_name,
      avatar_url: user.avatar_url,
      trust_level: user.trust_level,
      is_admin: user.is_admin,
    });
    setEditModalVisible(true);
  };

  interface UpdateUserValues {
    display_name: string;
    avatar_url?: string;
    trust_level?: number;
    is_admin?: boolean;
  }

  const handleUpdate = async (values: UpdateUserValues) => {
    if (!currentUser) return;

    try {
      await adminApi.updateUser(currentUser.user_id, values);
      message.success('Cập nhật thông tin người dùng thành công');
      setEditModalVisible(false);
      editForm.resetFields();
      loadUsers();
    } catch (error) {
      console.error('Cập nhật người dùng thất bại:', error);
      message.error('Cập nhật người dùng thất bại');
    }
  };

  // Chuyển đổi trạng thái người dùng
  const handleToggleStatus = async (user: UserWithStatus) => {
    const isActive = user.is_active !== false;
    const action = isActive ? 'vô hiệu hóa' : 'kích hoạt';

    try {
      await adminApi.toggleUserStatus(user.user_id, !isActive);
      message.success(`Người dùng đã được ${action}`);
      loadUsers();
    } catch (error) {
      console.error(`${action}người dùng thất bại:`, error);
      message.error(`${action}người dùng thất bại`);
    }
  };

  // Đặt lại mật khẩu
  const handleResetPassword = (user: UserWithStatus) => {
    setCurrentUser(user);
    setNewPassword('');
    setResetPasswordModalVisible(true);
  };

  const handleResetPasswordConfirm = async () => {
    if (!currentUser) return;

    try {
      const res = await adminApi.resetPassword(
        currentUser.user_id,
        newPassword || undefined
      );

      modal.info({
        title: 'Đặt lại mật khẩu thành công',
        content: (
          <div>
            <p>Người dùng:<Text strong>{currentUser.username}</Text></p>
            <p>Mật khẩu mới:<Text strong copyable>{res.new_password}</Text></p>
            <p style={{ color: token.colorError, marginTop: 16 }}>
              ⚠️ Vui lòng sao chép mật khẩu và thông báo cho người dùng!
            </p>
          </div>
        ),
        width: 500,
        centered: true,
      });

      setResetPasswordModalVisible(false);
      setNewPassword('');
    } catch (error) {
      console.error('Đặt lại mật khẩu thất bại:', error);
      message.error('Đặt lại mật khẩu thất bại');
    }
  };

  // Xóa người dùng
  const handleDelete = async (user: UserWithStatus) => {
    try {
      await adminApi.deleteUser(user.user_id);
      message.success('Đã xóa người dùng');
      loadUsers();
    } catch (error) {
      console.error('Xóa người dùng thất bại:', error);
      message.error('Xóa người dùng thất bại');
    }
  };

  const isMobile = window.innerWidth <= 768;

  // Định nghĩa cột bảng
  const columns = [
    {
      title: 'Tên đăng nhập',
      dataIndex: 'username',
      key: 'username',
      width: 150,
      sorter: true,
      sortOrder: sortField === 'username' ? sortOrder : null,
      render: (text: string) => (
        <Space>
          <UserOutlined style={{ color: token.colorPrimary }} />
          <Text strong>{text}</Text>
        </Space>
      ),
    },
    {
      title: 'Tên hiển thị',
      dataIndex: 'display_name',
      key: 'display_name',
      width: 150,
      sorter: true,
      sortOrder: sortField === 'display_name' ? sortOrder : null,
    },
    {
      title: 'Trạng thái',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 100,
      sorter: true,
      sortOrder: sortField === 'is_active' ? sortOrder : null,
      render: (isActive: boolean) => (
        <Badge
          status={isActive !== false ? 'success' : 'error'}
          text={isActive !== false ? 'Bình thường' : 'Đã vô hiệu hóa'}
        />
      ),
    },
    {
      title: 'Vai trò',
      dataIndex: 'is_admin',
      key: 'is_admin',
      width: 100,
      sorter: true,
      sortOrder: sortField === 'is_admin' ? sortOrder : null,
      render: (isAdmin: boolean) => (
        <Tag color={isAdmin ? 'gold' : 'blue'}>
          {isAdmin ? '👑 Quản trị viên' : 'Người dùng thường'}
        </Tag>
      ),
    },
    {
      title: 'Cấp độ tin cậy',
      dataIndex: 'trust_level',
      key: 'trust_level',
      width: 100,
      sorter: true,
      sortOrder: sortField === 'trust_level' ? sortOrder : null,
      render: (level: number) => (
        <Tag color={level === -1 ? 'default' : level >= 5 ? 'green' : 'blue'}>
          {level === -1 ? 'Đã vô hiệu hóa' : `Level ${level}`}
        </Tag>
      ),
    },
    {
      title: 'Thời gian tạo',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      sorter: true,
      sortOrder: sortField === 'created_at' ? sortOrder : null,
      render: (date: string) => date ? new Date(date).toLocaleString('vi-VN') : '-',
    },
    {
      title: 'Lần đăng nhập cuối',
      dataIndex: 'last_login',
      key: 'last_login',
      width: 180,
      sorter: true,
      sortOrder: sortField === 'last_login' ? sortOrder : null,
      render: (date: string) => date ? new Date(date).toLocaleString('vi-VN') : 'Chưa từng đăng nhập',
    },
    {
      title: 'Thao tác',
      key: 'action',
      width: isMobile ? 80 : 300,
      fixed: 'right' as const,
      render: (_: unknown, record: UserWithStatus) => {
        const isActive = record.is_active !== false;

        // Di động: dùng menu thả xuống
        if (isMobile) {
          const menuItems = [
            {
              key: 'edit',
              label: 'Chỉnh sửa người dùng',
              icon: <EditOutlined />,
              onClick: () => handleEdit(record),
            },
            {
              key: 'reset',
              label: 'Đặt lại mật khẩu',
              icon: <KeyOutlined />,
              onClick: () => handleResetPassword(record),
            },
            {
              key: 'toggle',
              label: isActive ? 'Vô hiệu hóa người dùng' : 'Kích hoạt người dùng',
              icon: isActive ? <StopOutlined /> : <CheckCircleOutlined />,
              danger: isActive,
              onClick: () => {
                modal.confirm({
                  title: `Bạn có chắc muốn ${isActive ? 'vô hiệu hóa' : 'kích hoạt'} người dùng này không?`,
                  onOk: () => handleToggleStatus(record),
                  okText: 'Bạn có chắc muốn ',
                  cancelText: 'Hủy',
                });
              },
            },
            ...(!record.is_admin ? [{
              key: 'delete',
              label: 'Xóa người dùng',
              icon: <DeleteOutlined />,
              danger: true,
              onClick: () => {
                modal.confirm({
                  title: 'Bạn có chắc muốn xóa người dùng này không? Hành động này không thể hoàn tác!',
                  onOk: () => handleDelete(record),
                  okText: 'Bạn có chắc muốn ',
                  cancelText: 'Hủy',
                  okButtonProps: { danger: true },
                });
              },
            }] : []),
          ];

          return (
            <Dropdown menu={{ items: menuItems }} trigger={['click']}>
              <Button type="text" icon={<MoreOutlined />} />
            </Dropdown>
          );
        }

        // Desktop: giữ nguyên kiểu nút
        return (
          <Space size="small">
            <Button
              type="link"
              size="small"
              icon={<EditOutlined />}
              onClick={() => handleEdit(record)}
            >
              Chỉnh sửa
            </Button>

            <Button
              type="link"
              size="small"
              icon={<KeyOutlined />}
              onClick={() => handleResetPassword(record)}
            >
              Đặt lại mật khẩu
            </Button>

            <Popconfirm
              title={`Bạn có chắc muốn ${isActive ? 'vô hiệu hóa' : 'kích hoạt'} người dùng này không?`}
              onConfirm={() => handleToggleStatus(record)}
              okText="Bạn có chắc muốn "
              cancelText="Hủy"
            >
              <Button
                type="link"
                size="small"
                danger={isActive}
                icon={isActive ? <StopOutlined /> : <CheckCircleOutlined />}
              >
                {isActive ? 'vô hiệu hóa' : 'kích hoạt'}
              </Button>
            </Popconfirm>

            {!record.is_admin && (
              <Popconfirm
                title="Bạn có chắc muốn xóa người dùng này không? Hành động này không thể hoàn tác!"
                onConfirm={() => handleDelete(record)}
                okText="Bạn có chắc muốn "
                cancelText="Hủy"
                okButtonProps={{ danger: true }}
              >
                <Button
                  type="link"
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                >
                  Xóa
                </Button>
              </Popconfirm>
            )}
          </Space>
        );
      },
    },
  ];

  return (
    <div style={{
      height: '100vh',
      background: `linear-gradient(180deg, ${token.colorBgLayout} 0%, ${alphaColor(token.colorPrimary, 0.08)} 100%)`,
      padding: isMobile ? '20px 16px' : '40px 24px',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
    }}>
      {contextHolder}
      <div style={{
        maxWidth: 1400,
        margin: '0 auto',
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}>
        {/* Thẻ điều hướng trên cùng */}
        <Card
          variant="borderless"
          style={{
            background: `linear-gradient(135deg, ${token.colorPrimary} 0%, ${alphaColor(token.colorPrimary, 0.8)} 50%, ${token.colorPrimaryHover} 100%)`,
            borderRadius: isMobile ? 16 : 24,
            boxShadow: `0 12px 40px ${alphaColor(token.colorPrimary, 0.25)}, 0 4px 12px ${alphaColor(token.colorText, 0.08)}`,
            marginBottom: isMobile ? 20 : 24,
            border: 'none',
            position: 'relative',
            overflow: 'hidden'
          }}
        >
          {/* Phần tử nền trang trí */}
          <div style={{ position: 'absolute', top: -60, right: -60, width: 200, height: 200, borderRadius: '50%', background: alphaColor(token.colorWhite, 0.08), pointerEvents: 'none' }} />
          <div style={{ position: 'absolute', bottom: -40, left: '30%', width: 120, height: 120, borderRadius: '50%', background: alphaColor(token.colorWhite, 0.05), pointerEvents: 'none' }} />
          <div style={{ position: 'absolute', top: '50%', right: '15%', width: 80, height: 80, borderRadius: '50%', background: alphaColor(token.colorWhite, 0.06), pointerEvents: 'none' }} />

          <Row align="middle" justify="space-between" gutter={[16, 16]} style={{ position: 'relative', zIndex: 1 }}>
            <Col xs={24} sm={12}>
              <Space direction="vertical" size={4}>
                <Title level={isMobile ? 3 : 2} style={{ margin: 0, color: token.colorWhite, textShadow: `0 2px 4px ${alphaColor(token.colorText, 0.2)}` }}>
                  <TeamOutlined style={{ color: alphaColor(token.colorWhite, 0.9), marginRight: 12 }} />
                  Quản lý người dùng
                </Title>
                <Text style={{ fontSize: isMobile ? 12 : 14, color: alphaColor(token.colorWhite, 0.85) }}>
                  Quản lý người dùng và quyền trong hệ thống
                </Text>
              </Space>
            </Col>
            <Col xs={24} sm={12}>
              <Space size={12} style={{ display: 'flex', justifyContent: isMobile ? 'flex-start' : 'flex-end', width: '100%' }}>
                <Button
                  icon={<ArrowLeftOutlined />}
                  onClick={() => navigate('/')}
                  style={{
                    borderRadius: 12,
                    background: alphaColor(token.colorWhite, 0.15),
                    border: `1px solid ${alphaColor(token.colorWhite, 0.3)}`,
                    boxShadow: `0 2px 8px ${alphaColor(token.colorText, 0.15)}`,
                    color: token.colorWhite,
                    backdropFilter: 'blur(10px)',
                    transition: 'all 0.3s ease'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = alphaColor(token.colorWhite, 0.25);
                    e.currentTarget.style.transform = 'translateY(-1px)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = alphaColor(token.colorWhite, 0.15);
                    e.currentTarget.style.transform = 'none';
                  }}
                >
                  Về trang chủ
                </Button>
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => setModalVisible(true)}
                  style={{
                    borderRadius: 12,
                    background: alphaColor(token.colorWarning, 0.95),
                    border: `1px solid ${alphaColor(token.colorWhite, 0.3)}`,
                    boxShadow: `0 4px 16px ${alphaColor(token.colorWarning, 0.4)}`,
                    color: token.colorWhite,
                    fontWeight: 600
                  }}
                >
                  Thêm người dùng
                </Button>
                <UserMenu />
              </Space>
            </Col>
          </Row>
        </Card>

        {/* Thẻ nội dung chính */}
        <Card
          variant="borderless"
          style={{
            background: alphaColor(token.colorBgContainer, 0.72),
            borderRadius: isMobile ? 16 : 24,
            border: `1px solid ${alphaColor(token.colorWhite, 0.45)}`,
            backdropFilter: 'blur(20px)',
            boxShadow: `0 4px 24px ${alphaColor(token.colorText, 0.06)}`,
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
          }}
          bodyStyle={{
            padding: 0,
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
          }}
        >
          {/* Thanh tìm kiếm */}
          <div style={{
            padding: '16px 24px 0 24px',
            borderBottom: `1px solid ${alphaColor(token.colorText, 0.06)}`,
          }}>
            <Input
              placeholder="Tìm kiếm tên đăng nhập, tên hiển thị hoặc ID người dùng"
              prefix={<SearchOutlined style={{ color: token.colorTextTertiary }} />}
              value={searchText}
              onChange={(e) => {
                setSearchText(e.target.value);
                setCurrentPage(1); // Khi tìm kiếm đặt lại về trang đầu
              }}
              allowClear
              style={{
                borderRadius: 8,
              }}
            />
          </div>

          {/* Khu vực bảng */}
          <div style={{
            flex: 1,
            overflow: 'auto',
            padding: '16px 24px 0 24px',
          }}>
            <Table
              columns={columns}
              dataSource={sortedUsers.slice((currentPage - 1) * pageSize, currentPage * pageSize)}
              rowKey="user_id"
              loading={loading}
              scroll={{
                x: 1400,
                y: 'calc(100vh - 410px)'
              }}
              pagination={false}
              onChange={(_pagination, _filters, sorter) => {
                const currentSorter = Array.isArray(sorter) ? sorter[0] : sorter;
                setCurrentPage(1);

                if (currentSorter && currentSorter.field && currentSorter.order) {
                  setSortField(currentSorter.field as SortField);
                  setSortOrder(currentSorter.order as SortOrder);
                } else {
                  setSortField(null);
                  setSortOrder(null);
                }
              }}
            />
          </div>

          {/* Điều khiển phân trang cố định */}
          <div style={{
            padding: '16px 24px 24px 24px',
            borderTop: `1px solid ${alphaColor(token.colorText, 0.06)}`,
            background: 'transparent',
            display: 'flex',
            justifyContent: 'center',
          }}>
            <Pagination
              current={currentPage}
              pageSize={pageSize}
              total={filteredUsers.length}
              showSizeChanger
              showTotal={(total) => `Tổng ${total} người dùng${searchText ? ' (đã lọc)' : ''}`}
              pageSizeOptions={[20, 50, 100]}
              onChange={(page, size) => {
                setCurrentPage(page);
                setPageSize(size);
              }}
              onShowSizeChange={(_current, size) => {
                setCurrentPage(1);
                setPageSize(size);
              }}
            />
          </div>
        </Card>
      </div>

      {/* Hộp thoại thêm người dùng */}
      <Modal
        title={<span><PlusOutlined style={{ marginRight: 8 }} />Thêm người dùng</span>}
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false);
          form.resetFields();
        }}
        onOk={() => form.submit()}
        width={isMobile ? '90%' : 600}
        centered
        okText="Tạo"
        cancelText="Hủy"
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleCreate}
        >
          <Form.Item
            label="Tên đăng nhập"
            name="username"
            rules={[
              { required: true, message: 'Vui lòng nhập tên đăng nhập' },
              { min: 3, max: 20, message: 'Độ dài tên đăng nhập 3-20 ký tự' },
              { pattern: /^[a-zA-Z0-9_]+$/, message: 'Chỉ được chứa chữ cái, số và dấu gạch dưới' },
            ]}
          >
            <Input placeholder="Vui lòng nhập tên đăng nhập" />
          </Form.Item>

          <Form.Item
            label="Tên hiển thị"
            name="display_name"
            rules={[
              { required: true, message: 'Vui lòng nhập tên hiển thị' },
              { min: 2, max: 50, message: 'Độ dài tên hiển thị 2-50 ký tự' },
            ]}
          >
            <Input placeholder="Vui lòng nhập tên hiển thị" />
          </Form.Item>

          <Form.Item
            label="Mật khẩu ban đầu"
            name="password"
            extra="Để trống để tự động tạo username@666"
            rules={[
              { min: 6, message: 'Mật khẩu dài ít nhất 6 ký tự' },
            ]}
          >
            <Input.Password placeholder="Để trống để tự động tạo" />
          </Form.Item>

          <Form.Item
            label="URL ảnh đại diện"
            name="avatar_url"
          >
            <Input placeholder="Vui lòng nhập URL ảnh đại diện (tùy chọn)" />
          </Form.Item>

          <Form.Item
            label="Cấp độ tin cậy"
            name="trust_level"
            initialValue={0}
          >
            <InputNumber min={0} max={9} style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item
            label="Đặt làm quản trị viên"
            name="is_admin"
            valuePropName="checked"
            initialValue={false}
          >
            <Switch
              size={isMobile ? 'small' : 'default'}
              style={{
                flexShrink: 0,
                height: isMobile ? 16 : 22,
                minHeight: isMobile ? 16 : 22,
                lineHeight: isMobile ? '16px' : '22px'
              }}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* Hộp thoại chỉnh sửa người dùng */}
      <Modal
        title={<span><EditOutlined style={{ marginRight: 8 }} />Chỉnh sửa người dùng</span>}
        open={editModalVisible}
        onCancel={() => {
          setEditModalVisible(false);
          editForm.resetFields();
        }}
        onOk={() => editForm.submit()}
        width={isMobile ? '90%' : 600}
        centered
        okText="Lưu"
        cancelText="Hủy"
      >
        <Form
          form={editForm}
          layout="vertical"
          onFinish={handleUpdate}
        >
          <Form.Item
            label="Tên hiển thị"
            name="display_name"
            rules={[
              { required: true, message: 'Vui lòng nhập tên hiển thị' },
              { min: 2, max: 50, message: 'Độ dài tên hiển thị 2-50 ký tự' },
            ]}
          >
            <Input placeholder="Vui lòng nhập tên hiển thị" />
          </Form.Item>

          <Form.Item
            label="URL ảnh đại diện"
            name="avatar_url"
          >
            <Input placeholder="Vui lòng nhập URL ảnh đại diện (tùy chọn)" />
          </Form.Item>

          <Form.Item
            label="Cấp độ tin cậy"
            name="trust_level"
          >
            <InputNumber min={0} max={9} style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item
            label="Đặt làm quản trị viên"
            name="is_admin"
            valuePropName="checked"
          >
            <Switch
              size={isMobile ? 'small' : 'default'}
              style={{
                flexShrink: 0,
                height: isMobile ? 16 : 22,
                minHeight: isMobile ? 16 : 22,
                lineHeight: isMobile ? '16px' : '22px'
              }}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* Hộp thoại đặt lại mật khẩu */}
      <Modal
        title={<span><KeyOutlined style={{ marginRight: 8 }} />Đặt lại mật khẩu</span>}
        open={resetPasswordModalVisible}
        onCancel={() => {
          setResetPasswordModalVisible(false);
          setNewPassword('');
        }}
        onOk={handleResetPasswordConfirm}
        width={isMobile ? '90%' : 500}
        centered
        okText="Xác nhận đặt lại"
        cancelText="Hủy"
      >
        <div style={{ marginBottom: 16 }}>
          <Text>Người dùng:<Text strong>{currentUser?.username}</Text></Text>
        </div>
        <Form layout="vertical">
          <Form.Item
            label="Mật khẩu mới"
            extra="Để trống để đặt lại thành mật khẩu mặc định username@666"
          >
            <Input.Password
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="Để trống để dùng mật khẩu mặc định"
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}