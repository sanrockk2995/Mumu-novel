import React, { useState, useEffect } from 'react';
import {
  Modal,
  Form,
  Input,
  Button,
  Checkbox,
  InputNumber,
  Space,
  Alert,
  Divider,
  Tag,
  message,
  Collapse,
  Card,
  Radio
} from 'antd';
import {
  ReloadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined
} from '@ant-design/icons';
import { ssePost } from '../utils/sseClient';
import { SSEProgressModal } from './SSEProgressModal';

const { TextArea } = Input;
const { Panel } = Collapse;

interface Suggestion {
  category: string;
  content: string;
  priority: string;
}

interface ChapterRegenerationModalProps {
  visible: boolean;
  onCancel: () => void;
  onSuccess: (newContent: string, wordCount: number) => void;
  chapterId: string;
  chapterTitle: string;
  chapterNumber: number;
  suggestions?: Suggestion[];
  hasAnalysis: boolean;
}


const ChapterRegenerationModal: React.FC<ChapterRegenerationModalProps> = ({
  visible,
  onCancel,
  onSuccess,
  chapterId,
  chapterTitle,
  chapterNumber,
  suggestions = [],
  hasAnalysis
}) => {
  const [form] = Form.useForm();
  const [modal, contextHolder] = Modal.useModal();
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState<'idle' | 'generating' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState('');
  const [wordCount, setWordCount] = useState(0);
  const [selectedSuggestions, setSelectedSuggestions] = useState<number[]>([]);
  const [modificationSource, setModificationSource] = useState<'custom' | 'analysis_suggestions' | 'mixed'>('custom');

  useEffect(() => {
    if (visible) {
      // Reset trạng thái
      setStatus('idle');
      setProgress(0);
      setErrorMessage('');
      setWordCount(0);
      setSelectedSuggestions([]);
      
      // Nếu có gợi ý phân tích, mặc định chọn chế độ hỗn hợp
      if (hasAnalysis && suggestions.length > 0) {
        setModificationSource('mixed');
      } else {
        setModificationSource('custom');
      }
      
      // Đặt giá trị mặc định
      form.setFieldsValue({
        modification_source: hasAnalysis && suggestions.length > 0 ? 'mixed' : 'custom',
        target_word_count: 3000,
        preserve_structure: false,
        preserve_character_traits: true,
        focus_areas: []
      });
    }
  }, [visible, hasAnalysis, suggestions.length, form]);

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      
      // Kiểm tra phải cung cấp ít nhất một chỉ dẫn chỉnh sửa
      if (values.modification_source === 'custom' && !values.custom_instructions?.trim()) {
        message.error('Vui lòng nhập yêu cầu chỉnh sửa tùy chỉnh');
        return;
      }
      
      if (values.modification_source === 'analysis_suggestions' && selectedSuggestions.length === 0) {
        message.error('Vui lòng chọn ít nhất một gợi ý phân tích');
        return;
      }
      
      if (values.modification_source === 'mixed' && 
          selectedSuggestions.length === 0 && 
          !values.custom_instructions?.trim()) {
        message.error('Vui lòng chọn ít nhất một gợi ý hoặc nhập yêu cầu tùy chỉnh');
        return;
      }

      setLoading(true);
      setStatus('generating');
      setProgress(0);
      setWordCount(0);

      // Xây dựng dữ liệu request
      interface RegenerationRequest {
        modification_source: string;
        custom_instructions?: string;
        selected_suggestion_indices: number[];
        preserve_elements: {
          preserve_structure: boolean;
          preserve_dialogues: string[];
          preserve_plot_points: string[];
          preserve_character_traits: boolean;
        };
        style_id?: string;
        target_word_count: number;
        focus_areas: string[];
      }

      const requestData: RegenerationRequest = {
        modification_source: values.modification_source,
        custom_instructions: values.custom_instructions,
        selected_suggestion_indices: selectedSuggestions,
        preserve_elements: {
          preserve_structure: values.preserve_structure,
          preserve_dialogues: values.preserve_dialogues || [],
          preserve_plot_points: values.preserve_plot_points || [],
          preserve_character_traits: values.preserve_character_traits
        },
        style_id: values.style_id,
        target_word_count: values.target_word_count,
        focus_areas: values.focus_areas || []
      };

      let accumulatedContent = '';
      let currentWordCount = 0;

      // Dùng SSE để tạo theo stream
      await ssePost(
        `/api/chapters/${chapterId}/regenerate-stream`,
        requestData,
        {
          onProgress: (_msg: string, prog: number, _status: string, wordCount?: number) => {
            // Message tiến trình do backend gửi
            setProgress(prog);
            // Nếu backend cung cấp word_count thì dùng nó, nếu không sẽ dùng số ký tự tích lũy
            if (wordCount !== undefined) {
              setWordCount(wordCount);
              currentWordCount = wordCount;
            }
          },
          onChunk: (content: string) => {
            // Khối nội dung tích lũy
            accumulatedContent += content;
            // Chỉ dùng làm thống kê số ký tự dự phòng
            currentWordCount = accumulatedContent.length;
            // Không tự tính tiến trình nữa, hoàn toàn dựa vào message progress do backend gửi
          },
          onResult: (data: { word_count?: number }) => {
            // Tạo xong, đảm bảo dùng nội dung tích lũy mới nhất
            setProgress(100);
            setStatus('success');
            const finalWordCount = data.word_count || currentWordCount;
            setWordCount(finalWordCount);
            message.success('Tạo lại hoàn tất!');
            
            // Gọi trực tiếp onSuccess để mở giao diện so sánh, truyền nội dung tích lũy cuối cùng
            setTimeout(() => {
              onSuccess(accumulatedContent, finalWordCount);
            }, 500);
          },
          onComplete: () => {
            // SSEHoàn thành
          },
          onError: (error: string, code?: number) => {
            console.error('SSE Error:', error, code);
            setStatus('error');
            setErrorMessage(error || 'Tạo thất bại');
            message.error('Tạo lại thất bại: ' + (error || 'Lỗi không xác định'));
          }
        }
      );

    } catch (error: unknown) {
      console.error('Submit thất bại:', error);
      setStatus('error');
      const err = error as Error;
      setErrorMessage(err.message || 'Submit thất bại');
      message.error('Thao tác thất bại: ' + (err.message || 'Lỗi không xác định'));
    } finally {
      setLoading(false);
    }
  };

  const handleSuggestionSelect = (index: number, checked: boolean) => {
    if (checked) {
      setSelectedSuggestions([...selectedSuggestions, index]);
    } else {
      setSelectedSuggestions(selectedSuggestions.filter(i => i !== index));
    }
  };

  const handleCancel = () => {
    if (loading) {
      modal.confirm({
        title: 'Xác nhận hủy',
        content: 'Quá trình tạo đang diễn ra, bạn có chắc muốn hủy không?',
        centered: true,
        onOk: () => {
          setLoading(false);
          setStatus('idle');
          onCancel();
        }
      });
    } else {
      onCancel();
    }
  };

  return (
    <>
      {contextHolder}
      <Modal
      title={`Tạo lại chương - Chương ${chapterNumber}: ${chapterTitle}`}
      open={visible}
      onCancel={handleCancel}
      width={800}
      centered
      footer={
        status === 'success' ? null : (
          [
            <Button key="cancel" onClick={handleCancel} disabled={loading}>
              Hủy
            </Button>,
            <Button
              key="submit"
              type="primary"
              onClick={handleSubmit}
              loading={loading}
              icon={<ReloadOutlined />}
            >
              Bắt đầu tạo lại
            </Button>
          ]
        )
      }
    >

      {status === 'success' && (
        <Alert
          message="Tạo lại thành công!"
          description={`Đã tạo ${wordCount} ký tự`}
          type="success"
          showIcon
          icon={<CheckCircleOutlined />}
          style={{ marginBottom: 16 }}
        />
      )}

      {status === 'error' && (
        <Alert
          message="Tạo thất bại"
          description={errorMessage}
          type="error"
          showIcon
          icon={<CloseCircleOutlined />}
          style={{ marginBottom: 16 }}
        />
      )}

      <Form
        form={form}
        layout="vertical"
        disabled={loading || status === 'success'}
      >
        {/* Nguồn chỉnh sửa */}
        <Form.Item
          name="modification_source"
          label="Nguồn chỉnh sửa"
          rules={[{ required: true, message: 'Vui lòng chọn nguồn chỉnh sửa' }]}
        >
          <Radio.Group onChange={(e) => setModificationSource(e.target.value)}>
            <Radio value="custom">Chỉ chỉnh sửa tùy chỉnh</Radio>
            {hasAnalysis && suggestions.length > 0 && (
              <>
                <Radio value="analysis_suggestions">Chỉ dùng gợi ý phân tích</Radio>
                <Radio value="mixed">Chế độ hỗn hợp</Radio>
              </>
            )}
          </Radio.Group>
        </Form.Item>

        {/* Chọn gợi ý phân tích */}
        {hasAnalysis && suggestions.length > 0 && 
         (modificationSource === 'analysis_suggestions' || modificationSource === 'mixed') && (
          <Form.Item label={`Chọn gợi ý phân tích (${selectedSuggestions.length}/${suggestions.length})`}>
            <Card size="small" style={{ maxHeight: 300, overflow: 'auto' }}>
              <Space direction="vertical" style={{ width: '100%' }}>
                {suggestions.map((suggestion, index) => (
                  <Checkbox
                    key={index}
                    checked={selectedSuggestions.includes(index)}
                    onChange={(e) => handleSuggestionSelect(index, e.target.checked)}
                  >
                    <Space>
                      <Tag color={
                        suggestion.priority === 'high' ? 'red' :
                        suggestion.priority === 'medium' ? 'orange' : 'blue'
                      }>
                        {suggestion.category}
                      </Tag>
                      <span style={{ fontSize: 13 }}>{suggestion.content}</span>
                    </Space>
                  </Checkbox>
                ))}
              </Space>
            </Card>
          </Form.Item>
        )}

        {/* Yêu cầu chỉnh sửa tùy chỉnh */}
        {(modificationSource === 'custom' || modificationSource === 'mixed') && (
          <Form.Item
            name="custom_instructions"
            label="Yêu cầu chỉnh sửa tùy chỉnh"
            tooltip="Mô tả cách bạn muốn cải thiện chương này"
          >
            <TextArea
              rows={4}
              placeholder="VD: tăng cường khắc họa cảm xúc, khiến diễn biến nội tâm của nhân vật chính thêm tinh tế..."
              showCount
              maxLength={1000}
            />
          </Form.Item>
        )}

        {/* Tùy chọn nâng cao */}
        <Collapse ghost>
          <Panel header="Tùy chọn nâng cao" key="advanced">
            {/* Hướng tối ưu trọng điểm */}
            <Form.Item
              name="focus_areas"
              label="Hướng tối ưu trọng điểm"
            >
              <Checkbox.Group>
                <Space direction="vertical">
                  <Checkbox value="pacing">Kiểm soát nhịp độ</Checkbox>
                  <Checkbox value="emotion">Khắc họa cảm xúc</Checkbox>
                  <Checkbox value="description">Miêu tả cảnh</Checkbox>
                  <Checkbox value="dialogue">Chất lượng hội thoại</Checkbox>
                  <Checkbox value="conflict">Cường độ xung đột</Checkbox>
                </Space>
              </Checkbox.Group>
            </Form.Item>

            <Divider />

            {/* Yếu tố giữ lại */}
            <Form.Item label="Yếu tố giữ lại">
              <Space direction="vertical" style={{ width: '100%' }}>
                <Form.Item name="preserve_structure" valuePropName="checked" noStyle>
                  <Checkbox>Giữ nguyên cấu trúc tổng thể và khung cốt truyện</Checkbox>
                </Form.Item>
                <Form.Item name="preserve_character_traits" valuePropName="checked" noStyle>
                  <Checkbox>Giữ tính cách nhân vật nhất quán</Checkbox>
                </Form.Item>
              </Space>
            </Form.Item>

            <Divider />

            {/* Tham số tạo */}
            <Form.Item
              name="target_word_count"
              label="Số ký tự mục tiêu"
              tooltip="Số ký tự mục tiêu của nội dung được tạo, số ký tự thực tế có thể dao động ±20%"
            >
              <InputNumber min={500} max={10000} step={500} style={{ width: '100%' }} />
            </Form.Item>

          </Panel>
        </Collapse>
      </Form>

      {/* Dùng component hiển thị tiến trình thống nhất */}
      <SSEProgressModal
        visible={status === 'generating'}
        progress={progress}
        message={`Đang tạo lại... (đã tạo ${wordCount} ký tự)`}
        title="Tạo lại chương"
      />
      </Modal>
    </>
  );
};

export default ChapterRegenerationModal;