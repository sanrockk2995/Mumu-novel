// Định nghĩa kiểu người dùng
export interface User {
  user_id: string;
  username: string;
  display_name: string;
  avatar_url?: string;
  trust_level: number;
  is_admin: boolean;
  linuxdo_id: string;
  created_at: string;
  last_login: string;
}

export interface EmailLoginPayload {
  email: string;
  code: string;
}

export interface EmailRegisterPayload {
  email: string;
  code: string;
  password: string;
  display_name?: string;
}

export interface EmailSendCodePayload {
  email: string;
  scene: 'register' | 'login' | 'reset_password';
}

export interface EmailResetPasswordPayload {
  email: string;
  code: string;
  new_password: string;
}

export interface SystemSMTPSettings {
  id: string;
  user_id: string;
  smtp_provider: string;
  smtp_host?: string;
  smtp_port: number;
  smtp_username?: string;
  smtp_password?: string;
  smtp_use_tls: boolean;
  smtp_use_ssl: boolean;
  smtp_from_email?: string;
  smtp_from_name: string;
  email_auth_enabled: boolean;
  email_register_enabled: boolean;
  verification_code_ttl_minutes: number;
  verification_resend_interval_seconds: number;
  created_at: string;
  updated_at: string;
}

export interface SystemSMTPSettingsUpdate {
  smtp_provider?: string;
  smtp_host?: string;
  smtp_port?: number;
  smtp_username?: string;
  smtp_password?: string;
  smtp_use_tls?: boolean;
  smtp_use_ssl?: boolean;
  smtp_from_email?: string;
  smtp_from_name?: string;
  email_auth_enabled?: boolean;
  email_register_enabled?: boolean;
  verification_code_ttl_minutes?: number;
  verification_resend_interval_seconds?: number;
}

// Định nghĩa kiểu cài đặt
export interface Settings {
  id: string;
  user_id: string;
  api_provider: string;
  api_key: string;
  api_base_url: string;
  llm_model: string;
  temperature: number;
  max_tokens: number;
  system_prompt?: string;
  disable_thinking?: boolean;
  cover_api_provider?: string;
  cover_api_key?: string;
  cover_api_base_url?: string;
  cover_image_model?: string;
  cover_enabled?: boolean;
  preferences?: string;
  created_at: string;
  updated_at: string;
}

export interface SettingsUpdate {
  api_provider?: string;
  api_key?: string;
  api_base_url?: string;
  llm_model?: string;
  temperature?: number;
  max_tokens?: number;
  system_prompt?: string;
  disable_thinking?: boolean;
  cover_api_provider?: string;
  cover_api_key?: string;
  cover_api_base_url?: string;
  cover_image_model?: string;
  cover_enabled?: boolean;
  preferences?: string;
}

// Định nghĩa kiểu liên quan đến preset API
export interface APIKeyPresetConfig {
  api_provider: string;
  api_key: string;
  api_base_url?: string;
  llm_model: string;
  temperature: number;
  max_tokens: number;
  system_prompt?: string;
}

export interface APIKeyPreset {
  id: string;
  name: string;
  description?: string;
  is_active: boolean;
  created_at: string;
  config: APIKeyPresetConfig;
}

export interface PresetCreateRequest {
  name: string;
  description?: string;
  config: APIKeyPresetConfig;
}

export interface PresetUpdateRequest {
  name?: string;
  description?: string;
  config?: APIKeyPresetConfig;
}

export interface PresetListResponse {
  presets: APIKeyPreset[];
  total: number;
  active_preset_id?: string;
  chapter_analysis_preset_id?: string;
}

// Phản hồi URL ủy quyền LinuxDO
export interface AuthUrlResponse {
  auth_url: string;
  state: string;
}

