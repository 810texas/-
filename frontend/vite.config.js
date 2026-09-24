import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 代理到后端：开发期（server）与生产预览（preview）都要有，
// 否则 vite preview 下前端的 /api 请求会 404。
const proxy = {
  '/api': {
    // 代理规避 HTTPOnly Cookie 跨端口问题
    target: 'http://127.0.0.1:8000',
    changeOrigin: true,
  },
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy,
  },
  preview: {
    port: 4173,
    proxy,
  },
})
