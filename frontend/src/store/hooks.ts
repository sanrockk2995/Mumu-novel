/**
 * Store Hooks - cung cấp chức năng lấy dữ liệu và tự động đồng bộ
 * Các hooks đóng gói logic lấy dữ liệu và tự động cập nhật store
 */

import { useCallback } from 'react';
import { message } from 'antd';
import { useStore } from './index';
import { projectApi, outlineApi, characterApi, chapterApi } from '../services/api';
import type {
  PaginationResponse,
  Outline,
  Character,
  Chapter,
  Project,
  ProjectCreate,
  ProjectUpdate,
  OutlineCreate,
  OutlineUpdate,
  ChapterCreate,
  ChapterUpdate,
  GenerateOutlineRequest,
  GenerateCharacterRequest
} from '../types';

/**
 * Đồng bộ dữ liệu dự án Hook
 */
export function useProjectSync() {
  const { setProjects, setLoading, addProject, updateProject, removeProject } = useStore();

  // Refresh danh sách dự án
  const refreshProjects = useCallback(async () => {
    try {
      setLoading(true);
      const data = await projectApi.getProjects();
      const projects = Array.isArray(data) ? data : (data as PaginationResponse<Project>).items || [];
      setProjects(projects);
      return projects;
    } catch (error) {
      console.error('Refresh danh sách dự án thất bại:', error);
      message.error('Refresh danh sách dự án thất bại');
      return [];
    } finally {
      setLoading(false);
    }
  }, [setProjects, setLoading]);

  // Tạo dự án (có đồng bộ)
  const createProject = useCallback(async (data: ProjectCreate) => {
    try {
      const created = await projectApi.createProject(data);
      addProject(created);
      return created;
    } catch (error) {
      console.error('Tạo dự án thất bại:', error);
      throw error;
    }
  }, [addProject]);

  // Cập nhật dự án (có đồng bộ)
  const updateProjectSync = useCallback(async (id: string, data: ProjectUpdate) => {
    try {
      const updated = await projectApi.updateProject(id, data);
      updateProject(id, updated);
      return updated;
    } catch (error) {
      console.error('Cập nhật dự án thất bại:', error);
      throw error;
    }
  }, [updateProject]);

  // Xóa dự án (có đồng bộ)
  const deleteProject = useCallback(async (id: string) => {
    try {
      await projectApi.deleteProject(id);
      removeProject(id);
    } catch (error) {
      console.error('Xóa dự án thất bại:', error);
      throw error;
    }
  }, [removeProject]);

  return {
    refreshProjects,
    createProject,
    updateProject: updateProjectSync,
    deleteProject,
  };
}

/**
 * Đồng bộ dữ liệu nhân vật Hook
 */
export function useCharacterSync() {
  const { currentProject, setCharacters, addCharacter, removeCharacter } = useStore();

  // Refresh danh sách nhân vật
  const refreshCharacters = useCallback(async (projectId?: string) => {
    const id = projectId || currentProject?.id;
    if (!id) return [];

    try {
      const data = await characterApi.getCharacters(id);
      const characters = Array.isArray(data) ? data : (data as PaginationResponse<Character>).items || [];
      setCharacters(characters);
      return characters;
    } catch (error) {
      console.error('Refresh danh sách nhân vật thất bại:', error);
      message.error('Refresh danh sách nhân vật thất bại');
      return [];
    }
  }, [currentProject?.id, setCharacters]);

  // Xóa nhân vật (có đồng bộ)
  const deleteCharacter = useCallback(async (id: string) => {
    try {
      await characterApi.deleteCharacter(id);
      removeCharacter(id);
    } catch (error) {
      console.error('Xóa nhân vật thất bại:', error);
      throw error;
    }
  }, [removeCharacter]);

  // Tạo nhân vật bằng AI (có đồng bộ)
  const generateCharacter = useCallback(async (data: GenerateCharacterRequest) => {
    try {
      const generated = await characterApi.generateCharacter(data);
      addCharacter(generated);
      return generated;
    } catch (error) {
      console.error('Tạo nhân vật bằng AI thất bại:', error);
      throw error;
    }
  }, [addCharacter]);

  return {
    refreshCharacters,
    deleteCharacter,
    generateCharacter,
  };
}

