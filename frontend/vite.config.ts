import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// /api 요청을 FastAPI 백엔드(8000)로 프록시
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',          // 새 배포 시 자동 업데이트 (CI/CD 와 궁합)
      includeAssets: ['favicon.svg', 'icons.svg'],
      manifest: {
        name: 'autovest · 자동 적립',
        short_name: 'autovest',
        description: '지수 ETF 자동 적립 대시보드',
        theme_color: '#16161a',
        background_color: '#16161a',
        display: 'standalone',             // 주소창 없는 앱 형태
        orientation: 'portrait',
        start_url: '/',
        icons: [
          { src: '/favicon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any maskable' },
        ],
      },
      workbox: {
        // /api 는 실시간 데이터 → 서비스워커가 가로채거나 캐시하지 않음
        navigateFallbackDenylist: [/^\/api/],
      },
    }),
  ],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
