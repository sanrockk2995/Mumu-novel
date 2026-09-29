-- Script khởi tạo PostgreSQL

-- Tạo các extension cần thiết
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- Hỗ trợ sinh UUID
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- Hỗ trợ tìm kiếm mờ và tìm kiếm toàn văn

-- Xuất thông tin khởi tạo
DO $$
BEGIN
    RAISE NOTICE '==================================================';
    RAISE NOTICE 'Cài đặt extension PostgreSQL cho MuMuAINovel hoàn tất';
    RAISE NOTICE 'Các extension đã cài:';
    RAISE NOTICE '  - uuid-ossp: hỗ trợ sinh UUID';
    RAISE NOTICE '  - pg_trgm: hỗ trợ tìm kiếm mờ và tìm kiếm toàn văn';
    RAISE NOTICE '';
    RAISE NOTICE 'Lưu ý:';
    RAISE NOTICE '  - Cấu hình múi giờ: qua biến môi trường TZ trong docker-compose.yml';
    RAISE NOTICE '  - Mã hóa ký tự: cấu hình qua POSTGRES_INITDB_ARGS';
    RAISE NOTICE '  - Cấu trúc bảng: tự động tạo bởi SQLAlchemy ORM';
    RAISE NOTICE '  - Dữ liệu preset: chèn động bởi code Python init_db()';
    RAISE NOTICE '==================================================';
END $$;