/**
 * Đồng bộ dữ liệu dàn ý Hook
 */
export function useOutlineSync() {
  const { currentProject, setOutlines, addOutline, updateOutline, removeOutline } = useStore();

  // Refresh danh sách dàn ý
  const refreshOutlines = useCallback(async (projectId?: string) => {
    const id = projectId || currentProject?.id;
    if (!id) return [];

    try {
      const data = await outlineApi.getOutlines(id);
      const outlines = Array.isArray(data) ? data : (data as PaginationResponse<Outline>).items || [];
      setOutlines(outlines);
      return outlines;
    } catch (error) {
      console.error('Refresh danh sách dàn ý thất bại:', error);
      message.error('Refresh danh sách dàn ý thất bại');
      return [];
    }
  }, [currentProject?.id, setOutlines]); // Thêm currentProject?.id vào mảng dependency

  // Tạo dàn ý (có đồng bộ)
  const createOutline = useCallback(async (data: OutlineCreate) => {
    try {
      const created = await outlineApi.createOutline(data);
      addOutline(created);
      return created;
    } catch (error) {
      console.error('Tạo dàn ý thất bại:', error);
      throw error;
    }
  }, [addOutline]);

  // Cập nhật dàn ý (có đồng bộ)
  const updateOutlineSync = useCallback(async (id: string, data: OutlineUpdate) => {
    try {
      const updated = await outlineApi.updateOutline(id, data);
      updateOutline(id, updated);
      return updated;
    } catch (error) {
      console.error('Cập nhật dàn ý thất bại:', error);
      throw error;
    }
  }, [updateOutline]);

  // Xóa dàn ý (có đồng bộ)
  const deleteOutline = useCallback(async (id: string) => {
    try {
      await outlineApi.deleteOutline(id);
      removeOutline(id);
    } catch (error) {
      console.error('Xóa dàn ý thất bại:', error);
      throw error;
    }
  }, [removeOutline]);

  // Tạo dàn ý bằng AI (có đồng bộ)
  const generateOutlines = useCallback(async (data: GenerateOutlineRequest) => {
    try {
      const result = await outlineApi.generateOutline(data);
      const outlines = Array.isArray(result) ? result : (result as PaginationResponse<Outline>).items || [];
      outlines.forEach((outline: Outline) => addOutline(outline));
      return outlines;
    } catch (error) {
      console.error('Tạo dàn ý bằng AI thất bại:', error);
      throw error;
    }
  }, [addOutline]);

  return {
    refreshOutlines,
    createOutline,
    updateOutline: updateOutlineSync,
    deleteOutline,
    generateOutlines,
  };
}

/**
 * Đồng bộ dữ liệu chương Hook
 */
