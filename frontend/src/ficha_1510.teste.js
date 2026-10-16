/**
 * @vitest-environment node
 *
 * Blocos 5, 6, 7 e 8 — Ligações na ficha, Outros contatos, rascunho por
 * conversa e a sessão do dia (15/10).
 *
 * 🚨 É GUARDA DE TEXTO, NÃO DE COMPORTAMENTO. `jsdom` não faz layout e estes
 * testes não clicam em nada: eles impedem a VOLTA de decisões que custaram
 * caro, e não provam que a tela funciona. Quem prova é abrir a tela.
 *
 * O que cada bloco guarda, e por quê:
 *   · o modal da ficha pede 7 dias e DIZ A COBERTURA -- sem a frase, "nenhuma
 *     ligação" e "aquele PC não tem agente" ficam iguais na tela;
 *   · o salto para a aba só existe para quem tem a aba (senão é um 403);
 *   · o rascunho é guardado ANTES de a conversa trocar -- depois disso não há
 *     mais de quem ele é;
 *   · o rascunho morre nos três pontos de envio e com a sessão;
 *   · quem perde a sessão vai para o Login E lê por quê.
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

function ler(rel) {
  return readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8')
}

const caixa = ler('./telas/CaixaDeEntrada.vue')
const sessao = ler('./estado/sessao.js')
const barra = ler('./componentes/BarraStatus.vue')
const login = ler('./telas/Login.vue')
const app = ler('./App.vue')

describe('Bloco 5 — Ligações na ficha', () => {
  it('o botão Ligações existe na gaveta', () => {
    expect(caixa).toContain('@click="verLigacoes"')
    expect(caixa).toContain('Ligações')
  })

  it('o modal pede exatamente 7 dias', () => {
    expect(caixa).toContain('/ligacoes?dias=7')
  })

  it('separa por sentido com os TRÊS valores do banco', () => {
    /* São os três do CHECK da migração 059. Inventar um quarto rótulo aqui
       faria a tela mostrar um grupo que nunca tem linha. */
    expect(caixa).toContain("['feita', 'Feitas'")
    expect(caixa).toContain("['recebida', 'Recebidas'")
    expect(caixa).toContain("['perdida', 'Perdidas'")
  })

  it('diz a COBERTURA dentro do modal', () => {
    expect(caixa).toContain('Só aparecem ligações de ramais com o agente instalado')
    expect(caixa).toContain('ligacoesDados.cobertura.com_agente')
  })

  it('o salto para a aba só aparece para quem tem a aba', () => {
    expect(caixa).toContain("codigosPermitidos.value.has('LIG_1.1')")
    expect(caixa).toMatch(/v-if="vejoAbaLigacoes"[\s\S]{0,200}Ver todas na aba Ligações/)
  })

  it('e leva o número já filtrado, com 30 dias', () => {
    expect(caixa).toContain("router.push({ path: '/ligacoes', query: { numero, dias: 30 } })")
  })

  it('o player solta o blob ao trocar e ao sair', () => {
    /* Um áudio por vez, e o object URL revogado: sem isto cada clique deixa
       um blob de megabytes preso na aba. */
    expect(caixa).toContain('function soltarPlayerLigacao()')
    expect(caixa).toContain('URL.revokeObjectURL(tocandoLigacao.value.url)')
    expect(caixa).toMatch(/onUnmounted\([\s\S]{0,400}soltarPlayerLigacao\(\)/)
  })
})

