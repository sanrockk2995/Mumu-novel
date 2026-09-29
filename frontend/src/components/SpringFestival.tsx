/**
 * 🧧 Component trang trí Tết vui tươi
 * 
 * Gồm các yếu tố sau:
 * - 🏮 Đèn lồng treo (mỗi bên hai cái)
 * - 🎆 Hiệu ứng pháo hoa (canvas-confetti)
 * - 🌸 Vật trang trí rơi (hoa mai, chữ Phúc, v.v.)
 * - 🧧 Băng rôn chúc Tết
 * - Có thể bật/tắt qua nút nổi bên phải (hỗ trợ kéo thả + tự dính mép)
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import confetti from 'canvas-confetti';
import './SpringFestival.css';

// Phát hiện khoảng ngày Tết (khoảng 15 ngày trước/sau Tết âm lịch)
function isSpringFestivalSeason(): boolean {
  // Đánh giá đơn giản: hiển thị trong khoảng 15/1 ~ 5/3 hàng năm
  const now = new Date();
  const month = now.getMonth() + 1; // 1-12
  const day = now.getDate();
  return (month === 1 && day >= 15) || month === 2 || (month === 3 && day <= 5);
}

// Cấu hình vật trang trí rơi
const FALLING_ITEMS = ['🌸', '✨', '🧧', '💮', '🎐', '❄️', '🏮'];
const SPRING_COUPLETS = [
  'Năm Ngọ đại cát',
  'Cung hỷ phát tài',
  'Đưa lì xì đây',
  'Vạn sự như ý',
  'Gia đình sum vầy',
  'Xuân mới vui vẻ',
  'Phúc tinh cao chiếu',
];

interface FallingItem {
  id: number;
  emoji: string;
  left: number;
  delay: number;
  duration: number;
  size: number;
}

interface BtnPosition {
  x: number;
  y: number;
  side: 'left' | 'right';
}

// Vị trí nút mặc định: dính mép phải, căn giữa
function getDefaultBtnPosition(): BtnPosition {
  return {
    x: window.innerWidth - 22, // Dính mép phải
    y: window.innerHeight / 2,
    side: 'right',
  };
}

// Đọc vị trí đã lưu từ localStorage
function loadBtnPosition(): BtnPosition {
  try {
    const saved = localStorage.getItem('sf-btn-position');
    if (saved) {
      const pos = JSON.parse(saved) as BtnPosition;
      // Đảm bảo trong vùng hiển thị
      pos.y = Math.max(22, Math.min(window.innerHeight - 22, pos.y));
      pos.x = pos.side === 'left' ? 22 : window.innerWidth - 22;
      return pos;
    }
  } catch { /* ignore */ }
  return getDefaultBtnPosition();
}

