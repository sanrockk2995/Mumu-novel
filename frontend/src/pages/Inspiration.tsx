import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Input, Button, Space, Typography, message, Spin, Modal, theme } from 'antd';
import { SendOutlined, ArrowLeftOutlined, ReloadOutlined } from '@ant-design/icons';
import { inspirationApi } from '../services/api';
import { AIProjectGenerator, type GenerationConfig } from '../components/AIProjectGenerator';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

type Step = 'idea' | 'title' | 'description' | 'theme' | 'genre' | 'perspective' | 'outline_mode' | 'confirm' | 'generating' | 'complete';

interface FailedRequest {
  step: 'title' | 'description' | 'theme' | 'genre';
  context: Partial<WizardData>;
}

interface Message {
  type: 'ai' | 'user';
  content: string;
  options?: string[];
  isMultiSelect?: boolean;
  optionsDisabled?: boolean; // Đánh dấu tùy chọn đã bị vô hiệu chưa
  canRefine?: boolean; // Có thể tối ưu không (dùng để hỗ trợ hội thoại nhiều vòng)
  step?: Step; // Bước hiện tại (dùng cho phản hồi)
  failedRequest?: FailedRequest; // Gắn thao tác thất bại vào tin nhắn, tránh nút lịch sử thử lại request lỗi
}

interface WizardData {
  title: string;
  description: string;
  theme: string;
  genre: string[];
  narrative_perspective: string;
  outline_mode: 'one-to-one' | 'one-to-many';
}

// Interface dữ liệu cache
interface CacheData {
  messages: Message[];
  currentStep: Step;
  wizardData: Partial<WizardData>;
  initialIdea: string;
  selectedOptions: string[];
  lastFailedRequest: FailedRequest | null;
  timestamp: number;
}

// Key cache
const CACHE_KEY = 'inspiration_conversation_cache';
// Thời hạn cache: 24 giờ
const CACHE_EXPIRY = 24 * 60 * 60 * 1000;

