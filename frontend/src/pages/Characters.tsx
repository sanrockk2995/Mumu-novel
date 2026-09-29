import { useState, useEffect, useRef } from 'react';
import { Button, Modal, Form, Input, Select, message, Row, Col, Empty, Tabs, Divider, Typography, Space, InputNumber, Checkbox, theme } from 'antd';
import { ThunderboltOutlined, UserOutlined, TeamOutlined, PlusOutlined, ExportOutlined, ImportOutlined, DownloadOutlined } from '@ant-design/icons';
import { useStore } from '../store';
import { useCharacterSync } from '../store/hooks';
import { charactersPageGridConfig } from '../components/CardStyles';
import { CharacterCard } from '../components/CharacterCard';
import { SSELoadingOverlay } from '../components/SSELoadingOverlay';
import type { Character, ApiError } from '../types';
import { characterApi } from '../services/api';
import { SSEPostClient } from '../utils/sseClient';
import api from '../services/api';

const { Title } = Typography;
const { TextArea } = Input;

interface Career {
  id: string;
  name: string;
  type: 'main' | 'sub';
  max_stage: number;
}

// Kiểu dữ liệu nghề phụ
interface SubCareerData {
  career_id: string;
  stage: number;
}

// Kiểu giá trị form tạo nhân vật
interface CharacterFormValues {
  name: string;
  age?: string;
  gender?: string;
  role_type?: string;
  personality?: string;
  appearance?: string;
  background?: string;
  main_career_id?: string;
  main_career_stage?: number;
  sub_career_data?: SubCareerData[];
  // Trường tổ chức
  organization_type?: string;
  organization_purpose?: string;
  organization_members?: string;
  power_level?: number;
  location?: string;
  motto?: string;
  color?: string;
}

// Kiểu dữ liệu tạo nhân vật
interface CharacterCreateData {
  project_id: string;
  name: string;
  is_organization: boolean;
  age?: string;
  gender?: string;
  role_type?: string;
  personality?: string;
  appearance?: string;
  background?: string;
  main_career_id?: string;
  main_career_stage?: number;
  sub_careers?: string;
  organization_type?: string;
  organization_purpose?: string;
  organization_members?: string;
  power_level?: number;
  location?: string;
  motto?: string;
  color?: string;
}

// Kiểu dữ liệu cập nhật nhân vật
interface CharacterUpdateData {
  name?: string;
  age?: string;
  gender?: string;
  role_type?: string;
  personality?: string;
  appearance?: string;
  background?: string;
  main_career_id?: string;
  main_career_stage?: number;
  sub_careers?: string;
  organization_type?: string;
  organization_purpose?: string;
  organization_members?: string;
  power_level?: number;
  location?: string;
  motto?: string;
  color?: string;
}

