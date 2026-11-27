/**
 * TRAVA: rota protegida não se baixa por link nem por `window.open`.
 *
 * 🚨 O MESMO DEFEITO QUATRO VEZES. A rota é protegida por `Bearer` e nada mais,
 * e **navegação de link não manda cabeçalho `Authorization`** — então
 * `<a href="/api/...">` e `window.open('/api/...')` voltam **401** e o navegador
 * não baixa nada. O clique parece não fazer nada, e quem opera reporta como
 * "o arquivo não abre", não como "não estou autenticado".
 *
 *   · 27/08 — `<img src>` da mídia: 401, *"e o atendente veria um ícone
 *     quebrado sem explicação"*. Nasceu a `pedirBlob`.
 *   · o anexo do recado do painel: 401 em todo clique, e ninguém notou porque
 *     `os_observacao_arquivo` tinha ZERO linhas.
 *   · 26/11 — 🔵 ELE: *"os formulários que têm anexo, na página das
 *     'Solicitações' quando clico neles, não baixam direto"*. **4 × 401** no log.
 *   · 26/11, na mesma varredura — o comprovante da `PNL_1.6`: **2 × 401**.
 *
 * ⚠️ POR QUE UMA TRAVA E NÃO SÓ O CONSERTO. Quatro ocorrências da mesma causa
 * dizem que consertar caso a caso não para a quinta. E ela se mede lendo o
 * TEMPLATE, não a função: o defeito é a marcação, e seletor é suposição minha
 * sobre a marcação (`M13`).
 *
 * ⚠️ O que esta trava NÃO faz: julgar se a rota exige token. Ela cobra o
 * caminho seguro para QUALQUER `/api/`, porque o que é aberto hoje pode ganhar
 * `Depends` amanhã — e aí ninguém reabriria este arquivo.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

import { describe, it, expect } from 'vitest'

const RAIZ = join(process.cwd(), 'src')

/* 📏 A LINHA DE BASE, medida em 26/11: UM caso conhecido, à vista e não
   apagado. O `.xlsx` do Procfy (`PainelServicoDosTecnicos.baixar`) está
   quebrado do mesmo jeito e **espera decisão dele**: o nome do arquivo é
   `procfy_<técnico>.xlsx` e o saneamento é regra do servidor, então baixar por
   blob obriga a escolher entre ler o `Content-Disposition` numa função nova do
   `api/cliente.js` ou deixar a tela nomear — e a segunda muda o nome que o
   Procfy recebe hoje.
   🚨 TIRAR UM NOME DESTA LISTA É CONSERTAR O DEFEITO DELE. Acrescentar um nome
   é assumir dívida nova, e isso é decisão dele, não minha. */
const CONHECIDOS = new Set([
  '/telas/PainelServicoDosTecnicos.vue: window.open',
])

function vues(pasta = RAIZ, achados = []) {
  for (const nome of readdirSync(pasta)) {
    const caminho = join(pasta, nome)
    if (statSync(caminho).isDirectory()) vues(caminho, achados)
    else if (nome.endsWith('.vue')) achados.push(caminho)
  }
  return achados
}

/* ⚠️ O `<style>` SAI, e os COMENTÁRIOS TAMBÉM — e isto a trava aprendeu
   reprovando: na primeira execução ela acusou `ChatInterno.vue` e `Email.vue`,
   e os dois estavam CERTOS. O que ela tinha lido era o comentário que explica
   *"não dá para usar `<a href="/api/...">`"*. Trava que acusa quem documentou
   o conserto é trava que todo mundo aprende a ignorar. */
function partes(texto) {
  const corte = texto.indexOf('<style')
  const semEstilo = corte < 0 ? texto : texto.slice(0, corte)
  const limpo = semEstilo
    .replace(/<!--[\s\S]*?-->/g, ' ')     // comentário de template
    .replace(/\/\*[\s\S]*?\*\//g, ' ')    // comentário de bloco no script
  return { template: limpo, codigo: limpo }
}

const arquivos = vues().map((caminho) => ({
  curto: caminho.split('src').pop().replace(/\\/g, '/'),
  ...partes(readFileSync(caminho, 'utf8')),
}))

describe('baixar de rota protegida', () => {
  it('🚨 nenhum `<a href="/api/...">` sem `@click.prevent` no mesmo elemento',
     () => {
    const culpados = []
    for (const a of arquivos) {
      /* Cada tag `<a ...>` por inteiro, com os atributos que carrega. */
      for (const tag of a.template.matchAll(/<a\s[^>]*>/gs)) {
        const corpo = tag[0]
        if (!/:?href="[^"]*\/api\//.test(corpo)) continue
        if (corpo.includes('@click.prevent')) continue
        const chave = `${a.curto}: href`
        if (CONHECIDOS.has(chave)) continue
        culpados.push(chave)
      }
    }
    expect(culpados, 'link para /api/ sem @click.prevent devolve 401 e não '
      + 'baixa nada — use `baixarArquivo` do `util/baixar.js`').toEqual([])
  })

  it('🚨 nenhum `window.open` apontando para a API', () => {
    const culpados = []
    for (const a of arquivos) {
      for (const chamada of a.codigo.matchAll(/window\.open\(([^)]*)\)/gs)) {
        const alvo = chamada[1]
        if (!/\/api\/|\$\{BASE\}|\$\{API/.test(alvo)) continue
        const chave = `${a.curto}: window.open`
        if (CONHECIDOS.has(chave)) continue
        culpados.push(chave)
      }
    }
    expect(culpados, '`window.open` não manda `Authorization` — use '
      + '`baixarArquivo` do `util/baixar.js`').toEqual([])
  })

  it('⚠️ a linha de base não cresce sozinha: 1 caso conhecido, nomeado', () => {
    // Se este número subir, alguém assumiu dívida nova sem dizer.
    expect(CONHECIDOS.size).toBe(1)
  })

  it('a trava reprova de verdade — provada contra marcação inventada', () => {
    /* 🚨 Trava que nunca reprovou não é trava. Aqui ela mede o mesmo padrão
       contra um template de mentira, no mesmo caminho de código. */
    const ruim = '<a :href="`/api/solicitacoes/1/arquivo/2`" target="_blank">x</a>'
    const bom = '<a :href="`/api/solicitacoes/1/arquivo/2`" @click.prevent="b(a)">x</a>'
    const pega = (t) => [...t.matchAll(/<a\s[^>]*>/gs)]
      .filter((m) => /:?href="[^"]*\/api\//.test(m[0])
                     && !m[0].includes('@click.prevent')).length
    expect(pega(ruim)).toBe(1)
    expect(pega(bom)).toBe(0)
    expect([...'window.open(`${BASE}/arquivo/${id}`, "_blank")'
      .matchAll(/window\.open\(([^)]*)\)/gs)]
      .filter((m) => /\/api\/|\$\{BASE\}/.test(m[1])).length).toBe(1)
  })
})
