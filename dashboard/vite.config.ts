import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Las rutas del build siguen siendo relativas para admitir despliegues en subrutas.
export default defineConfig({
  base: './',
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
