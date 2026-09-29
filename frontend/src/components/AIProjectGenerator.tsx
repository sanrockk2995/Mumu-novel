import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Button, Space, Typography, message, Progress, Modal, theme } from 'antd';
import { CheckCircleOutlined, LoadingOutlined } from '@ant-design/icons';
import { wizardStreamApi } from '../services/api';
import type { ApiError } from '../types';

const { Title, Paragraph, Text } = Typography;

export interface GenerationConfig {
  title: string;
  description: string;
  theme: string;
  genre: string | string[];
  narrative_perspective: string;
  target_words: number;
  chapter_count: number;
  character_count: number;
  outline_mode?: 'one-to-one' | 'one-to-many';  // Chế độ chương dàn ý
}

interface AIProjectGeneratorProps {
  config: GenerationConfig;
  storagePrefix: 'wizard' | 'inspiration';
  onComplete: (projectId: string) => void;
  onBack?: () => void;
  isMobile?: boolean;
  resumeProjectId?: string;
}

type GenerationStep = 'pending' | 'processing' | 'completed' | 'error';

interface GenerationSteps {
  worldBuilding: GenerationStep;
  careers: GenerationStep;
  characters: GenerationStep;
  outline: GenerationStep;
}

interface WorldBuildingResult {
  project_id: string;
  time_period: string;
  location: string;
  atmosphere: string;
  rules: string;
}

const isAbortError = (error: unknown): boolean =>
  typeof error === 'object'
  && error !== null
  && 'name' in error
  && error.name === 'AbortError';

