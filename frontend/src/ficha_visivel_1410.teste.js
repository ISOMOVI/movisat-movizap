/**
 * @vitest-environment node
 *
 * O botão "Ficha" não pode ser recortado pelo nome do cliente — 14/10.
 *
 * 🚨 POR QUE ESTE ARQUIVO EXISTE. A queixa dele foi *"o botão 'Ficha' de cada
 * conversa tem ficado invisível"*, e o "tem ficado" era a assinatura: o defeito
 * dependia do TAMANHO DO NOME. A classe `conversa__quem` servia a dois lugares
 * com necessidades opostas — o item da lista, onde cortar com reticências é o
 * certo, e o cabeçalho da conversa, onde a mesma classe envolve o botão. Solta,
 * a regra punha nome e botão na mesma linha sem poder quebrar, dentro de uma
 * caixa com `overflow: hidden`: nome comprido empurrava o botão para fora e o
 * recortava. No celular não acontecia, porque lá o nome ganha linha própria.
 *
 * 🚨 É GUARDA DE TEXTO, NÃO DE LAYOUT. Nenhum teste de DOM calcula recorte —
 * `jsdom` não faz layout, e foi por isso que a suíte ficou verde com o botão
 * invisível por dias. Este arquivo impede a VOLTA desta regra; ele não
 * descobre a próxima. Quem descobre é abrir a tela.
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const fonte = readFileSync(
  fileURLToPath(new URL('./telas/CaixaDeEntrada.vue', import.meta.url)),
  'utf8',
)

describe('o botão Ficha sobrevive a nome comprido', () => {
  it('a regra de reticências está presa à LISTA, não solta', () => {
    expect(fonte).toContain('.conversa__topo .conversa__quem,')
    /* 🚨 O seletor solto é o defeito em si. Ele aplicava `overflow: hidden` e
       `white-space: nowrap` também no cabeçalho, que não pediu nenhum dos
       dois. */
    expect(fonte).not.toMatch(/^\.conversa__quem,\s*$/m)
  })

  it('o botão do cabeçalho não encolhe', () => {
    expect(fonte).toContain('.conversa__cabecalho .conversa__quem > .botao { flex: none; }')
  })

  it('o nome tem teto e corta com reticências, em vez de empurrar o botão', () => {
    const regra = fonte.slice(
      fonte.indexOf('.conversa__cabecalho .conversa__quem > strong {'),
    ).slice(0, 400)
    expect(regra).toContain('max-width: 32ch')
    expect(regra).toContain('text-overflow: ellipsis')
    /* Sem `min-width: 0` o item de flex se recusa a encolher e as reticências
       nunca aparecem -- o teto viraria enfeite. */
    expect(regra).toContain('min-width: 0')
  })

  it('o telefone fica em linha própria, e não disputa espaço com o botão', () => {
    expect(fonte).toContain('.conversa__cabecalho .conversa__detalhe { flex: 1 0 100%; margin: 0; }')
  })

  it('e o botão continua existindo para toda conversa que não é grupo', () => {
    /* ⚠️ Afirmação do rótulo, não do `aria-label`: foi a confusão entre os dois
       que deixou o "Criar grupo" inachável por três semanas. */
    expect(fonte).toContain('<template v-else>Ficha · vincular</template>')
    expect(fonte).toMatch(/v-if="!ehGrupo"\s*\n\s*class="botao botao--pequeno"/)
  })
})
