import React from 'react';
import { Modal, Spin, Button, theme } from 'antd';
import { LoadingOutlined, StopOutlined } from '@ant-design/icons';

interface SSEProgressModalProps {
  visible: boolean;
  progress: number;
  message: string;
  title?: string;
  showPercentage?: boolean;
  showIcon?: boolean;
  onCancel?: () => void;
  cancelButtonText?: string;
}

/**
 * Component Modal hiển thị tiến độ SSE thống nhất
 * Dùng để hiển thị tiến độ tạo AI trong Modal, kiểu đồng nhất với SSELoadingOverlay
 */
export const SSEProgressModal: React.FC<SSEProgressModalProps> = ({
  visible,
  progress,
  message,
  title = 'AI đang tạo...',
  showPercentage = true,
  showIcon = true,
  onCancel,
  cancelButtonText = 'Hủy tác vụ',
}) => {
  const { token } = theme.useToken();

  if (!visible) return null;

  return (
    <Modal
      title={null}
      open={visible}
      footer={null}
      closable={false}
      centered
      width={500}
      maskClosable={false}
      keyboard={false}
      styles={{
        body: {
          padding: '40px 40px 32px',
        }
      }}
    >
      <div>
        {/* Tiêu đề và biểu tượng */}
        {showIcon && (
          <div style={{
            textAlign: 'center',
            marginBottom: 24
          }}>
            <Spin
              indicator={<LoadingOutlined style={{ fontSize: 48, color: token.colorPrimary }} spin />}
            />
            <div style={{
              fontSize: 20,
              fontWeight: 'bold',
              marginTop: 16,
              color: token.colorText
            }}>
              {title}
            </div>
          </div>
        )}

        {/* Thanh tiến độ */}
        <div style={{
          marginBottom: showPercentage ? 16 : 24
        }}>
          <div style={{
            height: 12,
            background: token.colorBgLayout,
            borderRadius: 6,
            overflow: 'hidden',
            marginBottom: showPercentage ? 12 : 0
          }}>
            <div style={{
              height: '100%',
              background: progress === 100
                ? `linear-gradient(90deg, ${token.colorSuccess} 0%, ${token.colorSuccess} 100%)`
                : `linear-gradient(90deg, ${token.colorPrimary} 0%, ${token.colorPrimary} 100%)`,
              width: `${progress}%`,
              transition: 'all 0.3s ease',
              borderRadius: 6,
              boxShadow: progress > 0 ? token.boxShadow : 'none'
            }} />
          </div>

          {/* Phần trăm tiến độ */}
          {showPercentage && (
            <div style={{
              textAlign: 'center',
              fontSize: 32,
              fontWeight: 'bold',
              color: progress === 100 ? token.colorSuccess : token.colorPrimary,
              marginBottom: 8
            }}>
              {progress}%
            </div>
          )}
        </div>

        {/* Thông báo trạng thái */}
        <div style={{
          textAlign: 'center',
          fontSize: 16,
          color: token.colorTextSecondary,
          minHeight: 24,
          padding: '0 20px',
          marginBottom: 16
        }}>
          {message || 'Đang chuẩn bị tạo...'}
        </div>

        {/* Chữ gợi ý */}
        <div style={{
          textAlign: 'center',
          fontSize: 13,
          color: token.colorTextTertiary,
          marginBottom: onCancel ? 16 : 0
        }}>
          Vui lòng không đóng trang, quá trình tạo cần một khoảng thời gian
        </div>

        {/* Nút hủy */}
        {onCancel && (
          <div style={{
            textAlign: 'center',
            marginTop: 16
          }}>
            <Button
              danger
              size="large"
              icon={<StopOutlined />}
              onClick={onCancel}
            >
              {cancelButtonText}
            </Button>
          </div>
        )}
      </div>
    </Modal>
  );
};

export default SSEProgressModal;