// Định nghĩa kiểu dự án
export interface Project {
  id: string;  // Chuỗi UUID
  title: string;
  description?: string;
  theme?: string;
  genre?: string;
  target_words?: number;
  current_words: number;
  status: 'planning' | 'writing' | 'revising' | 'completed';
  wizard_status?: 'incomplete' | 'completed';
  wizard_step?: number;
  outline_mode: 'one-to-one' | 'one-to-many';  // Chế độ đề cương-chương
  world_time_period?: string;
  world_location?: string;
  world_atmosphere?: string;
  world_rules?: string;
  chapter_count?: number;
  narrative_perspective?: string;
  character_count?: number;
  cover_image_url?: string;
  cover_prompt?: string;
  cover_status?: 'none' | 'generating' | 'ready' | 'failed';
  cover_error?: string;
  cover_updated_at?: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  title: string;
  description?: string;
  theme?: string;
  genre?: string;
  target_words?: number;
  outline_mode?: 'one-to-one' | 'one-to-many';  // Chế độ đề cương-chương, mặc định one-to-many
  wizard_status?: 'incomplete' | 'completed';
  wizard_step?: number;
  world_time_period?: string;
  world_location?: string;
  world_atmosphere?: string;
  world_rules?: string;
}

export interface ProjectUpdate {
  title?: string;
  description?: string;
  theme?: string;
  genre?: string;
  target_words?: number;
  status?: 'planning' | 'writing' | 'revising' | 'completed';
  world_time_period?: string;
  world_location?: string;
  world_atmosphere?: string;
  world_rules?: string;
  chapter_count?: number;
  narrative_perspective?: string;
  character_count?: number;
  // current_words tự động tính từ nội dung chương, không có trong interface này
}

// Interface cập nhật dự án dành riêng cho wizard, gồm các trường điều khiển luồng wizard
export interface ProjectWizardUpdate extends ProjectUpdate {
  wizard_status?: 'incomplete' | 'completed';
  wizard_step?: number;
}

// Wizard tạo dự án
export interface ProjectWizardRequest {
  title: string;
  theme: string;
  genre?: string;
  chapter_count: number;
  narrative_perspective: string;
  character_count?: number;
  target_words?: number;
  outline_mode?: 'one-to-one' | 'one-to-many';  // Chế độ đề cương-chương
  world_building?: {
    time_period: string;
    location: string;
    atmosphere: string;
    rules: string;
  };
}

export interface WorldBuildingResponse {
  project_id: string;
  time_period: string;
  location: string;
  atmosphere: string;
  rules: string;
}

// Định nghĩa kiểu đề cương
export interface Outline {
  id: string;
  project_id: string;
  title: string;
  content: string;
  structure?: string;
  order_index: number;
  has_chapters?: boolean;
  created_at: string;
  updated_at: string;
}

export interface OutlineCreate {
  project_id: string;
  title: string;
  content: string;
  structure?: string;
  order_index: number;
}

export interface OutlineUpdate {
  title?: string;
  content?: string;
  structure?: string;  // Hỗ trợ sửa trường structure
  // order_index chỉ có thể điều chỉnh hàng loạt qua interface reorder
}

export interface AgentConversation {
  id: string;
  user_id: string;
  project_id: string;
  title: string;
  summary?: string;
  status: string;
  last_message_at: string;
  created_at: string;
  updated_at: string;
}

export interface AgentMessage {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'tool' | 'system';
  content: string;
  model?: string;
  prompt_tokens?: number;
  completion_tokens?: number;
  created_at: string;
}

export interface AgentToolCall {
  id: string;
  conversation_id: string;
  message_id?: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  risk_level: number;
  requires_confirmation: boolean;
  status: string;
  preview?: {
    entity_type: string;
    entity_id: string;
    label: string;
    changes: Record<string, { before: unknown; after: unknown }>;
    resources: string[];
  };
  result?: Record<string, unknown>;
  error_message?: string;
  created_at: string;
}

