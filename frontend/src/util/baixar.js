/* ============================================================================
   Baixar arquivo de rota protegida — um lugar só.
   ----------------------------------------------------------------------------
   🚨 ESTE DEFEITO JÁ APARECEU QUATRO VEZES, sempre do mesmo jeito: a rota é
   protegida por `Bearer` e nada mais, e **navegação de link não manda cabeçalho
   `Authorization`**. Então `<a href="/api/...">` e `window.open('/api/...')`
   voltam **401**, e o navegador não baixa nada — some, ou abre uma aba com o
   JSON do erro. Clique que não faz nada parece defeito do arquivo, não da
   autenticação, e é por isso que ninguém reporta direito.

   O rastro:
     · 27/08 — `<img src>` da mídia na Caixa voltava 401, *"e o atendente veria
       um ícone quebrado sem explicação"*. Nasceu a `pedirBlob`.
     · o anexo do recado do painel: 401 em todo clique, e ninguém notou porque
       `os_observacao_arquivo` tinha ZERO linhas.
     · 26/11 — 🔵 ELE: *"os formulários que têm anexo, na página das
       'Solicitações' quando clico neles, não baixam direto"*. Medido no log:
       **4 pedidos, 4 × 401**.
     · 26/11, na mesma varredura — o **comprovante** da `PNL_1.6`: **2 cliques,
       2 × 401**. E o **arquivo do Procfy**, que ninguém clicou ainda e está
       quebrado do mesmo jeito (lido na definição da rota, não suposto).

   ⚠️ A QUINTA OCORRÊNCIA É O QUE ESTA FUNÇÃO EXISTE PARA IMPEDIR, junto da
   trava em `baixar_protegido_2611.teste.js`, que reprova `<a href="/api/…">`
   sem `@click.prevent` e `window.open('/api/…')` em qualquer tela.
   ============================================================================ */
import { pedirBlob } from '../api/cliente.js';

/* Busca com o token, salva com o nome certo e devolve a memória.
   🚨 Levanta `ErroDeApi` quando o servidor recusa: quem chama MOSTRA a frase.
   Engolir aqui recriaria o silêncio que esta função veio tirar. */
export async function baixarArquivo(rota, nome) {
  const blob = await pedirBlob(rota);
  const url = URL.createObjectURL(blob);
  try {
    /* ⚠️ `download` com o nome ORIGINAL: sem ele o navegador salva com o nome
       do `blob:`, que é um UUID. */
    const l = document.createElement('a');
    l.href = url;
    l.download = nome || 'arquivo';
    l.rel = 'noopener';
    document.body.appendChild(l);
    l.click();
    l.remove();
  } finally {
    /* ⚠️ Solta o `blob:` DEPOIS do clique — cada download reservaria memória
       para sempre. O atraso existe porque revogar antes de o navegador começar
       a baixar cancela o download. */
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  }
}
