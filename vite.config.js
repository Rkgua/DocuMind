import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    target: 'es2020',
    cssCodeSplit: true,
    minify: false,
    rollupOptions: {
      output: {
        manualChunks(id) {
          const moduleId = id.replaceAll('\\\\', '/');
          if (!moduleId.includes('/node_modules/')) return undefined;
          if (moduleId.includes('/react/') || moduleId.includes('/react-dom/')) return 'vendor';
          if (moduleId.includes('/react-markdown/') || moduleId.includes('/remark-gfm/')) return 'markdown';
          if (moduleId.includes('/react-syntax-highlighter/')) return 'highlight';
          if (moduleId.includes('/lucide-react/')) return 'icons';
          return undefined;
        },
      },
    },
  },
})
