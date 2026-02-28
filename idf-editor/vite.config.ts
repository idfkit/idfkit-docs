import { defineConfig } from 'vite';
import path from 'path';

export default defineConfig({
  build: {
    lib: {
      entry: path.resolve(__dirname, 'src/main.ts'),
      name: 'IDFEditor',
      formats: ['iife'],
      fileName: () => 'idf-editor.js',
    },
    outDir: path.resolve(__dirname, 'dist'),
    cssFileName: 'idf-editor',
    minify: 'esbuild',
    sourcemap: false,
    rollupOptions: {
      output: {
        assetFileNames: 'idf-editor.[ext]',
      },
    },
  },
});
