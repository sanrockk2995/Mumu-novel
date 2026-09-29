import { useState, useEffect } from 'react';
import { Button, Table, Modal, Form, Input, Tag, Space, message, Popconfirm, Card, theme, Empty, Badge, Tooltip, Select } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, ReloadOutlined, ThunderboltOutlined, FileTextOutlined } from '@ant-design/icons';

const { TextArea } = Input;

interface SkillItem {
  template_key: string;
  name: string;
  template_name: string;
  display_name: string;
  category: string;
  description: string;
  triggers: string[];
}

interface SkillDetail {
  template_key: string;
  name: string;
  template_name: string;
  display_name: string;
  category: string;
  description: string;
  triggers: string[];
  body: string;
  raw_content: string;
  standalone_references: Record<string, string>;
}

const SKILL_CATEGORY_OPTIONS = [
  { label: 'Skill·长篇', value: 'Skill·长篇' },
  { label: 'Skill·短篇', value: 'Skill·短篇' },
  { label: 'Skill·润色', value: 'Skill·润色' },
  { label: 'Skill·工具', value: 'Skill·工具' },
  { label: 'Skill', value: 'Skill' },
];

const parseTriggers = (value: string): string[] => (
  (value || '')
    .split(/[\n,，、]+/)
    .map(item => item.trim())
    .filter(Boolean)
    .filter((item, index, array) => array.indexOf(item) === index)
);

const formatTriggers = (triggers: string[]) => (triggers || []).join('\n');

const normalizeCategory = (value: string | string[]) => (
  Array.isArray(value) ? (value[0] || '').trim() : (value || '').trim()
);

