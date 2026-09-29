import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'fs'
import { resolve } from 'path'

// Đọc package.json để lấy số phiên bản
const packageJson = JSON.parse(
  readFileSync(resolve(__dirname, 'package.json'), 'utf-8')
)

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Định nghĩa hằng số toàn cục, inject khi build
  define: {
    'import.meta.env.VITE_APP_VERSION': JSON.stringify(packageJson.version),
    'import.meta.env.VITE_BUILD_TIME': JSON.stringify(
      new Date().toISOString().split('T')[0]
    ),
  },
  build: {
    outDir: '../backend/static',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        // Chia thủ công code block, tách thư viện dependency lớn
        manualChunks: {
          // Thư viện lõi React
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          // Thư viện Ant Design UI (dependency lớn nhất)
          'vendor-antd': ['antd', '@ant-design/icons'],
          // Thư viện công cụ khác
          'vendor-utils': ['axios', 'dayjs', 'zustand'],
          // Trình xem Diff (component lớn)
          'vendor-diff': ['react-diff-viewer-continued'],
          // Thư viện kéo thả
          'vendor-dnd': ['@dnd-kit/core', '@dnd-kit/sortable', '@dnd-kit/utilities'],
        },
      },
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/generated-assets': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
})
