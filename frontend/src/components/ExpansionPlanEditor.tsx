import { Modal, Form, Input, InputNumber, Select, Tag, Space, Button, message, Divider } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { useState, useEffect, useCallback } from 'react';
import type { ExpansionPlanData, Character } from '../types';
import { characterApi } from '../services/api';

const { TextArea } = Input;

interface ExpansionPlanEditorProps {
  visible: boolean;
  planData: ExpansionPlanData | null;
  chapterSummary: string | null;
  projectId: string;
  onSave: (data: ExpansionPlanData & { summary?: string }) => Promise<void>;
  onCancel: () => void;
}

export default function ExpansionPlanEditor({
  visible,
  planData,
  chapterSummary,
  projectId,
  onSave,
  onCancel
}: ExpansionPlanEditorProps) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  
  // Nhập tag sự kiện then chốt
  const [keyEventInput, setKeyEventInput] = useState('');
  const [keyEvents, setKeyEvents] = useState<string[]>([]);
  
  // Danh sách và lựa chọn nhân vật
  const [availableCharacters, setAvailableCharacters] = useState<Character[]>([]);
  const [characters, setCharacters] = useState<string[]>([]);
  const [loadingCharacters, setLoadingCharacters] = useState(false);

  // Tải danh sách nhân vật của dự án
  const loadCharacters = useCallback(async () => {
    try {
      setLoadingCharacters(true);
      setAvailableCharacters([]); // Reset về mảng rỗng
      const response = await characterApi.getCharacters(projectId);
      console.log('Dữ liệu nhân vật đã tải:', response);
      
      // API trả về định dạng {total, items}, cần trích xuất items
      let chars: Character[] = [];
      if (Array.isArray(response)) {
        chars = response;
      } else if (response && typeof response === 'object' && 'items' in response) {
        const responseObj = response as { items?: Character[] };
        if (Array.isArray(responseObj.items)) {
          chars = responseObj.items;
        }
      } else {
        console.error('Định dạng trả về của API nhân vật bất thường:', response);
        message.warning('Định dạng dữ liệu nhân vật bất thường');
      }
      
      setAvailableCharacters(chars);
      console.log('Danh sách nhân vật đã đặt:', chars);
    } catch (error: unknown) {
      console.error('Tải danh sách nhân vật thất bại:', error);
      setAvailableCharacters([]);
      const err = error as Error;
      message.error('Tải danh sách nhân vật thất bại: ' + (err?.message || 'Lỗi không xác định'));
    } finally {
      setLoadingCharacters(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (visible && projectId) {
      loadCharacters();
    }
  }, [visible, projectId, loadCharacters]);

  // Cập nhật state khi planData hoặc chapterSummary thay đổi
  useEffect(() => {
    if (visible) {
      if (planData) {
        setKeyEvents(planData.key_events || []);
        setCharacters(planData.character_focus || []);
        form.setFieldsValue({
          summary: chapterSummary || '',
          emotional_tone: planData.emotional_tone,
          narrative_goal: planData.narrative_goal,
          conflict_type: planData.conflict_type,
          estimated_words: planData.estimated_words
        });
      } else {
        // Reset trạng thái
        setKeyEvents([]);
        setCharacters([]);
        form.setFieldsValue({
          summary: chapterSummary || ''
        });
      }
    }
  }, [planData, chapterSummary, form, visible]);

  const handleAddKeyEvent = () => {
    if (keyEventInput.trim()) {
      setKeyEvents([...keyEvents, keyEventInput.trim()]);
      setKeyEventInput('');
    }
  };

  const handleAddCharacter = (characterName: string) => {
    if (characterName && !characters.includes(characterName)) {
      setCharacters([...characters, characterName]);
    }
  };

  const handleSubmit = async () => {
    try {
      setLoading(true);
      const values = await form.validateFields();
      
      // Kiểm tra có ít nhất một sự kiện then chốt
      if (keyEvents.length === 0) {
        message.warning('Vui lòng thêm ít nhất một sự kiện then chốt');
        setLoading(false);
        return;
      }
      
      // Kiểm tra có ít nhất một nhân vật
      if (characters.length === 0) {
        message.warning('Vui lòng thêm ít nhất một nhân vật liên quan');
        setLoading(false);
        return;
      }
      
      const updatedPlan: ExpansionPlanData & { summary?: string } = {
        summary: values.summary,
        key_events: keyEvents,
        character_focus: characters,
        emotional_tone: values.emotional_tone,
        narrative_goal: values.narrative_goal,
        conflict_type: values.conflict_type,
        estimated_words: values.estimated_words,
        scenes: planData?.scenes || null
      };
      
      await onSave(updatedPlan);
      // message.success('Lưu thông tin quy hoạch thành công');
    } catch (error) {
      console.error('Lưu thất bại:', error);
      message.error('Lưu thất bại, vui lòng thử lại');
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    form.resetFields();
    setKeyEvents([]);
    setCharacters([]);
    setKeyEventInput('');
    onCancel();
  };

  return (
    <Modal
      title="Chỉnh sửa quy hoạch chương"
      open={visible}
      onCancel={handleCancel}
      width={700}
      centered
      footer={[
        <Button key="cancel" onClick={handleCancel} disabled={loading}>
          Hủy
        </Button>,
        <Button key="submit" type="primary" loading={loading} onClick={handleSubmit}>
          Lưu
        </Button>
      ]}
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          emotional_tone: 'Căng thẳng kịch tính',
          conflict_type: 'Xung đột nhân vật',
          estimated_words: 3000
        }}
      >
        {/* Tóm tắt cốt truyện */}
        <Form.Item
          label="Tóm tắt cốt truyện"
          name="summary"
          tooltip="Mô tả ngắn gọn cốt truyện chính và hướng phát triển của chương này"
        >
          <TextArea
            rows={3}
            placeholder="Mô tả ngắn gọn cốt truyện chính của chương này, VD: nhân vật chính gặp sự cố bất ngờ và bắt đầu một cuộc phiêu lưu mới..."
            maxLength={500}
            showCount
          />
        </Form.Item>

        <Divider orientation="left">Quy hoạch chi tiết</Divider>

        {/* Sự kiện then chốt */}
        <Form.Item
          label="Sự kiện then chốt"
          tooltip="Thêm ít nhất một sự kiện then chốt"
          required
        >
          <Space direction="vertical" style={{ width: '100%' }}>
            <Space.Compact style={{ width: '100%' }}>
              <Input
                placeholder="Nhập sự kiện then chốt rồi nhấn Enter hoặc bấm thêm"
                value={keyEventInput}
                onChange={(e) => setKeyEventInput(e.target.value)}
                onPressEnter={handleAddKeyEvent}
              />
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={handleAddKeyEvent}
              >
                Thêm
              </Button>
            </Space.Compact>
            <Space wrap>
              {keyEvents.map((event, idx) => (
                <Tag
                  key={idx}
                  closable
                  onClose={(e) => {
                    e.preventDefault();
                    setKeyEvents(keyEvents.filter((_, i) => i !== idx));
                  }}
                  color="purple"
                  style={{ marginBottom: 8 }}
                >
                  <span style={{ fontWeight: 'bold', marginRight: 4 }}>#{idx + 1}</span>
                  {event}
                </Tag>
              ))}
            </Space>
          </Space>
        </Form.Item>

        {/* Nhân vật liên quan */}
        <Form.Item
          label="Nhân vật liên quan"
          tooltip="Chọn từ các nhân vật hiện có của dự án"
          required
        >
          <Space direction="vertical" style={{ width: '100%' }}>
            <Select
              placeholder="Chọn nhân vật"
              style={{ width: '100%' }}
              loading={loadingCharacters}
              onChange={handleAddCharacter}
              value={undefined}
              showSearch
              optionFilterProp="children"
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
              options={Array.isArray(availableCharacters)
                ? availableCharacters
                    .filter(char => !characters.includes(char.name))
                    .map(char => ({
                      label: char.name,
                      value: char.name,
                    }))
                : []}
              notFoundContent={
                loadingCharacters ? 'Đang tải...' :
                !Array.isArray(availableCharacters) ? 'Tải nhân vật thất bại' :
                availableCharacters.length === 0 ? 'Chưa có nhân vật, vui lòng tạo trước trong quản lý nhân vật' :
                'Tất cả nhân vật đã được thêm'
              }
            />
            <Space wrap>
              {characters.map((char, idx) => (
                <Tag
                  key={idx}
                  closable
                  onClose={() => setCharacters(characters.filter((_, i) => i !== idx))}
                  color="cyan"
                >
                  {char}
                </Tag>
              ))}
            </Space>
          </Space>
        </Form.Item>

        {/* Tông cảm xúc */}
        <Form.Item
          label="Tông cảm xúc"
          name="emotional_tone"
          rules={[{ required: true, message: 'Vui lòng nhập tông cảm xúc' }]}
          tooltip="VD: căng thẳng kịch tính, ấm áp cảm động, huyền bí kinh dị, v.v."
        >
          <Input
            placeholder="Nhập tông cảm xúc, VD: căng thẳng kịch tính, ấm áp cảm động, v.v."
            maxLength={20}
          />
        </Form.Item>

        {/* Loại xung đột */}
        <Form.Item
          label="Loại xung đột"
          name="conflict_type"
          rules={[{ required: true, message: 'Vui lòng nhập loại xung đột' }]}
          tooltip="VD: xung đột nhân vật, xung đột nội tâm, xung đột môi trường, v.v."
        >
          <Input
            placeholder="Nhập loại xung đột, VD: xung đột nhân vật, xung đột nội tâm, v.v."
            maxLength={20}
          />
        </Form.Item>

        {/* Số ký tự ước tính */}
        <Form.Item
          label="Số ký tự ước tính"
          name="estimated_words"
          rules={[{ required: true, message: 'Vui lòng nhập số ký tự ước tính' }]}
        >
          <InputNumber
            min={500}
            max={10000}
            step={100}
            style={{ width: '100%' }}
            formatter={(value) => `${value} ký tự`}
            parser={(value) => Number(value?.replace(' ký tự', '')) as 500 | 10000}
          />
        </Form.Item>

        {/* Mục tiêu tự sự */}
        <Form.Item
          label="Mục tiêu tự sự"
          name="narrative_goal"
          rules={[{ required: true, message: 'Vui lòng nhập mục tiêu tự sự' }]}
        >
          <TextArea
            rows={3}
            placeholder="Mô tả mục tiêu tự sự chương này cần đạt được, VD: đẩy mạnh cốt truyện chính, làm sâu sắc quan hệ nhân vật, hé lộ thông tin quan trọng, v.v...."
            maxLength={500}
            showCount
          />
        </Form.Item>
      </Form>
    </Modal>
  );
}