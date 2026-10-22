/* ============================================================================
   Build da PAGINA PUBLICA dos formularios (`forms.movisat.com.br/f/<slug>`).
   ----------------------------------------------------------------------------
   🚨 SAO DOIS BUILDS, E O `npm run build` RODA OS DOIS. O destino aqui e
   `frontend/dist_publico`, que o `movizap/main.py` monta em `/pub/assets` e
   serve em `/f/{slug}`. Mudar um dos dois sem o outro deixa o formulario fora
   do ar sem derrubar nada -- o pior tipo de quebra.

   🚨 `sourcemap: false`, AO CONTRARIO DO PAINEL. No painel o sourcemap ajuda a
   depurar um erro relatado pelo atendente e nao vaza nada que o bundle ja nao
   tenha; aqui quem baixa a pagina e a internet.

   🚨 `base: '/pub/'`: o HTML publicado tem de apontar para `/pub/assets/...`,
   que e o unico caminho de estatico que o nginx do host publico deixa passar.
   ============================================================================ */
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  root: 'publico',
  base: '/pub/',
  build: {
    outDir: '../dist_publico',
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    port: 5174,
    // ⚠️ `..` liberado porque a pagina importa o renderizador de `src/`, que
    // fica FORA da raiz deste build. Vale so no `vite dev`.
    fs: { allow: ['..'] },
    proxy: { '/api': { target: 'http://127.0.0.1:8008', changeOrigin: false } },
  },
})