describe('Bloco 6 — Outros contatos da empresa', () => {
  it('usa a rota irmã sob ATD_1.2, não a de cadastro', () => {
    expect(caixa).toContain('/contatos-da-empresa')
    /* 🚨 `/api/clientes/{id}` é CAD_1.1 e daria 403 para quem atende: é o
       motivo de a rota irmã existir. */
    expect(caixa).not.toContain('/api/clientes/${aberta.value.empresa')
  })

  it('o vazio DIZ POR QUÊ, e os casos não se confundem', () => {
    expect(caixa).toContain("outros.motivo === 'sem_cadastro'")
    expect(caixa).toContain("outros.motivo === 'contato_sem_empresa'")
    expect(caixa).toContain('Esta empresa tem só este contato cadastrado.')
  })

  it('o botão Mensagem não aparece para quem foi conferido e não tem WhatsApp', () => {
    /* ⚠️ `!== false` e não `=== true`: `null` é "nunca conferido", e recusar
       por falta de conferência seria inventar o `false`. */
    expect(caixa).toContain("l.tem_whatsapp !== false")
    expect(caixa).not.toContain('l.tem_whatsapp === true')
  })

  it('pular para outra conversa reusa a receita que já existe', () => {
    /* busca → carregar → 1 acerto abre, 0 acerto abre "Nova mensagem". Não há
       rota que só localize ou crie conversa sem enviar. */
    const f = caixa.slice(caixa.indexOf('async function conversarCom('))
      .slice(0, 600)
    expect(f).toContain('busca.value = linha.e164')
    expect(f).toContain('await carregar()')
    expect(f).toContain('abrirNova()')
  })

  it('o botão Contatos só existe havendo empresa', () => {
    /* Sem empresa o modal só teria "este número não está no cadastro", que a
       própria ficha já diz em âmbar -- botão que só sabe dar a notícia ruim. */
    expect(caixa).toMatch(
      /v-if="aberta\.empresa && aberta\.empresa\.cliente && !ehTecnico"/)
  })
})

describe('desenho A da ficha — o que ele escolheu em 15/10', () => {
  /* 🔵 *"essa tela dentro da ficha esta redundante e um pouco feia"* →
     três mockups → *"Tipo A 100%"*. */

  it('o telefone do contato NÃO é mostrado de novo na lista de dados', () => {
    /* 🚨 ERA O DEFEITO QUE ELE VIU: `+5518998116168` no topo, em "Contato"
       (o nome derivado) e na linha de telefones que eu acrescentei no Bloco 6
       -- o mesmo número três vezes na mesma tela. Duas dessas três eram
       minhas, do mesmo dia. */
    expect(caixa).not.toContain('gaveta__fones')
    expect(caixa).not.toContain('aberta.empresa.contato.telefones')
  })

  it('nome derivado do telefone vira "sem nome no cadastro"', () => {
    /* Ausência de dado com cara de dado é tela que mente. */
    expect(caixa).toContain('const contatoSemNome = computed')
    expect(caixa).toContain('sem nome no cadastro')
    expect(caixa).toContain('v-else-if="contatoSemNome"')
  })

  it('e a comparação exige 10 dígitos, para não confundir nome com número', () => {
    expect(caixa).toContain('digitos.length >= 10')
  })

  it('as três consultas dividem UMA linha', () => {
    /* A gaveta é `flex-direction: column`: botão solto nela ganhava uma linha
       inteira, e eram três, numa gaveta com `max-height: 45%`. */
    expect(caixa).toContain('class="gaveta__acoes"')
    expect(caixa).toContain('.gaveta__acoes .botao { flex: 1 1 auto;')
  })

  it('a empresa é um cartão com hierarquia, e não quatro pares iguais', () => {
    expect(caixa).toContain('class="gaveta__cartao"')
    expect(caixa).toContain('class="gaveta__razao"')
    expect(caixa).toContain('class="gaveta__fantasia"')
    /* Os rótulos "Nome fantasia" e "CNPJ/CPF" saíram: o dado fala por si com
       o ícone ao lado. */
    expect(caixa).not.toContain('<dt>Nome fantasia</dt>')
    expect(caixa).not.toContain('<dt>CNPJ/CPF</dt>')
  })

  it('o e-mail quebra em vez de cortar com reticências', () => {
    /* E-mail cortado não dá para copiar, e copiar é o que se faz com ele. */
    expect(caixa).toContain('.gaveta__meta span > :last-child { overflow-wrap: anywhere;')
  })

  it('Desvincular saiu da pilha das consultas', () => {
    /* 🚨 Três botões de ler e um de APAGAR, todos iguais e na mesma pilha. */
    expect(caixa).toContain('class="gaveta__pe"')
    expect(caixa).toMatch(/gaveta__pe[\s\S]{0,600}@click="desvincular"/)
  })

  it('o Tipo continua na lista de dados, e não vira chip no topo', () => {
    /* ⚠️ DIVERGÊNCIA DECLARADA do mockup A: lá o Tipo era um chip no topo.
       Para quem tem `podeTrocarTipo` ele é um `<select>` -- um controle, não um
       rótulo --, e chip no topo mais select embaixo recriaria a duplicação que
       este desenho existe para matar. */
    expect(caixa).toContain('<dt>Tipo</dt>')
    expect(caixa).toContain('podeTrocarTipo')
  })
})

