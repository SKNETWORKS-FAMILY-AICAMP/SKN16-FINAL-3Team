import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: true,
    port: 3000,
    fs: {
      allow: [path.resolve(__dirname, '..')],
    },
    // 개발 환경에서는 CSP 헤더를 설정하지 않음 (Vite HMR을 위해)
    // 프로덕션 빌드에서는 웹 서버(Nginx 등)에서 안전한 CSP 설정
    headers: {
      // 개발 환경에서 CSP 헤더 제거 (HTML 메타 태그 사용)
      'Content-Security-Policy': ''
    },
    proxy: {
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  build: {
    // 프로덕션 빌드 최적화
    sourcemap: false,
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true, // 프로덕션에서 console.log 제거
        drop_debugger: true,
      },
    },
  },
})