export default function SpringFestival() {
  const [visible, setVisible] = useState(() => {
    const saved = localStorage.getItem('spring-festival-visible');
    if (saved !== null) return saved === 'true';
    return isSpringFestivalSeason();
  });

  const [showBanner, setShowBanner] = useState(true);
  const [bannerText] = useState(() => {
    return SPRING_COUPLETS[Math.floor(Math.random() * SPRING_COUPLETS.length)];
  });

  // Chữ đèn lồng: lấy từ bốn chữ trong SPRING_COUPLETS, luân phiên theo thời gian
  const [lanternChars, setLanternChars] = useState<string[]>(() => {
    const text = SPRING_COUPLETS[Math.floor(Math.random() * SPRING_COUPLETS.length)];
    return text.split('');
  });
  const [lanternFading, setLanternFading] = useState(false);
  const lanternIndexRef = useRef(Math.floor(Math.random() * SPRING_COUPLETS.length));

  const [fallingItems, setFallingItems] = useState<FallingItem[]>([]);
  const fireworksIntervalRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fallingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lanternIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const idCounterRef = useRef(0);

  // State liên quan đến kéo nút
  const [btnPos, setBtnPos] = useState<BtnPosition>(loadBtnPosition);
  const [isDragging, setIsDragging] = useState(false);
  const [hasDragged, setHasDragged] = useState(false);
  const dragStartRef = useRef<{ startX: number; startY: number; startBtnX: number; startBtnY: number } | null>(null);
  const btnRef = useRef<HTMLButtonElement>(null);

  // Tạo vật rơi
  const createFallingItem = useCallback((): FallingItem => {
    idCounterRef.current += 1;
    return {
      id: idCounterRef.current,
      emoji: FALLING_ITEMS[Math.floor(Math.random() * FALLING_ITEMS.length)],
      left: Math.random() * 100,
      delay: 0,
      duration: 6 + Math.random() * 8,
      size: 12 + Math.random() * 16,
    };
  }, []);

  // Hiệu ứng pháo hoa
  const launchFirework = useCallback(() => {
    if (!visible) return;

    const colors = ['#FF0000', '#FFD700', '#FF6347', '#FF4500', '#FFA500', '#DC143C'];

    confetti({
      particleCount: 30 + Math.floor(Math.random() * 30),
      spread: 60 + Math.random() * 40,
      origin: {
        x: 0.1 + Math.random() * 0.8,
        y: 0.2 + Math.random() * 0.4,
      },
      colors: colors.slice(0, 3 + Math.floor(Math.random() * 3)),
      shapes: ['circle', 'square'],
      gravity: 0.8,
      scalar: 0.8 + Math.random() * 0.4,
      drift: (Math.random() - 0.5) * 0.5,
      ticks: 200,
      disableForReducedMotion: true,
    });
  }, [visible]);

  // Hiệu ứng pháo hoa chào mừng ban đầu
  const launchWelcomeFireworks = useCallback(() => {
    const positions = [
      { x: 0.2, y: 0.3 },
      { x: 0.5, y: 0.2 },
      { x: 0.8, y: 0.3 },
    ];

    positions.forEach((pos, i) => {
      setTimeout(() => {
        confetti({
          particleCount: 60,
          spread: 80,
          origin: pos,
          colors: ['#FF0000', '#FFD700', '#FF6347', '#FF4500', '#DC143C', '#FFA500'],
          shapes: ['circle', 'square'],
          gravity: 0.7,
          scalar: 1,
          ticks: 250,
          disableForReducedMotion: true,
        });
      }, i * 400);
    });
  }, []);

  // Quản lý vật rơi và pháo hoa
  useEffect(() => {
    if (!visible) {
      setFallingItems([]);
      if (fireworksIntervalRef.current) {
        clearTimeout(fireworksIntervalRef.current);
        fireworksIntervalRef.current = null;
      }
      if (fallingIntervalRef.current) {
        clearInterval(fallingIntervalRef.current);
        fallingIntervalRef.current = null;
      }
      if (lanternIntervalRef.current) {
        clearInterval(lanternIntervalRef.current);
        lanternIntervalRef.current = null;
      }
      return;
    }

    // Tạo ban đầu một loạt vật rơi
    const initialItems: FallingItem[] = [];
    for (let i = 0; i < 12; i++) {
      const item = createFallingItem();
      item.delay = Math.random() * 8;
      initialItems.push(item);
    }
    setFallingItems(initialItems);

    // Pháo hoa chào mừng ban đầu
    setTimeout(launchWelcomeFireworks, 1000);

    // Thêm vật rơi mới định kỳ
    fallingIntervalRef.current = setInterval(() => {
      setFallingItems(prev => {
        const kept = prev.slice(-15);
        return [...kept, createFallingItem()];
      });
    }, 3000);

    // Bắn pháo hoa định kỳ (mỗi 20-40 giây một lần)
    const scheduleFirework = () => {
      const delay = 20000 + Math.random() * 20000;
      fireworksIntervalRef.current = setTimeout(() => {
        launchFirework();
        scheduleFirework();
      }, delay);
    };
    scheduleFirework();

    // Luân phiên chữ đèn lồng theo thời gian (mỗi 10 giây)
    lanternIntervalRef.current = setInterval(() => {
      // Kích hoạt mờ dần trước
      setLanternFading(true);
      // Sau 500ms đổi chữ và hiện dần
      setTimeout(() => {
        lanternIndexRef.current = (lanternIndexRef.current + 1) % SPRING_COUPLETS.length;
        const newText = SPRING_COUPLETS[lanternIndexRef.current];
        setLanternChars(newText.split(''));
        setLanternFading(false);
      }, 500);
    }, 10000);

    return () => {
      if (fireworksIntervalRef.current) {
        clearTimeout(fireworksIntervalRef.current);
        fireworksIntervalRef.current = null;
      }
      if (fallingIntervalRef.current) {
        clearInterval(fallingIntervalRef.current);
        fallingIntervalRef.current = null;
      }
      if (lanternIntervalRef.current) {
        clearInterval(lanternIntervalRef.current);
        lanternIntervalRef.current = null;
      }
    };
  }, [visible, createFallingItem, launchFirework, launchWelcomeFireworks]);

  // Băng rôn tự ẩn
  useEffect(() => {
    if (visible && showBanner) {
      const timer = setTimeout(() => setShowBanner(false), 8000);
      return () => clearTimeout(timer);
    }
  }, [visible, showBanner]);

  // ===== Logic kéo nút =====
  
  // Tự dính mép
  const snapToEdge = useCallback((x: number, y: number): BtnPosition => {
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const btnRadius = 22;
    const clampedY = Math.max(btnRadius, Math.min(vh - btnRadius, y));
    
    // Quyết định dính bên nào theo khoảng cách đến mép trái/phải
    const side: 'left' | 'right' = x < vw / 2 ? 'left' : 'right';
    const snapX = side === 'left' ? btnRadius : vw - btnRadius;
    
    return { x: snapX, y: clampedY, side };
  }, []);

  // Nhấn chuột/chạm
  const handleDragStart = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    e.preventDefault();
    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
    const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;
    
    dragStartRef.current = {
      startX: clientX,
      startY: clientY,
      startBtnX: btnPos.x,
      startBtnY: btnPos.y,
    };
    setIsDragging(true);
    setHasDragged(false);
  }, [btnPos]);

  // Di chuyển chuột/chạm
  useEffect(() => {
    if (!isDragging) return;

    const handleMove = (e: MouseEvent | TouchEvent) => {
      if (!dragStartRef.current) return;
      
      const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
      const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;
      
      const dx = clientX - dragStartRef.current.startX;
      const dy = clientY - dragStartRef.current.startY;
      
      // Di chuyển quá 5px mới tính là kéo
      if (Math.abs(dx) > 5 || Math.abs(dy) > 5) {
        setHasDragged(true);
      }
      
      const newX = dragStartRef.current.startBtnX + dx;
      const newY = dragStartRef.current.startBtnY + dy;
      
      setBtnPos({
        x: newX,
        y: Math.max(22, Math.min(window.innerHeight - 22, newY)),
        side: newX < window.innerWidth / 2 ? 'left' : 'right',
      });
    };

    const handleEnd = () => {
      setIsDragging(false);
      dragStartRef.current = null;
      
      // Tự dính mép
      setBtnPos(prev => {
        const snapped = snapToEdge(prev.x, prev.y);
        // Lưu vào localStorage
        localStorage.setItem('sf-btn-position', JSON.stringify(snapped));
        return snapped;
      });
    };

    window.addEventListener('mousemove', handleMove);
    window.addEventListener('mouseup', handleEnd);
    window.addEventListener('touchmove', handleMove, { passive: false });
    window.addEventListener('touchend', handleEnd);

    return () => {
      window.removeEventListener('mousemove', handleMove);
      window.removeEventListener('mouseup', handleEnd);
      window.removeEventListener('touchmove', handleMove);
      window.removeEventListener('touchend', handleEnd);
    };
  }, [isDragging, snapToEdge]);

  // Dính lại mép khi kích thước cửa sổ thay đổi
  useEffect(() => {
    const handleResize = () => {
      setBtnPos(prev => snapToEdge(prev.side === 'left' ? 22 : window.innerWidth - 22, prev.y));
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [snapToEdge]);

  // ===== Hiệu ứng tương tác chuột =====

  // Bắn pháo hoa nhỏ khi nhấn chuột vào trang
  const handlePageClick = useCallback((e: MouseEvent) => {
    if (!visible) return;
    // Bỏ qua nhấn vào vùng nút và đèn lồng (tránh xung đột với tương tác khác)
    const target = e.target as HTMLElement;
    if (target.closest('.sf-toggle-btn') || target.closest('.sf-banner')) return;
    
    const x = e.clientX / window.innerWidth;
    const y = e.clientY / window.innerHeight;
    
    confetti({
      particleCount: 15 + Math.floor(Math.random() * 15),
      spread: 40 + Math.random() * 30,
      origin: { x, y },
      colors: ['#FF0000', '#FFD700', '#FF6347', '#FF4500'],
      shapes: ['circle'],
      gravity: 1.2,
      scalar: 0.6 + Math.random() * 0.3,
      ticks: 120,
      disableForReducedMotion: true,
    });
  }, [visible]);

  // Gắn sự kiện nhấn chuột toàn cục
  useEffect(() => {
    if (!visible) return;
    
    window.addEventListener('click', handlePageClick);
    
    return () => {
      window.removeEventListener('click', handlePageClick);
    };
  }, [visible, handlePageClick]);

  // Nhấn đèn lồng: bùng pháo hoa + đổi ngay lời chúc
  const handleLanternClick = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    
    // Lấy vị trí đèn lồng để bắn pháo hoa
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const x = (rect.left + rect.width / 2) / window.innerWidth;
    const y = (rect.top + rect.height / 2) / window.innerHeight;
    
    confetti({
      particleCount: 50,
      spread: 70,
      origin: { x, y },
      colors: ['#FF0000', '#FFD700', '#FF6347', '#FF4500', '#DC143C'],
      shapes: ['circle', 'square'],
      gravity: 0.8,
      scalar: 0.9,
      ticks: 200,
      disableForReducedMotion: true,
    });

    // Đổi ngay lời chúc (kèm mờ dần/hiện dần)
    setLanternFading(true);
    setTimeout(() => {
      lanternIndexRef.current = (lanternIndexRef.current + 1) % SPRING_COUPLETS.length;
      const newText = SPRING_COUPLETS[lanternIndexRef.current];
      setLanternChars(newText.split(''));
      setLanternFading(false);
    }, 400);
  }, []);

  // Chuyển trạng thái hiển thị (chỉ kích hoạt khi chưa kéo)
  const handleBtnClick = () => {
    if (hasDragged) return; // Đã kéo thì không kích hoạt nhấn
    const next = !visible;
    setVisible(next);
    localStorage.setItem('spring-festival-visible', String(next));
    if (next) {
      setShowBanner(true);
    }
  };

  // Tính style nút
  const btnStyle: React.CSSProperties = {
    position: 'fixed',
    left: btnPos.x - 22,
    top: btnPos.y - 22,
    transition: isDragging ? 'none' : 'left 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), top 0.1s ease',
    cursor: isDragging ? 'grabbing' : 'grab',
    touchAction: 'none',
    userSelect: 'none',
  };

  return (
    <>
      {/* Nút điều khiển - luôn hiển thị, có thể kéo */}
      <button
        ref={btnRef}
        className={`sf-toggle-btn ${isDragging ? 'sf-dragging' : ''}`}
        style={btnStyle}
        onMouseDown={handleDragStart}
        onTouchStart={handleDragStart}
        onClick={handleBtnClick}
        title={visible ? 'Tắt trang trí Tết' : 'Bật trang trí Tết'}
      >
        {visible ? '🧨' : '🏮'}
      </button>

      {visible && (
        <>
          {/* Băng rôn chúc Tết */}
          {showBanner && (
            <div className="sf-banner" onClick={() => setShowBanner(false)}>
              <div className="sf-banner-content">
                <span className="sf-banner-icon">🧧</span>
                <span className="sf-banner-text">
                  {bannerText}
                </span>
                <span className="sf-banner-icon">🧧</span>
              </div>
            </div>
          )}

          {/* Đèn lồng - bên trái (hướng vào giữa), có thể nhấn */}
          <div className="sf-lantern-group sf-lantern-left sf-lantern-clickable" onClick={handleLanternClick}>
            <div className="sf-lantern sf-lantern-1">
              <div className="sf-lantern-line"></div>
              <div className="sf-lantern-body">
                <div className="sf-lantern-top"></div>
                <div className="sf-lantern-middle">
                  <span className={`sf-lantern-char ${lanternFading ? 'sf-char-fade-out' : 'sf-char-fade-in'}`}>
                    {lanternChars[0] || 'Phúc'}
                  </span>
                </div>
                <div className="sf-lantern-bottom"></div>
                <div className="sf-lantern-tassel"></div>
              </div>
            </div>
            <div className="sf-lantern sf-lantern-2">
              <div className="sf-lantern-line"></div>
              <div className="sf-lantern-body">
                <div className="sf-lantern-top"></div>
                <div className="sf-lantern-middle">
                  <span className={`sf-lantern-char ${lanternFading ? 'sf-char-fade-out' : 'sf-char-fade-in'}`}>
                    {lanternChars[1] || 'Xuân'}
                  </span>
                </div>
                <div className="sf-lantern-bottom"></div>
                <div className="sf-lantern-tassel"></div>
              </div>
            </div>
          </div>

          {/* Đèn lồng - bên phải (hướng vào giữa), có thể nhấn */}
          <div className="sf-lantern-group sf-lantern-right sf-lantern-clickable" onClick={handleLanternClick}>
            <div className="sf-lantern sf-lantern-3">
              <div className="sf-lantern-line"></div>
              <div className="sf-lantern-body">
                <div className="sf-lantern-top"></div>
                <div className="sf-lantern-middle">
                  <span className={`sf-lantern-char ${lanternFading ? 'sf-char-fade-out' : 'sf-char-fade-in'}`}>
                    {lanternChars[2] || 'Hỷ'}
                  </span>
                </div>
                <div className="sf-lantern-bottom"></div>
                <div className="sf-lantern-tassel"></div>
              </div>
            </div>
            <div className="sf-lantern sf-lantern-4">
              <div className="sf-lantern-line"></div>
              <div className="sf-lantern-body">
                <div className="sf-lantern-top"></div>
                <div className="sf-lantern-middle">
                  <span className={`sf-lantern-char ${lanternFading ? 'sf-char-fade-out' : 'sf-char-fade-in'}`}>
                    {lanternChars[3] || 'Lạc'}
                  </span>
                </div>
                <div className="sf-lantern-bottom"></div>
                <div className="sf-lantern-tassel"></div>
              </div>
            </div>
          </div>

          {/* Vật trang trí rơi */}
          <div className="sf-falling-container">
            {fallingItems.map(item => (
              <span
                key={item.id}
                className="sf-falling-item"
                style={{
                  left: `${item.left}%`,
                  animationDelay: `${item.delay}s`,
                  animationDuration: `${item.duration}s`,
                  fontSize: `${item.size}px`,
                }}
              >
                {item.emoji}
              </span>
            ))}
          </div>

          {/* Thanh trang trí đỏ trên cùng */}
          <div className="sf-top-border"></div>
        </>
      )}
    </>
  );
}