export function useChapterSync() {
  const { currentProject, setChapters, addChapter, updateChapter, removeChapter } = useStore();

  // Refresh danh sách chương
  const refreshChapters = useCallback(async (projectId?: string) => {
    const id = projectId || currentProject?.id;
    if (!id) return [];

    try {
      const data = await chapterApi.getChapters(id);
      const chapters = Array.isArray(data) ? data : (data as PaginationResponse<Chapter>).items || [];
      setChapters(chapters);
      return chapters;
    } catch (error) {
      console.error('Refresh danh sách chương thất bại:', error);
      message.error('Refresh danh sách chương thất bại');
      return [];
    }
  }, [currentProject?.id, setChapters]); // Thêm currentProject?.id vào mảng dependency

  // Tạo chương (có đồng bộ)
  const createChapter = useCallback(async (data: ChapterCreate) => {
    try {
      const created = await chapterApi.createChapter(data);
      addChapter(created);
      return created;
    } catch (error) {
      console.error('Tạo chương thất bại:', error);
      throw error;
    }
  }, [addChapter]);

  // Cập nhật chương (có đồng bộ)
  const updateChapterSync = useCallback(async (id: string, data: ChapterUpdate) => {
    try {
      const updated = await chapterApi.updateChapter(id, data);
      updateChapter(id, updated);
      return updated;
    } catch (error) {
      console.error('Cập nhật chương thất bại:', error);
      throw error;
    }
  }, [updateChapter]);

  // Xóa chương (có đồng bộ)
  const deleteChapter = useCallback(async (id: string) => {
    try {
      await chapterApi.deleteChapter(id);
      removeChapter(id);
    } catch (error) {
      console.error('Xóa chương thất bại:', error);
      throw error;
    }
  }, [removeChapter]);

  // Tạo nội dung chương bằng AI theo stream (có đồng bộ)
  const generateChapterContentStream = useCallback(async (
    chapterId: string,
    onProgress?: (content: string) => void,
    styleId?: number,
    targetWordCount?: number,
    onProgressUpdate?: (message: string, progress: number) => void,
    model?: string,
    narrativePerspective?: string,
    skillKey?: string
  ) => {
    try {
      // Dùng fetch để xử lý response stream
      const response = await fetch(`/api/chapters/${chapterId}/generate-stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          style_id: styleId,
          target_word_count: targetWordCount,
          model: model,
          narrative_perspective: narrativePerspective,
          skill_key: skillKey
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('Không thể lấy response stream');
      }

      let buffer = '';
      let fullContent = '';
      let analysisTaskId: string | undefined;

      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        
        // Xử lý các message hoàn chỉnh trong buffer
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.trim() === '' || line.startsWith(':')) {
            continue;
          }

          try {
            const dataMatch = line.match(/^data: (.+)$/m);
            if (dataMatch) {
              const message = JSON.parse(dataMatch[1]);
              
              if (message.type === 'start') {
                // Bắt đầu tạo
                if (onProgressUpdate) {
                  onProgressUpdate(message.message || 'Bắt đầu tạo...', 0);
                }
              } else if (message.type === 'progress') {
                // Cập nhật tiến trình
                if (onProgressUpdate) {
                  onProgressUpdate(
                    message.message || 'Đang tạo...',
                    message.progress || 0
                  );
                }
              } else if ((message.type === 'content' || message.type === 'chunk') && message.content) {
                fullContent += message.content;
                if (onProgress) {
                  onProgress(fullContent);
                }
              } else if (message.type === 'error') {
                throw new Error(message.error || 'Tạo thất bại');
              } else if (message.type === 'result') {
                // Message kết quả, bao gồm ID task phân tích
                if (message.data?.analysis_task_id) {
                  analysisTaskId = message.data.analysis_task_id;
                }
                if (onProgressUpdate) {
                  onProgressUpdate('Tạo hoàn tất', 100);
                }
              } else if (message.type === 'done') {
                // Tạo hoàn tất, refresh dữ liệu chương
                await refreshChapters();
              } else if (message.type === 'analysis_started') {
                // Phân tích đã bắt đầu
                analysisTaskId = message.task_id;
                if (onProgressUpdate) {
                  onProgressUpdate('Phân tích chương đã bắt đầu...', 100);
                }
              } else if (message.type === 'analysis_queued') {
                // Task phân tích đã được thêm vào hàng đợi
                analysisTaskId = message.task_id;
              }
            }
          } catch (error) {
            console.error('Phân tích message SSE thất bại:', error);
          }
        }
      }

      return {
        content: fullContent,
        analysis_task_id: analysisTaskId
      };
    } catch (error) {
      console.error('Tạo nội dung chương bằng AI theo stream thất bại:', error);
      throw error;
    }
  }, [refreshChapters]);

  return {
    refreshChapters,
    createChapter,
    updateChapter: updateChapterSync,
    deleteChapter,
    generateChapterContentStream,
  };
}
