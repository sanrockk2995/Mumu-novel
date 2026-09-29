import { useState, useEffect, useMemo } from 'react';
import { Button, List, Modal, Form, Input, message, Empty, Space, Popconfirm, Card, Select, Radio, Tag, InputNumber, Tabs, Pagination, theme, Upload, Alert, Divider } from 'antd';
import { EditOutlined, DeleteOutlined, ThunderboltOutlined, BranchesOutlined, AppstoreAddOutlined, CheckCircleOutlined, ExclamationCircleOutlined, PlusOutlined, FileTextOutlined, UploadOutlined, DownloadOutlined } from '@ant-design/icons';
import { useStore } from '../store';
import { eventBus, EventNames } from '../store/eventBus';
import { getProjectTasks, type TaskStatus } from '../services/backgroundTaskService';
import { useOutlineSync } from '../store/hooks';
import { generateOutlineBackground } from '../services/backgroundTaskService';
import { outlineApi, chapterApi, projectApi, characterApi } from '../services/api';
import type { ApiError, Character, OutlineImportMode, OutlineImportPreview } from '../types';

// Kiểu dữ liệu request tạo đề cương
interface OutlineGenerateRequestData {
  project_id: string;
  genre: string;
  theme: string;
  chapter_count: number;
  narrative_perspective: string;
  target_words: number;
  requirements?: string;
  mode: 'auto' | 'new' | 'continue';
  story_direction?: string;
  plot_stage: 'development' | 'climax' | 'ending';
  model?: string;
  provider?: string;
}

// Kiểu mục nhân vật/tổ chức (định dạng mới)
interface CharacterEntry {
  name: string;
  type: 'character' | 'organization';
}

/**
 * Phân tích trường characters, tương thích định dạng cũ và mới
 * Định dạng cũ: string[] -> tất cả coi như character
 * Định dạng mới: {name: string, type: "character"|"organization"}[]
 */
function parseCharacterEntries(characters: unknown): CharacterEntry[] {
  if (!Array.isArray(characters) || characters.length === 0) return [];
  
  return characters.map((entry) => {
    if (typeof entry === 'string') {
      // Định dạng cũ: chuỗi thuần, mặc định là character
      return { name: entry, type: 'character' as const };
    }
    if (typeof entry === 'object' && entry !== null && 'name' in entry) {
      // Định dạng mới: đối tượng có kèm định danh loại
      return {
        name: (entry as { name: string }).name,
        type: ((entry as { type?: string }).type === 'organization' ? 'organization' : 'character') as 'character' | 'organization'
      };
    }
    return null;
  }).filter((e): e is CharacterEntry => e !== null);
}

/** Trích xuất danh sách tên nhân vật từ entries */
function getCharacterNames(entries: CharacterEntry[]): string[] {
  return entries.filter(e => e.type === 'character').map(e => e.name);
}

/** Trích xuất danh sách tên tổ chức từ entries */
function getOrganizationNames(entries: CharacterEntry[]): string[] {
  return entries.filter(e => e.type === 'organization').map(e => e.name);
}

interface OutlineStructureData {
  key_events?: string[];
  key_points?: string[];
  characters_involved?: string[];
  characters?: unknown[];
  scenes?: string[] | Array<{
    location: string;
    characters: string[];
    purpose: string;
  }>;
  emotion?: string;
  goal?: string;
  title?: string;
  summary?: string;
  content?: string;
}

function parseOutlineStructure(structure?: string): OutlineStructureData {
  if (!structure) return {};
  try {
    return JSON.parse(structure) as OutlineStructureData;
  } catch (e) {
    console.error('Phân tích structure thất bại:', e);
    return {};
  }
}

function getOutlinePreview(content: string, maxLength = 120): { text: string; truncated: boolean } {
  const normalized = (content || '').replace(/\s+/g, ' ').trim();
  if (normalized.length <= maxLength) {
    return { text: normalized, truncated: false };
  }
  return {
    text: `${normalized.slice(0, maxLength).trimEnd()}...`,
    truncated: true
  };
}

const { TextArea } = Input;

