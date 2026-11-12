import { fileURLToPath, URL } from 'node:url'
import { readFileSync } from 'node:fs'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => ({
  define: {
    'import.meta.env.BMAT_ANDROID': JSON.stringify(mode === 'android'),
    'import.meta.env.BMAT_VERSION': JSON.stringify(
      JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8')).version
    ),
  },
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: { proxy: { '/api': 'http://127.0.0.1:37164' } },
  build: { chunkSizeWarningLimit: 1400, outDir: mode === 'android' ? 'dist-android' : 'dist' },
  plugins: [
    vue(),
    {
      name: 'build-platform',
      generateBundle() {
        this.emitFile({
          type: 'asset',
          fileName: 'build-platform.json',
          source: JSON.stringify({ platform: mode === 'android' ? 'android' : 'desktop' }),
        })
      },
    },
  ],
}))
