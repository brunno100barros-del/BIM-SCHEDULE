import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// O GitHub Pages publica este repositório em /BIM-SCHEDULE/.
// Em desenvolvimento local, a raiz continua sendo /.
const isGitHubPages = process.env.GITHUB_ACTIONS === 'true'

export default defineConfig({
  base: isGitHubPages ? '/BIM-SCHEDULE/' : '/',
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      }
    }
  }
})