export interface AgentExecutionStep {
  id: string;
  conversation_id: string;
  user_message_id?: string;
  assistant_message_id?: string;
  tool_call_id?: string;
  sequence: number;
  step_type: 'thought' | 'tool' | 'skill' | string;
  category: 'analysis' | 'project' | 'mcp' | 'skill' | string;
  title: string;
  content?: string;
  status: 'running' | 'completed' | 'failed' | 'cancelled' | 'rejected' | 'waiting_confirmation' | string;
  detail?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface AgentConversationDetail extends AgentConversation {
  messages: AgentMessage[];
  tool_calls: AgentToolCall[];
  execution_steps: AgentExecutionStep[];
}

export interface AgentToolDecision {
  success: boolean;
  message: string;
  tool_call: AgentToolCall;
  resources: string[];
}

export type OutlineImportMode = 'append' | 'merge';

export interface OutlineImportPreview {
  valid: boolean;
  version: string;
  source_type: 'outlines' | 'project' | 'unknown';
  source_project?: {
    title: string;
    outline_mode: 'one-to-one' | 'one-to-many';
  } | null;
  target_outline_mode?: 'one-to-one' | 'one-to-many' | null;
  mode: OutlineImportMode;
  statistics: {
    total: number;
    will_create: number;
    will_update: number;
    will_create_chapters: number;
  };
  errors: string[];
  warnings: string[];
}

export interface OutlineImportResult {
  success: boolean;
  message: string;
  mode: OutlineImportMode;
  imported: number;
  updated: number;
  created_chapters: number;
  details: Array<{
    source_order_index: number;
    target_order_index: number;
    title: string;
    action: 'created' | 'updated';
  }>;
  warnings: string[];
}

// Định nghĩa kiểu nhân vật
export interface Character {
  id: string;
  project_id: string;
  name: string;
  age?: string;
  gender?: string;
  is_organization: boolean;
  role_type?: string;
  personality?: string;
  background?: string;
  appearance?: string;
  relationships?: string;
  organization_type?: string;
  organization_purpose?: string;
  organization_members?: string;
  traits?: string;
  avatar_url?: string;
  // Trường mở rộng tổ chức (liên kết từ bảng Organization)
  power_level?: number;
  location?: string;
  motto?: string;
  color?: string;
  // Trạng thái nhân vật/tổ chức
  status?: string;
  status_changed_chapter?: number;
  current_state?: string;
  state_updated_chapter?: number;
  // Trường liên quan đến nghề nghiệp
  main_career_id?: string;
  main_career_stage?: number;
  sub_careers?: Array<{
    career_id: string;
    stage: number;
  }>;
  created_at: string;
  updated_at: string;
}

export interface CharacterUpdate {
  name?: string;
  age?: string;
  gender?: string;
  is_organization?: boolean;
  role_type?: string;
  personality?: string;
  background?: string;
  appearance?: string;
  organization_type?: string;
  organization_purpose?: string;
  organization_members?: string;
  traits?: string;
  // Trường mở rộng tổ chức
  power_level?: number;
  location?: string;
  motto?: string;
  color?: string;
}

// Cấu trúc dữ liệu kế hoạch mở rộng
export interface ExpansionPlanData {
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
}

// Định nghĩa kiểu chương
export interface Chapter {
  id: string;
  project_id: string;
  title: string;
  content?: string;
  summary?: string;
  chapter_number: number;
  word_count: number;
  status: 'draft' | 'writing' | 'completed';
  expansion_plan?: string; // Chuỗi JSON, sau khi parse là ExpansionPlanData
  outline_id?: string; // ID đề cương liên kết
  sub_index?: number; // Số thứ tự chương con dưới đề cương
  outline_title?: string; // Tiêu đề đề cương (lấy từ truy vấn join backend)
  outline_order?: number; // Số thứ tự sắp xếp đề cương (lấy từ truy vấn join backend)
  created_at: string;
  updated_at: string;
}

export interface ChapterCreate {
  project_id: string;
  title: string;
  chapter_number: number;
  content?: string;
  summary?: string;
  status?: 'draft' | 'writing' | 'completed';
}

export interface ChapterUpdate {
  title?: string;
  content?: string;
  // chapter_number không được phép sửa, do thứ tự đề cương quyết định
  summary?: string;
  // word_count tự động tính, không được sửa tay
  status?: 'draft' | 'writing' | 'completed';
}

// Kiểu request tạo chương
export interface ChapterGenerateRequest {
  style_id?: number;
  target_word_count?: number;
}

// Phản hồi kiểm tra tạo chương
export interface ChapterCanGenerateResponse {
  can_generate: boolean;
  reason: string;
  previous_chapters: {
    id: string;
    chapter_number: number;
    title: string;
    has_content: boolean;
    word_count: number;
  }[];
  chapter_number: number;
}

// Kiểu request tạo AI
export interface GenerateOutlineRequest {
  project_id: string;
  genre?: string;
  theme: string;
  chapter_count: number;
  narrative_perspective: string;
  world_context?: Record<string, unknown>;
  characters_context?: Character[];
  target_words?: number;
  requirements?: string;
  provider?: string;
  model?: string;
  // Trường mới của chức năng viết tiếp
  mode?: 'auto' | 'new' | 'continue';
  story_direction?: string;
  plot_stage?: 'development' | 'climax' | 'ending';
  keep_existing?: boolean;
}

// Kiểu request sắp xếp lại đề cương
export interface OutlineReorderItem {
  id: string;
  order_index: number;
}

export interface OutlineReorderRequest {
  orders: OutlineReorderItem[];
}

// Định nghĩa kiểu liên quan đến mở rộng đề cương
export interface ChapterPlanItem {
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
  }>;
}