export default function Outline() {
  const { currentProject, outlines, setCurrentProject } = useStore();
  const [isGenerating, setIsGenerating] = useState(false);
  const [editForm] = Form.useForm();
  const [generateForm] = Form.useForm();
  const [expansionForm] = Form.useForm();
  const [modalApi, contextHolder] = Modal.useModal();
  const [batchExpansionForm] = Form.useForm();
  const [manualCreateForm] = Form.useForm();
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);
  const [isExpanding, setIsExpanding] = useState(false);
  const [projectCharacters, setProjectCharacters] = useState<Array<{ label: string; value: string }>>([]);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importMode, setImportMode] = useState<OutlineImportMode>('append');
  const [importPreview, setImportPreview] = useState<OutlineImportPreview | null>(null);
  const [isPreviewingImport, setIsPreviewingImport] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const { token } = theme.useToken();
  const alphaColor = (color: string, alpha: number) =>
    `color-mix(in srgb, ${color} ${(alpha * 100).toFixed(0)}%, transparent)`;

  // ✅ Mới: ghi lại trạng thái mở rộng/thu gọn nội dung thẻ đề cương (mặc định thu gọn)
  const [outlineContentExpandStatus, setOutlineContentExpandStatus] = useState<Record<string, boolean>>({});

  // ✅ Mới: ghi lại trạng thái mở rộng/thu gọn khu vực cảnh
  const [scenesExpandStatus, setScenesExpandStatus] = useState<Record<string, boolean>>({});

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth <= 768);
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Trạng thái truy vấn và phân trang đề cương
  const [outlineSearchKeyword, setOutlineSearchKeyword] = useState('');
  const [outlinePage, setOutlinePage] = useState(1);
  const [outlinePageSize, setOutlinePageSize] = useState(20);

  // Dùng hooks đồng bộ
  const {
    refreshOutlines,
    updateOutline,
    deleteOutline
  } = useOutlineSync();

  // Tải ban đầu danh sách đề cương và danh sách nhân vật
  useEffect(() => {
    if (currentProject?.id) {
      refreshOutlines();
      // Tải danh sách nhân vật của dự án
      loadProjectCharacters();
      // Kiểm tra có tác vụ tạo đề cương đang hoạt động không, khôi phục trạng thái vô hiệu của nút
      checkActiveOutlineTasks();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentProject?.id]); // Chỉ phụ thuộc ID, không phụ thuộc hàm

  // Kiểm tra có tác vụ tạo đề cương đang hoạt động không (khôi phục trạng thái sau khi chuyển trang)
  const checkActiveOutlineTasks = async () => {
    if (!currentProject?.id) return;
    try {
      const result = await getProjectTasks(currentProject.id, 'outline_new', 5);
      const result2 = await getProjectTasks(currentProject.id, 'outline_continue', 5);
      const allTasks = [...(result.items || []), ...(result2.items || [])];
      const hasActive = allTasks.some((t: TaskStatus) => t.status === 'running' || t.status === 'pending');
      setIsGenerating(hasActive);
    } catch (error) {
      console.error('Kiểm tra tác vụ đề cương đang hoạt động thất bại:', error);
    }
  };

  // Tải danh sách nhân vật của dự án
  const loadProjectCharacters = async () => {
    if (!currentProject?.id) return;
    try {
      const characters = await characterApi.getCharacters(currentProject.id);
      setProjectCharacters(
        characters.map((char: Character) => ({
          label: char.name,
          value: char.name
        }))
      );
    } catch (error) {
      console.error('Tải danh sách nhân vật thất bại:', error);
    }
  };

  // Xây dựng trực tiếp trạng thái mở rộng từ trường backend trả về, tránh request N+1 phía frontend
  const outlineExpandStatus = useMemo(() => {
    const statusMap: Record<string, boolean> = {};
    outlines.forEach((outline) => {
      statusMap[outline.id] = Boolean(outline.has_chapters);
    });
    return statusMap;
  }, [outlines]);

  // Parse trước thống nhất structure, tránh lặp lại JSON.parse ở giai đoạn render
  const outlineStructureMap = useMemo(() => {
    const parsedMap: Record<string, OutlineStructureData> = {};
    outlines.forEach((outline) => {
      parsedMap[outline.id] = parseOutlineStructure(outline.structure);
    });
    return parsedMap;
  }, [outlines]);

  // Khi dữ liệu xác nhận nhân vật thay đổi, khởi tạo trạng thái chọn (mặc định chọn tất cả)
  // Khi dữ liệu xác nhận tổ chức thay đổi, khởi tạo trạng thái chọn (mặc định chọn tất cả)
  // Gỡ lắng nghe sự kiện, tránh vòng lặp vô hạn
  // Hook nội bộ đã cập nhật store, không cần refresh lại

  // Đảm bảo đề cương được sắp xếp theo order_index
  const sortedOutlines = [...outlines].sort((a, b) => a.order_index - b.order_index);

  // Lọc truy vấn frontend
  const filteredOutlines = useMemo(() => {
    const keyword = outlineSearchKeyword.trim().toLowerCase();
    if (!keyword) return sortedOutlines;

    return sortedOutlines.filter((outline) => {
      return (
        String(outline.order_index).includes(keyword) ||
        outline.title.toLowerCase().includes(keyword) ||
        outline.content.toLowerCase().includes(keyword)
      );
    });
  }, [sortedOutlines, outlineSearchKeyword]);

  // Dữ liệu phân trang hiện tại
  const pagedOutlines = useMemo(() => {
    const start = (outlinePage - 1) * outlinePageSize;
    return filteredOutlines.slice(start, start + outlinePageSize);
  }, [filteredOutlines, outlinePage, outlinePageSize]);

  // Khi từ khóa tìm kiếm hoặc kích thước trang thay đổi, quay về trang đầu
  useEffect(() => {
    setOutlinePage(1);
  }, [outlineSearchKeyword, outlinePageSize]);

  // Tự động điều chỉnh khi dữ liệu thay đổi khiến số trang vượt giới hạn
  useEffect(() => {
    const maxPage = Math.max(1, Math.ceil(filteredOutlines.length / outlinePageSize));
    if (outlinePage > maxPage) {
      setOutlinePage(maxPage);
    }
  }, [filteredOutlines.length, outlinePage, outlinePageSize]);

  if (!currentProject) return null;

  const handleOpenEditModal = (id: string) => {
    const outline = outlines.find(o => o.id === id);
    if (outline) {
      const structureData = outlineStructureMap[outline.id] || {};
      
      // Phân tích mục nhân vật/tổ chức (tương thích định dạng cũ/mới)
      const editEntries = parseCharacterEntries(structureData.characters);
      const editCharNames = getCharacterNames(editEntries);
      const editOrgNames = getOrganizationNames(editEntries);
      
      // Xử lý dữ liệu cảnh - có thể là mảng chuỗi hoặc mảng đối tượng
      let scenesText = '';
      if (structureData.scenes) {
        if (typeof structureData.scenes[0] === 'string') {
          // Định dạng mảng chuỗi
          scenesText = (structureData.scenes as string[]).join('\n');
        } else {
          // Định dạng mảng đối tượng
          scenesText = (structureData.scenes as Array<{location: string; characters: string[]; purpose: string}>)
            .map(s => `${s.location}|${(s.characters || []).join('、')}|${s.purpose}`)
            .join('\n');
        }
      }
      
      // Xử lý dữ liệu điểm nhấn tình tiết
      const keyPointsText = structureData.key_points ? structureData.key_points.join('\n') : '';
      
      // Thiết lập giá trị ban đầu của form
      editForm.setFieldsValue({
        title: outline.title,
        content: outline.content,
        characters: editCharNames,
        organizations: editOrgNames,
        scenes: scenesText,
        key_points: keyPointsText,
        emotion: structureData.emotion || '',
        goal: structureData.goal || ''
      });
      
      modalApi.confirm({
        title: 'Chỉnh sửa đề cương',
        width: 800,
        centered: true,
        styles: {
          body: {
            maxHeight: 'calc(100vh - 200px)',
            overflowY: 'auto'
          }
        },
        content: (
          <Form
            form={editForm}
            layout="vertical"
            style={{ marginTop: 12 }}
          >
            <Form.Item
              label="Tiêu đề"
              name="title"
              rules={[{ required: true, message: 'Vui lòng nhập tiêu đề' }]}
              style={{ marginBottom: 12 }}
            >
              <Input placeholder="Nhập tiêu đề đề cương" />
            </Form.Item>

            <Form.Item
              label="Nội dung"
              name="content"
              rules={[{ required: true, message: 'Vui lòng nhập nội dung' }]}
              style={{ marginBottom: 12 }}
            >
              <TextArea rows={4} placeholder="Nhập nội dung đề cương..." />
            </Form.Item>
            
            <Form.Item
              label="Nhân vật liên quan"
              name="characters"
              tooltip="Chọn từ nhân vật của dự án, cũng có thể nhập tay tên nhân vật mới"
              style={{ marginBottom: 12 }}
            >
              <Select
                mode="tags"
                style={{ width: '100%' }}
                placeholder="Chọn hoặc nhập tên nhân vật"
                options={projectCharacters}
                tokenSeparators={[',', '，']}
                maxTagCount="responsive"
              />
            </Form.Item>
            
            <Form.Item
              label="Tổ chức liên quan"
              name="organizations"
              tooltip="Chọn từ tổ chức của dự án, cũng có thể nhập tay tên tổ chức mới"
              style={{ marginBottom: 12 }}
            >
              <Select
                mode="tags"
                style={{ width: '100%' }}
                placeholder="Chọn hoặc nhập tên tổ chức/thế lực"
                tokenSeparators={[',', '，']}
                maxTagCount="responsive"
              />
            </Form.Item>
            
            <Form.Item
              label="Thông tin cảnh"
              name="scenes"
              tooltip="Hỗ trợ hai định dạng: mô tả đơn giản (mỗi dòng một cảnh) hoặc định dạng chi tiết (địa điểm|nhân vật|mục đích)"
              style={{ marginBottom: 12 }}
            >
              <TextArea
                rows={3}
                placeholder="Mỗi dòng một cảnh&#10;Định dạng chi tiết: địa điểm|nhân vật 1, nhân vật 2|mục đích"
              />
            </Form.Item>
            
            <Form.Item
              label="Điểm nhấn tình tiết"
              name="key_points"
              tooltip="Mỗi dòng một điểm nhấn tình tiết"
              style={{ marginBottom: 12 }}
            >
              <TextArea
                rows={2}
                placeholder="Mỗi dòng một điểm nhấn tình tiết"
              />
            </Form.Item>
            
            <Form.Item
              label="Tông cảm xúc"
              name="emotion"
              tooltip="Mô tả bầu không khí cảm xúc của chương này"
              style={{ marginBottom: 12 }}
            >
              <Input placeholder="Ví dụ: lạnh lẽo và xao động cùng tồn tại" />
            </Form.Item>
            
            <Form.Item
              label="Mục tiêu kể chuyện"
              name="goal"
              tooltip="Mục đích kể chuyện cần đạt được của chương này"
              style={{ marginBottom: 0 }}
            >
              <Input placeholder="Ví dụ: xây dựng tương phản thế giới quan và hoàn thành cuộc gặp đầu của nhân vật chính" />
            </Form.Item>
          </Form>
        ),
        okText: 'Cập nhật',
        cancelText: 'Hủy',
        onOk: async () => {
          const values = await editForm.validateFields();
          try {
            // Phân tích và tái cấu trúc dữ liệu structure (dùng cache parse trước, tránh lặp lại JSON.parse)
            const originalStructure = outlineStructureMap[outline.id] || {};
            
            // Xử lý dữ liệu nhân vật và tổ chức - gộp thành định dạng mới có định danh loại
            const charNames = Array.isArray(values.characters)
              ? values.characters.filter((c: string) => c && c.trim())
              : [];
            const orgNames = Array.isArray(values.organizations)
              ? values.organizations.filter((c: string) => c && c.trim())
              : [];
            const characters: CharacterEntry[] = [
              ...charNames.map((name: string) => ({ name: name.trim(), type: 'character' as const })),
              ...orgNames.map((name: string) => ({ name: name.trim(), type: 'organization' as const }))
            ];
            
            // Xử lý dữ liệu cảnh - phát hiện định dạng gốc
            let scenes: string[] | Array<{location: string; characters: string[]; purpose: string}> | undefined;
            if (values.scenes) {
              const lines = values.scenes.split('\n')
                .map((line: string) => line.trim())
                .filter((line: string) => line);
              
              // Kiểm tra có chứa ký tự | không để xác định định dạng
              const hasStructuredFormat = lines.some((line: string) => line.includes('|'));
              
              if (hasStructuredFormat) {
                // Thử parse thành định dạng mảng đối tượng
                scenes = lines
                  .map((line: string) => {
                    const parts = line.split('|');
                    if (parts.length >= 3) {
                      return {
                        location: parts[0].trim(),
                        characters: parts[1].split('、').map(c => c.trim()).filter(c => c),
                        purpose: parts[2].trim()
                      };
                    }
                    return null;
                  })
                  .filter((s: { location: string; characters: string[]; purpose: string } | null): s is { location: string; characters: string[]; purpose: string } => s !== null);
              } else {
                // Giữ định dạng mảng chuỗi
                scenes = lines;
              }
            }
            
            // Xử lý dữ liệu điểm nhấn tình tiết
            const keyPoints = values.key_points
              ? values.key_points.split('\n')
                  .map((line: string) => line.trim())
                  .filter((line: string) => line)
              : undefined;
            
            // Gộp dữ liệu structure, chỉ bao gồm các trường AI thực sự tạo ra
            const newStructure = {
              ...originalStructure,
              title: values.title,
              summary: values.content,
              characters: characters.length > 0 ? characters : undefined,
              scenes: scenes && scenes.length > 0 ? scenes : undefined,
              key_points: keyPoints && keyPoints.length > 0 ? keyPoints : undefined,
              emotion: values.emotion || undefined,
              goal: values.goal || undefined
            };
            
            // Cập nhật đề cương
            await updateOutline(id, {
              title: values.title,
              content: values.content,
              structure: JSON.stringify(newStructure, null, 2)
            });
            
            message.success('Cập nhật đề cương thành công');
          } catch (error) {
            console.error('Cập nhật thất bại:', error);
            message.error('Cập nhật thất bại');
          }
        },
      });
    }
  };

  const handleDeleteOutline = async (id: string) => {
    try {
      await deleteOutline(id);
      message.success('Xóa thành công');
      // Sau khi xóa, refresh danh sách đề cương và thông tin dự án, cập nhật hiển thị số chữ
      await refreshOutlines();
      if (currentProject?.id) {
        const updatedProject = await projectApi.getProject(currentProject.id);
        setCurrentProject(updatedProject);
      }
    } catch {
      message.error('Xóa thất bại');
    }
  };

  interface GenerateFormValues {
    theme?: string;
    chapter_count?: number;
    narrative_perspective?: string;
    requirements?: string;
    provider?: string;
    model?: string;
    mode?: 'auto' | 'new' | 'continue';
    story_direction?: string;
    plot_stage?: 'development' | 'climax' | 'ending';
    keep_existing?: boolean;
  }

  const handleGenerate = async (values: GenerateFormValues) => {
    try {
      setIsGenerating(true);

      // Thêm log debug chi tiết
      console.log('=== Thông tin debug tạo đề cương ===');
      console.log('1. Dữ liệu gốc Form values:', values);
      console.log('2. values.model:', values.model);
      console.log('3. values.provider:', values.provider);

      // Đóng Modal form tạo
      Modal.destroyAll();

      // Chuẩn bị dữ liệu request
      const requestData: OutlineGenerateRequestData = {
        project_id: currentProject.id,
        genre: currentProject.genre || '通用',
        theme: values.theme || currentProject.theme || '',
        chapter_count: values.chapter_count || 5,
        narrative_perspective: values.narrative_perspective || currentProject.narrative_perspective || '第三人称',
        target_words: currentProject.target_words || 100000,
        requirements: values.requirements,
        mode: values.mode || 'auto',
        story_direction: values.story_direction,
        plot_stage: values.plot_stage || 'development'
      };

      // Chỉ thêm tham số model khi người dùng đã chọn mô hình
      if (values.model) {
        requestData.model = values.model;
        console.log('4. Thêm model vào request:', values.model);
      } else {
        console.log('4. values.model rỗng, không thêm vào request');
      }

      // Thêm tham số provider (nếu có)
      if (values.provider) {
        requestData.provider = values.provider;
        console.log('5. Thêm provider vào request:', values.provider);
      }

      console.log('6. Dữ liệu request cuối cùng:', JSON.stringify(requestData, null, 2));
      console.log('=========================');

      // Tạo bằng tác vụ nền (không sợ mất kết nối, đóng trình duyệt vẫn tiếp tục chạy)
      // Không ép hiển thị popup tiến độ nữa, tiến độ tác vụ hiển thị trong khung tác vụ nổi góc dưới bên phải
      await generateOutlineBackground(
        requestData,
        () => {
          // Cập nhật tiến độ do khung tác vụ nổi xử lý, không cần thao tác thêm
        },
        (result) => {
          message.success(result.task_result?.message as string || 'Tạo đề cương hoàn tất!');
          setIsGenerating(false);
          refreshOutlines();
        },
        (error) => {
          message.error(`Tạo thất bại: ${error}`);
          setIsGenerating(false);
        }
      );

      message.info('Tác vụ tạo đề cương đã được gửi, có thể xem tiến độ tại bảng tác vụ góc dưới bên phải');
      // Thông báo khung tác vụ nổi refresh
      eventBus.emit('background-task-created');

    } catch (error) {
      console.error('AI tạo thất bại:', error);
      message.error('AI tạo thất bại');
      setIsGenerating(false);
    }
  };

  const showGenerateModal = async () => {
    const hasOutlines = outlines.length > 0;
    const initialMode = hasOutlines ? 'continue' : 'new';

    // Tải trực tiếp danh sách mô hình khả dụng
    const settingsResponse = await fetch('/api/settings');
    const settings = await settingsResponse.json();
    const { api_key, api_base_url, api_provider } = settings;

    let loadedModels: Array<{ value: string, label: string }> = [];
    let defaultModel: string | undefined = undefined;

    if (api_base_url) {
      try {
        const modelsResponse = await fetch(
          `/api/settings/models?api_key=${encodeURIComponent(api_key || '')}&api_base_url=${encodeURIComponent(api_base_url)}&provider=${api_provider}`
        );
        if (modelsResponse.ok) {
          const data = await modelsResponse.json();
          if (data.models && data.models.length > 0) {
            loadedModels = data.models;
            defaultModel = settings.llm_model;
          }
        }
      } catch {
        console.log('Lấy danh sách mô hình thất bại, sẽ dùng mô hình mặc định');
      }
    }

    modalApi.confirm({
      title: hasOutlines ? (
        <Space>
          <span>AI tạo/viết tiếp đề cương</span>
          <Tag color="blue">Hiện đã có {outlines.length} quyển</Tag>
        </Space>
      ) : 'AI tạo đề cương',
      width: 700,
      centered: true,
      content: (
        <Form
          form={generateForm}
          layout="vertical"
          style={{ marginTop: 16 }}
          initialValues={{
            mode: initialMode,
            chapter_count: 5,
            narrative_perspective: currentProject.narrative_perspective || '第三人称',
            plot_stage: 'development',
            keep_existing: true,
            theme: currentProject.theme || '',
            model: defaultModel,
          }}
        >
          {hasOutlines && (
            <Form.Item
              label="Chế độ tạo"
              name="mode"
              tooltip="Tự động nhận định: tự chọn theo việc có đề cương hay không; Tạo hoàn toàn mới: xóa đề cương cũ và tạo lại; Chế độ viết tiếp: tiếp tục sáng tác dựa trên đề cương đã có"
            >
              <Radio.Group buttonStyle="solid">
                <Radio.Button value="auto">Tự động nhận định</Radio.Button>
                <Radio.Button value="new">Tạo hoàn toàn mới</Radio.Button>
                <Radio.Button value="continue">Chế độ viết tiếp</Radio.Button>
              </Radio.Group>
            </Form.Item>
          )}

          <Form.Item
            noStyle
            shouldUpdate={(prevValues, currentValues) => prevValues.mode !== currentValues.mode}
          >
            {({ getFieldValue }) => {
              const mode = getFieldValue('mode');
              const isContinue = mode === 'continue' || (mode === 'auto' && hasOutlines);

              // Chế độ viết tiếp không hiển thị ô nhập chủ đề, dùng chủ đề gốc của dự án
              if (isContinue) {
                return null;
              }

              // Chế độ tạo hoàn toàn mới cần nhập chủ đề
              return (
                <Form.Item
                  label="Chủ đề truyện"
                  name="theme"
                  rules={[{ required: true, message: 'Vui lòng nhập chủ đề truyện' }]}
                >
                  <TextArea rows={3} placeholder="Mô tả chủ đề truyện, thiết lập cốt lõi và tình tiết chính của bạn..." />
                </Form.Item>
              );
            }}
          </Form.Item>

          <Form.Item
            noStyle
            shouldUpdate={(prevValues, currentValues) => prevValues.mode !== currentValues.mode}
          >
            {({ getFieldValue }) => {
              const mode = getFieldValue('mode');
              const isContinue = mode === 'continue' || (mode === 'auto' && hasOutlines);

              return (
                <>
                  {isContinue && (
                    <>
                      <Form.Item
                        label="Hướng phát triển truyện"
                        name="story_direction"
                        tooltip="Cho AI biết bạn muốn truyện tiếp theo phát triển thế nào"
                      >
                        <TextArea
                          rows={3}
                          placeholder="Ví dụ: nhân vật chính gặp thử thách mới, giới thiệu nhân vật mới, hé lộ bí mật then chốt..."
                        />
                      </Form.Item>

                      <Form.Item
                        label="Giai đoạn tình tiết"
                        name="plot_stage"
                        tooltip="Giúp AI hiểu truyện hiện đang ở giai đoạn nào"
                      >
                        <Select>
                          <Select.Option value="development">Giai đoạn phát triển - Tiếp tục triển khai tình tiết</Select.Option>
                          <Select.Option value="climax">Giai đoạn cao trào - Mâu thuẫn leo thang</Select.Option>
                          <Select.Option value="ending">Giai đoạn kết thúc - Thu gọn các nút thắt</Select.Option>
                        </Select>
                      </Form.Item>
                    </>
                  )}

                  <Form.Item
                    label={isContinue ? "Số chương viết tiếp" : "Số lượng chương"}
                    name="chapter_count"
                    rules={[{ required: true, message: 'Vui lòng nhập số lượng chương' }]}
                  >
                    <Input
                      type="number"
                      min={1}
                      max={50}
                      placeholder={isContinue ? "Gợi ý 5-10 chương" : "VD: 30"}
                    />
                  </Form.Item>

                  <Form.Item
                    label="Góc nhìn kể chuyện"
                    name="narrative_perspective"
                    rules={[{ required: true, message: 'Vui lòng chọn góc nhìn kể chuyện' }]}
                  >
                    <Select>
                      <Select.Option value="第一人称">Ngôi thứ nhất</Select.Option>
                      <Select.Option value="第三人称">Ngôi thứ ba</Select.Option>
                      <Select.Option value="全知视角">Góc nhìn toàn tri</Select.Option>
                    </Select>
                  </Form.Item>

                  <Form.Item label="Yêu cầu khác" name="requirements">
                    <TextArea rows={2} placeholder="Yêu cầu đặc biệt khác (tùy chọn)" />
                  </Form.Item>

                </>
              );
            }}
          </Form.Item>

          {/* Tùy chọn mô hình tùy chỉnh - chuyển ra ngoài, mọi chế độ đều hiển thị */}
          {loadedModels.length > 0 && (
            <Form.Item
              label="Mô hình AI"
              name="model"
              tooltip="Chọn mô hình AI dùng để tạo, không chọn thì dùng mô hình mặc định của hệ thống"
            >
              <Select
                placeholder={defaultModel ? `Mặc định: ${loadedModels.find(m => m.value === defaultModel)?.label || defaultModel}` : "Dùng mô hình mặc định"}
                allowClear
                showSearch
                optionFilterProp="label"
                options={loadedModels}
                onChange={(value) => {
                  console.log('Người dùng đã chọn mô hình trong dropdown:', value);
                  // Đồng bộ thủ công vào Form
                  generateForm.setFieldsValue({ model: value });
                  console.log('Đã đồng bộ vào Form, giá trị Form hiện tại:', generateForm.getFieldsValue());
                }}
              />
              <div style={{ color: token.colorTextTertiary, fontSize: 12, marginTop: 4 }}>
                {defaultModel ? `Mô hình mặc định hiện tại: ${loadedModels.find(m => m.value === defaultModel)?.label || defaultModel}` : 'Chưa cấu hình mô hình mặc định'}
              </div>
            </Form.Item>
          )}
        </Form>
      ),
      okText: hasOutlines ? 'Bắt đầu viết tiếp' : 'Bắt đầu tạo',
      cancelText: 'Hủy',
      onOk: async () => {
        const values = await generateForm.validateFields();
        await handleGenerate(values);
      },
    });
  };

  // Tạo đề cương thủ công
  const showManualCreateOutlineModal = () => {
    const nextOrderIndex = outlines.length > 0
      ? Math.max(...outlines.map(o => o.order_index)) + 1
      : 1;

    modalApi.confirm({
      title: 'Tạo đề cương thủ công',
      width: 600,
      centered: true,
      content: (
        <Form
          form={manualCreateForm}
          layout="vertical"
          initialValues={{ order_index: nextOrderIndex }}
          style={{ marginTop: 16 }}
        >
          <Form.Item
            label="Số thứ tự đề cương"
            name="order_index"
            rules={[{ required: true, message: 'Vui lòng nhập số thứ tự' }]}
            tooltip={currentProject?.outline_mode === 'one-to-one' ? 'Ở chế độ truyền thống, số thứ tự là số chương' : 'Ở chế độ chi tiết, số thứ tự là số quyển'}
          >
            <InputNumber min={1} style={{ width: '100%' }} placeholder="Số thứ tự tiếp theo được tính tự động" />
          </Form.Item>

          <Form.Item
            label="Tiêu đề đề cương"
            name="title"
            rules={[{ required: true, message: 'Vui lòng nhập tiêu đề' }]}
          >
            <Input placeholder={currentProject?.outline_mode === 'one-to-one' ? 'Ví dụ: Chương 1: Bước vào giang hồ' : 'Ví dụ: Quyển 1: Bước vào giang hồ'} />
          </Form.Item>

          <Form.Item
            label="Nội dung đề cương"
            name="content"
            rules={[{ required: true, message: 'Vui lòng nhập nội dung' }]}
          >
            <TextArea
              rows={6}
              placeholder="Mô tả tình tiết chính và hướng phát triển của chương/quyển này..."
            />
          </Form.Item>
        </Form>
      ),
      okText: 'Tạo',
      cancelText: 'Hủy',
      onOk: async () => {
        const values = await manualCreateForm.validateFields();

        // Kiểm tra số thứ tự có bị trùng không
        const existingOutline = outlines.find(o => o.order_index === values.order_index);
        if (existingOutline) {
          modalApi.warning({
            title: 'Trùng số thứ tự',
            content: (
              <div>
                <p>Số thứ tự <strong>{values.order_index}</strong> đã được sử dụng:</p>
                <div style={{
                  padding: 12,
                  background: token.colorWarningBg,
                  borderRadius: token.borderRadius,
                  border: `1px solid ${token.colorWarningBorder}`,
                  marginTop: 8
                }}>
                  <div style={{ fontWeight: 500, color: token.colorWarning }}>
                    {currentProject?.outline_mode === 'one-to-one'
                      ? `Chương ${existingOutline.order_index}`
                      : `Quyển ${existingOutline.order_index}`
                    }：{existingOutline.title}
                  </div>
                </div>
                <p style={{ marginTop: 12, color: token.colorTextSecondary }}>
                  💡 Nên dùng số thứ tự <strong>{nextOrderIndex}</strong>, hoặc chọn số thứ tự khác chưa được dùng
                </p>
              </div>
            ),
            okText: 'Đã hiểu',
            centered: true
          });
          throw new Error('Số thứ tự trùng lặp');
        }

        try {
          await outlineApi.createOutline({
            project_id: currentProject.id,
            ...values
          });
          message.success('Tạo đề cương thành công');
          await refreshOutlines();
          manualCreateForm.resetFields();
        } catch (error: unknown) {
          const err = error as Error;
          if (err.message === 'Số thứ tự trùng lặp') {
            // Lỗi trùng số thứ tự đã hiển thị Modal, không cần hiển thị message nữa
            throw error;
          }
          message.error('Tạo thất bại: ' + (err.message || 'Lỗi không xác định'));
          throw error;
        }
      }
    });
  };

  // Mở rộng một đề cương thành nhiều chương - gửi tác vụ nền và hiển thị tiến độ trong bảng tác vụ nổi
  const handleExpandOutline = async (outlineId: string, outlineTitle: string) => {
    try {
      setIsExpanding(true);

      // ✅ Mới: kiểm tra có cần mở rộng theo thứ tự không
      const currentOutline = sortedOutlines.find(o => o.id === outlineId);
      if (currentOutline) {
        // Lấy tất cả đề cương đứng trước đề cương hiện tại
        const previousOutlines = sortedOutlines.filter(
          o => o.order_index < currentOutline.order_index
        );

        // Kiểm tra các đề cương phía trước đã được mở rộng hết chưa
        for (const prevOutline of previousOutlines) {
          try {
            const prevChapters = await outlineApi.getOutlineChapters(prevOutline.id);
            if (!prevChapters.has_chapters) {
              // Nếu phía trước có đề cương chưa mở rộng, hiển thị nhắc nhở và chặn thao tác
              setIsExpanding(false);
              modalApi.warning({
                title: 'Vui lòng mở rộng đề cương theo thứ tự',
                width: 600,
                centered: true,
                content: (
                  <div>
                    <p style={{ marginBottom: 12 }}>
                      Để giữ tính liên tục của số chương và mạch nội dung, vui lòng mở rộng các đề cương phía trước trước.
                    </p>
                    <div style={{
                      padding: 12,
                      background: token.colorWarningBg,
                      borderRadius: token.borderRadius,
                      border: `1px solid ${token.colorWarningBorder}`
                    }}>
                      <div style={{ fontWeight: 500, marginBottom: 8, color: token.colorWarning }}>
                        ⚠️ Cần mở rộng trước:
                      </div>
                      <div style={{ color: token.colorTextSecondary }}>
                        Quyển {prevOutline.order_index}: 《{prevOutline.title}》
                      </div>
                    </div>
                    <p style={{ marginTop: 12, color: token.colorTextSecondary, fontSize: 13 }}>
                      💡 Mẹo: bạn cũng có thể dùng chức năng "Mở rộng hàng loạt", hệ thống sẽ tự động xử lý tất cả đề cương theo thứ tự.
                    </p>
                  </div>
                ),
                okText: 'Đã hiểu'
              });
              return;
            }
          } catch (error) {
            console.error(`Kiểm tra đề cương ${prevOutline.id} thất bại:`, error);
            // Nếu kiểm tra thất bại, tiếp tục xử lý (tránh bị chặn do sự cố mạng)
          }
        }
      }

      // Bước 1: kiểm tra đã có chương được mở rộng chưa
      const existingChapters = await outlineApi.getOutlineChapters(outlineId);

      if (existingChapters.has_chapters && existingChapters.expansion_plans && existingChapters.expansion_plans.length > 0) {
        // Nếu đã có chương, hiển thị thông tin kế hoạch mở rộng đã có
        setIsExpanding(false);
        showExistingExpansionPreview(outlineTitle, existingChapters);
        return;
      }

      // Nếu chưa có chương, hiển thị form mở rộng
      setIsExpanding(false);
      modalApi.confirm({
        title: (
          <Space>
            <BranchesOutlined />
            <span>Mở rộng đề cương thành nhiều chương</span>
          </Space>
        ),
        width: 600,
        centered: true,
        content: (
          <div>
            <div style={{ marginBottom: 16, padding: 12, background: token.colorBgLayout, borderRadius: token.borderRadius }}>
              <div style={{ fontWeight: 500, marginBottom: 4 }}>Tiêu đề đề cương</div>
              <div style={{ color: token.colorTextSecondary }}>{outlineTitle}</div>
            </div>
            <Form
              form={expansionForm}
              layout="vertical"
              initialValues={{
                target_chapter_count: 3,
                expansion_strategy: 'balanced',
              }}
            >
              <Form.Item
                label="Số chương mục tiêu"
                name="target_chapter_count"
                rules={[{ required: true, message: 'Vui lòng nhập số chương mục tiêu' }]}
                tooltip="Mở rộng đề cương này thành bao nhiêu chương nội dung"
              >
                <InputNumber
                  min={2}
                  max={10}
                  style={{ width: '100%' }}
                  placeholder="Gợi ý 2-5 chương"
                />
              </Form.Item>

              <Form.Item
                label="Chiến lược mở rộng"
                name="expansion_strategy"
                tooltip="Chọn cách phân bổ nội dung cho các chương"
              >
                <Radio.Group>
                  <Radio.Button value="balanced">Phân bổ cân bằng</Radio.Button>
                  <Radio.Button value="climax">Tập trung cao trào</Radio.Button>
                  <Radio.Button value="detail">Chi tiết phong phú</Radio.Button>
                </Radio.Group>
              </Form.Item>
            </Form>
          </div>
        ),
        okText: 'Gửi tác vụ nền',
        cancelText: 'Hủy',
        onOk: async () => {
          try {
            const values = await expansionForm.validateFields();

            Modal.destroyAll();
            setIsExpanding(true);

            const requestData = {
              ...values,
              auto_create_chapters: true,
              enable_scene_analysis: true
            };

            const response = await fetch(`/api/outlines/${outlineId}/expand-background`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(requestData),
            });

            if (!response.ok) {
              const err = await response.json().catch(() => ({ detail: response.statusText }));
              throw new Error(err.detail || 'Tạo tác vụ mở rộng đề cương thất bại');
            }

            message.success('Tác vụ mở rộng đề cương đã được gửi, có thể xem tiến độ tại bảng tác vụ góc dưới bên phải');
            eventBus.emit('background-task-created');
            setIsExpanding(false);

          } catch (error) {
            console.error('Mở rộng thất bại:', error);
            message.error(error instanceof Error ? error.message : 'Mở rộng thất bại');
            setIsExpanding(false);
          }
        },
      });
    } catch (error) {
      console.error('Kiểm tra chương thất bại:', error);
      message.error('Kiểm tra chương thất bại');
      setIsExpanding(false);
    }
  };

  // Xóa nội dung chương đã mở rộng (giữ lại đề cương)
  const handleDeleteExpandedChapters = async (outlineTitle: string, chapters: Array<{ id: string }>) => {
    try {
      // Dùng xóa tuần tự để tránh điều kiện đua tính số chữ do đồng thời gây ra
      // Xóa đồng thời khiến nhiều request cùng đọc số chữ dự án và trừ số chữ chương riêng, gây lỗi tính toán
      for (const chapter of chapters) {
        await chapterApi.deleteChapter(chapter.id);
      }

      message.success(`Đã xóa tất cả ${chapters.length} chương được mở rộng từ 《${outlineTitle}》`);
      await refreshOutlines();
      // Refresh thông tin dự án để cập nhật hiển thị số chữ
      if (currentProject?.id) {
        const updatedProject = await projectApi.getProject(currentProject.id);
        setCurrentProject(updatedProject);
      }
    } catch (error: unknown) {
      const apiError = error as ApiError;
      message.error(apiError.response?.data?.detail || 'Xóa chương thất bại');
    }
  };

  // Hiển thị kế hoạch mở rộng của chương đã tồn tại
  const showExistingExpansionPreview = (
    outlineTitle: string,
    data: {
      chapter_count: number;
      chapters: Array<{ id: string; chapter_number: number; title: string }>;
      expansion_plans: Array<{
        sub_index: number;
        title: string;
        plot_summary: string;
        key_events: string[];
        character_focus: string[];
        emotional_tone: string;
        narrative_goal: string;
        conflict_type: string;
        estimated_words: number;
        scenes?: Array<{
          location: string;
          characters: string[];
          purpose: string;
        }> | null;
      }> | null;
    }
  ) => {
    modalApi.info({
      title: (
        <Space style={{ flexWrap: 'wrap' }}>
          <CheckCircleOutlined style={{ color: token.colorSuccess }} />
          <span>Thông tin mở rộng của 《{outlineTitle}》</span>
        </Space>
      ),
      width: isMobile ? '95%' : 900,
      centered: true,
      style: isMobile ? {
        top: 20,
        maxWidth: 'calc(100vw - 16px)',
        margin: '0 8px'
      } : undefined,
      styles: {
        body: {
          maxHeight: isMobile ? 'calc(100vh - 200px)' : 'calc(80vh - 60px)',
          overflowY: 'auto',
          overflowX: 'hidden'
        }
      },
      footer: (
        <Space wrap style={{ width: '100%', justifyContent: isMobile ? 'center' : 'flex-end' }}>
          <Button
            danger
            icon={<DeleteOutlined />}
            onClick={() => {
              Modal.destroyAll();
              modalApi.confirm({
                title: 'Xác nhận xóa',
                icon: <ExclamationCircleOutlined />,
                centered: true,
                content: (
                  <div>
                    <p>Thao tác này sẽ xóa tất cả <strong>{data.chapter_count}</strong> chương được mở rộng từ đề cương 《{outlineTitle}》.</p>
                    <p style={{ color: token.colorPrimary, marginTop: 8 }}>
                      📝 Lưu ý: bản thân đề cương sẽ được giữ lại, bạn có thể mở rộng lại
                    </p>
                    <p style={{ color: token.colorError, marginTop: 8 }}>
                      ⚠️ Cảnh báo: nội dung chương sẽ bị xóa vĩnh viễn và không thể khôi phục!
                    </p>
                  </div>
                ),
                okText: 'Xác nhận xóa',
                okType: 'danger',
                cancelText: 'Hủy',
                onOk: () => handleDeleteExpandedChapters(outlineTitle, data.chapters || []),
              });
            }}
            block={isMobile}
            size={isMobile ? 'middle' : undefined}
          >
            Xóa tất cả chương đã mở rộng ({data.chapter_count} chương)
          </Button>
          <Button onClick={() => Modal.destroyAll()}>
            Đóng
          </Button>
        </Space>
      ),
      content: (
        <div>
          <div style={{ marginBottom: 16 }}>
            <Space wrap style={{ maxWidth: '100%' }}>
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
                Đề cương: {outlineTitle}
              </Tag>
              <Tag color="green">Số chương: {data.chapter_count}</Tag>
              <Tag color="orange">Đã tạo chương</Tag>
            </Space>
          </div>
          <Tabs
            defaultActiveKey="0"
            type="card"
            items={data.expansion_plans?.map((plan, idx) => ({
              key: idx.toString(),
              label: (
                <Space size="small" style={{ maxWidth: isMobile ? '150px' : 'none' }}>
                  <span
                    style={{
                      fontWeight: 500,
                      whiteSpace: isMobile ? 'normal' : 'nowrap',
                      wordBreak: isMobile ? 'break-word' : 'normal',
                      fontSize: isMobile ? 12 : 14
                    }}
                  >
                    {plan.sub_index}. {plan.title}
                  </span>
                </Space>
              ),
              children: (
                <div style={{ maxHeight: '500px', overflowY: 'auto', padding: '8px 0' }}>
                  <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                    <Card size="small" title="Thông tin cơ bản">
                      <Space wrap style={{ maxWidth: '100%' }}>
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
                          {plan.emotional_tone}
                        </Tag>
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
                          {plan.conflict_type}
                        </Tag>
                        <Tag color="green">Khoảng {plan.estimated_words} chữ</Tag>
                      </Space>
                    </Card>

                    <Card size="small" title="Tóm tắt tình tiết">
                      <div style={{
                        wordBreak: 'break-word',
                        whiteSpace: 'normal',
                        overflowWrap: 'break-word'
                      }}>
                        {plan.plot_summary}
                      </div>
                    </Card>

                    <Card size="small" title="Mục tiêu kể chuyện">
                      <div style={{
                        wordBreak: 'break-word',
                        whiteSpace: 'normal',
                        overflowWrap: 'break-word'
                      }}>
                        {plan.narrative_goal}
                      </div>
                    </Card>

                    <Card size="small" title="Sự kiện then chốt">
                      <Space direction="vertical" size="small" style={{ width: '100%' }}>
                        {plan.key_events.map((event, eventIdx) => (
                          <div
                            key={eventIdx}
                            style={{
                              wordBreak: 'break-word',
                              whiteSpace: 'normal',
                              overflowWrap: 'break-word'
                            }}
                          >
                            • {event}
                          </div>
                        ))}
                      </Space>
                    </Card>

                    <Card size="small" title="Nhân vật liên quan">
                      <Space wrap style={{ maxWidth: '100%' }}>
                        {plan.character_focus.map((char, charIdx) => (
                          <Tag
                            key={charIdx}
                            color="purple"
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
                    </Card>

                    {plan.scenes && plan.scenes.length > 0 && (
                      <Card size="small" title="Cảnh">
                        <Space direction="vertical" size="small" style={{ width: '100%' }}>
                          {plan.scenes.map((scene, sceneIdx) => (
                            <Card
                              key={sceneIdx}
                              size="small"
                              style={{
                                backgroundColor: token.colorFillQuaternary,
                                maxWidth: '100%',
                                overflow: 'hidden'
                              }}
                            >
                              <div style={{
                                wordBreak: 'break-word',
                                whiteSpace: 'normal',
                                overflowWrap: 'break-word'
                              }}>
                                <strong>Địa điểm:</strong>{scene.location}
                              </div>
                              <div style={{
                                wordBreak: 'break-word',
                                whiteSpace: 'normal',
                                overflowWrap: 'break-word'
                              }}>
                                <strong>Nhân vật:</strong>{scene.characters.join(', ')}
                              </div>
                              <div style={{
                                wordBreak: 'break-word',
                                whiteSpace: 'normal',
                                overflowWrap: 'break-word'
                              }}>
                                <strong>Mục đích:</strong>{scene.purpose}
                              </div>
                            </Card>
                          ))}
                        </Space>
                      </Card>
                    )
                    }
                  </Space>
                </div >
              )
            }))}
          />
        </div >
      ),
    });
  };

  // Mở rộng hàng loạt tất cả đề cương - gửi tác vụ nền và hiển thị tiến độ trong bảng tác vụ nổi
  const handleBatchExpandOutlines = () => {
    if (!currentProject?.id || outlines.length === 0) {
      message.warning('Không có đề cương nào để mở rộng');
      return;
    }

    modalApi.confirm({
      title: (
        <Space>
          <AppstoreAddOutlined />
          <span>Mở rộng hàng loạt tất cả đề cương</span>
        </Space>
      ),
      width: 600,
      centered: true,
      content: (
        <div>
          <div
            style={{
              marginBottom: 16,
              padding: 12,
              background: token.colorWarningBg,
              borderRadius: token.borderRadius,
              border: `1px solid ${token.colorWarningBorder}`,
            }}
          >
            <div style={{ color: token.colorWarningText }}>
              ⚠️ Sẽ mở rộng tất cả {outlines.length} đề cương của dự án hiện tại
            </div>
          </div>
          <Form
            form={batchExpansionForm}
            layout="vertical"
            initialValues={{
              chapters_per_outline: 3,
              expansion_strategy: 'balanced',
            }}
          >
            <Form.Item
              label="Số chương mở rộng mỗi đề cương"
              name="chapters_per_outline"
              rules={[{ required: true, message: 'Vui lòng nhập số chương' }]}
              tooltip="Mỗi đề cương sẽ được mở rộng thành bao nhiêu chương"
            >
              <InputNumber
                min={2}
                max={10}
                style={{ width: '100%' }}
                placeholder="Gợi ý 2-5 chương"
              />
            </Form.Item>

            <Form.Item
              label="Chiến lược mở rộng"
              name="expansion_strategy"
            >
              <Radio.Group>
                <Radio.Button value="balanced">Phân bổ cân bằng</Radio.Button>
                <Radio.Button value="climax">Tập trung cao trào</Radio.Button>
                <Radio.Button value="detail">Chi tiết phong phú</Radio.Button>
              </Radio.Group>
            </Form.Item>
          </Form>
        </div>
      ),
      okText: 'Gửi tác vụ nền',
      cancelText: 'Hủy',
      okButtonProps: { type: 'primary' },
      onOk: async () => {
        try {
          const values = await batchExpansionForm.validateFields();

          Modal.destroyAll();
          setIsExpanding(true);

          const requestData = {
            project_id: currentProject.id,
            ...values,
            auto_create_chapters: true,
            enable_scene_analysis: true
          };

          const response = await fetch('/api/outlines/batch-expand-background', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestData),
          });

          if (!response.ok) {
            const err = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(err.detail || 'Tạo tác vụ mở rộng hàng loạt thất bại');
          }

          message.success('Tác vụ mở rộng hàng loạt đã được gửi, có thể xem tiến độ tại bảng tác vụ góc dưới bên phải');
          eventBus.emit('background-task-created');
          setIsExpanding(false);

        } catch (error) {
          console.error('Mở rộng hàng loạt thất bại:', error);
          message.error(error instanceof Error ? error.message : 'Mở rộng hàng loạt thất bại');
          setIsExpanding(false);
        }
      },
    });
  };

  const resetImportDialog = () => {
    setImportFile(null);
    setImportMode('append');
    setImportPreview(null);
    setIsPreviewingImport(false);
  };

  const handleExportOutlines = async () => {
    if (!currentProject?.id) return;
    setIsExporting(true);
    try {
      await outlineApi.exportOutlines(currentProject.id);
      message.success(`Đã xuất ${outlines.length} đề cương`);
    } catch (error) {
      console.error('Xuất đề cương thất bại:', error);
      message.error('Xuất đề cương thất bại, vui lòng thử lại sau');
    } finally {
      setIsExporting(false);
    }
  };

  const handlePreviewImport = async () => {
    if (!currentProject?.id || !importFile) {
      message.warning('Vui lòng chọn file JSON cần nhập trước');
      return;
    }

    setIsPreviewingImport(true);
    setImportPreview(null);
    try {
      const preview = await outlineApi.previewImport(currentProject.id, importMode, importFile);
      setImportPreview(preview);
    } catch (error) {
      console.error('Xem trước nhập đề cương thất bại:', error);
    } finally {
      setIsPreviewingImport(false);
    }
  };

  const handleConfirmImport = async () => {
    if (!currentProject?.id || !importFile || !importPreview?.valid) return;

    setIsImporting(true);
    try {
      const result = await outlineApi.importOutlines(currentProject.id, importMode, importFile);
      const chapterMessage = result.created_chapters > 0
        ? `, đồng thời tạo ${result.created_chapters} chương`
        : '';
      message.success(`${result.message}${chapterMessage}`);
      setImportModalOpen(false);
      resetImportDialog();
      await refreshOutlines();
      if (result.created_chapters > 0) {
        eventBus.emit(EventNames.CHAPTER_NEEDS_REFRESH);
      }
    } catch (error) {
      console.error('Nhập đề cương thất bại:', error);
      setImportPreview(null);
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <>
      {contextHolder}

      <Modal
        title="Nhập đề cương"
        open={importModalOpen}
        width={680}
        okText="Xác nhận nhập"
        cancelText="Hủy"
        confirmLoading={isImporting}
        okButtonProps={{ disabled: !importPreview?.valid || isPreviewingImport }}
        maskClosable={!isImporting}
        closable={!isImporting}
        onOk={handleConfirmImport}
        onCancel={() => {
          if (isImporting) return;
          setImportModalOpen(false);
          resetImportDialog();
        }}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Alert
            type="info"
            showIcon
            message="Hỗ trợ file xuất đề cương, cũng hỗ trợ trích xuất đề cương từ file xuất toàn bộ dự án. File phải ở định dạng JSON, tối đa 10MB."
          />

          <div>
            <div style={{ marginBottom: 8, fontWeight: 500 }}>1. Chọn file</div>
            <Upload
              accept=".json,application/json"
              maxCount={1}
              fileList={importFile ? [{
                uid: 'outline-import-file',
                name: importFile.name,
                size: importFile.size,
                type: importFile.type,
                status: 'done',
              }] : []}
              beforeUpload={(file) => {
                if (!file.name.toLowerCase().endsWith('.json')) {
                  message.error('Chỉ hỗ trợ file định dạng JSON');
                  return Upload.LIST_IGNORE;
                }
                if (file.size > 10 * 1024 * 1024) {
                  message.error('Kích thước file không được vượt quá 10MB');
                  return Upload.LIST_IGNORE;
                }
                setImportFile(file);
                setImportPreview(null);
                return false;
              }}
              onRemove={() => {
                setImportFile(null);
                setImportPreview(null);
                return true;
              }}
            >
              <Button icon={<UploadOutlined />}>Chọn file JSON</Button>
            </Upload>
          </div>

          <div>
            <div style={{ marginBottom: 8, fontWeight: 500 }}>2. Chọn cách nhập</div>
            <Radio.Group
              value={importMode}
              onChange={(event) => {
                setImportMode(event.target.value as OutlineImportMode);
                setImportPreview(null);
              }}
            >
              <Space direction="vertical">
                <Radio value="append">Thêm vào cuối: thêm mới từ cuối hiện tại, tự động đánh lại số</Radio>
                <Radio value="merge">Gộp theo số thứ tự: số thứ tự trùng thì cập nhật, khác thì thêm mới</Radio>
              </Space>
            </Radio.Group>
          </div>

          <Button
            type="primary"
            ghost
            icon={<FileTextOutlined />}
            disabled={!importFile}
            loading={isPreviewingImport}
            onClick={handlePreviewImport}
          >
            Xem trước kết quả nhập
          </Button>

          {importPreview && (
            <>
              <Divider style={{ margin: '4px 0' }} />
              <Alert
                type={importPreview.valid ? 'success' : 'error'}
                showIcon
                message={importPreview.valid ? 'File hợp lệ' : 'File không hợp lệ'}
                description={
                  <Space direction="vertical" size={4} style={{ width: '100%' }}>
                    <div>
                      Phiên bản định dạng file: {importPreview.version || 'Không rõ'}
                      {importPreview.source_project?.title && ` · Dự án nguồn: ${importPreview.source_project.title}`}
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                      <Tag>Tổng {importPreview.statistics.total} mục</Tag>
                      <Tag color="green">Thêm mới {importPreview.statistics.will_create} mục</Tag>
                      <Tag color="blue">Cập nhật {importPreview.statistics.will_update} mục</Tag>
                      {importPreview.target_outline_mode === 'one-to-one' && (
                        <Tag color="purple">Tạo {importPreview.statistics.will_create_chapters} chương</Tag>
                      )}
                    </div>
                  </Space>
                }
              />

              {importPreview.errors.length > 0 && (
                <Alert
                  type="error"
                  showIcon
                  message="Không thể nhập"
                  description={
                    <ul style={{ margin: 0, paddingLeft: 20 }}>
                      {importPreview.errors.map((error, index) => <li key={`${index}-${error}`}>{error}</li>)}
                    </ul>
                  }
                />
              )}

              {importPreview.warnings.length > 0 && (
                <Alert
                  type="warning"
                  showIcon
                  message="Lưu ý"
                  description={
                    <ul style={{ margin: 0, paddingLeft: 20 }}>
                      {importPreview.warnings.map((warning, index) => <li key={`${index}-${warning}`}>{warning}</li>)}
                    </ul>
                  }
                />
              )}
            </>
          )}
        </Space>
      </Modal>

      <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        {/* Header cố định */}
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
              <FileTextOutlined style={{ marginRight: 8 }} />
              Đề cương truyện
            </h2>
            {currentProject?.outline_mode && (
              <Tag color={currentProject.outline_mode === 'one-to-one' ? 'blue' : 'green'} style={{ width: 'fit-content' }}>
                {currentProject.outline_mode === 'one-to-one' ? 'Chế độ truyền thống (1→1)' : 'Chế độ chi tiết (1→N)'}
              </Tag>
            )}
          </div>
          <Space size="small" wrap={isMobile}>
            <Input.Search
              allowClear
              placeholder="Tìm kiếm đề cương (số thứ tự/tiêu đề/nội dung)"
              value={outlineSearchKeyword}
              onChange={(e) => setOutlineSearchKeyword(e.target.value)}
              style={{ width: isMobile ? '100%' : 280 }}
            />
            <Button
              icon={<UploadOutlined />}
              onClick={() => {
                resetImportDialog();
                setImportModalOpen(true);
              }}
              block={isMobile}
            >
              Nhập đề cương
            </Button>
            <Button
              icon={<DownloadOutlined />}
              onClick={handleExportOutlines}
              loading={isExporting}
              disabled={outlines.length === 0}
              block={isMobile}
            >
              Xuất đề cương
            </Button>
            <Button
              icon={<PlusOutlined />}
              onClick={showManualCreateOutlineModal}
              block={isMobile}
            >
              Tạo thủ công
            </Button>
            <Button
              type="primary"
              icon={<ThunderboltOutlined />}
              onClick={showGenerateModal}
              loading={isGenerating}
              block={isMobile}
            >
              {isMobile ? 'AI tạo/viết tiếp' : 'AI tạo/viết tiếp đề cương'}
            </Button>
            {outlines.length > 0 && currentProject?.outline_mode === 'one-to-many' && (
              <Button
                icon={<AppstoreAddOutlined />}
                onClick={handleBatchExpandOutlines}
                loading={isExpanding}
                disabled={isGenerating}
                title="Mở rộng tất cả đề cương thành nhiều chương, tạo quan hệ một-nhiều từ đề cương đến chương"
              >
                {isMobile ? 'Mở rộng hàng loạt' : 'Mở rộng hàng loạt thành nhiều chương'}
              </Button>
            )}
          </Space>
        </div>

        {/* Khu vực nội dung cuộn được */}
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {outlines.length === 0 ? (
            <Empty description="Chưa có đề cương, bắt đầu tạo nhé!" />
          ) : filteredOutlines.length === 0 ? (
            <Empty description="Không tìm thấy đề cương phù hợp" />
          ) : (
            <List
              dataSource={pagedOutlines}
              renderItem={(item) => {
                  const structureData = outlineStructureMap[item.id] || {};

                  // Phân tích mục nhân vật/tổ chức (tương thích định dạng cũ/mới)
                  const characterEntries = parseCharacterEntries(structureData.characters);
                  const characterNames = getCharacterNames(characterEntries);
                  const organizationNames = getOrganizationNames(characterEntries);
                  const isOutlineExpanded = outlineContentExpandStatus[item.id] || false;
                  const previewContent = getOutlinePreview(item.content, isMobile ? 70 : 140);
                  
                  return (
                    <List.Item
                      style={{
                        marginBottom: 16,
                        padding: 0,
                        border: 'none'
                      }}
                    >
                      <Card
                        style={{
                          width: '100%',
                          borderRadius: isMobile ? 6 : 8,
                          border: `1px solid ${token.colorBorderSecondary}`,
                          boxShadow: `0 1px 2px ${alphaColor(token.colorTextBase, 0.08)}`,
                          transition: 'all 0.3s ease'
                        }}
                        bodyStyle={{
                          padding: isMobile ? '10px 12px' : 16
                        }}
                        onMouseEnter={(e) => {
                          if (!isMobile) {
                            e.currentTarget.style.boxShadow = `0 4px 12px ${alphaColor(token.colorTextBase, 0.16)}`;
                            e.currentTarget.style.borderColor = token.colorPrimary;
                          }
                        }}
                        onMouseLeave={(e) => {
                          if (!isMobile) {
                            e.currentTarget.style.boxShadow = `0 1px 2px ${alphaColor(token.colorTextBase, 0.08)}`;
                            e.currentTarget.style.borderColor = token.colorBorderSecondary;
                          }
                        }}
                      >
                        <List.Item.Meta
                          style={{ width: '100%' }}
                          title={
                            <Space size="small" style={{ fontSize: isMobile ? 13 : 16, flexWrap: 'wrap', lineHeight: isMobile ? '1.4' : '1.5' }}>
                              <span style={{ color: token.colorPrimary, fontWeight: 'bold', fontSize: isMobile ? 13 : 16 }}>
                                {currentProject?.outline_mode === 'one-to-one'
                                  ? `Chương ${item.order_index || '?'}`
                                  : `Quyển ${item.order_index || '?'}`
                                }
                              </span>
                              <span style={{ fontSize: isMobile ? 13 : 16 }}>{item.title}</span>
                              {/* ✅ Mới: đánh dấu trạng thái mở rộng - chỉ hiển thị ở chế độ một-nhiều */}
                              {currentProject?.outline_mode === 'one-to-many' && (
                                outlineExpandStatus[item.id] ? (
                                  <Tag color="success" icon={<CheckCircleOutlined />} style={{ fontSize: isMobile ? 11 : 12 }}>Đã mở rộng</Tag>
                                ) : (
                                  <Tag color="default" style={{ fontSize: isMobile ? 11 : 12 }}>Chưa mở rộng</Tag>
                                )
                              )}
                            </Space>
                          }
                          description={
                            <div style={{ fontSize: isMobile ? 12 : 14, lineHeight: isMobile ? '1.5' : '1.6' }}>
                              {/* Nội dung đề cương */}
                              <div style={{
                                marginBottom: isMobile ? 10 : 12,
                                padding: isMobile ? '8px 10px' : '10px 12px',
                                background: token.colorFillQuaternary,
                                borderLeft: `3px solid ${token.colorBorderSecondary}`,
                                borderRadius: token.borderRadius,
                                fontSize: isMobile ? 12 : 13,
                                color: token.colorText,
                                lineHeight: '1.6'
                              }}>
                                <div style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'space-between',
                                  gap: 8,
                                  marginBottom: isMobile ? 4 : 6,
                                  flexWrap: isMobile ? 'wrap' : 'nowrap'
                                }}>
                                  <div style={{
                                    fontWeight: 600,
                                    color: token.colorTextSecondary,
                                    fontSize: isMobile ? 12 : 13
                                  }}>
                                    📝 Nội dung đề cương
                                  </div>
                                  <Button
                                    type="link"
                                    size="small"
                                    onClick={() => setOutlineContentExpandStatus(prev => ({
                                      ...prev,
                                      [item.id]: !isOutlineExpanded
                                    }))}
                                    style={{
                                      padding: 0,
                                      height: 'auto',
                                      fontSize: isMobile ? 12 : 13
                                    }}
                                  >
                                    {isOutlineExpanded ? 'Thu gọn' : 'Mở rộng'}
                                  </Button>
                                </div>
                                <div style={{
                                  padding: isMobile ? '6px 8px' : '6px 10px',
                                  background: token.colorBgContainer,
                                  border: `1px solid ${token.colorBorder}`,
                                  borderRadius: token.borderRadiusSM,
                                  fontSize: isMobile ? 12 : 13,
                                  color: token.colorText,
                                  lineHeight: '1.8',
                                  whiteSpace: isOutlineExpanded ? 'pre-wrap' : 'normal',
                                  wordBreak: 'break-word'
                                }}>
                                  {isOutlineExpanded ? item.content : previewContent.text || 'Chưa có nội dung'}
                                </div>
                              </div>

                              {isOutlineExpanded && (
                                <>
                              {/* ✨ Hiển thị nhân vật liên quan - bản tối ưu (hỗ trợ hiển thị phân loại nhân vật/tổ chức) */}
                              {characterNames.length > 0 && (
                                <div style={{
                                  marginTop: isMobile ? 10 : 12,
                                  padding: isMobile ? '8px 10px' : '10px 12px',
                                  background: token.colorPrimaryBg,
                                  borderLeft: `3px solid ${token.colorPrimary}`,
                                  borderRadius: token.borderRadius
                                }}>
                                  <div style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: isMobile ? 6 : 8,
                                    marginBottom: isMobile ? 6 : 8
                                  }}>
                                    <span style={{
                                      fontSize: isMobile ? 12 : 13,
                                      fontWeight: 600,
                                      color: token.colorPrimary,
                                      display: 'flex',
                                      alignItems: 'center',
                                      gap: 4
                                    }}>
                                      👥 Nhân vật liên quan
                                      <Tag
                                        color="purple"
                                        style={{
                                          margin: 0,
                                          fontSize: 10,
                                          borderRadius: 10,
                                          padding: '0 6px'
                                        }}
                                      >
                                        {characterNames.length}
                                      </Tag>
                                    </span>
                                  </div>
                                  <Space wrap size={[4, 4]}>
                                    {characterNames.map((name, idx) => (
                                      <Tag
                                        key={idx}
                                        color="purple"
                                        style={{
                                          margin: 0,
                                          borderRadius: 4,
                                          padding: isMobile ? '2px 8px' : '3px 10px',
                                          fontSize: isMobile ? 11 : 12,
                                          fontWeight: 500,
                                          border: `1px solid ${token.colorPrimaryBorder}`,
                                          background: token.colorBgContainer,
                                          color: token.colorPrimary,
                                          whiteSpace: 'normal',
                                          wordBreak: 'break-word',
                                          height: 'auto',
                                          lineHeight: '1.5'
                                        }}
                                      >
                                        {name}
                                      </Tag>
                                    ))}
                                  </Space>
                                </div>
                              )}
                              
                              {/* 🏛️ Hiển thị tổ chức liên quan */}
                              {organizationNames.length > 0 && (
                                <div style={{
                                  marginTop: isMobile ? 10 : 12,
                                  padding: isMobile ? '8px 10px' : '10px 12px',
                                  background: token.colorWarningBg,
                                  borderLeft: `3px solid ${token.colorWarning}`,
                                  borderRadius: token.borderRadius
                                }}>
                                  <div style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: isMobile ? 6 : 8,
                                    marginBottom: isMobile ? 6 : 8
                                  }}>
                                    <span style={{
                                      fontSize: isMobile ? 12 : 13,
                                      fontWeight: 600,
                                      color: token.colorWarning,
                                      display: 'flex',
                                      alignItems: 'center',
                                      gap: 4
                                    }}>
                                      🏛️ Tổ chức liên quan
                                      <Tag
                                        color="orange"
                                        style={{
                                          margin: 0,
                                          fontSize: 10,
                                          borderRadius: 10,
                                          padding: '0 6px'
                                        }}
                                      >
                                        {organizationNames.length}
                                      </Tag>
                                    </span>
                                  </div>
                                  <Space wrap size={[4, 4]}>
                                    {organizationNames.map((name, idx) => (
                                      <Tag
                                        key={idx}
                                        color="orange"
                                        style={{
                                          margin: 0,
                                          borderRadius: 4,
                                          padding: isMobile ? '2px 8px' : '3px 10px',
                                          fontSize: isMobile ? 11 : 12,
                                          fontWeight: 500,
                                          border: `1px solid ${token.colorWarningBorder}`,
                                          background: token.colorBgContainer,
                                          color: token.colorWarning,
                                          whiteSpace: 'normal',
                                          wordBreak: 'break-word',
                                          height: 'auto',
                                          lineHeight: '1.5'
                                        }}
                                      >
                                        {name}
                                      </Tag>
                                    ))}
                                  </Space>
                                </div>
                              )}
                              
                              {/* ✨ Hiển thị thông tin cảnh - bản tối ưu (hỗ trợ thu gọn, hiển thị tối đa 3) */}
                              {structureData.scenes && structureData.scenes.length > 0 ? (() => {
                                const isExpanded = scenesExpandStatus[item.id] || false;
                                const maxVisibleScenes = 4;
                                const hasMoreScenes = structureData.scenes!.length > maxVisibleScenes;
                                const visibleScenes = isExpanded ? structureData.scenes : structureData.scenes!.slice(0, maxVisibleScenes);
                                
                                return (
                                  <div style={{
                                    marginTop: isMobile ? 10 : 12,
                                    padding: isMobile ? '8px 10px' : '10px 12px',
                                    background: token.colorInfoBg,
                                    borderLeft: `3px solid ${token.colorInfo}`,
                                    borderRadius: token.borderRadius
                                  }}>
                                    <div style={{
                                      display: 'flex',
                                      alignItems: 'center',
                                      justifyContent: 'space-between',
                                      marginBottom: isMobile ? 6 : 8,
                                      flexWrap: isMobile ? 'wrap' : 'nowrap',
                                      gap: isMobile ? 4 : 0
                                    }}>
                                      <span style={{
                                        fontSize: isMobile ? 12 : 13,
                                        fontWeight: 600,
                                        color: token.colorInfo,
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: 4
                                      }}>
                                        🎬 Thiết lập cảnh
                                        <Tag
                                          color="cyan"
                                          style={{
                                            margin: 0,
                                            fontSize: 10,
                                            borderRadius: 10,
                                            padding: '0 6px'
                                          }}
                                        >
                                          {structureData.scenes!.length}
                                        </Tag>
                                      </span>
                                      {hasMoreScenes && (
                                        <Button
                                          type="text"
                                          size="small"
                                          onClick={() => setScenesExpandStatus(prev => ({
                                            ...prev,
                                            [item.id]: !isExpanded
                                          }))}
                                          style={{
                                            fontSize: isMobile ? 10 : 11,
                                            height: isMobile ? 20 : 22,
                                            padding: isMobile ? '0 6px' : '0 8px',
                                            color: token.colorInfo
                                          }}
                                        >
                                          {isExpanded ? 'Thu gọn ▲' : `Mở rộng (${structureData.scenes!.length - maxVisibleScenes}+) ▼`}
                                        </Button>
                                      )}
                                    </div>
                                    {/* Dùng layout grid, mobile một cột, desktop hai cột */}
                                    <div style={{
                                      display: 'grid',
                                      gridTemplateColumns: isMobile ? '1fr' : 'repeat(auto-fill, minmax(280px, 1fr))',
                                      gap: isMobile ? 6 : 8,
                                      width: '100%',
                                      minWidth: 0  // Ngăn phần tử con của grid bị tràn
                                    }}>
                                      {visibleScenes!.map((scene, idx) => {
                                      // Xác định là chuỗi hay đối tượng
                                      if (typeof scene === 'string') {
                                        // Định dạng chuỗi: thẻ gọn
                                        return (
                                          <div
                                            key={idx}
                                            style={{
                                              padding: isMobile ? '6px 8px' : '8px 10px',
                                              background: token.colorBgContainer,
                                              border: `1px solid ${token.colorInfoBorder}`,
                                              borderRadius: token.borderRadius,
                                              fontSize: isMobile ? 11 : 12,
                                              color: token.colorText,
                                              display: 'flex',
                                              alignItems: 'flex-start',
                                              gap: isMobile ? 6 : 8,
                                              transition: 'all 0.2s ease',
                                              cursor: 'default',
                                              width: '100%',
                                              minWidth: 0,
                                              boxSizing: 'border-box'
                                            }}
                                            onMouseEnter={(e) => {
                                              if (!isMobile) {
                                                e.currentTarget.style.borderColor = token.colorInfo;
                                                e.currentTarget.style.boxShadow = `0 2px 8px ${alphaColor(token.colorInfo, 0.25)}`;
                                              }
                                            }}
                                            onMouseLeave={(e) => {
                                              if (!isMobile) {
                                                e.currentTarget.style.borderColor = token.colorInfoBorder;
                                                e.currentTarget.style.boxShadow = 'none';
                                              }
                                            }}
                                          >
                                            <Tag
                                              color="cyan"
                                              style={{
                                                margin: 0,
                                                fontSize: 10,
                                                borderRadius: 4,
                                                flexShrink: 0
                                              }}
                                            >
                                              {idx + 1}
                                            </Tag>
                                            <span style={{
                                              flex: 1,
                                              lineHeight: '1.6',
                                              overflow: 'hidden',
                                              textOverflow: 'ellipsis',
                                              whiteSpace: 'nowrap'
                                            }}>{scene}</span>
                                          </div>
                                        );
                                      } else {
                                        // Định dạng đối tượng: thẻ chi tiết
                                        return (
                                          <div
                                            key={idx}
                                            style={{
                                              padding: isMobile ? '8px 10px' : '10px 12px',
                                              background: token.colorBgContainer,
                                              border: `1px solid ${token.colorInfoBorder}`,
                                              borderRadius: token.borderRadius,
                                              fontSize: isMobile ? 11 : 12,
                                              transition: 'all 0.2s ease',
                                              cursor: 'default',
                                              width: '100%',
                                              minWidth: 0,
                                              boxSizing: 'border-box'
                                            }}
                                            onMouseEnter={(e) => {
                                              if (!isMobile) {
                                                e.currentTarget.style.borderColor = token.colorInfo;
                                                e.currentTarget.style.boxShadow = `0 2px 8px ${alphaColor(token.colorInfo, 0.25)}`;
                                              }
                                            }}
                                            onMouseLeave={(e) => {
                                              if (!isMobile) {
                                                e.currentTarget.style.borderColor = token.colorInfoBorder;
                                                e.currentTarget.style.boxShadow = 'none';
                                              }
                                            }}
                                          >
                                            <div style={{
                                              display: 'flex',
                                              alignItems: 'center',
                                              gap: isMobile ? 6 : 8,
                                              marginBottom: isMobile ? 4 : 6,
                                              flexWrap: 'wrap'
                                            }}>
                                              <Tag
                                                color="cyan"
                                                style={{
                                                  margin: 0,
                                                  fontSize: 10,
                                                  borderRadius: 4
                                                }}
                                              >
                                                Cảnh {idx + 1}
                                              </Tag>
                                              <span style={{
                                                fontWeight: 600,
                                                color: token.colorText,
                                                fontSize: isMobile ? 12 : 13,
                                                flex: 1,
                                                overflow: 'hidden',
                                                textOverflow: 'ellipsis',
                                                whiteSpace: 'nowrap'
                                              }}>
                                                📍 {scene.location}
                                              </span>
                                            </div>
                                            {scene.characters && scene.characters.length > 0 && (
                                              <div style={{
                                                fontSize: isMobile ? 10 : 11,
                                                color: token.colorTextSecondary,
                                                marginBottom: 4,
                                                paddingLeft: isMobile ? 2 : 4,
                                                overflow: 'hidden',
                                                textOverflow: 'ellipsis',
                                                whiteSpace: 'nowrap'
                                              }}>
                                                <span style={{ fontWeight: 500 }}>👤 Nhân vật:</span>
                                                {scene.characters.join(' · ')}
                                              </div>
                                            )}
                                            {scene.purpose && (
                                              <div style={{
                                                fontSize: isMobile ? 10 : 11,
                                                color: token.colorTextSecondary,
                                                paddingLeft: isMobile ? 2 : 4,
                                                lineHeight: '1.5',
                                                overflow: 'hidden',
                                                textOverflow: 'ellipsis',
                                                whiteSpace: 'nowrap'
                                              }}>
                                                <span style={{ fontWeight: 500 }}>🎯 Mục đích:</span>
                                                {scene.purpose}
                                              </div>
                                            )}
                                          </div>
                                        );
                                      }
                                      })}
                                    </div>
                                  </div>
                                );
                              })() : null}
                            
                            {/* ✨ Hiển thị sự kiện then chốt */}
                            {structureData.key_events && structureData.key_events.length > 0 && (
                              <div style={{
                                marginTop: 12,
                                padding: '10px 12px',
                                background: token.colorWarningBg,
                                borderLeft: `3px solid ${token.colorWarning}`,
                                borderRadius: token.borderRadius
                              }}>
                                <div style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: 8,
                                  marginBottom: 8
                                }}>
                                  <span style={{
                                    fontSize: 13,
                                    fontWeight: 600,
                                    color: token.colorWarning,
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 4
                                  }}>
                                    ⚡ Sự kiện then chốt
                                    <Tag
                                      color="orange"
                                      style={{
                                        margin: 0,
                                        fontSize: 11,
                                        borderRadius: 10,
                                        padding: '0 6px'
                                      }}
                                    >
                                      {structureData.key_events.length}
                                    </Tag>
                                  </span>
                                </div>
                                <Space direction="vertical" size={6} style={{ width: '100%' }}>
                                  {structureData.key_events.map((event, idx) => (
                                    <div
                                      key={idx}
                                      style={{
                                        padding: '6px 10px',
                                        background: token.colorBgContainer,
                                        border: `1px solid ${token.colorWarningBorder}`,
                                        borderRadius: token.borderRadiusSM,
                                        fontSize: 12,
                                        color: token.colorWarningText,
                                        display: 'flex',
                                        alignItems: 'flex-start',
                                        gap: 8
                                      }}
                                    >
                                      <Tag
                                        color="orange"
                                        style={{
                                          margin: 0,
                                          fontSize: 11,
                                          borderRadius: 4,
                                          flexShrink: 0
                                        }}
                                      >
                                        {idx + 1}
                                      </Tag>
                                      <span style={{
                                        flex: 1,
                                        lineHeight: '1.6',
                                        overflow: 'hidden',
                                        textOverflow: 'ellipsis',
                                        whiteSpace: 'nowrap'
                                      }}>{event}</span>
                                    </div>
                                  ))}
                                </Space>
                              </div>
                            )}
                            
                            {/* ✨ Hiển thị điểm nhấn tình tiết (key_points) */}
                            {structureData.key_points && structureData.key_points.length > 0 && (
                              <div style={{
                                marginTop: 12,
                                padding: '10px 12px',
                                background: token.colorSuccessBg,
                                borderLeft: `3px solid ${token.colorSuccess}`,
                                borderRadius: token.borderRadius
                              }}>
                                <div style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: 8,
                                  marginBottom: 8
                                }}>
                                  <span style={{
                                    fontSize: 13,
                                    fontWeight: 600,
                                    color: token.colorSuccess,
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 4
                                  }}>
                                    💡 Điểm nhấn tình tiết
                                    <Tag
                                      color="green"
                                      style={{
                                        margin: 0,
                                        fontSize: 11,
                                        borderRadius: 10,
                                        padding: '0 6px'
                                      }}
                                    >
                                      {structureData.key_points.length}
                                    </Tag>
                                  </span>
                                </div>
                                {/* Dùng layout grid, mobile một cột, desktop hai cột */}
                                <div style={{
                                  display: 'grid',
                                  gridTemplateColumns: isMobile ? '1fr' : 'repeat(auto-fill, minmax(280px, 1fr))',
                                  gap: isMobile ? 6 : 8,
                                  width: '100%',
                                  minWidth: 0
                                }}>
                                  {structureData.key_points.map((point, idx) => (
                                    <div
                                      key={idx}
                                      style={{
                                        padding: isMobile ? '6px 8px' : '8px 10px',
                                        background: token.colorBgContainer,
                                        border: `1px solid ${token.colorSuccessBorder}`,
                                        borderRadius: token.borderRadius,
                                        fontSize: isMobile ? 11 : 12,
                                        color: token.colorText,
                                        display: 'flex',
                                        alignItems: 'flex-start',
                                        gap: isMobile ? 6 : 8,
                                        transition: 'all 0.2s ease',
                                        cursor: 'default',
                                        width: '100%',
                                        minWidth: 0,
                                        boxSizing: 'border-box'
                                      }}
                                      onMouseEnter={(e) => {
                                        if (!isMobile) {
                                          e.currentTarget.style.borderColor = token.colorSuccess;
                                          e.currentTarget.style.boxShadow = `0 2px 8px ${alphaColor(token.colorSuccess, 0.25)}`;
                                        }
                                      }}
                                      onMouseLeave={(e) => {
                                        if (!isMobile) {
                                          e.currentTarget.style.borderColor = token.colorSuccessBorder;
                                          e.currentTarget.style.boxShadow = 'none';
                                        }
                                      }}
                                    >
                                      <Tag
                                        color="green"
                                        style={{
                                          margin: 0,
                                          fontSize: 10,
                                          borderRadius: 4,
                                          flexShrink: 0
                                        }}
                                      >
                                        {idx + 1}
                                      </Tag>
                                      <span style={{
                                        flex: 1,
                                        lineHeight: '1.6',
                                        overflow: 'hidden',
                                        textOverflow: 'ellipsis',
                                        whiteSpace: 'nowrap'
                                      }}>{point}</span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                            
                            {/* ✨ Hiển thị tông cảm xúc (emotion) */}
                            {structureData.emotion && (
                              <div style={{
                                marginTop: 12,
                                padding: '10px 12px',
                                background: token.colorWarningBg,
                                borderLeft: `3px solid ${token.colorWarning}`,
                                borderRadius: token.borderRadius,
                                display: 'flex',
                                alignItems: 'center',
                                gap: 8
                              }}>
                                <span style={{
                                  fontSize: 13,
                                  fontWeight: 600,
                                  color: token.colorWarning
                                }}>
                                  💫 Tông cảm xúc:
                                </span>
                                <Tag
                                  color="gold"
                                  style={{
                                    margin: 0,
                                    fontSize: 12,
                                    padding: '2px 12px',
                                    borderRadius: 12,
                                    background: token.colorBgContainer,
                                    border: `1px solid ${token.colorWarningBorder}`,
                                    color: token.colorWarningText
                                  }}
                                >
                                  {structureData.emotion}
                                </Tag>
                              </div>
                            )}
                            
                            {/* ✨ Hiển thị mục tiêu kể chuyện (goal) */}
                            {structureData.goal && (
                              <div style={{
                                marginTop: 12,
                                padding: '10px 12px',
                                background: token.colorInfoBg,
                                borderLeft: `3px solid ${token.colorInfo}`,
                                borderRadius: token.borderRadius
                              }}>
                                <div style={{
                                  fontSize: 13,
                                  fontWeight: 600,
                                  color: token.colorInfo,
                                  marginBottom: 6
                                }}>
                                  🎯 Mục tiêu kể chuyện
                                </div>
                                <div style={{
                                  fontSize: 12,
                                  color: token.colorText,
                                  lineHeight: '1.6',
                                  padding: '6px 10px',
                                  background: token.colorBgContainer,
                                  border: `1px solid ${token.colorInfoBorder}`,
                                  borderRadius: token.borderRadiusSM,
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                  whiteSpace: 'nowrap'
                                }}>
                                  {structureData.goal}
                                </div>
                              </div>
                            )}
                              </>
                            )}
                          </div>
                        }
                      />
                        
                        {/* Khu vực nút thao tác - bên trong thẻ */}
                        <div style={{
                          marginTop: 16,
                          paddingTop: 12,
                          borderTop: `1px solid ${token.colorBorderSecondary}`,
                          display: 'flex',
                          justifyContent: 'flex-end',
                          gap: 8
                        }}>
                          {currentProject?.outline_mode === 'one-to-many' && (
                            <Button
                              icon={<BranchesOutlined />}
                              onClick={() => handleExpandOutline(item.id, item.title)}
                              loading={isExpanding}
                              size={isMobile ? 'middle' : 'small'}
                            >
                              Mở rộng
                            </Button>
                          )}
                          <Button
                            icon={<EditOutlined />}
                            onClick={() => handleOpenEditModal(item.id)}
                            size={isMobile ? 'middle' : 'small'}
                          >
                            Chỉnh sửa
                          </Button>
                          <Popconfirm
                            title="Chắc chắn xóa đề cương này chứ?"
                            onConfirm={() => handleDeleteOutline(item.id)}
                            okText="Xác nhận"
                            cancelText="Hủy"
                          >
                            <Button
                              danger
                              icon={<DeleteOutlined />}
                              size={isMobile ? 'middle' : 'small'}
                            >
                              Xóa
                            </Button>
                          </Popconfirm>
                        </div>
                      </Card>
                    </List.Item>
                  );
                }}
              />
          )}

        </div>

        {/* Thanh phân trang cố định dưới cùng */}
        {outlines.length > 0 && (
          <div
            style={{
              position: 'sticky',
              bottom: 0,
              zIndex: 10,
              backgroundColor: token.colorBgContainer,
              borderTop: `1px solid ${token.colorBorderSecondary}`,
              padding: isMobile ? '8px 0' : '10px 0',
              display: 'flex',
              justifyContent: 'flex-end'
            }}
          >
            <Pagination
              current={outlinePage}
              pageSize={outlinePageSize}
              total={filteredOutlines.length}
              showSizeChanger
              pageSizeOptions={['10', '20', '50', '100']}
              onChange={(page, size) => {
                setOutlinePage(page);
                if (size !== outlinePageSize) {
                  setOutlinePageSize(size);
                  setOutlinePage(1);
                }
              }}
              showTotal={(total) => `Tổng cộng ${total} mục`}
              size={isMobile ? 'small' : 'default'}
            />
          </div>
        )}
      </div>
    </>
  );
}