const Inspiration: React.FC = () => {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState<Step>('idea');
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);
  const { token } = theme.useToken();

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth <= 768);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const [messages, setMessages] = useState<Message[]>([
    {
      type: 'ai',
      content: 'Xin chào! Tôi là trợ lý sáng tác AI của bạn. Cùng nhau sáng tác một tiểu thuyết thật hay nhé!\n\nHãy cho tôi biết, bạn muốn viết một tiểu thuyết như thế nào?',
    }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [selectedOptions, setSelectedOptions] = useState<string[]>([]);

  // Dữ liệu đã thu thập
  const [wizardData, setWizardData] = useState<Partial<WizardData>>({});
  // Lưu ý tưởng gốc của người dùng để giữ nhất quán ngữ cảnh
  const [initialIdea, setInitialIdea] = useState<string>('');
  
  // State liên quan đến phản hồi
  const [feedbackValue, setFeedbackValue] = useState('');
  const [showFeedbackInput, setShowFeedbackInput] = useState<number | null>(null); // Index tin nhắn đang hiển thị ô nhập phản hồi
  const [refining, setRefining] = useState(false); // Đang tối ưu tùy chọn

  // Cấu hình tạo
  const [generationConfig, setGenerationConfig] = useState<GenerationConfig | null>(null);

  // Modal hook
  const [modal, contextHolder] = Modal.useModal();

  // Tham chiếu container cuộn
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const sessionVersionRef = useRef(0);

  // Ghi lại tham số request thất bại lần trước để thử lại
  const [lastFailedRequest, setLastFailedRequest] = useState<FailedRequest | null>(null);

  // Đánh dấu đã tải cache chưa
  const [cacheLoaded, setCacheLoaded] = useState(false);

  // ==================== Hàm quản lý cache ====================

  // Xóa cache
  const clearCache = useCallback(() => {
    try {
      localStorage.removeItem(CACHE_KEY);
      console.log('🗑️ Đã xóa cache');
    } catch (error) {
      console.error('Xóa cache thất bại:', error);
    }
  }, []);

  // Lưu vào cache
  const saveToCache = useCallback(() => {
    try {
      // Chỉ lưu ở giai đoạn hội thoại, giai đoạn tạo thì không lưu
      if (currentStep === 'generating' || currentStep === 'complete') {
        return;
      }

      // Chỉ lưu khi người dùng có nhập (ít nhất hai tin nhắn: AI chào + người dùng trả lời)
      if (messages.length <= 1) {
        return;
      }

      const cacheData: CacheData = {
        messages,
        currentStep,
        wizardData,
        initialIdea,
        selectedOptions,
        lastFailedRequest,
        timestamp: Date.now()
      };

      localStorage.setItem(CACHE_KEY, JSON.stringify(cacheData));
      console.log('💾 Hội thoại đã được tự động lưu');
    } catch (error) {
      console.error('Lưu cache thất bại:', error);
    }
  }, [currentStep, messages, wizardData, initialIdea, selectedOptions, lastFailedRequest]);

  // Khôi phục từ cache
  const restoreFromCache = useCallback((): boolean => {
    try {
      const cached = localStorage.getItem(CACHE_KEY);
      if (!cached) {
        return false;
      }

      const cacheData: CacheData = JSON.parse(cached);
      const age = Date.now() - cacheData.timestamp;

      // Kiểm tra cache có hết hạn không
      if (age > CACHE_EXPIRY) {
        console.log('⏰ Cache đã hết hạn, xóa');
        clearCache();
        return false;
      }

      // Phải có dữ liệu hội thoại hợp lệ
      if (!cacheData.messages || cacheData.messages.length <= 1) {
        return false;
      }

      // Khôi phục tất cả state
      setMessages(cacheData.messages);
      setCurrentStep(cacheData.currentStep);
      setWizardData(cacheData.wizardData);
      setInitialIdea(cacheData.initialIdea);
      setSelectedOptions(cacheData.selectedOptions);
      // Khôi phục thông tin request thất bại, đảm bảo nút "Tạo lại" khả dụng
      if (cacheData.lastFailedRequest) {
        setLastFailedRequest(cacheData.lastFailedRequest);
      }

      console.log('✅ Đã khôi phục tiến độ hội thoại lần trước');
      message.success('Đã khôi phục tiến độ hội thoại lần trước', 2);
      return true;
    } catch (error) {
      console.error('Khôi phục cache thất bại:', error);
      clearCache();
      return false;
    }
  }, [clearCache]);

  // ==================== Khôi phục cache khi component mount ====================

  useEffect(() => {
    if (!cacheLoaded) {
      restoreFromCache();
      setCacheLoaded(true);
    }
  }, [cacheLoaded, restoreFromCache]);

  // ==================== Tự động lưu: lưu khi state thay đổi ====================

  useEffect(() => {
    // Lưu debounce
    const timer = setTimeout(() => {
      if (cacheLoaded) {
        saveToCache();
      }
    }, 500);

    return () => clearTimeout(timer);
  }, [messages, currentStep, wizardData, initialIdea, selectedOptions, lastFailedRequest, cacheLoaded, saveToCache]);

  // Tự động cuộn xuống cuối
  const scrollToBottom = () => {
    setTimeout(() => {
      if (chatContainerRef.current) {
        chatContainerRef.current.scrollTo({
          top: chatContainerRef.current.scrollHeight,
          behavior: 'smooth'
        });
      }
    }, 100);
  };

  // Tự động cuộn khi tin nhắn cập nhật
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Thử tạo lại
  const handleRetry = async (failedRequest: FailedRequest | null = lastFailedRequest) => {
    if (!failedRequest || loading) return;

    const sessionVersion = sessionVersionRef.current;
    setLoading(true);
    try {
      const response = await inspirationApi.generateOptions({
        step: failedRequest.step,
        context: failedRequest.context
      });

      if (sessionVersion !== sessionVersionRef.current) return;

      if (response.error) {
        message.error(response.error);
        return;
      }

      setMessages(prev => {
        const newMessages = [...prev];
        let failedMessageIndex = -1;
        for (let index = newMessages.length - 1; index >= 0; index -= 1) {
          if (newMessages[index].failedRequest?.step === failedRequest.step) {
            failedMessageIndex = index;
            break;
          }
        }
        if (failedMessageIndex >= 0) {
          newMessages.splice(failedMessageIndex, 1);
        }
        return newMessages;
      });

      const aiMessage: Message = {
        type: 'ai',
        content: response.prompt || 'Vui lòng chọn một tùy chọn, hoặc nhập của riêng bạn:',
        options: response.options || [],
        isMultiSelect: failedRequest.step === 'genre',
        canRefine: true,
        step: failedRequest.step,
      };
      setMessages(prev => [...prev, aiMessage]);
      setCurrentStep(failedRequest.step);
      setLastFailedRequest(null);
    } catch (error: unknown) {
      console.error('Thử lại thất bại:', error);
      message.error('Thử lại thất bại, vui lòng thử lại sau');
    } finally {
      if (sessionVersion === sessionVersionRef.current) setLoading(false);
    }
  };

  // Xử lý phản hồi người dùng, tạo lại tùy chọn
  const handleRefineOptions = async (messageIndex: number, feedback: string) => {
    if (!feedback.trim() || refining || loading) {
      message.warning('Vui lòng nhập ý kiến phản hồi của bạn');
      return;
    }

    const targetMessage = messages[messageIndex];
    if (!targetMessage.options || !targetMessage.step) {
      return;
    }

    const sessionVersion = sessionVersionRef.current;
    setRefining(true);
    setShowFeedbackInput(null);
    setFeedbackValue('');

    // Vô hiệu hóa tùy chọn cũ trước
    setMessages(prev => {
      const newMessages = [...prev];
      if (newMessages[messageIndex]) {
        newMessages[messageIndex] = {
          ...newMessages[messageIndex],
          optionsDisabled: true,
          canRefine: false, // Đồng thời vô hiệu hóa chức năng phản hồi
        };
      }
      return newMessages;
    });

    try {
      // Thêm tin nhắn phản hồi của người dùng
      const feedbackMessage: Message = {
        type: 'user',
        content: `💭 ${feedback}`,
      };
      setMessages(prev => [...prev, feedbackMessage]);

      const step = targetMessage.step as 'title' | 'description' | 'theme' | 'genre';
      
      // Xây dựng ngữ cảnh
      const context: Partial<WizardData> & { initial_idea?: string } = {
        initial_idea: initialIdea,
        title: wizardData.title,
        description: wizardData.description,
        theme: wizardData.theme,
      };

      // Gọi API refine
      const response = await inspirationApi.refineOptions({
        step,
        context,
        feedback,
        previous_options: targetMessage.options,
      });

      if (sessionVersion !== sessionVersionRef.current) return;

      if (response.error) {
        setMessages(prev => prev.map((item, index) => index === messageIndex
          ? { ...item, optionsDisabled: false, canRefine: true }
          : item));
        setFeedbackValue(feedback);
        setShowFeedbackInput(messageIndex);
        message.error(response.error);
        return;
      }

      // Thêm tin nhắn AI mới
      const aiMessage: Message = {
        type: 'ai',
        content: response.prompt || `Dựa trên phản hồi của bạn, tôi đã tạo lại một số tùy chọn ${step === 'title' ? 'tên sách' : step === 'description' ? 'giới thiệu' : step === 'theme' ? 'chủ đề' : 'thể loại'}:`,
        options: response.options || [],
        isMultiSelect: step === 'genre',
        canRefine: true,
        step: step,
      };
      setMessages(prev => [...prev, aiMessage]);

      message.success('Đã tạo lại tùy chọn dựa trên phản hồi của bạn');
    } catch (error: unknown) {
      if (sessionVersion !== sessionVersionRef.current) return;
      setMessages(prev => prev.map((item, index) => index === messageIndex
        ? { ...item, optionsDisabled: false, canRefine: true }
        : item));
      setFeedbackValue(feedback);
      setShowFeedbackInput(messageIndex);
      console.error('Tối ưu tùy chọn thất bại:', error);
      const errMsg = error instanceof Error ? error.message : 'Tối ưu thất bại, vui lòng thử lại';
      const axiosError = error as { response?: { data?: { detail?: string } } };
      message.error(axiosError.response?.data?.detail || errMsg);
    } finally {
      if (sessionVersion === sessionVersionRef.current) setRefining(false);
    }
  };

  // Thứ tự các bước
  const stepOrder: Step[] = ['idea', 'title', 'description', 'theme', 'genre', 'perspective', 'outline_mode', 'confirm'];

  const handleSendMessage = async () => {
    if (!inputValue.trim() || loading || refining) {
      message.warning('Vui lòng nhập nội dung');
      return;
    }

    const userMessage: Message = {
      type: 'user',
      content: inputValue,
    };
    setMessages(prev => [...prev, userMessage]);

    const userInput = inputValue;
    setInputValue('');
    const sessionVersion = sessionVersionRef.current;
    setLoading(true);

    try {
      if (currentStep === 'idea') {
        setInitialIdea(userInput);

        const requestData = {
          step: 'title' as const,
          context: {
            initial_idea: userInput,
            description: userInput
          }
        };

        const response = await inspirationApi.generateOptions(requestData);

        if (sessionVersion !== sessionVersionRef.current) return;

        if (response.error || !response.options || response.options.length < 3) {
          const errorMessage: Message = {
            type: 'ai',
            content: response.error
              ? `Tạo tên sách bị lỗi: ${response.error}\n\nBạn có thể chọn:`
              : `Định dạng tùy chọn được tạo không đúng (cần ít nhất 3 tùy chọn hợp lệ)\n\nBạn có thể chọn:`,
            options: ['Tạo lại', 'Tôi tự nhập tên sách'],
            failedRequest: requestData,
          };
          setMessages(prev => [...prev, errorMessage]);
          setLastFailedRequest(requestData);
          return;
        }

        const aiMessage: Message = {
          type: 'ai',
          content: response.prompt || 'Vui lòng chọn một tên sách, hoặc nhập của riêng bạn:',
          options: response.options,
          canRefine: true,
          step: 'title'
        };
        setMessages(prev => [...prev, aiMessage]);
        setCurrentStep('title');
        setLastFailedRequest(null);
      } else {
        await handleCustomInput(userInput);
      }
    } catch (error: unknown) {
      if (sessionVersion !== sessionVersionRef.current) return;
      console.error('Gửi tin nhắn thất bại:', error);
      const errMsg = error instanceof Error ? error.message : 'Tạo thất bại, vui lòng thử lại';
      const axiosError = error as { response?: { data?: { detail?: string } } };
      message.error(axiosError.response?.data?.detail || errMsg);
    } finally {
      if (sessionVersion === sessionVersionRef.current) setLoading(false);
    }
  };

  const handleSelectOption = async (option: string, sourceMessage?: Message) => {
    const retryRequest = sourceMessage?.failedRequest || lastFailedRequest;
    if ((option === 'Tạo lại' || option === 'Để AI tạo lại') && retryRequest) {
      await handleRetry(retryRequest);
      return;
    }

    if (loading || refining) return;

    if (option === 'Tôi tự nhập tên sách' || option === 'Tôi tự nhập') {
      message.info('Vui lòng nhập nội dung của bạn vào ô nhập bên dưới');
      return;
    }

    // Với loại chọn nhiều, không vô hiệu hóa tùy chọn ngay
    if (currentStep === 'genre') {
      const newSelected = selectedOptions.includes(option)
        ? selectedOptions.filter(o => o !== option)
        : [...selectedOptions, option];
      setSelectedOptions(newSelected);
      return;
    }

    // Vô hiệu hóa ngay tùy chọn của tin nhắn hiện tại (trường hợp chọn một)
    setMessages(prev => {
      const newMessages = [...prev];
      const lastAiMessageIndex = newMessages.map((m, i) => m.type === 'ai' && m.options ? i : -1).filter(i => i >= 0).pop();
      if (lastAiMessageIndex !== undefined && lastAiMessageIndex >= 0) {
        newMessages[lastAiMessageIndex] = {
          ...newMessages[lastAiMessageIndex],
          optionsDisabled: true
        };
      }
      return newMessages;
    });

    if (currentStep === 'perspective') {
      const userMessage: Message = {
        type: 'user',
        content: option,
      };
      setMessages(prev => [...prev, userMessage]);

      const updatedData = { ...wizardData, narrative_perspective: option };
      setWizardData(updatedData);

      // Hỏi chế độ đề cương
      const aiMessage: Message = {
        type: 'ai',
        content: `Rất tốt! Giờ hãy chọn chế độ đề cương bạn muốn:

📋 Chế độ một-một: chế độ truyền thống, một đề cương tương ứng một chương, phù hợp với tiểu thuyết có cấu trúc rõ ràng, chương độc lập.

📚 Chế độ một-nhiều: chế độ chi tiết, một đề cương có thể mở rộng thành nhiều chương, phù hợp với tiểu thuyết cần triển khai chi tiết tình tiết.

Vui lòng chọn:`,
        options: ['📋 Chế độ một-một', '📚 Chế độ một-nhiều']
      };
      setMessages(prev => [...prev, aiMessage]);
      setCurrentStep('outline_mode');
      return;
    }

    if (currentStep === 'outline_mode') {
      const userMessage: Message = {
        type: 'user',
        content: option,
      };
      setMessages(prev => [...prev, userMessage]);

      // Chuyển tùy chọn thành giá trị chế độ thực tế
      const modeValue: 'one-to-one' | 'one-to-many' =
        option === '📋 Chế độ một-một' ? 'one-to-one' : 'one-to-many';

      const updatedData = {
        ...wizardData,
        outline_mode: modeValue,
        genre: wizardData.genre || []
      } as WizardData;
      setWizardData(updatedData);

      // Hiển thị tóm tắt
      const modeText = modeValue === 'one-to-one' ? 'Chế độ một-một' : 'Chế độ một-nhiều';
      const summary = `
Tuyệt vời! Thiết lập tiểu thuyết của bạn đã hoàn tất, vui lòng xác nhận:

📖 Tên sách: ${updatedData.title}
📝 Giới thiệu: ${updatedData.description}
🎯 Chủ đề: ${updatedData.theme}
🏷️ Thể loại: ${updatedData.genre.join(', ')}
👁️ Góc nhìn: ${updatedData.narrative_perspective}
📋 Chế độ đề cương: ${modeText}

Vui lòng chọn thao tác tiếp theo:
      `.trim();

      const aiMessage: Message = {
        type: 'ai',
        content: summary,
        options: ['✅ Xác nhận tạo', '🔄 Bắt đầu lại']
      };
      setMessages(prev => [...prev, aiMessage]);
      setCurrentStep('confirm');
      return;
    }

    if (currentStep === 'confirm') {
      if (option === '✅ Xác nhận tạo') {
        const userMessage: Message = {
          type: 'user',
          content: 'Xác nhận tạo',
        };
        setMessages(prev => [...prev, userMessage]);

        const aiMessage: Message = {
          type: 'ai',
          content: 'OK! Đang tạo dự án cho bạn, có thể mất vài phút...'
        };
        setMessages(prev => [...prev, aiMessage]);

        // Xóa cache (hội thoại hoàn tất, chuyển sang giai đoạn tạo)
        clearCache();

        // Bắt đầu tạo dự án
        const data = wizardData as WizardData;
        const config: GenerationConfig = {
          title: data.title,
          description: data.description,
          theme: data.theme,
          genre: data.genre,
          narrative_perspective: data.narrative_perspective,
          target_words: 100000,
          chapter_count: 3,
          character_count: 5,
          outline_mode: data.outline_mode,
        };
        setGenerationConfig(config);
        setCurrentStep('generating');
        return;
      } else if (option === '🔄 Bắt đầu lại') {
        handleRestart();
        return;
      }
    }

    const userMessage: Message = {
      type: 'user',
      content: option,
    };
    setMessages(prev => [...prev, userMessage]);
    const sessionVersion = sessionVersionRef.current;
    setLoading(true);

    try {
      const updatedData = { ...wizardData };
      if (currentStep === 'title') {
        updatedData.title = option;
      } else if (currentStep === 'description') {
        updatedData.description = option;
      } else if (currentStep === 'theme') {
        updatedData.theme = option;
      }
      setWizardData(updatedData);

      await generateNextStep(updatedData);
    } catch (error: unknown) {
      if (sessionVersion !== sessionVersionRef.current) return;
      console.error('Chọn tùy chọn thất bại:', error);
      const errMsg = error instanceof Error ? error.message : 'Tạo thất bại, vui lòng thử lại';
      const axiosError = error as { response?: { data?: { detail?: string } } };
      message.error(axiosError.response?.data?.detail || errMsg);
    } finally {
      if (sessionVersion === sessionVersionRef.current) setLoading(false);
    }
  };

  const handleCustomInput = async (input: string) => {
    const sessionVersion = sessionVersionRef.current;
    setLoading(true);
    try {
      const updatedData = { ...wizardData };

      if (currentStep === 'title') {
        updatedData.title = input;
      } else if (currentStep === 'description') {
        updatedData.description = input;
      } else if (currentStep === 'theme') {
        updatedData.theme = input;
      } else if (currentStep === 'genre') {
        updatedData.genre = [input];
      } else if (currentStep === 'perspective') {
        updatedData.narrative_perspective = input;
        setWizardData(updatedData);
        
        // Vào thẳng chọn chế độ đề cương
        const aiMessage: Message = {
          type: 'ai',
          content: `Rất tốt! Giờ hãy chọn chế độ đề cương bạn muốn:

📋 Chế độ một-một: chế độ truyền thống, một đề cương tương ứng một chương, phù hợp với tiểu thuyết có cấu trúc rõ ràng, chương độc lập.

📚 Chế độ một-nhiều: chế độ chi tiết, một đề cương có thể mở rộng thành nhiều chương, phù hợp với tiểu thuyết cần triển khai chi tiết tình tiết.

Vui lòng chọn:`,
          options: ['📋 Chế độ một-một', '📚 Chế độ một-nhiều']
        };
        setMessages(prev => [...prev, aiMessage]);
        setCurrentStep('outline_mode');
        setLoading(false);
        return;
      } else if (currentStep === 'outline_mode') {
        // Chế độ đề cương không hỗ trợ nhập tùy chỉnh
        message.warning('Vui lòng chọn một chế độ đề cương từ các tùy chọn');
        setLoading(false);
        return;
      }

      setWizardData(updatedData);
      await generateNextStep(updatedData);
    } catch (error: unknown) {
      if (sessionVersion !== sessionVersionRef.current) return;
      console.error('Xử lý nhập tùy chỉnh thất bại:', error);
      const errMsg = error instanceof Error ? error.message : 'Xử lý thất bại, vui lòng thử lại';
      const axiosError = error as { response?: { data?: { detail?: string } } };
      message.error(axiosError.response?.data?.detail || errMsg);
    } finally {
      if (sessionVersion === sessionVersionRef.current) setLoading(false);
    }
  };

  const handleConfirmGenres = async () => {
    if (selectedOptions.length === 0) {
      message.warning('Vui lòng chọn ít nhất một thể loại');
      return;
    }

    // Vô hiệu hóa tùy chọn của chọn thể loại
    setMessages(prev => {
      const newMessages = [...prev];
      const lastAiMessageIndex = newMessages.map((m, i) => m.type === 'ai' && m.options ? i : -1).filter(i => i >= 0).pop();
      if (lastAiMessageIndex !== undefined && lastAiMessageIndex >= 0) {
        newMessages[lastAiMessageIndex] = {
          ...newMessages[lastAiMessageIndex],
          optionsDisabled: true
        };
      }
      return newMessages;
    });

    const userMessage: Message = {
      type: 'user',
      content: selectedOptions.join('、'),
    };
    setMessages(prev => [...prev, userMessage]);

    const updatedData = { ...wizardData, genre: selectedOptions };
    setWizardData(updatedData);
    setSelectedOptions([]);

    setLoading(true);
    try {
      const aiMessage: Message = {
        type: 'ai',
        content: 'Rất tốt! Tiếp theo, vui lòng chọn góc nhìn kể chuyện của tiểu thuyết:',
        options: ['第一人称', '第三人称', '全知视角']
      };
      setMessages(prev => [...prev, aiMessage]);
      setCurrentStep('perspective');
    } finally {
      setLoading(false);
    }
  };

  const generateNextStep = async (data: Partial<WizardData>) => {
    const sessionVersion = sessionVersionRef.current;
    const currentIndex = stepOrder.indexOf(currentStep);
    const nextStep = stepOrder[currentIndex + 1];

    if (nextStep === 'perspective') {
      // Sau khi bước genre hoàn tất, chuyển sang perspective
      const aiMessage: Message = {
        type: 'ai',
        content: 'Rất tốt! Tiếp theo, vui lòng chọn góc nhìn kể chuyện của tiểu thuyết:',
        options: ['第一人称', '第三人称', '全知视角']
      };
      setMessages(prev => [...prev, aiMessage]);
      setCurrentStep('perspective');
    } else if (nextStep === 'description') {
      const requestData = {
        step: 'description' as const,
        context: {
          initial_idea: initialIdea,
          title: data.title
        }
      };
      const response = await inspirationApi.generateOptions(requestData);

      if (sessionVersion !== sessionVersionRef.current) return;

      if (response.error || !response.options || response.options.length < 3) {
        const errorMessage: Message = {
          type: 'ai',
          content: response.error
            ? `Tạo giới thiệu bị lỗi: ${response.error}\n\nBạn có thể chọn:`
            : `Định dạng tùy chọn được tạo không đúng (cần ít nhất 3 tùy chọn hợp lệ)\n\nBạn có thể chọn:`,
          options: ['Tạo lại', 'Tôi tự nhập'],
          failedRequest: requestData,
        };
        setMessages(prev => [...prev, errorMessage]);
        setLastFailedRequest(requestData);
        return;
      }

      const aiMessage: Message = {
        type: 'ai',
        content: response.prompt || 'Vui lòng chọn một giới thiệu, hoặc nhập của riêng bạn:',
        options: response.options,
        canRefine: true,
        step: 'description'
      };
      setMessages(prev => [...prev, aiMessage]);
      setCurrentStep('description');
      setLastFailedRequest(null);

    } else if (nextStep === 'theme') {
      const requestData = {
        step: 'theme' as const,
        context: {
          initial_idea: initialIdea,
          title: data.title,
          description: data.description
        }
      };
      const response = await inspirationApi.generateOptions(requestData);

      if (sessionVersion !== sessionVersionRef.current) return;

      if (response.error || !response.options || response.options.length < 3) {
        const errorMessage: Message = {
          type: 'ai',
          content: response.error
            ? `Tạo chủ đề bị lỗi: ${response.error}\n\nBạn có thể chọn:`
            : `Định dạng tùy chọn được tạo không đúng (cần ít nhất 3 tùy chọn hợp lệ)\n\nBạn có thể chọn:`,
          options: ['Tạo lại', 'Tôi tự nhập'],
          failedRequest: requestData,
        };
        setMessages(prev => [...prev, errorMessage]);
        setLastFailedRequest(requestData);
        return;
      }

      const aiMessage: Message = {
        type: 'ai',
        content: response.prompt || 'Vui lòng chọn một chủ đề, hoặc nhập của riêng bạn:',
        options: response.options,
        canRefine: true,
        step: 'theme'
      };
      setMessages(prev => [...prev, aiMessage]);
      setCurrentStep('theme');
      setLastFailedRequest(null);

    } else if (nextStep === 'genre') {
      const requestData = {
        step: 'genre' as const,
        context: {
          initial_idea: initialIdea,
          title: data.title,
          description: data.description,
          theme: data.theme
        }
      };
      const response = await inspirationApi.generateOptions(requestData);

      if (sessionVersion !== sessionVersionRef.current) return;

      if (response.error || !response.options || response.options.length < 3) {
        const errorMessage: Message = {
          type: 'ai',
          content: response.error
            ? `Tạo thể loại bị lỗi: ${response.error}\n\nBạn có thể chọn:`
            : `Định dạng tùy chọn được tạo không đúng (cần ít nhất 3 tùy chọn hợp lệ)\n\nBạn có thể chọn:`,
          options: ['Tạo lại', 'Tôi tự nhập'],
          isMultiSelect: false,
          failedRequest: requestData,
        };
        setMessages(prev => [...prev, errorMessage]);
        setLastFailedRequest(requestData);
        return;
      }

      const aiMessage: Message = {
        type: 'ai',
        content: response.prompt || 'Vui lòng chọn nhãn thể loại (có thể chọn nhiều):',
        options: response.options,
        isMultiSelect: true,
        canRefine: true,
        step: 'genre'
      };
      setMessages(prev => [...prev, aiMessage]);
      setCurrentStep('genre');
      setLastFailedRequest(null);
    }
  };

  const handleRestart = () => {
    sessionVersionRef.current += 1;
    // Xóa cache
    clearCache();
    localStorage.removeItem('inspiration_project_id');
    localStorage.removeItem('inspiration_generation_data');
    localStorage.removeItem('inspiration_current_step');

    setCurrentStep('idea');
    setMessages([
      {
        type: 'ai',
        content: 'OK, chúng ta bắt đầu lại nhé!\n\nHãy cho tôi biết, bạn muốn viết một tiểu thuyết như thế nào?',
      }
    ]);
    setWizardData({});
    setInitialIdea('');
    setSelectedOptions([]);
    setLastFailedRequest(null);
    setFeedbackValue('');
    setShowFeedbackInput(null);
    setRefining(false);
    setGenerationConfig(null);
    setInputValue('');
    setLoading(false);
  };

  const handleBack = () => {
    navigate('/projects');
  };

  // Callback khi tạo hoàn tất
  const handleComplete = (projectId: string) => {
    console.log('Tạo dự án chế độ cảm hứng hoàn tất:', projectId);
    // Đảm bảo xóa cache
    clearCache();
    setCurrentStep('complete');
  };

  // Quay về giao diện hội thoại
  const handleBackToChat = () => {
    clearCache();
    setCurrentStep('idea');
    setGenerationConfig(null);
    handleRestart();
  };

  // Render giao diện hội thoại
  const renderChat = () => (
    <>
      <Card
        ref={chatContainerRef}
        style={{
          height: isMobile ? 'calc(100vh - 280px)' : 600,
          overflowY: 'auto',
          marginBottom: 16,
          boxShadow: `0 8px 24px color-mix(in srgb, ${token.colorTextBase} 20%, transparent)`,
          scrollBehavior: 'smooth'
        }}
      >
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          {messages.map((msg, index) => (
            <div
              key={index}
              style={{
                display: 'flex',
                justifyContent: msg.type === 'ai' ? 'flex-start' : 'flex-end',
                alignItems: 'flex-start',
                animation: 'fadeInUp 0.5s ease-out',
                animationFillMode: 'both',
                animationDelay: `${index * 0.1}s`
              }}
            >
              <div style={{
                maxWidth: '80%',
                padding: '12px 16px',
                borderRadius: 12,
                background: msg.type === 'ai' ? token.colorBgContainer : token.colorPrimary,
                color: msg.type === 'ai' ? token.colorText : token.colorWhite,
                boxShadow: msg.type === 'ai'
                  ? `0 2px 10px color-mix(in srgb, ${token.colorTextBase} 12%, transparent)`
                  : `0 4px 14px color-mix(in srgb, ${token.colorPrimary} 30%, transparent)`,
              }}>
                <Paragraph
                  style={{
                    margin: 0,
                    color: msg.type === 'ai' ? token.colorText : token.colorWhite,
                    whiteSpace: 'pre-wrap'
                  }}
                >
                  {msg.content}
                </Paragraph>

                {msg.options && msg.options.length > 0 && (
                  <Space
                    direction="vertical"
                    style={{ width: '100%', marginTop: 12 }}
                    size="small"
                  >
                    {msg.options.map((option, optIndex) => (
                      <Card
                        key={optIndex}
                        hoverable={!msg.optionsDisabled}
                        size="small"
                        onClick={() => !msg.optionsDisabled && !loading && !refining && handleSelectOption(option, msg)}
                        style={{
                          cursor: msg.optionsDisabled || loading || refining ? 'not-allowed' : 'pointer',
                          border: msg.isMultiSelect && selectedOptions.includes(option)
                            ? `2px solid ${token.colorPrimary}`
                            : `1px solid ${token.colorBorder}`,
                          background: msg.optionsDisabled
                            ? token.colorBgLayout
                            : msg.isMultiSelect && selectedOptions.includes(option)
                              ? token.colorPrimaryBg
                              : token.colorBgContainer,
                          opacity: msg.optionsDisabled ? 0.6 : 1,
                          animation: 'floatIn 0.6s ease-out',
                          animationDelay: `${optIndex * 0.1}s`,
                          animationFillMode: 'both',
                          transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                        }}
                        onMouseEnter={(e) => {
                          if (!msg.optionsDisabled) {
                            e.currentTarget.style.transform = 'translateY(-2px) scale(1.02)';
                            e.currentTarget.style.boxShadow = `0 8px 22px color-mix(in srgb, ${token.colorTextBase} 14%, transparent)`;
                          }
                        }}
                        onMouseLeave={(e) => {
                          if (!msg.optionsDisabled) {
                            e.currentTarget.style.transform = 'translateY(0) scale(1)';
                            e.currentTarget.style.boxShadow = 'none';
                          }
                        }}
                      >
                        {option}
                      </Card>
                    ))}

                    {msg.isMultiSelect && (
                      <Button
                        type="primary"
                        block
                        onClick={handleConfirmGenres}
                        disabled={selectedOptions.length === 0}
                      >
                        Xác nhận chọn ({selectedOptions.length})
                      </Button>
                    )}

                    {/* Khu vực tối ưu phản hồi - mới */}
                    {msg.canRefine && !msg.optionsDisabled && !msg.isMultiSelect && (
                      <div style={{ marginTop: 8, paddingTop: 8, borderTop: `1px dashed ${token.colorBorder}` }}>
                        {showFeedbackInput === index ? (
                          <Space direction="vertical" style={{ width: '100%' }} size="small">
                            <TextArea
                              value={feedbackValue}
                              onChange={(e) => setFeedbackValue(e.target.value)}
                              placeholder="Ví dụ: tôi muốn chủ đề bi thảm hơn, có thể ngắn gọn hơn không, thiên về cổ phong..."
                              autoSize={{ minRows: 2, maxRows: 3 }}
                              disabled={refining}
                              onPressEnter={(e) => {
                                if (!e.shiftKey && feedbackValue.trim()) {
                                  e.preventDefault();
                                  handleRefineOptions(index, feedbackValue);
                                }
                              }}
                            />
                            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
                              <Button
                                size="small"
                                onClick={() => {
                                  setShowFeedbackInput(null);
                                  setFeedbackValue('');
                                }}
                                disabled={refining}
                              >
                                Hủy
                              </Button>
                              <Button
                                type="primary"
                                size="small"
                                onClick={() => handleRefineOptions(index, feedbackValue)}
                                loading={refining}
                                disabled={!feedbackValue.trim()}
                              >
                                Tạo theo phản hồi
                              </Button>
                            </Space>
                          </Space>
                        ) : (
                          <Button
                            type="link"
                            size="small"
                            onClick={() => setShowFeedbackInput(index)}
                            style={{ padding: 0, height: 'auto' }}
                          >
                            💡 Chưa hài lòng? Hãy cho tôi biết ý tưởng của bạn
                          </Button>
                        )}
                      </div>
                    )}
                  </Space>
                )}
              </div>
            </div>
          ))}

          {(loading || refining) && (
            <div style={{
              textAlign: 'center',
              padding: 20,
              animation: 'fadeIn 0.3s ease-in'
            }}>
              <Spin tip={refining ? "Đang tạo lại dựa trên phản hồi của bạn..." : "AI đang suy nghĩ..."} />
            </div>
          )}

          <div ref={messagesEndRef} />
        </Space>
      </Card>

      <Card
        style={{ boxShadow: `0 4px 12px color-mix(in srgb, ${token.colorTextBase} 14%, transparent)` }}
        styles={{ body: { padding: 12 } }}
      >
        <Space.Compact style={{ width: '100%' }}>
          <TextArea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder={
              currentStep === 'idea'
                ? 'Ví dụ: tôi muốn viết một tiểu thuyết khoa học viễn tưởng về du hành thời gian...'
                : 'Nhập nội dung tùy chỉnh, hoặc nhấn vào thẻ tùy chọn phía trên...'
            }
            autoSize={{ minRows: 2, maxRows: 4 }}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault();
                handleSendMessage();
              }
            }}
            disabled={loading}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSendMessage}
            loading={loading}
            style={{ height: 'auto' }}
          >
            Gửi
          </Button>
        </Space.Compact>
        <Text type="secondary" style={{ fontSize: 12, marginTop: 8, display: 'block' }}>
          💡 Mẹo: nhấn Enter để gửi, Shift+Enter để xuống dòng
        </Text>
      </Card>
    </>
  );

  return (
    <div style={{
      minHeight: '100dvh',
      background: token.colorBgBase,
    }}>
      {contextHolder}
      <style>
        {`
          @keyframes fadeInUp {
            from {
              opacity: 0;
              transform: translateY(20px);
            }
            to {
              opacity: 1;
              transform: translateY(0);
            }
          }
          
          @keyframes floatIn {
            0% {
              opacity: 0;
              transform: translateY(10px) scale(0.95);
            }
            60% {
              transform: translateY(-5px) scale(1.02);
            }
            100% {
              opacity: 1;
              transform: translateY(0) scale(1);
            }
          }
          
          @keyframes fadeIn {
            from {
              opacity: 0;
            }
            to {
              opacity: 1;
            }
          }
        `}
      </style>

      {/* Thanh tiêu đề trên cùng - cố định không cuộn */}
      <div style={{
        position: 'sticky',
        top: 0,
        zIndex: 100,
        background: token.colorPrimary,
        boxShadow: `0 6px 20px color-mix(in srgb, ${token.colorPrimary} 30%, transparent)`,
      }}>
        <div style={{
          maxWidth: 1200,
          margin: '0 auto',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: isMobile ? '12px 16px' : '16px 24px',
        }}>
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={handleBack}
            size={isMobile ? 'middle' : 'large'}
            style={{
              background: `color-mix(in srgb, ${token.colorWhite} 20%, transparent)`,
              borderColor: `color-mix(in srgb, ${token.colorWhite} 30%, transparent)`,
              color: token.colorWhite,
            }}
          >
            {isMobile ? 'Quay lại' : 'Về trang chủ'}
          </Button>

          <div style={{ textAlign: 'center' }}>
            <Title
              level={isMobile ? 4 : 2}
              style={{
                margin: 0,
                color: token.colorWhite,
                textShadow: '0 2px 4px color-mix(in srgb, var(--ant-color-black) 18%, transparent)',
                lineHeight: 1.2
              }}
            >
              ✨ Chế độ cảm hứng
            </Title>
          </div>

          {/* Nút bắt đầu lại - chỉ hiển thị khi hội thoại đang diễn ra */}
          {currentStep !== 'idea' && currentStep !== 'generating' && currentStep !== 'complete' ? (
            <Button
              icon={<ReloadOutlined />}
              onClick={() => {
                modal.confirm({
                  title: 'Xác nhận bắt đầu lại',
                  content: 'Chắc chắn bắt đầu lại chứ? Tiến độ hội thoại hiện tại sẽ bị mất.',
                  okText: 'Xác nhận',
                  cancelText: 'Hủy',
                  centered: true,
                  okButtonProps: { danger: true },
                  onOk: () => {
                    handleRestart();
                  },
                });
              }}
              size={isMobile ? 'middle' : 'large'}
              style={{
                background: `color-mix(in srgb, ${token.colorWhite} 20%, transparent)`,
                borderColor: `color-mix(in srgb, ${token.colorWhite} 30%, transparent)`,
                color: token.colorWhite,
              }}
            >
              {isMobile ? 'Làm lại' : 'Bắt đầu lại'}
            </Button>
          ) : (
            <div style={{ width: isMobile ? 60 : 120 }}></div>
          )}
        </div>
      </div>

      <div style={{
        maxWidth: 800,
        margin: '0 auto',
        padding: isMobile ? '16px 12px' : '24px 24px',
      }}>
        {(currentStep === 'idea' || currentStep === 'title' || currentStep === 'description' ||
          currentStep === 'theme' || currentStep === 'genre' || currentStep === 'perspective' ||
          currentStep === 'outline_mode' || currentStep === 'confirm') && renderChat()}
        {(currentStep === 'generating' || currentStep === 'complete') && generationConfig && (
          <AIProjectGenerator
            config={generationConfig}
            storagePrefix="inspiration"
            onComplete={handleComplete}
            onBack={handleBackToChat}
            isMobile={isMobile}
          />
        )}
      </div>
    </div>
  );
};

export default Inspiration;