export interface OutlineExpansionRequest {
  target_chapter_count: number;
  expansion_strategy?: 'balanced' | 'climax' | 'detail';
  auto_create_chapters?: boolean;
  provider?: string;
  model?: string;
}

export interface OutlineExpansionResponse {
  outline_id: string;
  outline_title: string;
  target_chapter_count: number;
  actual_chapter_count: number;
  expansion_strategy: string;
  chapter_plans: ChapterPlanItem[];
  created_chapters?: Array<{
    id: string;
    chapter_number: number;
    title: string;
    summary: string;
    outline_id: string;
    sub_index: number;
    status: string;
  }> | null;
}

export interface BatchOutlineExpansionRequest {
  project_id: string;
  outline_ids?: string[];
  chapters_per_outline: number;
  expansion_strategy?: 'balanced' | 'climax' | 'detail';
  auto_create_chapters?: boolean;
  provider?: string;
  model?: string;
}

export interface BatchOutlineExpansionResponse {
  project_id: string;
  total_outlines_expanded: number;
  total_chapters_created: number;
  expansion_results: OutlineExpansionResponse[];
  skipped_outlines?: Array<{
    outline_id: string;
    outline_title: string;
    reason: string;
  }>;
}

export interface GenerateCharacterRequest {
  project_id: string;
  name?: string;
  role_type?: string;
  background?: string;
  requirements?: string;
  provider?: string;
  model?: string;
}

export interface PolishTextRequest {
  text: string;
  style?: string;
}

// Kiểu phản hồi API wizard
export interface GenerateCharactersResponse {
  characters: Character[];
}

export interface GenerateOutlineResponse {
  outlines: Outline[];
}

// Kiểu phản hồi API
export interface ApiResponse<T> {
  data: T;
  message?: string;
}

// Định nghĩa kiểu phong cách viết
export interface WritingStyle {
  id: number;
  user_id: string | null;  // NULL nghĩa là phong cách preset toàn cục
  name: string;
  style_type: 'preset' | 'custom';
  preset_id?: string;
  description?: string;
  prompt_content: string;
  is_default: boolean;
  order_index: number;
  created_at: string;
  updated_at: string;
}

export interface WritingStyleCreate {
  name: string;
  style_type?: 'preset' | 'custom';
  preset_id?: string;
  description?: string;
  prompt_content: string;
}

export interface WritingStyleUpdate {
  name?: string;
  description?: string;
  prompt_content?: string;
  order_index?: number;
}

export interface PresetStyle {
  id: string;
  name: string;
  description: string;
  prompt_content: string;
}

export interface WritingStyleListResponse {
  styles: WritingStyle[];
  total: number;
}

