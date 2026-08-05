/* ============================================================================
   Build do painel.
   ----------------------------------------------------------------------------
   O destino é `frontend/dist`, que é exatamente onde `movizap/main.py` procura
   (`RAIZ / "frontend" / "dist"`) para montar /assets e servir o index. Mudar
   um dos dois sem o outro derruba o painel sem derrubar a API — o pior tipo de
   quebra, porque o serviço continua `active`.
   ============================================================================ */
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    // O painel é interno e servido pela própria API: sourcemap ajuda a depurar
    // um erro relatado pelo atendente e não vaza nada que já não esteja no bundle.
    sourcemap: true,
    chunkSizeWarningLimit: 700,
  },
  server: {
    // Só para `npm run dev`. Em produção quem serve é o FastAPI.
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8008', changeOrigin: false },
    },
  },
})