export default function Characters() {
  const { token } = theme.useToken();
  const { currentProject, characters } = useStore();
  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const [activeTab, setActiveTab] = useState<'all' | 'character' | 'organization'>('all');
  const [generateForm] = Form.useForm();
  const [generateOrgForm] = Form.useForm();
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [createType, setCreateType] = useState<'character' | 'organization'>('character');
  const [editingCharacter, setEditingCharacter] = useState<Character | null>(null);
  const [mainCareers, setMainCareers] = useState<Career[]>([]);
  const [subCareers, setSubCareers] = useState<Career[]>([]);
  const [selectedCharacters, setSelectedCharacters] = useState<string[]>([]);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const {
    refreshCharacters,
    deleteCharacter
  } = useCharacterSync();

  useEffect(() => {
    if (currentProject?.id) {
      refreshCharacters();
      fetchCareers();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentProject?.id]);
  const [modal, contextHolder] = Modal.useModal();

  const fetchCareers = async () => {
    if (!currentProject?.id) return;
    try {
      const response = await api.get<unknown, { main_careers: Career[]; sub_careers: Career[] }>('/careers', {
        params: { project_id: currentProject.id }
      });
      setMainCareers(response.main_careers || []);
      setSubCareers(response.sub_careers || []);
    } catch (error) {
      console.error('Lấy danh sách nghề nghiệp thất bại:', error);
    }
  };

  if (!currentProject) return null;

  const handleDeleteCharacter = async (id: string) => {
    try {
      await deleteCharacter(id);
      message.success('Xóa thành công');
    } catch {
      message.error('Xóa thất bại');
    }
  };

  const handleGenerate = async (values: { name?: string; role_type: string; background?: string }) => {
    try {
      setIsGenerating(true);
      setProgress(0);
      setProgressMessage('Đang chuẩn bị sinh nhân vật...');

      const client = new SSEPostClient(
        '/api/characters/generate-stream',
        {
          project_id: currentProject.id,
          name: values.name,
          role_type: values.role_type,
          background: values.background,
        },
        {
          onProgress: (msg, prog) => {
            setProgress(prog);
            setProgressMessage(msg);
          },
          onResult: (data) => {
            console.log('Sinh nhân vật hoàn tất:', data);
          },
          onError: (error) => {
            message.error(`Sinh thất bại: ${error}`);
          },
          onComplete: () => {
            setProgress(100);
            setProgressMessage('Sinh hoàn tất!');
          }
        }
      );

      await client.connect();
      message.success('AI sinh nhân vật thành công');
      Modal.destroyAll();
      await refreshCharacters();
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'AISinh thất bại';
      message.error(errorMessage);
    } finally {
      setTimeout(() => {
        setIsGenerating(false);
        setProgress(0);
        setProgressMessage('');
      }, 500);
    }
  };

  const handleGenerateOrganization = async (values: {
    name?: string;
    organization_type?: string;
    background?: string;
    requirements?: string;
  }) => {
    try {
      setIsGenerating(true);
      setProgress(0);
      setProgressMessage('Đang chuẩn bị sinh tổ chức...');

      const client = new SSEPostClient(
        '/api/organizations/generate-stream',
        {
          project_id: currentProject.id,
          name: values.name,
          organization_type: values.organization_type,
          background: values.background,
          requirements: values.requirements,
        },
        {
          onProgress: (msg, prog) => {
            setProgress(prog);
            setProgressMessage(msg);
          },
          onResult: (data) => {
            console.log('Sinh tổ chức hoàn tất:', data);
          },
          onError: (error) => {
            message.error(`Sinh thất bại: ${error}`);
          },
          onComplete: () => {
            setProgress(100);
            setProgressMessage('Sinh hoàn tất!');
          }
        }
      );

      await client.connect();
      message.success('AI sinh tổ chức thành công');
      Modal.destroyAll();
      await refreshCharacters();
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'AISinh thất bại';
      message.error(errorMessage);
    } finally {
      setTimeout(() => {
        setIsGenerating(false);
        setProgress(0);
        setProgressMessage('');
      }, 500);
    }
  };

  const handleCreateCharacter = async (values: CharacterFormValues) => {
    try {
      const createData: CharacterCreateData = {
        project_id: currentProject.id,
        name: values.name,
        is_organization: createType === 'organization',
      };

      if (createType === 'character') {
        // Trường nhân vật
        createData.age = values.age;
        createData.gender = values.gender;
        createData.role_type = values.role_type || 'supporting';
        createData.personality = values.personality;
        createData.appearance = values.appearance;
        createData.background = values.background;
        
        // Trường nghề nghiệp
        if (values.main_career_id) {
          createData.main_career_id = values.main_career_id;
          createData.main_career_stage = values.main_career_stage || 1;
        }
        
        // Xử lý dữ liệu nghề phụ
        if (values.sub_career_data && Array.isArray(values.sub_career_data) && values.sub_career_data.length > 0) {
          createData.sub_careers = JSON.stringify(values.sub_career_data);
        }
      } else {
        // Trường tổ chức
        createData.organization_type = values.organization_type;
        createData.organization_purpose = values.organization_purpose;
        createData.background = values.background;
        createData.power_level = values.power_level;
        createData.location = values.location;
        createData.motto = values.motto;
        createData.color = values.color;
        createData.role_type = 'supporting'; // Tổ chức mặc định là nhân vật phụ
      }

      await characterApi.createCharacter(createData);
      message.success(`${createType === 'character' ? 'Nhân vật' : 'Tổ chức'} đã tạo thành công`);
      setIsCreateModalOpen(false);
      createForm.resetFields();
      await refreshCharacters();
    } catch {
      message.error('Tạo thất bại');
    }
  };

  const handleEditCharacter = (character: Character) => {
    setEditingCharacter(character);

    // Trích xuất dữ liệu nghề phụ (bao gồm IDnghề nghiệp và giai đoạn)
    const subCareerData: SubCareerData[] = character.sub_careers?.map((sc) => ({
      career_id: sc.career_id,
      stage: sc.stage || 1
    })) || [];

    editForm.setFieldsValue({
      ...character,
      sub_career_data: subCareerData
    });
    setIsEditModalOpen(true);
  };

  const handleUpdateCharacter = async (values: CharacterFormValues) => {
    if (!editingCharacter) return;

    try {
      // Trích xuất dữ liệu nghề phụ, phần còn lại làm dữ liệu cập nhật
      const { sub_career_data: subCareerData, ...restValues } = values;
      const updateData: CharacterUpdateData = { ...restValues };

      // Chuyển thành sub_careersđịnh dạng
      if (subCareerData && Array.isArray(subCareerData) && subCareerData.length > 0) {
        updateData.sub_careers = JSON.stringify(subCareerData);
      } else {
        updateData.sub_careers = JSON.stringify([]);
      }

      await characterApi.updateCharacter(editingCharacter.id, updateData);
      message.success('Cập nhật thành công');
      setIsEditModalOpen(false);
      editForm.resetFields();
      setEditingCharacter(null);
      await refreshCharacters();
    } catch (error) {
      console.error('Cập nhật thất bại:', error);
      message.error('Cập nhật thất bại');
    }
  };

  const handleDeleteCharacterWrapper = (id: string) => {
    handleDeleteCharacter(id);
  };

  // Xuất nhân vật đã chọn/Tổ chức
  const handleExportSelected = async () => {
    if (selectedCharacters.length === 0) {
      message.warning('Vui lòng chọn ít nhất một nhân vật hoặc tổ chức');
      return;
    }

    try {
      await characterApi.exportCharacters(selectedCharacters);
      message.success(`Xuất thành công  ${selectedCharacters.length}  nhân vật/tổ chức`);
      setSelectedCharacters([]);
    } catch (error) {
      message.error('Xuất thất bại');
      console.error('Lỗi xuất:', error);
    }
  };

  // Xuất một nhân vật/tổ chức
  const handleExportSingle = async (characterId: string) => {
    try {
      await characterApi.exportCharacters([characterId]);
      message.success('Xuất thành công');
    } catch (error) {
      message.error('Xuất thất bại');
      console.error('Lỗi xuất:', error);
    }
  };

  // Xử lý chọn tệp
  const handleFileSelect = async (file: File) => {
    try {
      // Kiểm tra tệp
      const validation = await characterApi.validateImportCharacters(file);
      
      if (!validation.valid) {
        modal.error({
          title: 'Kiểm tra tệp thất bại',
          centered: true,
          content: (
            <div>
              {validation.errors.map((error, index) => (
                <div key={index} style={{ color: token.colorError }}>• {error}</div>
              ))}
            </div>
          ),
        });
        return;
      }

      // Hiển thị hộp thoại xem trước
      modal.confirm({
        title: 'Xem trước nhập',
        width: 500,
        centered: true,
        content: (
          <div>
            <p><strong>Phiên bản tệp:</strong> {validation.version}</p>
            <Divider style={{ margin: '12px 0' }} />
            <p><strong>Sẽ nhập:</strong></p>
            <ul style={{ marginLeft: 20 }}>
              <li>Nhân vật: {validation.statistics.characters} </li>
              <li>Tổ chức: {validation.statistics.organizations} </li>
            </ul>
            {validation.warnings.length > 0 && (
              <>
                <Divider style={{ margin: '12px 0' }} />
                <p style={{ color: token.colorWarning }}><strong>⚠️ Cảnh báo:</strong></p>
                <ul style={{ marginLeft: 20 }}>
                  {validation.warnings.map((warning, index) => (
                    <li key={index} style={{ color: token.colorWarning }}>{warning}</li>
                  ))}
                </ul>
              </>
            )}
          </div>
        ),
        okText: 'Xác nhận nhập',
        cancelText: 'Hủy',
        onOk: async () => {
          try {
            const result = await characterApi.importCharacters(currentProject.id, file);
            
            if (result.success) {
              // Hiển thị kết quả nhập
              modal.success({
                title: 'Nhập hoàn tất',
                width: 600,
                centered: true,
                content: (
                  <div>
                    <p><strong>✅ Nhập thành công: {result.statistics.imported}</strong></p>
                    {result.details.imported_characters.length > 0 && (
                      <>
                        <p style={{ marginTop: 12, marginBottom: 4 }}>Nhân vật:</p>
                        <ul style={{ marginLeft: 20 }}>
                          {result.details.imported_characters.map((name, index) => (
                            <li key={index}>{name}</li>
                          ))}
                        </ul>
                      </>
                    )}
                    {result.details.imported_organizations.length > 0 && (
                      <>
                        <p style={{ marginTop: 12, marginBottom: 4 }}>Tổ chức:</p>
                        <ul style={{ marginLeft: 20 }}>
                          {result.details.imported_organizations.map((name, index) => (
                            <li key={index}>{name}</li>
                          ))}
                        </ul>
                      </>
                    )}
                    {result.statistics.skipped > 0 && (
                      <>
                        <Divider style={{ margin: '12px 0' }} />
                        <p style={{ color: token.colorWarning }}>⚠️ Bỏ qua: {result.statistics.skipped} </p>
                        <ul style={{ marginLeft: 20 }}>
                          {result.details.skipped.map((name, index) => (
                            <li key={index} style={{ color: token.colorWarning }}>{name}</li>
                          ))}
                        </ul>
                      </>
                    )}
                    {result.warnings.length > 0 && (
                      <>
                        <Divider style={{ margin: '12px 0' }} />
                        <p style={{ color: token.colorWarning }}>⚠️ Cảnh báo:</p>
                        <ul style={{ marginLeft: 20 }}>
                          {result.warnings.map((warning, index) => (
                            <li key={index} style={{ color: token.colorWarning }}>{warning}</li>
                          ))}
                        </ul>
                      </>
                    )}
                    {result.details.errors.length > 0 && (
                      <>
                        <Divider style={{ margin: '12px 0' }} />
                        <p style={{ color: token.colorError }}>❌ Thất bại: {result.statistics.errors} </p>
                        <ul style={{ marginLeft: 20 }}>
                          {result.details.errors.map((error, index) => (
                            <li key={index} style={{ color: token.colorError }}>{error}</li>
                          ))}
                        </ul>
                      </>
                    )}
                  </div>
                ),
              });
              
              // Refresh danh sách
              await refreshCharacters();
              setIsImportModalOpen(false);
            } else {
              message.error(result.message || 'Nhập thất bại');
            }
          } catch (error: unknown) {
            const apiError = error as ApiError;
            message.error(apiError.response?.data?.detail || 'Nhập thất bại');
            console.error('Lỗi nhập:', error);
          }
        },
      });
    } catch (error: unknown) {
      const apiError = error as ApiError;
      message.error(apiError.response?.data?.detail || 'Kiểm tra tệp thất bại');
      console.error('Lỗi kiểm tra:', error);
    }
  };

  // Chuyển đổi lựa chọn
  const toggleSelectCharacter = (id: string) => {
    setSelectedCharacters(prev =>
      prev.includes(id) ? prev.filter(cid => cid !== id) : [...prev, id]
    );
  };

  // Chọn tất cả/Bỏ chọn tất cả
  const toggleSelectAll = () => {
    if (selectedCharacters.length === displayList.length) {
      setSelectedCharacters([]);
    } else {
      setSelectedCharacters(displayList.map(c => c.id));
    }
  };

  const showGenerateModal = () => {
    modal.confirm({
      title: 'AISinh nhân vật',
      width: 600,
      centered: true,
      content: (
        <Form form={generateForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            label="Tên nhân vật"
            name="name"
          >
            <Input placeholder="VD: Trương Tam, Lý Tứ (tùy chọn, AIAI sẽ tự sinh)" />
          </Form.Item>
          <Form.Item
            label="Định vị nhân vật"
            name="role_type"
            rules={[{ required: true, message: 'Vui lòng chọn định vị nhân vật' }]}
          >
            <Select placeholder="Chọn định vị nhân vật">
              <Select.Option value="protagonist">Nhân vật chính</Select.Option>
              <Select.Option value="supporting">Nhân vật phụ</Select.Option>
              <Select.Option value="antagonist">Phản diện</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item label="Thiết lập nền" name="background">
            <TextArea rows={3} placeholder="Mô tả ngắn gọn nền nhân vật và môi trường câu chuyện..." />
          </Form.Item>
        </Form>
      ),
      okText: 'Sinh',
      cancelText: 'Hủy',
      onOk: async () => {
        const values = await generateForm.validateFields();
        await handleGenerate(values);
      },
    });
  };

  const showGenerateOrgModal = () => {
    modal.confirm({
      title: 'AISinh tổ chức',
      width: 600,
      centered: true,
      content: (
        <Form form={generateOrgForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            label="Tên tổ chức"
            name="name"
          >
            <Input placeholder="VD: Thiên Kiếm Môn, Hắc Long Hội (tùy chọn, AIAI sẽ tự sinh)" />
          </Form.Item>
          <Form.Item
            label="Loại tổ chức"
            name="organization_type"
          >
            <Input placeholder="VD: môn phái, bang phái, công ty, học viện (tùy chọn, AIAI sẽ sinh theo thế giới quan)" />
          </Form.Item>
          <Form.Item label="Thiết lập nền" name="background">
            <TextArea rows={3} placeholder="Mô tả ngắn gọn nền và môi trường của tổ chức..." />
          </Form.Item>
          <Form.Item label="Yêu cầu khác" name="requirements">
            <TextArea rows={2} placeholder="Yêu cầu đặc biệt khác..." />
          </Form.Item>
        </Form>
      ),
      okText: 'Sinh',
      cancelText: 'Hủy',
      onOk: async () => {
        const values = await generateOrgForm.validateFields();
        await handleGenerateOrganization(values);
      },
    });
  };

  const characterList = characters.filter(c => !c.is_organization);
  const organizationList = characters.filter(c => c.is_organization);

  const getDisplayList = () => {
    if (activeTab === 'character') return characterList;
    if (activeTab === 'organization') return organizationList;
    return characters;
  };

  const displayList = getDisplayList();

  const isMobile = window.innerWidth <= 768;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {contextHolder}
      <div style={{
        position: 'sticky',
        top: 0,
        zIndex: 10,
        backgroundColor: 'var(--color-bg-container)',
        padding: isMobile ? '12px 0' : '16px 0',
        marginBottom: isMobile ? 12 : 16,
        borderBottom: '1px solid var(--color-border-secondary)',
        display: 'flex',
        flexDirection: isMobile ? 'column' : 'row',
        gap: isMobile ? 12 : 0,
        justifyContent: 'space-between',
        alignItems: isMobile ? 'stretch' : 'center'
      }}>
        <h2 style={{ margin: 0, fontSize: isMobile ? 18 : 24 }}>
          <TeamOutlined style={{ marginRight: 8 }} />
          Quản lý nhân vật và tổ chức
        </h2>
        <Space wrap>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setCreateType('character');
              setIsCreateModalOpen(true);
            }}
            size={isMobile ? 'small' : 'middle'}
          >
            Tạo nhân vật
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setCreateType('organization');
              setIsCreateModalOpen(true);
            }}
            size={isMobile ? 'small' : 'middle'}
          >
            Tạo tổ chức
          </Button>
          <Button
            type="dashed"
            icon={<ThunderboltOutlined />}
            onClick={showGenerateModal}
            loading={isGenerating}
            size={isMobile ? 'small' : 'middle'}
          >
            AISinh nhân vật
          </Button>
          <Button
            type="dashed"
            icon={<ThunderboltOutlined />}
            onClick={showGenerateOrgModal}
            loading={isGenerating}
            size={isMobile ? 'small' : 'middle'}
          >
            AISinh tổ chức
          </Button>
          <Button
            icon={<ImportOutlined />}
            onClick={() => setIsImportModalOpen(true)}
            size={isMobile ? 'small' : 'middle'}
          >
            Nhập
          </Button>
          {selectedCharacters.length > 0 && (
            <Button
              icon={<ExportOutlined />}
              onClick={handleExportSelected}
              size={isMobile ? 'small' : 'middle'}
            >
              Xuất hàng loạt ({selectedCharacters.length})
            </Button>
          )}
        </Space>
      </div>

      {characters.length > 0 && (
        <div style={{
          position: 'sticky',
          top: isMobile ? 60 : 72,
          zIndex: 9,
          backgroundColor: 'var(--color-bg-container)',
          paddingBottom: 8,
          borderBottom: '1px solid var(--color-border-secondary)',
        }}>
          <Tabs
            activeKey={activeTab}
            onChange={(key) => setActiveTab(key as 'all' | 'character' | 'organization')}
            items={[
              {
                key: 'all',
                label: `Tất cả  (${characters.length})`,
              },
              {
                key: 'character',
                label: (
                  <span>
                    <UserOutlined /> Nhân vật ({characterList.length})
                  </span>
                ),
              },
              {
                key: 'organization',
                label: (
                  <span>
                    <TeamOutlined /> Tổ chức ({organizationList.length})
                  </span>
                ),
              },
            ]}
          />
        </div>
      )}

      {/* Thanh công cụ chọn hàng loạt */}
      {characters.length > 0 && (
        <div style={{
          position: 'sticky',
          top: isMobile ? 120 : 132,
          zIndex: 8,
          backgroundColor: 'var(--color-bg-container)',
          paddingBottom: 8,
          paddingTop: 8,
          marginTop: 8,
          borderBottom: selectedCharacters.length > 0 ? '1px solid var(--color-border-secondary)' : 'none',
        }}>
          <Space>
            <Checkbox
              checked={selectedCharacters.length === displayList.length && displayList.length > 0}
              indeterminate={selectedCharacters.length > 0 && selectedCharacters.length < displayList.length}
              onChange={toggleSelectAll}
            >
              {selectedCharacters.length > 0 ? `Đã chọn  ${selectedCharacters.length} ` : 'Chọn tất cả'}
            </Checkbox>
            {selectedCharacters.length > 0 && (
              <Button
                type="link"
                size="small"
                onClick={() => setSelectedCharacters([])}
              >
                Bỏ chọn
              </Button>
            )}
          </Space>
        </div>
      )}

      <div style={{ flex: 1, overflowY: 'auto' }}>
        {characters.length === 0 ? (
          <Empty description="Chưa có nhân vật hay tổ chức nào, hãy bắt đầu tạo!" />
        ) : (
          <>
            <Row gutter={isMobile ? [8, 8] : charactersPageGridConfig.gutter}>
              {activeTab === 'all' && (
                <>
                  {characterList.length > 0 && (
                    <>
                      <Col span={24}>
                        <Divider orientation="left">
                          <Title level={5} style={{ margin: 0 }}>
                            <UserOutlined style={{ marginRight: 8 }} />
                            Nhân vật ({characterList.length})
                          </Title>
                        </Divider>
                      </Col>
                      {characterList.map((character) => (
                        <Col
                          xs={24}
                          sm={charactersPageGridConfig.sm}
                          md={charactersPageGridConfig.md}
                          lg={charactersPageGridConfig.lg}
                          xl={charactersPageGridConfig.xl}
                          key={character.id}
                          style={{ padding: isMobile ? '4px' : '8px' }}
                        >
                          <div style={{ position: 'relative' }}>
                            <Checkbox
                              checked={selectedCharacters.includes(character.id)}
                              onChange={() => toggleSelectCharacter(character.id)}
                              style={{ position: 'absolute', top: 8, left: 8, zIndex: 1 }}
                            />
                            <CharacterCard
                              character={character}
                              onEdit={handleEditCharacter}
                              onDelete={handleDeleteCharacterWrapper}
                              onExport={() => handleExportSingle(character.id)}
                            />
                          </div>
                        </Col>
                      ))}
                    </>
                  )}

                  {organizationList.length > 0 && (
                    <>
                      <Col span={24}>
                        <Divider orientation="left">
                          <Title level={5} style={{ margin: 0 }}>
                            <TeamOutlined style={{ marginRight: 8 }} />
                            Tổ chức ({organizationList.length})
                          </Title>
                        </Divider>
                      </Col>
                      {organizationList.map((org) => (
                        <Col
                          xs={24}
                          sm={charactersPageGridConfig.sm}
                          md={charactersPageGridConfig.md}
                          lg={charactersPageGridConfig.lg}
                          xl={charactersPageGridConfig.xl}
                          key={org.id}
                          style={{ padding: isMobile ? '4px' : '8px' }}
                        >
                          <div style={{ position: 'relative' }}>
                            <Checkbox
                              checked={selectedCharacters.includes(org.id)}
                              onChange={() => toggleSelectCharacter(org.id)}
                              style={{ position: 'absolute', top: 8, left: 8, zIndex: 1 }}
                            />
                            <CharacterCard
                              character={org}
                              onEdit={handleEditCharacter}
                              onDelete={handleDeleteCharacterWrapper}
                              onExport={() => handleExportSingle(org.id)}
                            />
                          </div>
                        </Col>
                      ))}
                    </>
                  )}
                </>
              )}

              {activeTab === 'character' && characterList.map((character) => (
                <Col
                  xs={24}
                  sm={charactersPageGridConfig.sm}
                  md={charactersPageGridConfig.md}
                  lg={charactersPageGridConfig.lg}
                  xl={charactersPageGridConfig.xl}
                  key={character.id}
                  style={{ padding: isMobile ? '4px' : '8px' }}
                >
                  <div style={{ position: 'relative' }}>
                    <Checkbox
                      checked={selectedCharacters.includes(character.id)}
                      onChange={() => toggleSelectCharacter(character.id)}
                      style={{ position: 'absolute', top: 8, left: 8, zIndex: 1 }}
                    />
                    <CharacterCard
                      character={character}
                      onEdit={handleEditCharacter}
                      onDelete={handleDeleteCharacterWrapper}
                      onExport={() => handleExportSingle(character.id)}
                    />
                  </div>
                </Col>
              ))}

              {activeTab === 'organization' && organizationList.map((org) => (
                <Col
                  xs={24}
                  sm={charactersPageGridConfig.sm}
                  md={charactersPageGridConfig.md}
                  lg={charactersPageGridConfig.lg}
                  xl={charactersPageGridConfig.xl}
                  key={org.id}
                  style={{ padding: isMobile ? '4px' : '8px' }}
                >
                  <div style={{ position: 'relative' }}>
                    <Checkbox
                      checked={selectedCharacters.includes(org.id)}
                      onChange={() => toggleSelectCharacter(org.id)}
                      style={{ position: 'absolute', top: 8, left: 8, zIndex: 1 }}
                    />
                    <CharacterCard
                      character={org}
                      onEdit={handleEditCharacter}
                      onDelete={handleDeleteCharacterWrapper}
                      onExport={() => handleExportSingle(org.id)}
                    />
                  </div>
                </Col>
              ))}
            </Row>

            {displayList.length === 0 && (
              <Empty
                description={
                  activeTab === 'character'
                    ? 'Chưa có nhân vật'
                    : activeTab === 'organization'
                      ? 'Chưa có tổ chức'
                      : 'Chưa có dữ liệu'
                }
              />
            )}
          </>
        )}
      </div>

      <Modal
        title={editingCharacter?.is_organization ? 'Chỉnh sửa tổ chức' : 'Chỉnh sửa nhân vật'}
        open={isEditModalOpen}
        onCancel={() => {
          setIsEditModalOpen(false);
          editForm.resetFields();
          setEditingCharacter(null);
        }}
        footer={
          <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
            <Button onClick={() => {
              setIsEditModalOpen(false);
              editForm.resetFields();
              setEditingCharacter(null);
            }}>
              Hủy
            </Button>
            <Button type="primary" onClick={() => editForm.submit()}>
              Lưu
            </Button>
          </Space>
        }
        centered
        width={isMobile ? '100%' : 700}
        style={isMobile ? { top: 0, paddingBottom: 0, maxWidth: '100vw' } : undefined}
        styles={{
          body: {
            maxHeight: isMobile ? 'calc(100vh - 110px)' : 'calc(100vh - 200px)',
            overflowY: 'auto',
            overflowX: 'hidden'
          }
        }}
      >
        <Form form={editForm} layout="vertical" onFinish={handleUpdateCharacter} style={{ marginTop: 8 }}>
          {!editingCharacter?.is_organization ? (
            <>
              {/* Chỉnh sửa nhân vật - Hàng đầu: tên, định vị, tuổi, giới tính */}
              <Row gutter={12}>
                <Col span={8}>
                  <Form.Item
                    label="Tên nhân vật"
                    name="name"
                    rules={[{ required: true, message: 'Vui lòng nhập tên nhân vật' }]}
                    style={{ marginBottom: 12 }}
                  >
                    <Input placeholder="Tên nhân vật" />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="Định vị nhân vật" name="role_type" style={{ marginBottom: 12 }}>
                    <Select>
                      <Select.Option value="protagonist">Nhân vật chính</Select.Option>
                      <Select.Option value="supporting">Nhân vật phụ</Select.Option>
                      <Select.Option value="antagonist">Phản diện</Select.Option>
                    </Select>
                  </Form.Item>
                </Col>
                <Col span={5}>
                  <Form.Item label="Tuổi" name="age" style={{ marginBottom: 12 }}>
                    <Input placeholder="VD: 25 tuổi" />
                  </Form.Item>
                </Col>
                <Col span={5}>
                  <Form.Item label="Giới tính" name="gender" style={{ marginBottom: 12 }}>
                    <Select placeholder="Giới tính">
                      <Select.Option value="Nam">Nam</Select.Option>
                      <Select.Option value="Nữ">Nữ</Select.Option>
                      <Select.Option value="Khác">Khác</Select.Option>
                    </Select>
                  </Form.Item>
                </Col>
              </Row>

              {/* Hàng hai: đặc điểm tính cách, miêu tả ngoại hình */}
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item label="Đặc điểm tính cách" name="personality" style={{ marginBottom: 12 }}>
                    <TextArea rows={2} placeholder="Mô tả đặc điểm tính cách của nhân vật..." />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="Miêu tả ngoại hình" name="appearance" style={{ marginBottom: 12 }}>
                    <TextArea rows={2} placeholder="Mô tả đặc điểm ngoại hình của nhân vật..." />
                  </Form.Item>
                </Col>
              </Row>

              {/* Quan hệ nhân vật (chỉ đọc, do trang quản lý quan hệ duy trì) */}
              {editingCharacter?.relationships && (
                <Form.Item label="Quan hệ nhân vật (do quản lý quan hệ duy trì)" style={{ marginBottom: 12 }}>
                  <Input.TextArea
                    value={editingCharacter.relationships}
                    readOnly
                    autoSize={{ minRows: 1, maxRows: 3 }}
                    style={{ backgroundColor: token.colorFillTertiary, cursor: 'default' }}
                  />
                </Form.Item>
              )}

              {/* Hàng bốn: nền nhân vật */}
              <Form.Item label="Nền nhân vật" name="background" style={{ marginBottom: 12 }}>
                <TextArea rows={2} placeholder="Mô tả câu chuyện nền của nhân vật..." />
              </Form.Item>

              {/* Thông tin nghề nghiệp */}
              {(mainCareers.length > 0 || subCareers.length > 0) && (
                <>
                  <Divider style={{ margin: '8px 0' }}>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>Thông tin nghề nghiệp</Typography.Text>
                  </Divider>
                  {mainCareers.length > 0 && (
                    <Row gutter={12}>
                      <Col span={16}>
                        <Form.Item label="Nghề chính" name="main_career_id" tooltip="Nghề tu luyện chính của nhân vật" style={{ marginBottom: 12 }}>
                          <Select placeholder="Chọn nghề chính" allowClear size="small">
                            {mainCareers.map(career => (
                              <Select.Option key={career.id} value={career.id}>
                                {career.name} (tối đa bậc {career.max_stage})
                              </Select.Option>
                            ))}
                          </Select>
                        </Form.Item>
                      </Col>
                      <Col span={8}>
                        <Form.Item label="Giai đoạn hiện tại" name="main_career_stage" tooltip="Giai đoạn tu luyện hiện tại của nghề chính" style={{ marginBottom: 12 }}>
                          <InputNumber
                            min={1}
                            max={editForm.getFieldValue('main_career_id') ?
                              mainCareers.find(c => c.id === editForm.getFieldValue('main_career_id'))?.max_stage || 10
                              : 10}
                            style={{ width: '100%' }}
                            placeholder="Giai đoạn"
                            size="small"
                          />
                        </Form.Item>
                      </Col>
                    </Row>
                  )}
                  {subCareers.length > 0 && (
                    <Form.List name="sub_career_data">
                      {(fields, { add, remove }) => (
                        <>
                          <div style={{ marginBottom: 4 }}>
                            <Typography.Text strong style={{ fontSize: 12 }}>Nghề phụ</Typography.Text>
                          </div>
                          <div style={{ maxHeight: '80px', overflowY: 'auto', overflowX: 'hidden', marginBottom: 8, paddingRight: 8 }}>
                            {fields.map((field) => (
                              <Row key={field.key} gutter={8} style={{ marginBottom: 4 }}>
                                <Col span={16}>
                                  <Form.Item
                                    {...field}
                                    name={[field.name, 'career_id']}
                                    rules={[{ required: true, message: 'Vui lòng chọn nghề phụ' }]}
                                    style={{ marginBottom: 0 }}
                                  >
                                    <Select placeholder="Chọn nghề phụ" size="small">
                                      {subCareers.map(career => (
                                        <Select.Option key={career.id} value={career.id}>
                                          {career.name} (tối đa bậc {career.max_stage})
                                        </Select.Option>
                                      ))}
                                    </Select>
                                  </Form.Item>
                                </Col>
                                <Col span={5}>
                                  <Form.Item
                                    {...field}
                                    name={[field.name, 'stage']}
                                    rules={[{ required: true, message: 'Giai đoạn' }]}
                                    style={{ marginBottom: 0 }}
                                  >
                                    <InputNumber
                                      min={1}
                                      max={(() => {
                                        const careerId = editForm.getFieldValue(['sub_career_data', field.name, 'career_id']);
                                        const career = subCareers.find(c => c.id === careerId);
                                        return career?.max_stage || 10;
                                      })()}
                                      placeholder="Giai đoạn"
                                      style={{ width: '100%' }}
                                      size="small"
                                    />
                                  </Form.Item>
                                </Col>
                                <Col span={3}>
                                  <Button
                                    type="text"
                                    danger
                                    size="small"
                                    onClick={() => remove(field.name)}
                                  >
                                    Xóa
                                  </Button>
                                </Col>
                              </Row>
                            ))}
                          </div>
                          <Button
                            type="dashed"
                            onClick={() => add({ career_id: undefined, stage: 1 })}
                            block
                            size="small"
                          >
                            + Thêm nghề phụ
                          </Button>
                        </>
                      )}
                    </Form.List>
                  )}
                </>
              )}
            </>
          ) : (
            <>
              {/* Chỉnh sửa tổ chức - Hàng đầu: tên, loại, cấp thế lực */}
              <Row gutter={12}>
                <Col span={10}>
                  <Form.Item
                    label="Tên tổ chức"
                    name="name"
                    rules={[{ required: true, message: 'Vui lòng nhập tên tổ chức' }]}
                    style={{ marginBottom: 12 }}
                  >
                    <Input placeholder="Tên tổ chức" />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item
                    label="Loại tổ chức"
                    name="organization_type"
                    rules={[{ required: true, message: 'Vui lòng nhập loại tổ chức' }]}
                    style={{ marginBottom: 12 }}
                  >
                    <Input placeholder="VD: môn phái, bang phái" />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item
                    label="Cấp thế lực"
                    name="power_level"
                    tooltip="Giá trị 0-100"
                    style={{ marginBottom: 12 }}
                  >
                    <InputNumber min={0} max={100} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>

              {/* Hàng hai: mục đích tổ chức */}
              <Form.Item
                label="Mục đích tổ chức"
                name="organization_purpose"
                rules={[{ required: true, message: 'Vui lòng nhập mục đích tổ chức' }]}
                style={{ marginBottom: 12 }}
              >
                <Input placeholder="Mô tả tôn chỉ và mục tiêu của tổ chức..." />
              </Form.Item>

              {/* Hàng ba: thành viên chính (chỉ hiển thị) */}
              <Form.Item
                label="Thành viên chính"
                name="organization_members"
                style={{ marginBottom: 4 }}
                tooltip="Thông tin thành viên do module quản lý tổ chức duy trì, ở đây chỉ hiển thị"
              >
                <TextArea
                  disabled
                  autoSize={{ minRows: 1, maxRows: 4 }}
                  placeholder="Chưa có thành viên, vui lòng thêm trong quản lý tổ chức"
                  style={{ color: token.colorText, backgroundColor: token.colorFillAlter }}
                />
              </Form.Item>
              <div style={{ marginBottom: 12, fontSize: 12, color: token.colorTextTertiary }}>
                💡 💡 Vui lòng đến trang "Quản lý tổ chức" để thêm hoặc quản lý thành viên tổ chức
              </div>

              {/* Hàng bốn: địa điểm, màu đại diện */}
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item label="Địa điểm" name="location" style={{ marginBottom: 12 }}>
                    <Input placeholder="Vị trí tổng bộ" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="Màu đại diện" name="color" style={{ marginBottom: 12 }}>
                    <Input placeholder="VD: màu vàng kim" />
                  </Form.Item>
                </Col>
              </Row>

              {/* Hàng bốn: châm ngôn/khẩu hiệu */}
              <Form.Item label="Châm ngôn/khẩu hiệu" name="motto" style={{ marginBottom: 12 }}>
                <Input placeholder="Tôn chỉ, châm ngôn hoặc khẩu hiệu của tổ chức" />
              </Form.Item>

              {/* Hàng năm: nền tổ chức */}
              <Form.Item label="Nền tổ chức" name="background" style={{ marginBottom: 12 }}>
                <TextArea rows={2} placeholder="Mô tả câu chuyện nền của tổ chức..." />
              </Form.Item>
            </>
          )}
        </Form>
      </Modal>

      {/* Modal tạo thủ công nhân vật/tổ chức */}
      <Modal
        title={createType === 'character' ? 'Tạo nhân vật' : 'Tạo tổ chức'}
        open={isCreateModalOpen}
        onCancel={() => {
          setIsCreateModalOpen(false);
          createForm.resetFields();
        }}
        footer={null}
        centered
        width={isMobile ? '100%' : 700}
        style={isMobile ? { top: 0, paddingBottom: 0, maxWidth: '100vw' } : undefined}
        styles={{
          body: {
            maxHeight: isMobile ? 'calc(100vh - 110px)' : 'calc(100vh - 200px)',
            overflowY: 'auto',
            overflowX: 'hidden'
          }
        }}
      >
        <Form form={createForm} layout="vertical" onFinish={handleCreateCharacter} style={{ marginTop: 8 }}>
          {createType === 'character' ? (
            <>
              {/* Thông tin cơ bản nhân vật - Hàng đầu: tên, định vị, tuổi, giới tính */}
              <Row gutter={12}>
                <Col span={8}>
                  <Form.Item
                    label="Tên nhân vật"
                    name="name"
                    rules={[{ required: true, message: 'Vui lòng nhập tên nhân vật' }]}
                    style={{ marginBottom: 12 }}
                  >
                    <Input placeholder="Tên nhân vật" />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="Định vị nhân vật" name="role_type" initialValue="supporting" style={{ marginBottom: 12 }}>
                    <Select>
                      <Select.Option value="protagonist">Nhân vật chính</Select.Option>
                      <Select.Option value="supporting">Nhân vật phụ</Select.Option>
                      <Select.Option value="antagonist">Phản diện</Select.Option>
                    </Select>
                  </Form.Item>
                </Col>
                <Col span={5}>
                  <Form.Item label="Tuổi" name="age" style={{ marginBottom: 12 }}>
                    <Input placeholder="VD: 25 tuổi" />
                  </Form.Item>
                </Col>
                <Col span={5}>
                  <Form.Item label="Giới tính" name="gender" style={{ marginBottom: 12 }}>
                    <Select placeholder="Giới tính">
                      <Select.Option value="Nam">Nam</Select.Option>
                      <Select.Option value="Nữ">Nữ</Select.Option>
                      <Select.Option value="Khác">Khác</Select.Option>
                    </Select>
                  </Form.Item>
                </Col>
              </Row>

              {/* Hàng hai: đặc điểm tính cách, miêu tả ngoại hình */}
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item label="Đặc điểm tính cách" name="personality" style={{ marginBottom: 12 }}>
                    <TextArea rows={2} placeholder="Mô tả đặc điểm tính cách của nhân vật..." />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="Miêu tả ngoại hình" name="appearance" style={{ marginBottom: 12 }}>
                    <TextArea rows={2} placeholder="Mô tả đặc điểm ngoại hình của nhân vật..." />
                  </Form.Item>
                </Col>
              </Row>

              {/* Hàng ba: nền nhân vật */}
              <Form.Item label="Nền nhân vật" name="background" style={{ marginBottom: 12 }}>
                <TextArea rows={2} placeholder="Mô tả câu chuyện nền của nhân vật..." />
              </Form.Item>

              {/* Thông tin nghề nghiệp - khu vực thu gọn */}
              {(mainCareers.length > 0 || subCareers.length > 0) && (
                <>
                  <Divider style={{ margin: '8px 0' }}>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>Thông tin nghề nghiệp (tùy chọn)</Typography.Text>
                  </Divider>
                  {mainCareers.length > 0 && (
                    <Row gutter={12}>
                      <Col span={16}>
                        <Form.Item label="Nghề chính" name="main_career_id" tooltip="Nghề tu luyện chính của nhân vật" style={{ marginBottom: 12 }}>
                          <Select placeholder="Chọn nghề chính" allowClear size="small">
                            {mainCareers.map(career => (
                              <Select.Option key={career.id} value={career.id}>
                                {career.name} (tối đa bậc {career.max_stage})
                              </Select.Option>
                            ))}
                          </Select>
                        </Form.Item>
                      </Col>
                      <Col span={8}>
                        <Form.Item label="Giai đoạn hiện tại" name="main_career_stage" tooltip="Giai đoạn tu luyện hiện tại của nghề chính" style={{ marginBottom: 12 }}>
                          <InputNumber
                            min={1}
                            max={createForm.getFieldValue('main_career_id') ?
                              mainCareers.find(c => c.id === createForm.getFieldValue('main_career_id'))?.max_stage || 10
                              : 10}
                            style={{ width: '100%' }}
                            placeholder="Giai đoạn"
                            size="small"
                          />
                        </Form.Item>
                      </Col>
                    </Row>
                  )}
                  {subCareers.length > 0 && (
                    <Form.List name="sub_career_data">
                      {(fields, { add, remove }) => (
                        <>
                          <div style={{ marginBottom: 4 }}>
                            <Typography.Text strong style={{ fontSize: 12 }}>Nghề phụ</Typography.Text>
                          </div>
                          <div style={{ maxHeight: '80px', overflowY: 'auto', overflowX: 'hidden', marginBottom: 8, paddingRight: 8 }}>
                            {fields.map((field) => (
                              <Row key={field.key} gutter={8} style={{ marginBottom: 4 }}>
                                <Col span={16}>
                                  <Form.Item
                                    {...field}
                                    name={[field.name, 'career_id']}
                                    rules={[{ required: true, message: 'Vui lòng chọn nghề phụ' }]}
                                    style={{ marginBottom: 0 }}
                                  >
                                    <Select placeholder="Chọn nghề phụ" size="small">
                                      {subCareers.map(career => (
                                        <Select.Option key={career.id} value={career.id}>
                                          {career.name} (tối đa bậc {career.max_stage})
                                        </Select.Option>
                                      ))}
                                    </Select>
                                  </Form.Item>
                                </Col>
                                <Col span={5}>
                                  <Form.Item
                                    {...field}
                                    name={[field.name, 'stage']}
                                    rules={[{ required: true, message: 'Giai đoạn' }]}
                                    style={{ marginBottom: 0 }}
                                  >
                                    <InputNumber
                                      min={1}
                                      max={(() => {
                                        const careerId = createForm.getFieldValue(['sub_career_data', field.name, 'career_id']);
                                        const career = subCareers.find(c => c.id === careerId);
                                        return career?.max_stage || 10;
                                      })()}
                                      placeholder="Giai đoạn"
                                      style={{ width: '100%' }}
                                      size="small"
                                    />
                                  </Form.Item>
                                </Col>
                                <Col span={3}>
                                  <Button
                                    type="text"
                                    danger
                                    size="small"
                                    onClick={() => remove(field.name)}
                                  >
                                    Xóa
                                  </Button>
                                </Col>
                              </Row>
                            ))}
                          </div>
                          <Button
                            type="dashed"
                            onClick={() => add({ career_id: undefined, stage: 1 })}
                            block
                            size="small"
                          >
                            + Thêm nghề phụ
                          </Button>
                        </>
                      )}
                    </Form.List>
                  )}
                </>
              )}
            </>
          ) : (
            <>
              {/* Thông tin cơ bản tổ chức - Hàng đầu: tên, loại, cấp thế lực */}
              <Row gutter={12}>
                <Col span={10}>
                  <Form.Item
                    label="Tên tổ chức"
                    name="name"
                    rules={[{ required: true, message: 'Vui lòng nhập tên tổ chức' }]}
                    style={{ marginBottom: 12 }}
                  >
                    <Input placeholder="Tên tổ chức" />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item
                    label="Loại tổ chức"
                    name="organization_type"
                    rules={[{ required: true, message: 'Vui lòng nhập loại tổ chức' }]}
                    style={{ marginBottom: 12 }}
                  >
                    <Input placeholder="VD: môn phái, bang phái" />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item
                    label="Cấp thế lực"
                    name="power_level"
                    initialValue={50}
                    tooltip="Giá trị 0-100"
                    style={{ marginBottom: 12 }}
                  >
                    <InputNumber min={0} max={100} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>

              {/* Hàng hai: mục đích tổ chức */}
              <Form.Item
                label="Mục đích tổ chức"
                name="organization_purpose"
                rules={[{ required: true, message: 'Vui lòng nhập mục đích tổ chức' }]}
                style={{ marginBottom: 12 }}
              >
                <Input placeholder="Mô tả tôn chỉ và mục tiêu của tổ chức..." />
              </Form.Item>

              {/* Hàng ba: địa điểm, màu đại diện */}
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item label="Địa điểm" name="location" style={{ marginBottom: 12 }}>
                    <Input placeholder="Vị trí tổng bộ" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="Màu đại diện" name="color" style={{ marginBottom: 12 }}>
                    <Input placeholder="VD: màu vàng kim" />
                  </Form.Item>
                </Col>
              </Row>

              {/* Hàng bốn: châm ngôn/khẩu hiệu */}
              <Form.Item label="Châm ngôn/khẩu hiệu" name="motto" style={{ marginBottom: 12 }}>
                <Input placeholder="Tôn chỉ, châm ngôn hoặc khẩu hiệu của tổ chức" />
              </Form.Item>

              {/* Hàng năm: nền tổ chức */}
              <Form.Item label="Nền tổ chức" name="background" style={{ marginBottom: 12 }}>
                <TextArea rows={2} placeholder="Mô tả câu chuyện nền của tổ chức..." />
              </Form.Item>
            </>
          )}

          <Form.Item style={{ marginBottom: 0, marginTop: 16 }}>
            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
              <Button onClick={() => {
                setIsCreateModalOpen(false);
                createForm.resetFields();
              }}>
                Hủy
              </Button>
              <Button type="primary" htmlType="submit">
                Tạo
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* Hộp thoại nhập */}
      <Modal
        title="Nhập nhân vật/tổ chức"
        open={isImportModalOpen}
        onCancel={() => setIsImportModalOpen(false)}
        footer={null}
        width={500}
        centered
      >
        <div style={{ textAlign: 'center', padding: '40px 20px' }}>
          <DownloadOutlined style={{ fontSize: 48, color: '#1890ff', marginBottom: 16 }} />
          <p style={{ fontSize: 16, marginBottom: 24 }}>
            Chọn tệp JSON nhân vật/tổ chức đã xuất trước đó /Tổ chứcJSONđể nhập
          </p>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            style={{ display: 'none' }}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) {
                handleFileSelect(file);
                e.target.value = ''; // Xóa input, cho phép chọn lại cùng một tệp
              }
            }}
          />
          <Button
            type="primary"
            size="large"
            icon={<ImportOutlined />}
            onClick={() => fileInputRef.current?.click()}
          >
            Chọn tệp
          </Button>
          <Divider />
          <div style={{ textAlign: 'left', fontSize: 12, color: '#666' }}>
            <p style={{ marginBottom: 8 }}><strong>Hướng dẫn:</strong></p>
            <ul style={{ marginLeft: 20 }}>
              <li>Hỗ trợ nhập .jsontệp định dạng .json /nhân vật/tổ chức</li>
              <li>Nhân vật/tổ chức trùng tên /sẽ bị bỏ qua</li>
              <li>Thông tin nghề nghiệp nếu không tồn tại sẽ bị bỏ qua</li>
            </ul>
          </div>
        </div>
      </Modal>

      {/* SSEHiển thị tiến trình */}
      <SSELoadingOverlay
        loading={isGenerating}
        progress={progress}
        message={progressMessage}
      />
    </div>
  );
}