export interface PaginationResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// Kiểu dữ liệu form wizard
export interface WizardBasicInfo {
  title: string;
  description: string;
  theme: string;
  genre: string | string[];
  chapter_count: number;
  narrative_perspective: string;
  character_count?: number;
  target_words?: number;
  outline_mode?: 'one-to-one' | 'one-to-many';  // Chế độ đề cương-chương
}

// Kiểu phản hồi lỗi API
export interface ApiError {
  response?: {
    data?: {
      detail?: string;
    };
  };
  message?: string;
}

// Kiểu liên quan đến task phân tích chương
export interface AnalysisTask {
  has_task: boolean;
  task_id: string | null;
  chapter_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'none';
  progress: number;
  error_message?: string | null;
  auto_recovered?: boolean;
  created_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface BatchAnalysisStatusResponse {
  project_id: string;
  total: number;
  items: Record<string, AnalysisTask>;
}

export interface BatchAnalyzeUnanalyzedRequest {
  chapter_ids?: string[];
}

export interface BatchAnalyzeUnanalyzedResponse {
  project_id: string;
  total_candidates: number;
  total_started: number;
  total_skipped_no_content: number;
  total_skipped_running: number;
  total_already_completed: number;
  started_tasks: Record<string, AnalysisTask>;
}

// Kết quả phân tích - Hook
export interface AnalysisHook {
  type: string;
  content: string;
  strength: number;
  position: string;
}

// Kết quả phân tích - phục bút
export interface AnalysisForeshadow {
  content: string;
  type: 'planted' | 'resolved';
  strength: number;
  subtlety: number;
  reference_chapter?: number;
}

// Kết quả phân tích - xung đột
export interface AnalysisConflict {
  types: string[];
  parties: string[];
  level: number;
  description: string;
  resolution_progress: number;
}

// Kết quả phân tích - đường cong cảm xúc
export interface AnalysisEmotionalArc {
  primary_emotion: string;
  intensity: number;
  curve: string;
  secondary_emotions: string[];
}

// Kết quả phân tích - trạng thái nhân vật
export interface AnalysisCharacterState {
  character_name: string;
  state_before: string;
  state_after: string;
  psychological_change: string;
  key_event: string;
  relationship_changes: Record<string, string>;
}

// Kết quả phân tích - điểm cốt truyện
export interface AnalysisPlotPoint {
  content: string;
  type: 'revelation' | 'conflict' | 'resolution' | 'transition';
  importance: number;
  impact: string;
}

// Kết quả phân tích - cảnh
export interface AnalysisScene {
  location: string;
  atmosphere: string;
  duration: string;
}

// Kết quả phân tích - điểm số
export interface AnalysisScores {
  pacing: number;
  engagement: number;
  coherence: number;
  overall: number;
}

// Dữ liệu phân tích đầy đủ - khớp model PlotAnalysis backend
export interface AnalysisData {
  id: string;
  chapter_id: string;
  plot_stage: string;
  conflict_level: number;
  conflict_types: string[];
  emotional_tone: string;
  emotional_intensity: number;
  hooks: AnalysisHook[];
  hooks_count: number;
  foreshadows: AnalysisForeshadow[];
  foreshadows_planted: number;
  foreshadows_resolved: number;
  plot_points: AnalysisPlotPoint[];
  plot_points_count: number;
  character_states: AnalysisCharacterState[];
  scenes?: AnalysisScene[];
  pacing: string;
  overall_quality_score: number;
  pacing_score: number;
  engagement_score: number;
  coherence_score: number;
  analysis_report: string;
  suggestions: string[];
  dialogue_ratio: number;
  description_ratio: number;
  created_at: string;
}

// Đoạn ký ức
export interface StoryMemory {
  id: string;
  type: 'hook' | 'foreshadow' | 'plot_point' | 'character_event';
  title: string;
  content: string;
  importance: number;
  tags: string[];
  is_foreshadow: 0 | 1 | 2; // 0=thường, 1=đã gieo, 2=đã thu hồi
}

export interface EntityChangesSummaryItem {
  updated_count?: number;
  state_updated_count?: number;
  relationship_created_count?: number;
  relationship_updated_count?: number;
  org_updated_count?: number;
  changes: string[];
}

// Phản hồi kết quả phân tích chương - khớp API backend trả về
export interface ChapterAnalysisResponse {
  chapter_id: string;
  analysis: AnalysisData;  // Lưu ý: backend trả về analysis chứ không phải analysis_data
  memories: StoryMemory[];
  created_at: string;
  entity_changes?: {
    careers: EntityChangesSummaryItem;
    character_states: EntityChangesSummaryItem;
    organization_states: EntityChangesSummaryItem;
  };
}

// Phản hồi kích hoạt phân tích thủ công
export interface TriggerAnalysisResponse {
  task_id: string;
  chapter_id: string;
  status: string;
  message: string;
}

// Định nghĩa kiểu plugin MCP - sau tối ưu chỉ gồm trường cần thiết
export interface MCPPlugin {
  id: string;
  plugin_name: string;
  display_name: string;
  description?: string;
  plugin_type: 'http' | 'stdio' | 'streamable_http' | 'sse';
  category: string;

