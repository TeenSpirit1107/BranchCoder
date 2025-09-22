import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import monacoEditorPlugin from 'vite-plugin-monaco-editor';
import { fileURLToPath, URL } from 'node:url';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    // @ts-expect-error - vite-plugin-monaco-editor类型定义问题
    monacoEditorPlugin.default({})
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  optimizeDeps: {
    esbuildOptions: {
      target: 'esnext',
      supported: {
        'top-level-await': true
      }
    },
    include: ['pdfjs-dist', '@react-pdf-viewer/core', '@react-pdf-viewer/default-layout']
  },
  build: {
    target: 'esnext'
  },
  assetsInclude: ['**/*.pdf']
}); 