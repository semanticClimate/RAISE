import path from 'path';
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { visualizer } from 'rollup-plugin-visualizer';
import { defineConfig, type Plugin } from 'vite';

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    process.env.ANALYZE === 'true' &&
      visualizer({
        filename: 'dist/stats.html',
        open: true,
        gzipSize: true,
        brotliSize: true,
      }),
  ].filter(Boolean) as Plugin[],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  envDir: path.resolve(import.meta.dirname, '..'),
  envPrefix: [
    'VITE_',
    'GEMINI_',
    'GROQ_',
    'DEEPSEEK_',
    'NVIDIA_',
    'COHERE_',
    'OPENROUTER_',
    'OPENAI_',
    'ANTHROPIC_',
    'MISTRAL_',
    'POSTGRES_',
    'REDIS_',
    'NEO4J_',
    'LLM_',
    'CHROMA_',
  ],
  base: './', // Ensures static deployment compatibility (e.g. GitHub Pages)
  server: {
    port: 5173,
    strictPort: true,
    host: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
      },
    },
    watch: {
      ignored: [
        '**/*.md',
        '**/.git/**',
        '**/docs/**',
        '**/backend_docs/**',
        '**/backend/**',
        '**/.github/**',
        '**/evaluation/**',
        '**/scripts/**',
        '**/sugestions by frontend/**',
      ],
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (
            id.includes('node_modules/react/') ||
            id.includes('node_modules/react-dom/') ||
            id.includes('node_modules/react-router-dom/')
          ) {
            return 'vendor-react';
          }
          if (id.includes('node_modules/@tanstack/react-query/')) {
            return 'vendor-query';
          }
          if (id.includes('node_modules/lucide-react/')) {
            return 'vendor-icons';
          }
          if (id.includes('node_modules/katex/')) {
            return 'vendor-katex';
          }
          if (id.includes('node_modules/zod/') || id.includes('node_modules/zustand/')) {
            return 'vendor-utils';
          }
        },
      },
    },
    chunkSizeWarningLimit: 650,
  },
});

