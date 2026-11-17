import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Destino do proxy /api. Padrão: serviço local na porta 8000 (start.bat).
// Os testes de ponta a ponta usam outra porta para não interferir em um serviço aberto.
const apiTarget = process.env.BIM_SCHEDULE_API_PROXY ?? 'http://127.0.0.1:8000'

// base relativa: o mesmo build funciona servido pelo Vite, em subpastas
// e carregado por file:// dentro do aplicativo Windows (Electron).
export default defineConfig({
  base: './',
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 4173,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
})