export const AIProjectGenerator: React.FC<AIProjectGeneratorProps> = ({
  config,
  storagePrefix,
  onComplete,
  onBack,
  isMobile = false,
  resumeProjectId
}) => {
  const navigate = useNavigate();
  const { token } = theme.useToken();
  const alphaColor = (color: string, alpha: number) =>
    `color-mix(in srgb, ${color} ${(alpha * 100).toFixed(0)}%, transparent)`;

  // Quản lý trạng thái
  const [loading, setLoading] = useState(false);
  const [projectId, setProjectId] = useState<string>('');

  // Trạng thái tiến trình streaming SSE
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const [errorDetails, setErrorDetails] = useState<string>('');
  const [generationSteps, setGenerationSteps] = useState<GenerationSteps>({
    worldBuilding: 'pending',
    careers: 'pending',
    characters: 'pending',
    outline: 'pending'
  });

  // Lưu dữ liệu sinh để thử lại
  const [generationData, setGenerationData] = useState<GenerationConfig | null>(null);
  // Lưu kết quả sinh thế giới quan cho các bước sau
  const [worldBuildingResult, setWorldBuildingResult] = useState<WorldBuildingResult | null>(null);

  // LocalStorage Tên key
  const storageKeys = {
    projectId: `${storagePrefix}_project_id`,
    generationData: `${storagePrefix}_generation_data`,
    currentStep: `${storagePrefix}_current_step`
  };

  // Lưu tiến độ vào localStorage
  const saveProgress = (projectId: string, data: GenerationConfig, step: string) => {
    try {
      localStorage.setItem(storageKeys.projectId, projectId);
      localStorage.setItem(storageKeys.generationData, JSON.stringify(data));
      localStorage.setItem(storageKeys.currentStep, step);
    } catch (error) {
      console.error('Lưu tiến độ thất bại:', error);
    }
  };

  // Dọn dẹp localStorage
  const clearStorage = () => {
    localStorage.removeItem(storageKeys.projectId);
    localStorage.removeItem(storageKeys.generationData);
    localStorage.removeItem(storageKeys.currentStep);
  };

  const handleRestartGeneration = () => {
    Modal.confirm({
      title: 'Xác nhận bắt đầu lại quá trình sinh',
      content: 'Tiến trình sinh hiện tại sẽ bị hủy và quay lại cuộc trò chuyện gợi ý để cấu hình lại. Dữ liệu dự án đã tạo sẽ không tự động bị xóa.',
      okText: 'Bắt đầu lại',
      cancelText: 'Hủy',
      centered: true,
      okButtonProps: { danger: true },
      onOk: () => {
        clearStorage();
        onBack?.();
      },
    });
  };

  // Dùng nội dung cấu hình làm dependency, tránh khởi động lại quy trình sinh khi component cha tạo object mới tương đương.
  const generationKey = JSON.stringify([
    config.title,
    config.description,
    config.theme,
    config.genre,
    config.narrative_perspective,
    config.target_words,
    config.chapter_count,
    config.character_count,
    config.outline_mode,
  ]);

  // Bắt đầu quy trình sinh tự động
  useEffect(() => {
    const controller = new AbortController();

    // Trì hoãn đến vòng lặp sự kiện tiếp theo: StrictMode StrictMode sẽ dọn dẹp ngay lần thăm dò đầu tiên  Effect, 
    // vì vậy lần thăm dò sẽ không thực sự gửi yêu cầu sinh, lần  Effect thứ hai chính thức mới khởi động quy trình.
    const startTimer = window.setTimeout(() => {
      if (controller.signal.aborted) return;

      if (resumeProjectId) {
        // Chế độ khôi phục sinh
        void handleResumeGenerate(config, resumeProjectId, controller.signal);
      } else {
        // Chế độ tạo dự án mới
        void handleAutoGenerate(config, controller.signal);
      }
    }, 0);

    return () => {
      window.clearTimeout(startTimer);
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [generationKey, resumeProjectId]);

  // Khôi phục sinh cho dự án chưa hoàn tất
  const handleResumeGenerate = async (
    data: GenerationConfig,
    projectIdParam: string,
    signal?: AbortSignal,
  ) => {
    try {
      setLoading(true);
      setProgress(0);
      setProgressMessage('Đang kiểm tra trạng thái dự án...');
      setErrorDetails('');
      setGenerationData(data);
      setProjectId(projectIdParam);

      // Lấy thông tin dự án,, xác định đã hoàn thành đến bước nào
      const response = await fetch(`/api/projects/${projectIdParam}`, {
        credentials: 'include',
        signal,
      });
      if (!response.ok) {
        throw new Error('Lấy thông tin dự án thất bại');
      }
      const project = await response.json();
      const wizardStep = project.wizard_step || 0;

      // Dựa vào wizard_stepwizard_step để xác định tiếp tục từ đâu
      // wizard_step: 0=chưa bắt đầu, 1=Thế giới quan đã xong, 2=Hệ thống nghề nghiệp đã xong, 3=Nhân vật đã xong, 4=dàn ý đã xong
      // Lấy dữ liệu thế giới quan (cho các bước sau)
      const worldResult = {
        project_id: projectIdParam,
        time_period: project.world_time_period || '',
        location: project.world_location || '',
        atmosphere: project.world_atmosphere || '',
        rules: project.world_rules || ''
      };

      if (wizardStep === 0) {
        // Bắt đầu từ thế giới quan
        message.info('Bắt đầu sinh từ bước thế giới quan...');
        setGenerationSteps({ worldBuilding: 'processing', careers: 'pending', characters: 'pending', outline: 'pending' });
        await resumeFromWorldBuilding(data, signal);
      } else if (wizardStep === 1) {
        // Thế giới quan đã xong, bắt đầu từ hệ thống nghề nghiệp
        message.info('Thế giới quan đã xong, tiếp tục từ bước hệ thống nghề nghiệp...');
        setGenerationSteps({ worldBuilding: 'completed', careers: 'processing', characters: 'pending', outline: 'pending' });
        setWorldBuildingResult(worldResult);
        setProgress(20);
        await resumeFromCareers(data, worldResult, signal);
      } else if (wizardStep === 2) {
        // Hệ thống nghề nghiệp đã xong, bắt đầu từ nhân vật
        message.info('Hệ thống nghề nghiệp đã xong, tiếp tục từ bước nhân vật...');
        setGenerationSteps({ worldBuilding: 'completed', careers: 'completed', characters: 'processing', outline: 'pending' });
        setWorldBuildingResult(worldResult);
        setProgress(40);
        await resumeFromCharacters(data, worldResult, signal);
      } else if (wizardStep === 3) {
        // Nhân vật đã xong, bắt đầu từ dàn ý
        message.info('Nhân vật đã xong, tiếp tục từ bước dàn ý...');
        setGenerationSteps({ worldBuilding: 'completed', careers: 'completed', characters: 'completed', outline: 'processing' });
        setProgress(70);
        await resumeFromOutline(data, projectIdParam, signal);
      } else {
        // Đã hoàn tất toàn bộ
        message.success('Dự án đã hoàn tất,, đang chuyển hướng...');
        setProgress(100);
        onComplete(projectIdParam);
        setTimeout(() => {
          navigate(`/project/${projectIdParam}`);
        }, 1000);
      }
    } catch (error) {
      if (isAbortError(error)) return;

      const apiError = error as ApiError;
      const errorMsg = apiError.response?.data?.detail || apiError.message || 'Lỗi không xác định';
      console.error('Khôi phục sinh thất bại:', errorMsg);
      setErrorDetails(errorMsg);
      message.error('Khôi phục sinh thất bại: ' + errorMsg);
      setLoading(false);
    }
  };

  // Khôi phục:: bắt đầu từ bước thế giới quan
  const resumeFromWorldBuilding = async (data: GenerationConfig, signal?: AbortSignal) => {
    const genreString = Array.isArray(data.genre) ? data.genre.join('、') : data.genre;

    const worldResult = await wizardStreamApi.generateWorldBuildingStream(
      {
        title: data.title,
        description: data.description,
        theme: data.theme,
        genre: genreString,
        narrative_perspective: data.narrative_perspective,
        target_words: data.target_words,
        chapter_count: data.chapter_count,
        character_count: data.character_count,
        outline_mode: data.outline_mode || 'one-to-many',  // Truyền chế độ dàn ý
      },
      {
        signal,
        onProgress: (msg, prog) => {
          // Dùng trực tiếp giá trị tiến độ backend trả về
          setProgress(prog);
          setProgressMessage(msg);
        },
        onResult: (result) => {
          setWorldBuildingResult(result);
          setGenerationSteps(prev => ({ ...prev, worldBuilding: 'completed' }));
        },
        onError: (error) => {
          console.error('Sinh thế giới quan thất bại:', error);
          setErrorDetails(`Sinh thế giới quan thất bại: ${error}`);
          setGenerationSteps(prev => ({ ...prev, worldBuilding: 'error' }));
          setLoading(false);
          throw new Error(error);
        },
        onComplete: () => {
          console.log('Sinh thế giới quan hoàn tất');
        }
      }
    );

    await resumeFromCareers(data, worldResult, signal);
  };

  // Khôi phục:Khôi phục: tiếp tục từ bước hệ thống nghề nghiệp
  const resumeFromCareers = async (
    data: GenerationConfig,
    worldResult: WorldBuildingResult,
    signal?: AbortSignal,
  ) => {
    const pid = projectId || worldResult.project_id;

    setGenerationSteps(prev => ({ ...prev, careers: 'processing' }));
    setProgressMessage('Đang sinh hệ thống nghề nghiệp...');

    await wizardStreamApi.generateCareerSystemStream(
      {
        project_id: pid,
      },
      {
        signal,
        onProgress: (msg, prog) => {
          setProgress(prog);
          setProgressMessage(msg);
        },
        onResult: (result) => {
          console.log(`Sinh hệ thống nghề nghiệp thành công: ${result.main_careers_count} nghề chính, ${result.sub_careers_count} nghề phụ`);
          setGenerationSteps(prev => ({ ...prev, careers: 'completed' }));
        },
        onError: (error) => {
          console.error('Sinh hệ thống nghề nghiệp thất bại:', error);
          setErrorDetails(`Sinh hệ thống nghề nghiệp thất bại: ${error}`);
          setGenerationSteps(prev => ({ ...prev, careers: 'error' }));
          setLoading(false);
          throw new Error(error);
        },
        onComplete: () => {
          console.log('Sinh hệ thống nghề nghiệp hoàn tất');
        }
      }
    );

    await resumeFromCharacters(data, worldResult, signal);
  };

  // Khôi phục:Khôi phục: tiếp tục từ bước nhân vật
  const resumeFromCharacters = async (
    data: GenerationConfig,
    worldResult: WorldBuildingResult,
    signal?: AbortSignal,
  ) => {
    const genreString = Array.isArray(data.genre) ? data.genre.join('、') : data.genre;
    const pid = projectId || worldResult.project_id;

    setGenerationSteps(prev => ({ ...prev, characters: 'processing' }));
    setProgressMessage('Đang sinh nhân vật...');

    await wizardStreamApi.generateCharactersStream(
      {
        project_id: pid,
        count: data.character_count,
        world_context: {
          time_period: worldResult.time_period || '',
          location: worldResult.location || '',
          atmosphere: worldResult.atmosphere || '',
          rules: worldResult.rules || '',
        },
        theme: data.theme,
        genre: genreString,
      },
      {
        signal,
        onProgress: (msg, prog) => {
          // Dùng trực tiếp giá trị tiến độ backend trả về
          setProgress(prog);
          setProgressMessage(msg);
        },
        onResult: (result) => {
          console.log(`Đã sinh thành công ${result.characters?.length || 0} nhân vật`);
          setGenerationSteps(prev => ({ ...prev, characters: 'completed' }));
        },
        onError: (error) => {
          console.error('Sinh nhân vật thất bại:', error);
          setErrorDetails(`Sinh nhân vật thất bại: ${error}`);
          setGenerationSteps(prev => ({ ...prev, characters: 'error' }));
          setLoading(false);
          throw new Error(error);
        },
        onComplete: () => {
          console.log('Sinh nhân vật hoàn tất');
        }
      }
    );

    await resumeFromOutline(data, pid, signal);
  };

  // Khôi phục:Khôi phục: tiếp tục từ bước dàn ý
  const resumeFromOutline = async (
    data: GenerationConfig,
    pid: string,
    signal?: AbortSignal,
  ) => {
    setGenerationSteps(prev => ({ ...prev, outline: 'processing' }));
    setProgressMessage('Đang sinh dàn ý...');

    await wizardStreamApi.generateCompleteOutlineStream(
      {
        project_id: pid,
        chapter_count: data.chapter_count,
        narrative_perspective: data.narrative_perspective,
        target_words: data.target_words,
      },
      {
        signal,
        onProgress: (msg, prog) => {
          // Dùng trực tiếp giá trị tiến độ backend trả về
          setProgress(prog);
          setProgressMessage(msg);
        },
        onResult: () => {
          console.log('Sinh dàn ý hoàn tất');
          setGenerationSteps(prev => ({ ...prev, outline: 'completed' }));
        },
        onError: (error) => {
          console.error('Sinh dàn ý thất bại:', error);
          setErrorDetails(`Sinh dàn ý thất bại: ${error}`);
          setGenerationSteps(prev => ({ ...prev, outline: 'error' }));
          setLoading(false);
          throw new Error(error);
        },
        onComplete: () => {
          console.log('Sinh dàn ý hoàn tất');
        }
      }
    );

    // Hoàn tất toàn bộ
    setProgress(100);
    setProgressMessage('Tạo dự án hoàn tất! Đang chuyển hướng...');
    message.success('Tạo dự án thành công! Đang vào dự án...');
    clearStorage();
    setLoading(false);

    onComplete(pid);
    setTimeout(() => {
      navigate(`/project/${pid}`);
    }, 1000);
  };

  // Quy trình sinh tự động
  const handleAutoGenerate = async (data: GenerationConfig, signal?: AbortSignal) => {
    try {
      setLoading(true);
      setProgress(0);
      setProgressMessage('Bắt đầu tạo dự án...');
      setErrorDetails('');
      setGenerationData(data);
      saveProgress('', data, 'generating');

      const genreString = Array.isArray(data.genre) ? data.genre.join('、') : data.genre;

      // Bước 1: sinh thế giới quan và tạo dự án
      setGenerationSteps(prev => ({ ...prev, worldBuilding: 'processing' }));
      setProgressMessage('Đang sinh thế giới quan...');

      const worldResult = await wizardStreamApi.generateWorldBuildingStream(
        {
          title: data.title,
          description: data.description,
          theme: data.theme,
          genre: genreString,
          narrative_perspective: data.narrative_perspective,
          target_words: data.target_words,
          chapter_count: data.chapter_count,
          character_count: data.character_count,
          outline_mode: data.outline_mode || 'one-to-many',  // Truyền chế độ dàn ý
        },
        {
          signal,
          onProgress: (msg, prog) => {
            // Dùng trực tiếp giá trị tiến độ backend trả về
            setProgress(prog);
            setProgressMessage(msg);
          },
          onResult: (result) => {
            setProjectId(result.project_id);
            setWorldBuildingResult(result);
            setGenerationSteps(prev => ({ ...prev, worldBuilding: 'completed' }));
          },
          onError: (error) => {
            console.error('Sinh thế giới quan thất bại:', error);
            setErrorDetails(`Sinh thế giới quan thất bại: ${error}`);
            setGenerationSteps(prev => ({ ...prev, worldBuilding: 'error' }));
            setLoading(false);
            throw new Error(error);
          },
          onComplete: () => {
            console.log('Sinh thế giới quan hoàn tất');
          }
        }
      );

      if (!worldResult?.project_id) {
        throw new Error('Tạo dự án thất bại: không lấy được dự ánID');
      }

      const createdProjectId = worldResult.project_id;
      setProjectId(createdProjectId);
      setWorldBuildingResult(worldResult);
      saveProgress(createdProjectId, data, 'generating');

      // Bước 2: Sinh hệ thống nghề nghiệp
      setGenerationSteps(prev => ({ ...prev, careers: 'processing' }));
      setProgressMessage('Đang sinh hệ thống nghề nghiệp...');

      await wizardStreamApi.generateCareerSystemStream(
        {
          project_id: createdProjectId,
        },
        {
          signal,
          onProgress: (msg, prog) => {
            setProgress(prog);
            setProgressMessage(msg);
          },
          onResult: (result) => {
            console.log(`Sinh hệ thống nghề nghiệp thành công: ${result.main_careers_count} nghề chính, ${result.sub_careers_count} nghề phụ`);
            setGenerationSteps(prev => ({ ...prev, careers: 'completed' }));
          },
          onError: (error) => {
            console.error('Sinh hệ thống nghề nghiệp thất bại:', error);
            setErrorDetails(`Sinh hệ thống nghề nghiệp thất bại: ${error}`);
            setGenerationSteps(prev => ({ ...prev, careers: 'error' }));
            setLoading(false);
            throw new Error(error);
          },
          onComplete: () => {
            console.log('Sinh hệ thống nghề nghiệp hoàn tất');
          }
        }
      );

      // Bước 3: Sinh nhân vật
      setGenerationSteps(prev => ({ ...prev, characters: 'processing' }));
      setProgressMessage('Đang sinh nhân vật...');

      await wizardStreamApi.generateCharactersStream(
        {
          project_id: createdProjectId,
          count: data.character_count,
          world_context: {
            time_period: worldResult.time_period || '',
            location: worldResult.location || '',
            atmosphere: worldResult.atmosphere || '',
            rules: worldResult.rules || '',
          },
          theme: data.theme,
          genre: genreString,
        },
        {
          signal,
          onProgress: (msg, prog) => {
            // Dùng trực tiếp giá trị tiến độ backend trả về
            setProgress(prog);
            setProgressMessage(msg);
          },
          onResult: (result) => {
            console.log(`Đã sinh thành công ${result.characters?.length || 0} nhân vật`);
            setGenerationSteps(prev => ({ ...prev, characters: 'completed' }));
          },
          onError: (error) => {
            console.error('Sinh nhân vật thất bại:', error);
            setErrorDetails(`Sinh nhân vật thất bại: ${error}`);
            setGenerationSteps(prev => ({ ...prev, characters: 'error' }));
            setLoading(false);
            throw new Error(error);
          },
          onComplete: () => {
            console.log('Sinh nhân vật hoàn tất');
          }
        }
      );

      // Bước 3: Sinh dàn ý
      setGenerationSteps(prev => ({ ...prev, outline: 'processing' }));
      setProgressMessage('Đang sinh dàn ý...');

      await wizardStreamApi.generateCompleteOutlineStream(
        {
          project_id: createdProjectId,
          chapter_count: data.chapter_count,
          narrative_perspective: data.narrative_perspective,
          target_words: data.target_words,
        },
        {
          signal,
          onProgress: (msg, prog) => {
            // Dùng trực tiếp giá trị tiến độ backend trả về
            setProgress(prog);
            setProgressMessage(msg);
          },
          onResult: () => {
            console.log('Sinh dàn ý hoàn tất');
            setGenerationSteps(prev => ({ ...prev, outline: 'completed' }));
          },
          onError: (error) => {
            console.error('Sinh dàn ý thất bại:', error);
            setErrorDetails(`Sinh dàn ý thất bại: ${error}`);
            setGenerationSteps(prev => ({ ...prev, outline: 'error' }));
            setLoading(false);
            throw new Error(error);
          },
          onComplete: () => {
            console.log('Sinh dàn ý hoàn tất');
          }
        }
      );

      // Hoàn tất toàn bộ - tự động chuyển đến trang chi tiết dự án
      setProgress(100);
      setProgressMessage('Tạo dự án hoàn tất! Đang chuyển hướng...');
      message.success('Tạo dự án thành công! Đang vào dự án...');
      clearStorage();

      // Gọi callback hoàn tất
      onComplete(createdProjectId);

      // Trì hoãn 1giây rồi tự động chuyển đến trang chi tiết dự án
      setTimeout(() => {
        navigate(`/project/${createdProjectId}`);
      }, 1000);

    } catch (error) {
      if (isAbortError(error)) return;

      const apiError = error as ApiError;
      const errorMsg = apiError.response?.data?.detail || apiError.message || 'Lỗi không xác định';
      console.error('Tạo dự án thất bại:', errorMsg);
      setErrorDetails(errorMsg);
      message.error('Tạo dự án thất bại: ' + errorMsg);
      setLoading(false);
    }
  };

  // Thử lại thông minh: tiếp tục sinh từ bước thất bại
  const handleSmartRetry = async () => {
    if (!generationData) {
      message.warning('Thiếu dữ liệu sinh');
      return;
    }

    setLoading(true);
    setErrorDetails('');

    try {
      if (generationSteps.worldBuilding === 'error') {
        message.info('Bắt đầu sinh lại từ bước thế giới quan...');
        await retryFromWorldBuilding();
      } else if (generationSteps.careers === 'error') {
        message.info('Tiếp tục sinh từ bước hệ thống nghề nghiệp...');
        await retryFromCareers();
      } else if (generationSteps.characters === 'error') {
        message.info('Tiếp tục sinh từ bước nhân vật...');
        await retryFromCharacters();
      } else if (generationSteps.outline === 'error') {
        message.info('Tiếp tục sinh từ bước dàn ý...');
        await retryFromOutline();
      }
    } catch (error) {
      console.error('Thử lại thông minh thất bại:', error);
      const errorMessage = error instanceof Error ? error.message : 'Lỗi không xác định';
      message.error('Thử lại thất bại: ' + errorMessage);
      setLoading(false);
    }
  };

  // Bắt đầu lại từ bước thế giới quan
  const retryFromWorldBuilding = async () => {
    if (!generationData) return;

    setGenerationSteps(prev => ({ ...prev, worldBuilding: 'processing' }));
    setProgressMessage('Đang sinh lại thế giới quan...');

    const genreString = Array.isArray(generationData.genre) ? generationData.genre.join('、') : generationData.genre;

    const worldResult = await wizardStreamApi.generateWorldBuildingStream(
      {
        title: generationData.title,
        description: generationData.description,
        theme: generationData.theme,
        genre: genreString,
        narrative_perspective: generationData.narrative_perspective,
        target_words: generationData.target_words,
        chapter_count: generationData.chapter_count,
        character_count: generationData.character_count,
        outline_mode: generationData.outline_mode || 'one-to-many',  // Truyền chế độ dàn ý
      },
      {
        onProgress: (msg, prog) => {
          // Dùng trực tiếp giá trị tiến độ backend trả về
          setProgress(prog);
          setProgressMessage(msg);
        },
        onResult: (result) => {
          setProjectId(result.project_id);
          setWorldBuildingResult(result);
          setGenerationSteps(prev => ({ ...prev, worldBuilding: 'completed' }));
        },
        onError: (error) => {
          console.error('Sinh thế giới quan thất bại:', error);
          setErrorDetails(`Sinh thế giới quan thất bại: ${error}`);
          setGenerationSteps(prev => ({ ...prev, worldBuilding: 'error' }));
          setLoading(false);
          throw new Error(error);
        },
        onComplete: () => {
          console.log('Sinh lại thế giới quan hoàn tất');
        }
      }
    );

    if (!worldResult?.project_id) {
      throw new Error('Tạo dự án thất bại: không lấy được dự ánID');
    }

    await continueFromCareers(worldResult);
  };

  // Khôi phục: tiếp tục từ bước hệ thống nghề nghiệp
  const retryFromCareers = async () => {
    if (!worldBuildingResult) {
      message.warning('Thiếu dữ liệu cần thiết, không thể tiếp tục từ bước hệ thống nghề nghiệp');
      setLoading(false);
      return;
    }

    const pid = worldBuildingResult.project_id || projectId;
    if (!pid) {
      message.warning('Thiếu dự ánID, không thể tiếp tục từ bước hệ thống nghề nghiệp');
      setLoading(false);
      return;
    }

    setGenerationSteps(prev => ({ ...prev, careers: 'processing' }));
    setProgressMessage('Đang sinh lại hệ thống nghề nghiệp...');

    await wizardStreamApi.generateCareerSystemStream(
      {
        project_id: pid,
      },
      {
        onProgress: (msg, prog) => {
          setProgress(prog);
          setProgressMessage(msg);
        },
        onResult: (result) => {
          console.log(`Sinh hệ thống nghề nghiệp thành công: ${result.main_careers_count} nghề chính, ${result.sub_careers_count} nghề phụ`);
          setGenerationSteps(prev => ({ ...prev, careers: 'completed' }));
        },
        onError: (error) => {
          console.error('Sinh hệ thống nghề nghiệp thất bại:', error);
          setErrorDetails(`Sinh hệ thống nghề nghiệp thất bại: ${error}`);
          setGenerationSteps(prev => ({ ...prev, careers: 'error' }));
          setLoading(false);
          throw new Error(error);
        },
        onComplete: () => {
          console.log('Sinh lại hệ thống nghề nghiệp hoàn tất');
        }
      }
    );

    await continueFromCharacters(worldBuildingResult);
  };

  // Khôi phục: tiếp tục từ bước nhân vật
  const retryFromCharacters = async () => {
    if (!generationData || !worldBuildingResult) {
      message.warning('Thiếu dữ liệu cần thiết, không thể tiếp tục từ bước nhân vật');
      setLoading(false);
      return;
    }

    // Ưu tiên dùng  worldBuildingResult  trong  project_id vì thử lại có thể đã tạo dự án mới
    const pid = worldBuildingResult.project_id || projectId;
    if (!pid) {
      message.warning('Thiếu dự ánID, không thể tiếp tục từ bước nhân vật');
      setLoading(false);
      return;
    }

    setGenerationSteps(prev => ({ ...prev, characters: 'processing' }));
    setProgressMessage('Đang sinh lại nhân vật...');

    const genreString = Array.isArray(generationData.genre) ? generationData.genre.join('、') : generationData.genre;

    await wizardStreamApi.generateCharactersStream(
      {
        project_id: pid,
        count: generationData.character_count,
        world_context: {
          time_period: worldBuildingResult.time_period || '',
          location: worldBuildingResult.location || '',
          atmosphere: worldBuildingResult.atmosphere || '',
          rules: worldBuildingResult.rules || '',
        },
        theme: generationData.theme,
        genre: genreString,
      },
      {
        onProgress: (msg, prog) => {
          // Dùng trực tiếp giá trị tiến độ backend trả về
          setProgress(prog);
          setProgressMessage(msg);
        },
        onResult: (result) => {
          console.log(`Đã sinh thành công ${result.characters?.length || 0} nhân vật`);
          setGenerationSteps(prev => ({ ...prev, characters: 'completed' }));
        },
        onError: (error) => {
          console.error('Sinh nhân vật thất bại:', error);
          setErrorDetails(`Sinh nhân vật thất bại: ${error}`);
          setGenerationSteps(prev => ({ ...prev, characters: 'error' }));
          setLoading(false);
          throw new Error(error);
        },
        onComplete: () => {
          console.log('Sinh lại nhân vật hoàn tất');
        }
      }
    );

    await continueFromOutline(pid);
  };

  // Khôi phục: tiếp tục từ bước dàn ý
  const retryFromOutline = async () => {
    if (!generationData) {
      message.warning('Thiếu dữ liệu cần thiết, không thể tiếp tục từ bước dàn ý');
      setLoading(false);
      return;
    }

    // Ưu tiên dùng  worldBuildingResult  trong  project_id, fallback về  projectId
    const pid = (worldBuildingResult?.project_id) || projectId;
    if (!pid) {
      message.warning('Thiếu dự ánID, không thể tiếp tục từ bước dàn ý');
      setLoading(false);
      return;
    }

    setGenerationSteps(prev => ({ ...prev, outline: 'processing' }));
    setProgressMessage('Đang sinh lại dàn ý...');

    await wizardStreamApi.generateCompleteOutlineStream(
      {
        project_id: pid,
        chapter_count: generationData.chapter_count,
        narrative_perspective: generationData.narrative_perspective,
        target_words: generationData.target_words,
      },
      {
        onProgress: (msg, prog) => {
          // Dùng trực tiếp giá trị tiến độ backend trả về
          setProgress(prog);
          setProgressMessage(msg);
        },
        onResult: () => {
          console.log('Sinh dàn ý hoàn tất');
          setGenerationSteps(prev => ({ ...prev, outline: 'completed' }));
        },
        onError: (error) => {
          console.error('Sinh dàn ý thất bại:', error);
          setErrorDetails(`Sinh dàn ý thất bại: ${error}`);
          setGenerationSteps(prev => ({ ...prev, outline: 'error' }));
          setLoading(false);
          throw new Error(error);
        },
        onComplete: () => {
          console.log('Sinh lại dàn ý hoàn tất');
        }
      }
    );

    setProgress(100);
    setProgressMessage('Tạo dự án hoàn tất! Đang chuyển hướng...');
    message.success('Tạo dự án thành công! Đang vào dự án...');
    setLoading(false);

    // Gọi callback hoàn tất
    if (pid) {
      onComplete(pid);

      // Trì hoãn 1giây rồi tự động chuyển đến trang chi tiết dự án
      setTimeout(() => {
        navigate(`/project/${pid}`);
      }, 1000);
    }
  };

  // Quy trình đầy đủ bắt đầu từ bước hệ thống nghề nghiệp
  const continueFromCareers = async (worldResult: WorldBuildingResult) => {
    if (!generationData || !worldResult?.project_id) return;

    const pid = worldResult.project_id;

    setGenerationSteps(prev => ({ ...prev, careers: 'processing' }));
    setProgressMessage('Đang sinh hệ thống nghề nghiệp...');

    await wizardStreamApi.generateCareerSystemStream(
      {
        project_id: pid,
      },
      {
        onProgress: (msg, prog) => {
          setProgress(prog);
          setProgressMessage(msg);
        },
        onResult: (result) => {
          console.log(`Sinh hệ thống nghề nghiệp thành công: ${result.main_careers_count} nghề chính, ${result.sub_careers_count} nghề phụ`);
          setGenerationSteps(prev => ({ ...prev, careers: 'completed' }));
        },
        onError: (error) => {
          console.error('Sinh hệ thống nghề nghiệp thất bại:', error);
          setErrorDetails(`Sinh hệ thống nghề nghiệp thất bại: ${error}`);
          setGenerationSteps(prev => ({ ...prev, careers: 'error' }));
          setLoading(false);
          throw new Error(error);
        },
        onComplete: () => {
          console.log('Sinh hệ thống nghề nghiệp hoàn tất');
        }
      }
    );

    await continueFromCharacters(worldResult);
  };

  // Quy trình đầy đủ bắt đầu từ bước nhân vật
  const continueFromCharacters = async (worldResult: WorldBuildingResult) => {
    if (!generationData || !worldResult?.project_id) return;

    const pid = worldResult.project_id;
    const genreString = Array.isArray(generationData.genre) ? generationData.genre.join('、') : generationData.genre;

    setGenerationSteps(prev => ({ ...prev, characters: 'processing' }));
    setProgressMessage('Đang sinh nhân vật...');

    await wizardStreamApi.generateCharactersStream(
      {
        project_id: pid,
        count: generationData.character_count,
        world_context: {
          time_period: worldResult.time_period || '',
          location: worldResult.location || '',
          atmosphere: worldResult.atmosphere || '',
          rules: worldResult.rules || '',
        },
        theme: generationData.theme,
        genre: genreString,
      },
      {
        onProgress: (msg, prog) => {
          // Dùng trực tiếp giá trị tiến độ backend trả về
          setProgress(prog);
          setProgressMessage(msg);
        },
        onResult: (result) => {
          console.log(`Đã sinh thành công ${result.characters?.length || 0} nhân vật`);
          setGenerationSteps(prev => ({ ...prev, characters: 'completed' }));
        },
        onError: (error) => {
          console.error('Sinh nhân vật thất bại:', error);
          setErrorDetails(`Sinh nhân vật thất bại: ${error}`);
          setGenerationSteps(prev => ({ ...prev, characters: 'error' }));
          setLoading(false);
          throw new Error(error);
        },
        onComplete: () => {
          console.log('Sinh nhân vật hoàn tất');
        }
      }
    );

    await continueFromOutline(pid);
  };

  // Quy trình đầy đủ bắt đầu từ bước dàn ý
  const continueFromOutline = async (pid: string) => {
    if (!generationData || !pid) return;

    setGenerationSteps(prev => ({ ...prev, outline: 'processing' }));
    setProgressMessage('Đang sinh dàn ý...');

    await wizardStreamApi.generateCompleteOutlineStream(
      {
        project_id: pid,
        chapter_count: generationData.chapter_count,
        narrative_perspective: generationData.narrative_perspective,
        target_words: generationData.target_words,
      },
      {
        onProgress: (msg, prog) => {
          // Dùng trực tiếp giá trị tiến độ backend trả về
          setProgress(prog);
          setProgressMessage(msg);
        },
        onResult: () => {
          console.log('Sinh dàn ý hoàn tất');
          setGenerationSteps(prev => ({ ...prev, outline: 'completed' }));
        },
        onError: (error) => {
          console.error('Sinh dàn ý thất bại:', error);
          setErrorDetails(`Sinh dàn ý thất bại: ${error}`);
          setGenerationSteps(prev => ({ ...prev, outline: 'error' }));
          setLoading(false);
          throw new Error(error);
        },
        onComplete: () => {
          console.log('Sinh dàn ý hoàn tất');
        }
      }
    );

    setProgress(100);
    setProgressMessage('Tạo dự án hoàn tất! Đang chuyển hướng...');
    message.success('Tạo dự án thành công! Đang vào dự án...');
    setLoading(false);

    // Gọi callback hoàn tất
    if (pid) {
      onComplete(pid);

      // Trì hoãn 1giây rồi tự động chuyển đến trang chi tiết dự án
      setTimeout(() => {
        navigate(`/project/${pid}`);
      }, 1000);
    }
  };


  // Lấy icon và style trạng thái bước
  const getStepStatus = (step: GenerationStep) => {
    if (step === 'completed') {
      return {
        icon: <CheckCircleOutlined />,
        color: token.colorSuccess,
        text: 'Đã xong',
        background: `linear-gradient(135deg, ${alphaColor(token.colorSuccess, 0.12)} 0%, ${token.colorBgContainer} 100%)`,
        borderColor: alphaColor(token.colorSuccess, 0.28),
      };
    }

    if (step === 'processing') {
      return {
        icon: <LoadingOutlined spin />,
        color: token.colorPrimary,
        text: 'Đang tiến hành',
        background: `linear-gradient(135deg, ${alphaColor(token.colorPrimary, 0.14)} 0%, ${token.colorBgContainer} 100%)`,
        borderColor: alphaColor(token.colorPrimary, 0.32),
      };
    }

    if (step === 'error') {
      return {
        icon: '✕',
        color: token.colorError,
        text: 'Thất bại',
        background: `linear-gradient(135deg, ${alphaColor(token.colorError, 0.12)} 0%, ${token.colorBgContainer} 100%)`,
        borderColor: alphaColor(token.colorError, 0.32),
      };
    }

    return {
      icon: '○',
      color: token.colorTextQuaternary,
      text: 'Đang chờ',
      background: token.colorFillQuaternary,
      borderColor: token.colorBorderSecondary,
    };
  };

  const hasError = generationSteps.worldBuilding === 'error' ||
    generationSteps.careers === 'error' ||
    generationSteps.characters === 'error' ||
    generationSteps.outline === 'error';

  const progressAccentColor = hasError
    ? token.colorError
    : progress === 100
      ? token.colorSuccess
      : token.colorPrimary;

  const stepItems = [
    { key: 'worldBuilding', label: 'Sinh thế giới quan', step: generationSteps.worldBuilding },
    { key: 'careers', label: 'Sinh hệ thống nghề nghiệp', step: generationSteps.careers },
    { key: 'characters', label: 'Sinh nhân vật', step: generationSteps.characters },
    { key: 'outline', label: 'Sinh dàn ý', step: generationSteps.outline },
  ];

  const availableViewportHeight = isMobile
    ? 'calc(100dvh - 96px)'
    : 'calc(100dvh - 128px)';

  // Render trang tiến trình sinh
  const renderGenerating = () => (
    <div
      style={{
        padding: isMobile ? '4px 0 8px' : '8px 0 12px',
        maxWidth: 920,
        margin: '0 auto',
        overflow: 'hidden',
        minHeight: availableViewportHeight,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: hasError ? 'flex-start' : 'center',
      }}
    >
      <div
        style={{
          marginBottom: 14,
          padding: isMobile ? '18px 16px' : '24px 24px 20px',
          borderRadius: 18,
          border: `1px solid ${alphaColor(hasError ? token.colorError : token.colorPrimary, 0.18)}`,
          background: `linear-gradient(135deg, ${alphaColor(token.colorPrimary, 0.12)} 0%, ${token.colorBgContainer} 48%, ${alphaColor(hasError ? token.colorError : token.colorSuccess, hasError ? 0.08 : 0.04)} 100%)`,
          boxShadow: `0 12px 28px ${alphaColor(token.colorText, 0.06)}`,
          textAlign: 'center',
        }}
      >
        <Title
          level={isMobile ? 4 : 3}
          style={{
            marginBottom: 8,
            color: token.colorTextHeading,
            wordBreak: 'break-word',
            whiteSpace: 'normal',
            overflowWrap: 'break-word',
          }}
        >
          Đang sinh nội dung cho "{config.title}"
        </Title>

        <Paragraph
          style={{
            maxWidth: 620,
            margin: '0 auto',
            color: token.colorTextSecondary,
            fontSize: isMobile ? 13 : 14,
            lineHeight: 1.7,
            wordBreak: 'break-word',
            whiteSpace: 'normal',
            overflowWrap: 'break-word',
          }}
        >
          {hasError
            ? 'Quy trình sinh bị gián đoạn, đã giữ lại tiến độ và thông tin ngữ cảnh hiện tại, có thể thử lại từ bước thất bại.'
            : 'Hệ thống sẽ lần lượt sinh thế giới quan, hệ thống nghề nghiệp, nhân vật và dàn ý, vui lòng kiên nhẫn chờ.'}
        </Paragraph>
      </div>

      <Card
        style={{
          marginBottom: 12,
          borderRadius: 18,
          border: `1px solid ${alphaColor(token.colorText, 0.08)}`,
          background: `linear-gradient(180deg, ${alphaColor(token.colorBgContainer, 0.97)} 0%, ${alphaColor(token.colorPrimary, 0.03)} 100%)`,
          boxShadow: `0 10px 24px ${alphaColor(token.colorText, 0.06)}`,
        }}
        styles={{
          body: {
            padding: isMobile ? 14 : 20,
          }
        }}
      >
        <div
          style={{
            padding: isMobile ? '14px 14px 16px' : '16px 18px 18px',
            marginBottom: 16,
            borderRadius: 14,
            background: token.colorFillQuaternary,
            border: `1px solid ${alphaColor(progressAccentColor, 0.18)}`,
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: isMobile ? 'flex-start' : 'center',
              flexDirection: isMobile ? 'column' : 'row',
              gap: 10,
              marginBottom: 10,
            }}
          >
            <div style={{ flex: 1, textAlign: 'left' }}>
              <Text
                style={{
                  display: 'block',
                  marginBottom: 6,
                  color: token.colorTextTertiary,
                  fontSize: 12,
                  letterSpacing: 0.4,
                }}
              >
                Tiến độ hiện tại
              </Text>
              <Paragraph
                style={{
                  margin: 0,
                  color: hasError ? token.colorError : token.colorText,
                  fontSize: isMobile ? 13 : 15,
                  lineHeight: 1.7,
                  wordBreak: 'break-word',
                  whiteSpace: 'normal',
                  overflowWrap: 'break-word',
                }}
              >
                {progressMessage || 'Chuẩn bị sinh...'}
              </Paragraph>
            </div>

            <div
              style={{
                minWidth: isMobile ? 'auto' : 96,
                textAlign: isMobile ? 'left' : 'right',
              }}
            >
              <Text
                style={{
                  fontSize: isMobile ? 24 : 32,
                  lineHeight: 1,
                  fontWeight: 700,
                  color: progressAccentColor,
                }}
              >
                {progress}%
              </Text>
            </div>
          </div>

          <Progress
            percent={progress}
            showInfo={false}
            status={hasError ? 'exception' : (progress === 100 ? 'success' : 'active')}
            strokeColor={progress === 100
              ? {
                '0%': token.colorSuccess,
                '100%': token.colorSuccessActive,
              }
              : {
                '0%': token.colorPrimary,
                '100%': token.colorPrimaryActive,
              }}
            trailColor={token.colorFillTertiary}
            strokeLinecap="round"
            style={{ marginBottom: 0 }}
          />
        </div>

        {errorDetails && (
          <div
            style={{
              marginBottom: 16,
              padding: isMobile ? '12px 14px' : '14px 16px',
              borderRadius: 14,
              background: `linear-gradient(135deg, ${alphaColor(token.colorError, 0.12)} 0%, ${token.colorBgContainer} 100%)`,
              border: `1px solid ${alphaColor(token.colorError, 0.24)}`,
              textAlign: 'left',
              overflow: 'hidden',
            }}
          >
            <Text strong style={{ color: token.colorError, display: 'block', marginBottom: 8 }}>
              Chi tiết lỗi
            </Text>
            <Text
              style={{
                color: token.colorTextSecondary,
                fontSize: 14,
                lineHeight: 1.7,
                wordBreak: 'break-word',
                whiteSpace: 'normal',
                overflowWrap: 'break-word',
                display: 'block',
              }}
            >
              {errorDetails}
            </Text>
          </div>
        )}

        <div
          style={{
            display: 'grid',
            gap: 10,
          }}
        >
          {stepItems.map(({ key, label, step }) => {
            const status = getStepStatus(step);
            return (
              <div
                key={key}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: isMobile ? '10px 12px' : '12px 14px',
                  background: status.background,
                  borderRadius: 14,
                  border: `1px solid ${status.borderColor}`,
                  gap: 12,
                  maxWidth: '100%',
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    flex: 1,
                    minWidth: 0,
                  }}
                >
                  <span
                    style={{
                      width: 30,
                      height: 30,
                      borderRadius: '50%',
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: status.color,
                      background: alphaColor(status.color, 0.12),
                      fontSize: 18,
                      flexShrink: 0,
                    }}
                  >
                    {status.icon}
                  </span>

                  <div
                    style={{
                      minWidth: 0,
                      flex: 1,
                      textAlign: 'left',
                    }}
                  >
                    <Text
                      style={{
                        display: 'block',
                        fontSize: isMobile ? 13 : 14,
                        fontWeight: step === 'processing' ? 600 : 500,
                        color: token.colorText,
                        wordBreak: 'break-word',
                        whiteSpace: 'normal',
                        overflowWrap: 'break-word',
                      }}
                    >
                      {label}
                    </Text>
                    <Text
                      style={{
                        fontSize: 12,
                        color: step === 'pending' ? token.colorTextTertiary : status.color,
                      }}
                    >
                      {status.text}
                    </Text>
                  </div>
                </div>

                <Text
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: status.color,
                    padding: '4px 10px',
                    borderRadius: 999,
                    background: alphaColor(status.color, 0.1),
                    whiteSpace: 'nowrap',
                    flexShrink: 0,
                  }}
                >
                  {status.text}
                </Text>
              </div>
            );
          })}
        </div>
      </Card>

      <Paragraph
        type="secondary"
        style={{
          marginBottom: hasError ? 14 : 0,
          color: token.colorTextSecondary,
          opacity: 0.92,
          textAlign: 'center',
          wordBreak: 'break-word',
          whiteSpace: 'normal',
          overflowWrap: 'break-word',
          fontSize: isMobile ? 13 : 14,
        }}
      >
        {hasError ? 'Có thể bấm thử lại thông minh bên dưới để tiếp tục sinh từ nút thất bại, tránh lặp lại các bước đã xong.' : 'Vui lòng không đóng trang, sau khi sinh xong sẽ tự động vào trang chi tiết dự án.'}
      </Paragraph>

      {hasError && (
        <Space
          direction={isMobile ? 'vertical' : 'horizontal'}
          style={{ width: '100%', justifyContent: 'center' }}
        >
          <Button
            type="primary"
            size="large"
            onClick={handleSmartRetry}
            loading={loading}
            disabled={loading}
            style={{
              minWidth: isMobile ? '100%' : 160,
              height: 44,
              borderRadius: 12,
              boxShadow: `0 10px 24px ${alphaColor(token.colorPrimary, 0.22)}`,
            }}
          >
            Thử lại thông minh
          </Button>
          {onBack && (
            <Button
              size="large"
              danger
              onClick={handleRestartGeneration}
              disabled={loading}
              style={{
                minWidth: isMobile ? '100%' : 160,
                height: 44,
                borderRadius: 12,
              }}
            >
              Bắt đầu lại quá trình sinh
            </Button>
          )}
        </Space>
      )}
    </div>
  );

  return renderGenerating();
};