  // Trường kiểu HTTP
  server_url?: string;
  headers?: Record<string, string>;

  // Trường kiểu Stdio
  command?: string;
  args?: string[];
  env?: Record<string, string>;

  // Trường trạng thái
  enabled: boolean;
  status: 'active' | 'inactive' | 'error';
  last_error?: string;
  last_test_at?: string;

  // Dấu thời gian
  created_at: string;
}

export interface MCPPluginCreate {
  plugin_name: string;
  display_name?: string;
  description?: string;
  server_type: 'http' | 'stdio' | 'streamable_http' | 'sse';
  server_url?: string;
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  headers?: Record<string, string>;
  enabled?: boolean;
}

export interface MCPPluginUpdate {
  display_name?: string;
  description?: string;
  server_url?: string;
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  headers?: Record<string, string>;
  enabled?: boolean;
}

export interface MCPTool {
  name: string;
  description?: string;
  inputSchema?: Record<string, unknown>;
}

export interface MCPTestResult {
  success: boolean;
  message: string;
  tools?: MCPTool[];
  tools_count?: number;
  response_time_ms?: number;
  error?: string;
  error_type?: string;
  suggestions?: string[];
}

export interface MCPToolCallRequest {
  plugin_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
}

export interface MCPToolCallResponse {
  success: boolean;
  result?: unknown;
  error?: string;
}

// Định nghĩa kiểu quản lý phục bút
export type ForeshadowStatus = 'pending' | 'planted' | 'resolved' | 'partially_resolved' | 'abandoned';
export type ForeshadowSourceType = 'analysis' | 'manual';
export type ForeshadowCategory = 'identity' | 'mystery' | 'item' | 'relationship' | 'event' | 'ability' | 'prophecy';

export interface Foreshadow {
  id: string;
  project_id: string;
  title: string;
  content: string;
  hint_text?: string;
  resolution_text?: string;
  source_type?: ForeshadowSourceType;
  source_memory_id?: string;
  source_analysis_id?: string;
  plant_chapter_id?: string;
  plant_chapter_number?: number;
  target_resolve_chapter_id?: string;
  target_resolve_chapter_number?: number;
  actual_resolve_chapter_id?: string;
  actual_resolve_chapter_number?: number;
  status: ForeshadowStatus;
  is_long_term: boolean;
  importance: number;
  strength: number;
  subtlety: number;
  urgency: number;
  related_characters?: string[];
  related_foreshadow_ids?: string[];
  tags?: string[];
  category?: ForeshadowCategory;
  notes?: string;
  resolution_notes?: string;
  auto_remind: boolean;
  remind_before_chapters: number;
  include_in_context: boolean;
  created_at?: string;
  updated_at?: string;
  planted_at?: string;
  resolved_at?: string;
}

export interface ForeshadowCreate {
  project_id: string;
  title: string;
  content: string;
  hint_text?: string;
  resolution_text?: string;
  plant_chapter_number?: number;
  target_resolve_chapter_number?: number;
  is_long_term?: boolean;
  importance?: number;
  strength?: number;
  subtlety?: number;
  related_characters?: string[];
  tags?: string[];
  category?: ForeshadowCategory;
  notes?: string;
  resolution_notes?: string;
  auto_remind?: boolean;
  remind_before_chapters?: number;
  include_in_context?: boolean;
}

export interface ForeshadowUpdate {
  title?: string;
  content?: string;
  hint_text?: string;
  resolution_text?: string;
  plant_chapter_number?: number;
  target_resolve_chapter_number?: number;
  status?: ForeshadowStatus;
  is_long_term?: boolean;
  importance?: number;
  strength?: number;
  subtlety?: number;
  urgency?: number;
  related_characters?: string[];
  related_foreshadow_ids?: string[];
  tags?: string[];
  category?: ForeshadowCategory;
  notes?: string;
  resolution_notes?: string;
  auto_remind?: boolean;
  remind_before_chapters?: number;
  include_in_context?: boolean;
}

export interface ForeshadowStats {
  total: number;
  pending: number;
  planted: number;
  resolved: number;
  partially_resolved: number;
  abandoned: number;
  long_term_count: number;
  overdue_count: number;
}

export interface ForeshadowListResponse {
  total: number;
  items: Foreshadow[];
  stats?: ForeshadowStats;
}

export interface PlantForeshadowRequest {
  chapter_id: string;
  chapter_number: number;
  hint_text?: string;
}

export interface ResolveForeshadowRequest {
  chapter_id: string;
  chapter_number: number;
  resolution_text?: string;
  is_partial?: boolean;
}

export interface SyncFromAnalysisRequest {
  chapter_ids?: string[];
  overwrite_existing?: boolean;
  auto_set_planted?: boolean;
}

export interface SyncFromAnalysisResponse {
  synced_count: number;
  skipped_count: number;
  new_foreshadows: Foreshadow[];
  skipped_reasons: Array<{ source_memory_id: string; reason: string }>;
}

export interface ForeshadowContextResponse {
  chapter_number: number;
  context_text: string;
  pending_plant: Foreshadow[];
  pending_resolve: Foreshadow[];
  overdue: Foreshadow[];
  recently_planted: Foreshadow[];
}

// ==================== Định nghĩa kiểu nhập tách sách ====================

export type BookImportTaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
export type BookImportWarningLevel = 'info' | 'warning' | 'error';
export type BookImportExtractMode = 'tail' | 'full';

export interface BookImportWarning {
  code: string;
  message: string;
  level: BookImportWarningLevel;
}

export interface BookImportProjectSuggestion {
  title: string;
  description?: string;
  theme?: string;
  genre?: string;
  narrative_perspective: string;
  target_words: number;
}

export interface BookImportChapter {
  title: string;
  content: string;
  summary?: string;
  chapter_number: number;
  outline_title?: string;
}

export interface BookImportOutline {
  title: string;
  content?: string;
  order_index: number;
  structure?: Record<string, unknown>;
}

export interface BookImportTask {
  task_id: string;
  status: BookImportTaskStatus;
  progress: number;
  message?: string;
  error?: string;
  created_at: string;
  updated_at: string;
}

export interface BookImportPreview {
  task_id: string;
  project_suggestion: BookImportProjectSuggestion;
  chapters: BookImportChapter[];
  outlines: BookImportOutline[];
  warnings: BookImportWarning[];
}

export interface BookImportApplyPayload {
  project_suggestion: BookImportProjectSuggestion;
  chapters: BookImportChapter[];
  outlines: BookImportOutline[];
  import_mode?: 'append' | 'overwrite';
}

export interface BookImportCreateTaskPayload {
  file: File;
  extract_mode?: BookImportExtractMode;
  tail_chapter_count?: number;
}

export interface BookImportResult {
  success: boolean;
  project_id: string;
  statistics: {
    chapters: number;
    outlines: number;
    generated_careers?: number;
    generated_entities?: number;
    generated_world_building?: number;
  };
  warnings: BookImportWarning[];
}

export interface BookImportStepFailure {
  step_name: string;       // world_building / career_system / characters
  step_label: string;      // Tên bước (tiếng Trung, do backend trả về)
  error: string;           // Chi tiết lỗi
  retry_count?: number;    // Số lần đã thử lại
}

export interface BookImportRetryResult {
  success: boolean;
  project_id: string;
  retry_results: Record<string, number>;
  still_failed: BookImportStepFailure[];
}

// ==================== Định nghĩa kiểu prompt workshop ====================

export interface PromptWorkshopItem {
  id: string;
  name: string;
  description?: string;
  prompt_content: string;
  category: string;
  tags?: string[];
  author_name?: string;
  is_official: boolean;
  download_count: number;
  like_count: number;
  is_liked?: boolean;
  created_at?: string;
}

export interface PromptSubmission {
  id: string;
  name: string;
  description?: string;
  prompt_content?: string;
  category: string;
  tags?: string[];
  author_display_name?: string;
  is_anonymous: boolean;
  status: 'pending' | 'approved' | 'rejected';
  review_note?: string;
  reviewed_at?: string;
  created_at?: string;
  source_instance?: string;
  submitter_name?: string;
}

export interface PromptSubmissionCreate {
  name: string;
  description?: string;
  prompt_content: string;
  category: string;
  tags?: string[];
  author_display_name?: string;
  is_anonymous?: boolean;
  source_style_id?: number;
}

export interface PromptWorkshopCategory {
  id: string;
  name: string;
  count: number;
}

export interface PromptWorkshopListResponse {
  success: boolean;
  data: {
    total: number;
    page: number;
    limit: number;
    items: PromptWorkshopItem[];
    categories: PromptWorkshopCategory[];
  };
}

export interface PromptWorkshopStatusResponse {
  mode: 'client' | 'server';
  instance_id: string;
  cloud_url?: string;
  cloud_connected?: boolean;
}

export interface PromptWorkshopAdminStats {
  total_items: number;
  total_official: number;
  total_pending: number;
  total_downloads: number;
  total_likes: number;
}

// ==================== Định nghĩa kiểu thông báo ====================

export type AnnouncementLevel = 'info' | 'success' | 'warning' | 'error';
export type AnnouncementStatus = 'draft' | 'published' | 'hidden';

export interface Announcement {
  id: string;
  title: string;
  content: string;
  summary?: string | null;
  level: AnnouncementLevel;
  status?: AnnouncementStatus;
  pinned: boolean;
  author_id?: string | null;
  author_name?: string | null;
  publish_at?: string | null;
  expire_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface AnnouncementCreate {
  title: string;
  content: string;
  summary?: string;
  level?: AnnouncementLevel;
  status?: AnnouncementStatus;
  pinned?: boolean;
  publish_at?: string;
  expire_at?: string;
}

export interface AnnouncementUpdate {
  title?: string;
  content?: string;
  summary?: string;
  level?: AnnouncementLevel;
  status?: AnnouncementStatus;
  pinned?: boolean;
  publish_at?: string | null;
  expire_at?: string | null;
}

export interface AnnouncementListResponse {
  success: boolean;
  data: {
    total: number;
    page: number;
    limit: number;
    items: Announcement[];
    active_ids?: string[];
    latest_updated_at?: string | null;
    server_time?: string;
  };
}

export interface AnnouncementStatusResponse {
  mode: 'client' | 'server' | string;
  instance_id: string;
  cloud_url?: string;
  cloud_connected?: boolean;
}

// Hằng số phân loại prompt workshop
export const PROMPT_CATEGORIES: Record<string, string> = {
  general: 'Chung',
  fantasy: 'Huyền huyễn/Tiên hiệp',
  martial: 'Võ hiệp',
  romance: 'Ngôn tình',
  scifi: 'Khoa học viễn tưởng',
  horror: 'Trinh thám/Kinh dị',
  history: 'Lịch sử',
  urban: 'Đô thị',
  game: 'Game/Esports',
  other: 'Khác',
};