describe('Bloco 7 — rascunho por conversa', () => {
  it('guarda ANTES de trocar de conversa', () => {
    /* 🚨 A ORDEM É O RECURSO. Depois de `aberta.value` mudar, não há mais de
       quem o texto é -- e era exatamente assim que o texto de uma conversa
       aparecia na outra. */
    const abrir = caixa.slice(caixa.indexOf('async function abrir(id) {')).slice(0, 500)
    expect(abrir.indexOf('guardarRascunho()')).toBeGreaterThan(-1)
    expect(abrir.indexOf('guardarRascunho()')).toBeLessThan(abrir.indexOf('soltarMidias()'))
  })

  it('restaura o rascunho DAQUELA conversa ao abrir', () => {
    expect(caixa).toContain('resposta.value = lerRascunho(id)')
  })

  it('a chave segue o padrão do projeto e o acesso é protegido', () => {
    expect(caixa).toContain("const PREFIXO_RASCUNHO = 'movizap.rascunho.'")
    expect(caixa).toMatch(/try \{ localStorage\.setItem\(chaveRascunho\(id\), texto\) \} catch/)
  })

  it('morre nos TRÊS pontos de envio bem-sucedido', () => {
    const n = (caixa.match(/apagarRascunho\(\)/g) || []).length
    expect(n).toBeGreaterThanOrEqual(3)
  })

  it('o fechar da aba também guarda', () => {
    expect(caixa).toContain("window.addEventListener('beforeunload', guardarRascunho)")
    expect(caixa).toContain("window.removeEventListener('beforeunload', guardarRascunho)")
  })

  it('a lista marca quem tem rascunho, sem ler o storage por item', () => {
    /* Ler o `localStorage` dentro do `v-for` seria uma leitura por conversa em
       cada desenho da lista -- são centenas. */
    expect(caixa).toContain('comRascunho.has(c.id)')
    expect(caixa).toContain('function lerRascunhosGuardados()')
  })

  it('e morre junto com a sessão, que é o que ele decidiu', () => {
    expect(sessao).toContain("const PREFIXO_RASCUNHO = 'movizap.rascunho.'")
    expect(sessao).toMatch(/function limpar\(\)[\s\S]{0,300}apagarRascunhos\(\)/)
    /* Varrendo ao contrário: remover num laço crescente pula item, porque o
       índice do `localStorage` reindexa. */
    expect(sessao).toContain('for (let i = localStorage.length - 1; i >= 0; i--)')
  })
})

describe('Bloco 8 — um login por dia', () => {
  it('a hora do fim vem do backend, nos dois caminhos', () => {
    /* Nunca calculada no navegador: duas contas da mesma regra divergem. */
    expect(sessao).toContain('sessao.expiraEm = r.expira_em')
    expect(sessao).toContain('sessao.expiraEm = eu.sessao_expira_em')
  })

  it('a barra diz a hora, e não "quantas horas"', () => {
    expect(barra).toContain('sessão do dia · até {{ fimDoDia }}')
    expect(barra).toContain('const QUASE = 15 * 60 * 1000')
  })

  it('quem perde a sessão vai para o Login', () => {
    /* Era defeito existente: a sessão caía, a casca sumia e a tela de dentro
       continuava desenhada sem responder nada. */
    expect(app).toContain('watch(autenticado,')
    expect(app).toContain("roteador.push({ name: 'login'")
  })

  it('e lê por que voltou para lá', () => {
    expect(sessao).toContain('export const motivoDaSaida')
    expect(sessao).toContain('Sua sessão do dia terminou. Entre de novo.')
    expect(login).toContain('motivoDaSaida.value')
    /* A recusa do Google ganha a vez: ela é sobre a tentativa de agora. */
    expect(login).toContain('if (!erro.value && motivoDaSaida.value)')
  })

  it('sair por vontade própria não mostra explicação', () => {
    expect(sessao).toMatch(/export function sair\(\)[\s\S]{0,200}motivoDaSaida\.value = ''/)
  })
})
