import { useState, useEffect } from 'react';
import { Typography, Space, Divider, Badge, Button, Grid, theme } from 'antd';
import { GithubOutlined, CopyrightOutlined, HeartFilled, ClockCircleOutlined, GiftOutlined } from '@ant-design/icons';
import { VERSION_INFO, getVersionString } from '../config/version';
import { checkLatestVersion } from '../services/versionService';

const { Text, Link } = Typography;
const { useBreakpoint } = Grid;

interface AppFooterProps {
  sidebarWidth?: number;
}

export default function AppFooter({ sidebarWidth = 0 }: AppFooterProps) {
  const screens = useBreakpoint();
  const isMobile = !screens.md;
  const [hasUpdate, setHasUpdate] = useState(false);
  const [latestVersion, setLatestVersion] = useState('');
  const [releaseUrl, setReleaseUrl] = useState('');
  const { token } = theme.useToken();
  const alphaColor = (color: string, alpha: number) => `color-mix(in srgb, ${color} ${(alpha * 100).toFixed(0)}%, transparent)`;

  useEffect(() => {
    // Kiểm tra cập nhật phiên bản (mỗi lần đều kiểm tra lại)
    const checkVersion = async () => {
      try {
        const result = await checkLatestVersion();
        setHasUpdate(result.hasUpdate);
        setLatestVersion(result.latestVersion);
        setReleaseUrl(result.releaseUrl);
      } catch {
        // Thất bại âm thầm
      }
    };

    // Delay 3 giây rồi kiểm tra, tránh ảnh hưởng lần tải đầu
    const timer = setTimeout(checkVersion, 3000);
    return () => clearTimeout(timer);
  }, []);

  // Nhấn vào số phiên bản để xem cập nhật
  const handleVersionClick = () => {
    if (hasUpdate && releaseUrl) {
      window.open(releaseUrl, '_blank');
    }
  };

  // Tính lề trái: trên desktop có sidebar cần dịch chuyển
  const leftOffset = isMobile ? 0 : sidebarWidth;

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 0,
        left: leftOffset,
        right: 0,
        backdropFilter: 'blur(20px) saturate(180%)',
        WebkitBackdropFilter: 'blur(20px) saturate(180%)',
        borderTop: `1px solid ${token.colorBorder}`,
        padding: isMobile ? '8px 12px' : '10px 16px',
        zIndex: 100,
        boxShadow: `0 -2px 16px ${alphaColor(token.colorText, 0.08)}`,
        backgroundColor: alphaColor(token.colorBgContainer, 0.82), // Nền bán trong suốt để hỗ trợ backdrop-filter
        transition: 'left 0.3s ease', // Chuyển mượt
      }}
    >
      <div
        style={{
          maxWidth: 1400,
          margin: '0 auto',
          textAlign: 'center',
        }}
      >
        {isMobile ? (
          // Di động: bố cục một dòng gọn
          <div style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            gap: 8,
            flexWrap: 'wrap'
          }}>
            <Badge dot={hasUpdate} offset={[-8, 2]}>
              <Text
                onClick={handleVersionClick}
                style={{
                  fontSize: 11,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  color: token.colorPrimary,
                  cursor: hasUpdate ? 'pointer' : 'default',
                }}
                title={hasUpdate ? `Phát hiện phiên bản mới v${latestVersion}, nhấn để xem` : 'Phiên bản hiện tại'}
              >
                <strong style={{ color: token.colorText }}>{VERSION_INFO.projectName}</strong>
                <span>{getVersionString()}</span>
              </Text>
            </Badge>
            <Divider type="vertical" style={{ margin: '0 4px', borderColor: token.colorBorder }} />
            <Button
              type="text"
              size="small"
              icon={<GiftOutlined />}
              onClick={() => window.open('https://mumuverse.space:1588/', '_blank')}
              style={{
                color: token.colorTextSecondary,
                fontSize: 11,
                height: 24,
                padding: '0 4px',
                display: 'flex',
                alignItems: 'center',
                gap: 4,
              }}
            >
              Tài trợ
            </Button>
            <Divider type="vertical" style={{ margin: '0 4px', borderColor: token.colorBorder }} />
            <Link
              href={VERSION_INFO.githubUrl}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                fontSize: 11,
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                color: token.colorTextSecondary,
              }}
            >
              <GithubOutlined style={{ fontSize: 12 }} />
            </Link>
            <Text
              style={{
                fontSize: 10,
                color: token.colorTextTertiary,
              }}
            >
              <ClockCircleOutlined style={{ fontSize: 10, marginRight: 4 }} />
              {VERSION_INFO.buildTime}
            </Text>
          </div>
        ) : (
          // PC: bố cục đầy đủ
          <Space
            direction="horizontal"
            size={12}
            split={<Divider type="vertical" style={{ borderColor: token.colorBorder }} />}
            style={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center'
            }}
          >
            {/* Thông tin phiên bản */}
            <Badge dot={hasUpdate} offset={[-8, 2]}>
              <Text
                onClick={handleVersionClick}
                style={{
                  fontSize: 12,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  color: token.colorTextSecondary,
                  textShadow: 'none',
                  cursor: hasUpdate ? 'pointer' : 'default',
                  transition: 'all 0.3s',
                }}
                onMouseEnter={(e) => {
                  if (hasUpdate) {
                    e.currentTarget.style.transform = 'scale(1.05)';
                  }
                }}
                onMouseLeave={(e) => {
                  if (hasUpdate) {
                    e.currentTarget.style.transform = 'scale(1)';
                  }
                }}
                title={hasUpdate ? `Phát hiện phiên bản mới v${latestVersion}, nhấn để xem` : 'Phiên bản hiện tại'}
              >
                <strong style={{ color: token.colorText }}>{VERSION_INFO.projectName}</strong>
                <span>{getVersionString()}</span>
              </Text>
            </Badge>

            {/* Link GitHub */}
            <Link
              href={VERSION_INFO.githubUrl}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                fontSize: 12,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                color: token.colorTextSecondary,
              }}
            >
              <GithubOutlined style={{ fontSize: 13 }} />
              <span>GitHub</span>
            </Link>

            {/* Cộng đồng LinuxDO */}
            <Link
              href={VERSION_INFO.linuxDoUrl}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                fontSize: 12,
                color: token.colorTextSecondary,
              }}
            >
              Cộng đồng LinuxDO
            </Link>

            {/* Nút tài trợ */}
            <Button
              type="primary"
              icon={<GiftOutlined style={{ fontSize: 14 }} />}
              onClick={() => window.open('https://mumuverse.space:1588/', '_blank')}
              style={{
                background: token.colorPrimary,
                border: 'none',
                boxShadow: `0 4px 12px ${alphaColor(token.colorPrimary, 0.35)}`,
                fontSize: 13,
                height: 32,
                padding: '0 20px',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                fontWeight: 600,
                transition: 'all 0.3s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-2px)';
                e.currentTarget.style.boxShadow = `0 6px 16px ${alphaColor(token.colorPrimary, 0.5)}`;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = `0 4px 12px ${alphaColor(token.colorPrimary, 0.35)}`;
              }}
            >
              Hỗ trợ tài trợ
            </Button>

            {/* Giấy phép */}
            <Link
              href={VERSION_INFO.licenseUrl}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                fontSize: 12,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                color: token.colorTextSecondary,
              }}
            >
              <CopyrightOutlined style={{ fontSize: 11 }} />
              <span>{VERSION_INFO.license}</span>
            </Link>

            {/* Thời gian cập nhật */}
            <Text
              style={{
                fontSize: 12,
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                color: token.colorTextTertiary,
              }}
            >
              <ClockCircleOutlined style={{ fontSize: 12 }} />
              <span>{VERSION_INFO.buildTime}</span>
            </Text>

            {/* Thông tin cảm ơn */}
            <Text
              style={{
                fontSize: 12,
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                color: token.colorTextSecondary,
                textShadow: `0 1px 3px ${alphaColor(token.colorText, 0.08)}`,
              }}
            >
              <span>Made with</span>
              <HeartFilled style={{ color: token.colorError, fontSize: 11 }} />
              <span>by {VERSION_INFO.author}</span>
            </Text>
          </Space>
        )}
      </div>

    </div>
  );
}