export default function SkillManage() {
  const { token } = theme.useToken();
  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [editingSkill, setEditingSkill] = useState<SkillDetail | null>(null);
  const [editForm] = Form.useForm();
  const [createForm] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [viewModalVisible, setViewModalVisible] = useState(false);
  const [viewingContent, setViewingContent] = useState('');

  // Tải danh sách Skill
  const loadSkills = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/skills/list');
      if (response.ok) {
        const data = await response.json();
        setSkills(data);
      }
    } catch {
      message.error('Tải danh sách Skill thất bại');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSkills();
  }, []);

  // Mở popup chỉnh sửa
  const handleEdit = async (skill: SkillItem) => {
    try {
      const response = await fetch(`/api/skills/detail/${skill.template_key}`);
      if (response.ok) {
        const detail: SkillDetail = await response.json();
        setEditingSkill(detail);
        editForm.setFieldsValue({
          name: detail.name,
          display_name: detail.display_name || detail.template_name,
          category: detail.category,
          description: detail.description,
          triggers: formatTriggers(detail.triggers),
          body: detail.body,
          references: JSON.stringify(detail.standalone_references, null, 2),
        });
        setEditModalVisible(true);
      } else {
        message.error('Lấy chi tiết Skill thất bại');
      }
    } catch {
      message.error('Lấy chi tiết Skill thất bại');
    }
  };

  // Mở popup xem nội dung gốc
  const handleViewRaw = async (skill: SkillItem) => {
    try {
      const response = await fetch(`/api/skills/detail/${skill.template_key}`);
      if (response.ok) {
        const detail: SkillDetail = await response.json();
        setViewingContent(detail.raw_content);
        setViewModalVisible(true);
      }
    } catch {
      message.error('Lấy nội dung thất bại');
    }
  };

  // Lưu chỉnh sửa
  const handleSaveEdit = async () => {
    if (!editingSkill) return;
    const values = await editForm.validateFields();
    setSaving(true);
    try {
      // Phân tích references JSON
      let refs: Record<string, string> | undefined;
      if (values.references?.trim()) {
        try {
          refs = JSON.parse(values.references);
        } catch {
          message.error('Định dạng JSON tài liệu tham khảo không đúng');
          setSaving(false);
          return;
        }
      }

      const triggers = parseTriggers(values.triggers);
      if (triggers.length === 0) {
        message.error('Vui lòng điền ít nhất một từ kích hoạt');
        setSaving(false);
        return;
      }
      const category = normalizeCategory(values.category);
      if (!category) {
        message.error('Vui lòng chọn hoặc nhập phân loại');
        setSaving(false);
        return;
      }

      const response = await fetch(`/api/skills/update/${editingSkill.template_key}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          display_name: values.display_name,
          category,
          description: values.description,
          triggers,
          body: values.body,
          references: refs,
        }),
      });

      if (response.ok) {
        message.success('Cập nhật Skill thành công');
        setEditModalVisible(false);
        loadSkills();
      } else {
        const err = await response.json();
        message.error(err.detail || 'Cập nhật thất bại');
      }
    } catch {
      message.error('Lưu thất bại');
    } finally {
      setSaving(false);
    }
  };

  // Tạo Skill mới
  const handleCreate = async () => {
    const values = await createForm.validateFields();
    setSaving(true);
    try {
      let refs: Record<string, string> | undefined;
      if (values.references?.trim()) {
        try {
          refs = JSON.parse(values.references);
        } catch {
          message.error('Định dạng JSON tài liệu tham khảo không đúng');
          setSaving(false);
          return;
        }
      }

      const triggers = parseTriggers(values.triggers);
      if (triggers.length === 0) {
        message.error('Vui lòng điền ít nhất một từ kích hoạt');
        setSaving(false);
        return;
      }
      const category = normalizeCategory(values.category);
      if (!category) {
        message.error('Vui lòng chọn hoặc nhập phân loại');
        setSaving(false);
        return;
      }

      const response = await fetch('/api/skills/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: values.name,
          display_name: values.display_name,
          category,
          description: values.description,
          triggers,
          body: values.body,
          references: refs,
        }),
      });

      if (response.ok) {
        message.success('Tạo Skill thành công');
        setCreateModalVisible(false);
        createForm.resetFields();
        loadSkills();
      } else {
        const err = await response.json();
        message.error(err.detail || 'Tạo thất bại');
      }
    } catch {
      message.error('Tạo thất bại');
    } finally {
      setSaving(false);
    }
  };

  // Xóa Skill
  const handleDelete = async (skillKey: string) => {
    try {
      const response = await fetch(`/api/skills/delete/${skillKey}`, { method: 'DELETE' });
      if (response.ok) {
        message.success('Xóa thành công');
        loadSkills();
      } else {
        const err = await response.json();
        message.error(err.detail || 'Xóa thất bại');
      }
    } catch {
      message.error('Xóa thất bại');
    }
  };

  const columns = [
    {
      title: 'Tên',
      dataIndex: 'display_name',
      key: 'display_name',
      width: 220,
      ellipsis: true,
      render: (text: string, record: SkillItem) => (
        <div style={{ minWidth: 0 }}>
          <Tooltip title={text}>
            <strong style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{text}</strong>
          </Tooltip>
          <Tooltip title={record.name || record.template_key}>
            <span style={{ display: 'block', marginTop: 2, color: token.colorTextTertiary, fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {record.name || record.template_key}
            </span>
          </Tooltip>
        </div>
      ),
    },
    {
      title: 'Phân loại',
      dataIndex: 'category',
      key: 'category',
      width: 120,
      render: (cat: string) => {
        const colorMap: Record<string, string> = {
          'Skill·长篇': 'blue',
          'Skill·短篇': 'green',
          'Skill·润色': 'orange',
          'Skill·工具': 'purple',
          'Skill': 'default',
        };
        return <Tag color={colorMap[cat] || 'default'}>{cat}</Tag>;
      },
    },
    {
      title: 'Mô tả',
      dataIndex: 'description',
      key: 'description',
      width: 260,
      ellipsis: true,
      render: (text: string) => (
        <Tooltip title={text}>
          <span
            style={{
              display: 'block',
              maxWidth: 240,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              color: token.colorTextSecondary,
              fontSize: 13,
            }}
          >
            {text}
          </span>
        </Tooltip>
      ),
    },
    {
      title: 'Từ kích hoạt',
      dataIndex: 'triggers',
      key: 'triggers',
      width: 180,
      render: (triggers: string[]) => (
        <Space wrap size={4}>
          {triggers.slice(0, 3).map((t, i) => (
            <Tag key={i} style={{ fontSize: 11 }}>{t}</Tag>
          ))}
          {triggers.length > 3 && <Tag>+{triggers.length - 3}</Tag>}
        </Space>
      ),
    },
    {
      title: 'Thao tác',
      key: 'actions',
      width: 200,
      render: (_: unknown, record: SkillItem) => (
        <Space>
          <Button
            type="text"
            icon={<FileTextOutlined />}
            onClick={() => handleViewRaw(record)}
            size="small"
          >
            Xem
          </Button>
          <Button
            type="text"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
            size="small"
          >
            Chỉnh sửa
          </Button>
          <Popconfirm
            title="Bạn có chắc muốn xóa Skill này không?"
            description="Sau khi xóa không thể khôi phục, các file liên quan sẽ bị xóa vĩnh viễn."
            onConfirm={() => handleDelete(record.template_key)}
            okText="Xóa"
            cancelText="Hủy"
            okButtonProps={{ danger: true }}
          >
            <Button type="text" danger icon={<DeleteOutlined />} size="small">
              Xóa
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Thanh tiêu đề trên cùng */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 16,
        flexWrap: 'wrap',
        gap: 12,
      }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20 }}>
            <ThunderboltOutlined style={{ marginRight: 8, color: token.colorPrimary }} />
            Quản lý Skill
            <Badge count={skills.length} style={{ marginLeft: 8, backgroundColor: token.colorPrimary }} />
          </h2>
          <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
            Quản lý trực tuyến quy trình Skill: thêm, sửa hoặc xóa
          </div>
        </div>
        <Space wrap>
          <Button
            icon={<ReloadOutlined />}
            onClick={loadSkills}
            loading={loading}
          >
            Làm mới
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              createForm.resetFields();
              setCreateModalVisible(true);
            }}
          >
            Thêm Skill
          </Button>
        </Space>
      </div>

      {/* Danh sách Skill */}
      {skills.length === 0 && !loading ? (
        <Card>
          <Empty description="Chưa có Skill, bấm “Thêm Skill” để tạo">
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalVisible(true)}>
              Thêm Skill
            </Button>
          </Empty>
        </Card>
      ) : (
        <div style={{ flex: 1, overflowY: 'auto' }}>
          <Table
            dataSource={skills}
            columns={columns}
            rowKey="template_key"
            loading={loading}
            pagination={false}
            size="middle"
            style={{ background: token.colorBgContainer }}
          />
        </div>
      )}

      {/* Popup xem nội dung gốc */}
      <Modal
        title="Nội dung gốc SKILL.md"
        open={viewModalVisible}
        onCancel={() => setViewModalVisible(false)}
        width={800}
        footer={<Button onClick={() => setViewModalVisible(false)}>Đóng</Button>}
        styles={{ body: { maxHeight: '60vh', overflowY: 'auto' } }}
      >
        <pre style={{
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          fontSize: 13,
          lineHeight: 1.6,
          background: token.colorFillQuaternary,
          padding: 16,
          borderRadius: 8,
        }}>
          {viewingContent}
        </pre>
      </Modal>

      {/* Popup chỉnh sửa Skill */}
      <Modal
        title="Chỉnh sửa Skill"
        open={editModalVisible}
        onCancel={() => setEditModalVisible(false)}
        width={900}
        footer={
          <Space>
            <Button onClick={() => setEditModalVisible(false)}>Hủy</Button>
            <Button type="primary" onClick={handleSaveEdit} loading={saving}>Lưu</Button>
          </Space>
        }
        styles={{ body: { maxHeight: '70vh', overflowY: 'auto' } }}
        destroyOnClose
      >
        <Form form={editForm} layout="vertical">
          <Form.Item label="Định danh nội bộ" name="name" tooltip="Lấy từ trường name của SKILL.md, không hỗ trợ sửa khi đang chỉnh sửa">
            <Input disabled />
          </Form.Item>
          <Form.Item label="Tên hiển thị" name="display_name" rules={[{ required: true, whitespace: true, message: 'Vui lòng nhập tên hiển thị' }]}
            tooltip="Tên hiển thị trong bảng và hộp công cụ">
            <Input placeholder="VD: phân tích truyện mạng dài" maxLength={60} />
          </Form.Item>
          <Form.Item label="Phân loại" name="category" rules={[{ required: true, message: 'Vui lòng chọn phân loại' }]}
            tooltip="Phân loại Skill hiển thị trong bảng và hộp công cụ">
            <Select
              showSearch
              options={SKILL_CATEGORY_OPTIONS}
              placeholder="Vui lòng chọn hoặc nhập phân loại"
              mode="tags"
              maxCount={1}
              tokenSeparators={[',', '，', '、']}
            />
          </Form.Item>
          <Form.Item label="Mô tả" name="description" rules={[{ required: true, whitespace: true, message: 'Vui lòng nhập mô tả' }]}
            tooltip="Dùng để giải thích mục đích của Skill, không còn đảm nhận cấu hình tên và từ kích hoạt">
            <TextArea rows={4} placeholder="Mô tả ngắn gọn chức năng, tình huống áp dụng và cách dùng của Skill..." />
          </Form.Item>
          <Form.Item label="Từ kích hoạt" name="triggers" rules={[{ required: true, whitespace: true, message: 'Vui lòng điền ít nhất một từ kích hoạt' }]}
            tooltip="Mỗi dòng một từ kích hoạt, cũng hỗ trợ phân tách bằng dấu phẩy. Nên bao gồm /skill-name">
            <TextArea rows={4} placeholder={'/story-long-analyze\n/长篇拆文\ngiúp tôi phân tích cuốn sách này'} />
          </Form.Item>
          <Form.Item label="Chỉ dẫn quy trình" name="body" rules={[{ required: true, message: 'Vui lòng nhập chỉ dẫn quy trình' }]}
            tooltip="Phần Markdown chính trong SKILL.md sau YAML frontmatter">
            <TextArea rows={15} placeholder="Nhập chỉ dẫn quy trình đầy đủ của Skill..." style={{ fontFamily: 'monospace', fontSize: 13 }} />
          </Form.Item>
          <Form.Item label="Tài liệu tham khảo (JSON)" name="references"
            tooltip='Định dạng: {"文件名": "内容"}. Để trống sẽ giữ nguyên tài liệu tham khảo cũ'>
            <TextArea rows={8} placeholder='{"anti-ai-tips": "mẹo khử mùi AI...", "quality-check": "danh sách kiểm tra chất lượng..."}' style={{ fontFamily: 'monospace', fontSize: 12 }} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Popup tạo Skill */}
      <Modal
        title="Thêm Skill mới"
        open={createModalVisible}
        onCancel={() => setCreateModalVisible(false)}
        width={900}
        footer={
          <Space>
            <Button onClick={() => setCreateModalVisible(false)}>Hủy</Button>
            <Button type="primary" onClick={handleCreate} loading={saving}>Tạo</Button>
          </Space>
        }
        styles={{ body: { maxHeight: '70vh', overflowY: 'auto' } }}
        destroyOnClose
      >
        <Form form={createForm} layout="vertical">
          <Form.Item label="Tên Skill (tiếng Anh)" name="name" rules={[{ required: true, message: 'Vui lòng nhập tên' }]}
            tooltip="Chữ thường tiếng Anh + dấu gạch ngang, VD: my-new-skill. Sẽ được dùng làm tên thư mục và định danh nội bộ">
            <Input placeholder="my-new-skill" />
          </Form.Item>
          <Form.Item label="Tên hiển thị" name="display_name" rules={[{ required: true, whitespace: true, message: 'Vui lòng nhập tên hiển thị' }]}
            tooltip="Tên hiển thị trong bảng và hộp công cụ">
            <Input placeholder="VD: Skill mới của tôi" maxLength={60} />
          </Form.Item>
          <Form.Item label="Phân loại" name="category" rules={[{ required: true, message: 'Vui lòng chọn phân loại' }]}
            tooltip="Phân loại Skill hiển thị trong bảng và hộp công cụ">
            <Select
              showSearch
              options={SKILL_CATEGORY_OPTIONS}
              placeholder="Vui lòng chọn hoặc nhập phân loại"
              mode="tags"
              maxCount={1}
              tokenSeparators={[',', '，', '、']}
            />
          </Form.Item>
          <Form.Item label="Mô tả" name="description" rules={[{ required: true, whitespace: true, message: 'Vui lòng nhập mô tả' }]}
            tooltip="Dùng để giải thích mục đích của Skill, không còn đảm nhận cấu hình tên và từ kích hoạt">
            <TextArea rows={4} placeholder="Mô tả ngắn gọn chức năng, tình huống áp dụng và cách dùng của Skill..." />
          </Form.Item>
          <Form.Item label="Từ kích hoạt" name="triggers" rules={[{ required: true, whitespace: true, message: 'Vui lòng điền ít nhất một từ kích hoạt' }]}
            tooltip="Mỗi dòng một từ kích hoạt, cũng hỗ trợ phân tách bằng dấu phẩy. Nên bao gồm /skill-name">
            <TextArea rows={4} placeholder={'/my-new-skill\nSkill mới của tôi'} />
          </Form.Item>
          <Form.Item label="Chỉ dẫn quy trình" name="body" rules={[{ required: true, message: 'Vui lòng nhập chỉ dẫn quy trình' }]}
            tooltip="Nội dung Markdown cốt lõi của Skill">
            <TextArea rows={15} placeholder={"# my-new-skill: Tiêu đề Skill\n\nBạn là chuyên gia xxx. Nhiệm vụ của bạn là giúp người dùng hoàn thành xxx.\n\n## Nguyên tắc cốt lõi\n\n- Nguyên tắc 1...\n\n## Quy trình làm việc\n\n### Phase 1: Xác nhận nhu cầu\n..."} style={{ fontFamily: 'monospace', fontSize: 13 }} />
          </Form.Item>
          <Form.Item label="Tài liệu tham khảo (JSON, tùy chọn)" name="references"
            tooltip='Định dạng: {"文件名": "内容"}'>
            <TextArea rows={8} placeholder='{"tips": "mẹo tham khảo...", "examples": "ví dụ..."}' style={{ fontFamily: 'monospace', fontSize: 12 }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
