import { useState } from 'react';
import { FloatButton, Grid } from 'antd';
import { FileTextOutlined } from '@ant-design/icons';
import ChangelogModal from './ChangelogModal';

const { useBreakpoint } = Grid;

export default function ChangelogFloatingButton() {
  const [showChangelog, setShowChangelog] = useState(false);
  const screens = useBreakpoint();
  const isMobile = !screens.md;

  return (
    <>
      <FloatButton
        icon={<FileTextOutlined />}
        type="primary"
        tooltip="Xem nhật ký cập nhật"
        style={{
          // Trên desktop, đảm bảo nút nằm trong khu vực nội dung chính (bên phải sidebar)
          right: 24,
          bottom: 100,
          // Di động không có sidebar, không cần xử lý thêm
          ...(isMobile ? {} : {
            // Đảm bảo zIndex thấp hơn sidebar nhưng cao hơn nội dung
            zIndex: 999,
          }),
        }}
        onClick={() => setShowChangelog(true)}
      />

      <ChangelogModal
        visible={showChangelog}
        onClose={() => setShowChangelog(false)}
      />
    </>
  );
}