import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Spin, Result, Button, Modal, Input, message, theme } from 'antd';
import { authApi } from '../services/api';
import AnnouncementModal from '../components/AnnouncementModal';

export default function AuthCallback() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState('');
  const [showAnnouncement, setShowAnnouncement] = useState(false);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const { token } = theme.useToken();
  const alphaColor = (color: string, alpha: number) => `color-mix(in srgb, ${color} ${(alpha * 100).toFixed(0)}%, transparent)`;
  interface PasswordStatus {
    has_password: boolean;
    has_custom_password: boolean;
    username: string;
    default_password: string;
  }
  const [passwordStatus, setPasswordStatus] = useState<PasswordStatus | null>(null);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [settingPassword, setSettingPassword] = useState(false);

  useEffect(() => {
    const handleCallback = async () => {
      try {
        // Backend sẽ tự động đặt thông tin xác thực qua Cookie
        // Ở đây chỉ cần xác minh trạng thái đăng nhập
        const currentUser = await authApi.getCurrentUser();

        // Kiểm tra có phải lần đăng nhập đầu tiên không (qua cờ Cookie)
        const isFirstLogin = document.cookie.includes('first_login=true');
        
        setStatus('success');

        if (isFirstLogin) {
          // Lần đăng nhập đầu: tạo mật khẩu mặc định và hiển thị gợi ý
          const defaultPassword = `${currentUser.username}@666`;
          const pwdStatus = {
            has_password: false,
            has_custom_password: false,
            username: currentUser.username,
            default_password: defaultPassword
          };
          setPasswordStatus(pwdStatus);

          // Xóa cờ Cookie đánh dấu lần đăng nhập đầu
          document.cookie = 'first_login=; path=/; max-age=0';

          // Hiển thị popup khởi tạo mật khẩu
          setTimeout(() => {
            setShowPasswordModal(true);
          }, 1000);
          return;
        }

        // Không phải lần đầu: luồng bình thường
        // Lấy địa chỉ redirect từ sessionStorage
        const redirect = sessionStorage.getItem('login_redirect') || '/';
        sessionStorage.removeItem('login_redirect');

        // Kiểm tra đã ẩn thông báo vĩnh viễn hoặc đã ẩn hôm nay chưa
        const hideForever = localStorage.getItem('announcement_hide_forever');
        const hideToday = localStorage.getItem('announcement_hide_today');
        const today = new Date().toDateString();

        if (hideForever === 'true' || hideToday === today) {
          // Delay một chút rồi chuyển, để người dùng thấy thông báo thành công
          setTimeout(() => {
            navigate(redirect);
          }, 1000);
        } else {
          // Delay một chút rồi hiển thị thông báo, để người dùng thấy thông báo thành công
          setTimeout(() => {
            setShowAnnouncement(true);
          }, 1000);
        }
      } catch (error) {
        console.error('Đăng nhập thất bại:', error);
        setStatus('error');
        setErrorMessage('Đăng nhập thất bại, vui lòng thử lại');
      }
    };

    handleCallback();
  }, [navigate]);

  if (status === 'loading') {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
        background: `linear-gradient(135deg, ${token.colorPrimary} 0%, ${token.colorPrimaryHover} 100%)`,
      }}>
        <div style={{ textAlign: 'center' }}>
          <Spin size="large" />
          <div style={{ marginTop: 20, color: token.colorWhite, fontSize: 16 }}>
            Đang xử lý đăng nhập...
          </div>
        </div>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
        background: `linear-gradient(135deg, ${token.colorPrimary} 0%, ${token.colorPrimaryHover} 100%)`,
      }}>
        <Result
          status="error"
          title="Đăng nhập thất bại"
          subTitle={errorMessage}
          extra={
            <Button type="primary" onClick={() => navigate('/login')}>
              Về đăng nhập
            </Button>
          }
          style={{ background: token.colorBgContainer, padding: 40, borderRadius: 8 }}
        />
      </div>
    );
  }

  const handleAnnouncementClose = () => {
    setShowAnnouncement(false);
    const redirect = sessionStorage.getItem('login_redirect') || '/';
    sessionStorage.removeItem('login_redirect');
    navigate(redirect);
  };

  const handleDoNotShowToday = () => {
    // Đặt không hiển thị nữa trong hôm nay
    const today = new Date().toDateString();
    localStorage.setItem('announcement_hide_today', today);
  };

  const handleNeverShow = () => {
    // Đặt không hiển thị nữa vĩnh viễn
    localStorage.setItem('announcement_hide_forever', 'true');
  };

  const handleSetPassword = async () => {
    // Nếu không nhập mật khẩu mới, dùng mật khẩu mặc định
    const passwordToSet = newPassword || passwordStatus?.default_password;
    
    if (!passwordToSet) {
      message.error('Vui lòng nhập mật khẩu mới');
      return;
    }
    if (passwordToSet.length < 6) {
      message.error('Mật khẩu dài ít nhất 6 ký tự');
      return;
    }
    if (newPassword && newPassword !== confirmPassword) {
      message.error('Hai lần nhập mật khẩu không khớp');
      return;
    }

    setSettingPassword(true);
    try {
      // Lần đăng nhập đầu dùng API khởi tạo, các lần sau dùng API sửa
      const isFirstLogin = !passwordStatus?.has_password;
      if (isFirstLogin) {
        await authApi.initializePassword(passwordToSet);
        message.success('Khởi tạo mật khẩu thành công');
      } else {
        await authApi.setPassword(passwordToSet);
        message.success('Đặt mật khẩu thành công');
      }
      setShowPasswordModal(false);

      // Tiếp tục luồng tiếp theo
      const redirect = sessionStorage.getItem('login_redirect') || '/';
      sessionStorage.removeItem('login_redirect');

      const hideForever = localStorage.getItem('announcement_hide_forever');
      const hideToday = localStorage.getItem('announcement_hide_today');
      const today = new Date().toDateString();

      if (hideForever === 'true' || hideToday === today) {
        setTimeout(() => {
          navigate(redirect);
        }, 500);
      } else {
        setTimeout(() => {
          setShowAnnouncement(true);
        }, 500);
      }
    } catch {
      message.error('Đặt mật khẩu thất bại, vui lòng thử lại');
    } finally {
      setSettingPassword(false);
    }
  };

  const handleSkipPasswordSetting = async () => {
    // Khi đăng nhập lần đầu, nếu bỏ qua cài đặt, dùng mật khẩu mặc định để khởi tạo
    const isFirstLogin = !passwordStatus?.has_password;
    if (isFirstLogin && passwordStatus?.default_password) {
      try {
        await authApi.initializePassword(passwordStatus.default_password);
      } catch (error) {
        console.error('Khởi tạo mật khẩu mặc định thất bại:', error);
      }
    }

    setShowPasswordModal(false);

    // Tiếp tục luồng tiếp theo
    const redirect = sessionStorage.getItem('login_redirect') || '/';
    sessionStorage.removeItem('login_redirect');

    const hideForever = localStorage.getItem('announcement_hide_forever');
    const hideToday = localStorage.getItem('announcement_hide_today');
    const today = new Date().toDateString();

    if (hideForever === 'true' || hideToday === today) {
      setTimeout(() => {
        navigate(redirect);
      }, 500);
    } else {
      setTimeout(() => {
        setShowAnnouncement(true);
      }, 500);
    }
  };

  return (
    <>
      <AnnouncementModal
        visible={showAnnouncement}
        onClose={handleAnnouncementClose}
        onDoNotShowToday={handleDoNotShowToday}
        onNeverShow={handleNeverShow}
      />

      <Modal
        title="Đặt mật khẩu tài khoản"
        open={showPasswordModal}
        centered
        onOk={handleSetPassword}
        onCancel={handleSkipPasswordSetting}
        confirmLoading={settingPassword}
        okText="Đặt mật khẩu"
        cancelText="Để sau"
        width={500}
      >
        <div style={{ marginBottom: 20 }}>
          <p>Bạn đã đăng nhập thành công qua ủy quyền Linux DO!</p>
          <p>Hệ thống đã tự động tạo mật khẩu mặc định cho bạn, bạn có thể chọn đặt mật khẩu tùy chỉnh hoặc tiếp tục dùng mật khẩu mặc định.</p>
          {passwordStatus?.default_password && (
            <div style={{
              background: token.colorFillTertiary,
              padding: 12,
              borderRadius: 4,
              marginTop: 12
            }}>
              <strong>Tài khoản:</strong>{passwordStatus.username}<br />
              <strong>Mật khẩu mặc định:</strong><code style={{
                background: token.colorBgContainer,
                padding: '2px 8px',
                borderRadius: 3,
                color: token.colorPrimary,
                fontSize: 14
              }}>{passwordStatus.default_password}</code>
            </div>
          )}
        </div>

        <div style={{ marginTop: 20 }}>
          <div style={{ marginBottom: 12 }}>
            <label>Mật khẩu mới (ít nhất 6 ký tự):</label>
            <Input.Password
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="Vui lòng nhập mật khẩu mới"
              style={{ marginTop: 4 }}
            />
          </div>
          <div>
            <label>Xác nhận mật khẩu:</label>
            <Input.Password
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Vui lòng nhập lại mật khẩu"
              style={{ marginTop: 4 }}
            />
          </div>
        </div>
      </Modal>

      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
        background: `linear-gradient(135deg, ${token.colorPrimary} 0%, ${token.colorPrimaryHover} 100%)`,
      }}>
        <Result
          status="success"
          title="Đăng nhập thành công"
          subTitle={showPasswordModal ? "Vui lòng đặt mật khẩu tài khoản..." : (showAnnouncement ? "Chào mừng sử dụng..." : "Đang chuyển...")}
          style={{ background: alphaColor(token.colorBgContainer, 0.96), padding: 40, borderRadius: 8 }}
        />
      </div>
    </>
  );
}