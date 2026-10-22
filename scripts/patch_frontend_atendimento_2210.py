"""Fase 2: o frontend, e o rotulo dos atalhos que e backend.

🚨 A VARREDURA DA FASE 0 (M13: le a TELA, nao o seletor) achou SEIS lugares
que dizem "Caixa de entrada" para o operador, e nao um. Renomear so o menu
deixaria as outras cinco mentindo -- `M12`. Sao estes, e todos entram aqui:

  1. movizap/preferencia.py  -- 5 atalhos com `"tela": "Caixa de entrada"`.
     🚨 E BACKEND, e eu ia deixar passar na Fase 1. O catalogo e servido por
     `/api/eu/atalhos` e aparece na CFG_6.1. A CHAVE e `acao`, nao `tela`:
     renomear o rotulo nao mexe em preferencia gravada de ninguem.
  2. frontend/src/router/index.js   -- meta.titulo da ATD_1.1
  3. frontend/src/telas/CaixaDeEntrada.vue -- o <h1> da propria tela
  4. frontend/src/componentes/BarraCelular.vue -- o rotulo no celular
  5. frontend/src/telas/ChatInterno.vue -- a frase "use a Caixa de entrada"
  6. docs/06_Conteudo_das_Telas.md -- a tabela de atalhos (nao o diario)

⚠️ O QUE NAO MUDA, de proposito: `frontend/src/telas/Email.vue` chama de
"Caixa de entrada" a pasta INBOX do Gmail. E outro significado, dentro da
tela de e-mail, e trocar ali seria introduzir o erro em vez de tirar.
Tambem ficam os comentarios que narram a historia ("a Caixa de entrada usa a
mesma regua desde 23/09"): diario nao se reescreve.
"""
import re
import shutil
import sys

# (arquivo, antes, depois, ocorrencias)
TROCAS = [
    # ---- 1. backend: o catalogo de atalhos ----
    ("movizap/preferencia.py",
     '"tela": "Caixa de entrada"', '"tela": "WhatsApp"', 5),
    # ---- 2. a rota ----
    ("frontend/src/router/index.js",
     "meta: { codigo: 'ATD_1.1', titulo: 'Caixa de entrada', cheio: true },",
     "meta: { codigo: 'ATD_1.1', titulo: 'WhatsApp', cheio: true },", 1),
    # ---- 3. o titulo da tela ----
    ("frontend/src/telas/CaixaDeEntrada.vue",
     "<h1>Caixa de entrada</h1>", "<h1>WhatsApp</h1>", 1),
    # ---- 4. o celular ----
    ("frontend/src/componentes/BarraCelular.vue",
     "      Caixa de entrada\n", "      WhatsApp\n", 1),
    # ---- 5. a frase do Chat interno ----
    ("frontend/src/telas/ChatInterno.vue",
     "Nada aqui chega ao cliente — para falar com ele, use a Caixa de entrada.",
     "Nada aqui chega ao cliente — para falar com ele, use o WhatsApp.", 1),
    # ---- 6. a tabela de atalhos do doc (nao o diario) ----
    ("docs/06_Conteudo_das_Telas.md",
     "| Caixa de entrada | próxima conversa | `j` | não |",
     "| WhatsApp | próxima conversa | `j` | não |", 1),
    ("docs/06_Conteudo_das_Telas.md",
     "| Caixa de entrada | conversa anterior | `k` | não |",
     "| WhatsApp | conversa anterior | `k` | não |", 1),
    ("docs/06_Conteudo_das_Telas.md",
     "| Caixa de entrada | ir para a busca | `/` | não |",
     "| WhatsApp | ir para a busca | `/` | não |", 1),
    ("docs/06_Conteudo_das_Telas.md",
     "| Caixa de entrada | **assumir a conversa** | `a` | 🔴 **sim** |",
     "| WhatsApp | **assumir a conversa** | `a` | 🔴 **sim** |", 1),
    ("docs/06_Conteudo_das_Telas.md",
     "| Caixa de entrada | abrir o concluir | `c` | não — abre a janela |",
     "| WhatsApp | abrir o concluir | `c` | não — abre a janela |", 1),
    # ---- os testes JS que fingem o catalogo ----
    ("frontend/src/telas_novas.teste.js",
     "{ acao: 'proxima', tela: 'Caixa de entrada', padrao: 'j',",
     "{ acao: 'proxima', tela: 'WhatsApp', padrao: 'j',", 1),
    ("frontend/src/telas_novas.teste.js",
     "{ acao: 'assumir', tela: 'Caixa de entrada', padrao: 'a',",
     "{ acao: 'assumir', tela: 'WhatsApp', padrao: 'a',", 1),
    ("frontend/src/telas_novas.teste.js",
     "expect(w.text()).toContain('Caixa de entrada')",
     "expect(w.text()).toContain('WhatsApp')", 1),
    # ---- o teste de ordem do menu (vai cobrar: a ordem mudou de proposito) ----
    ("frontend/src/menu_grupos_2110.teste.js",
     "      .toEqual(['Caixa de entrada', 'Chat interno', 'Ligações'])",
     "      .toEqual(['WhatsApp', 'Chat interno', 'Ligações'])", 1),
]

# ---------------------------------------------------------------------------
# O MenuLateral: os tres selos e a soma no cabecalho fechado.
# ---------------------------------------------------------------------------

MENU = "frontend/src/componentes/MenuLateral.vue"

# A leitura: sai das duas chamadas proprias e passa a usar o estado que o
# Notificador (em toda tela, 8 s) ja preenche.
MENU_SCRIPT_ANTES = '''const naoLidas = ref(0)'''
MENU_SCRIPT_DEPOIS = '''const naoLidas = ref(0)

/* 🔵 22/10, pedido dele: o selo do Chat interno passa a ter irmãos -- o do
   WhatsApp (*"conforme notificações da aba 'Minhas'"*) e o do E-mail (não
   lidos), e o cabeçalho de "Atendimento" fechado mostra A SOMA DOS TRÊS.

   🚨 OS DOIS NOVOS NÃO ABREM UM TERCEIRO RITMO. O `Notificador.vue` está
   montado no `App.vue` e já pergunta `/api/eu/notificacoes` de 8 em 8 s em
   TODA tela; o número de "Minhas" e o de e-mail saem de lá, do estado
   reativo, sem uma requisição nova. Selo que pisca em dois relógios
   diferentes (8 s e 15 s) mostraria soma que não bate com as partes por
   alguns segundos, e "a bolinha não pode discordar da aba" é a regra desta
   casa desde 24/09.

   ⚠️ O do Chat interno continua tendo chamada própria porque `nao-lidas` e
   `mencoes` exigem a ATD_6.1 e trazem a conta de menção separada (a que muda
   a COR do selo) -- juntá-los a esta rota é uma limpeza de outro dia. */
const naoLidasWhatsapp = computed(() => notificacoes.abas?.minhas || 0)
const naoLidosEmail = computed(() => notificacoes.email_nao_lidos || 0)

/* A soma que o grupo fechado carrega. Os três, sempre -- inclusive quando um
   deles é zero: é a mesma conta, só sem a parcela. */
const somaDoGrupo = computed(
  () => naoLidasWhatsapp.value + naoLidas.value + naoLidosEmail.value)

/* O selo de um item qualquer. Fora destes três códigos não há selo: devolver
   0 é o que faz o `v-if` do template não desenhar nada. */
function seloDaTela(codigo) {
  if (codigo === 'ATD_1.1') return naoLidasWhatsapp.value
  if (codigo === 'ATD_6.1') return naoLidas.value
  if (codigo === 'EML_1.1') return naoLidosEmail.value
  return 0
}

function textoDoSelo(codigo) {
  if (codigo === 'ATD_1.1') {
    return `${naoLidasWhatsapp.value} conversa(s) sua(s) com mensagem não lida`
  }
  if (codigo === 'EML_1.1') {
    return `${naoLidosEmail.value} e-mail(s) não lido(s) na entrada`
  }
  return mencoes.value > 0
    ? `${mencoes.value} vez(es) em que te chamaram pelo nome, de ${naoLidas.value} não lida(s)`
    : `${naoLidas.value} mensagem(ns) nova(s) no chat interno`
}

/* 🚨 QUANTOS SÃO SÓ 99+ NO DESENHO. O número real vai no `title`, porque
   "99+" no cabeçalho fechado é a única informação que a pessoa tem. */
function curto(n) {
  return n > 99 ? '99+' : String(n)
}'''

# O import do estado das notificacoes.
MENU_IMPORT_ANTES = "import { sessao, sair } from '../estado/sessao.js'"
MENU_IMPORT_DEPOIS = ("import { sessao, sair } from '../estado/sessao.js'\n"
                      "import { notificacoes } from '../estado/notificacoes.js'")

# O cabecalho do grupo fechado: de "tem chat interno" para "soma dos tres".
GRUPO_ANTES = '''function temChatInterno(grupo) {
  return grupo.subgrupos.some((s) => s.telas.some((t) => t.codigo === 'ATD_6.1'))
}'''
GRUPO_DEPOIS = '''/* 🔵 22/10: era só o Chat interno; passou a ser qualquer um dos três que
   têm selo. O grupo fechado some com o item E com o aviso dele, e o aviso é
   justamente para quem não está olhando -- valia para o chat em 21/10 e vale
   igual para o WhatsApp e para o e-mail agora. */
const CODIGOS_COM_SELO = ['ATD_1.1', 'ATD_6.1', 'EML_1.1']

function temSelo(grupo) {
  return grupo.subgrupos.some(
    (s) => s.telas.some((t) => CODIGOS_COM_SELO.includes(t.codigo)))
}'''

# O selo no cabecalho fechado.
CAB_ANTES = '''          <span
            v-if="!mostrarItens(grupo.nome) && temChatInterno(grupo) && naoLidas > 0"
            class="menu__selo menu__selo--grupo"
            :class="{ 'menu__selo--mencao': mencoes > 0 }"
            :title="`${naoLidas} mensagem(ns) nova(s) no chat interno, dentro deste grupo fechado`"
          >{{ naoLidas > 99 ? '99+' : naoLidas }}</span>'''
CAB_DEPOIS = '''          <span
            v-if="!mostrarItens(grupo.nome) && temSelo(grupo) && somaDoGrupo > 0"
            class="menu__selo menu__selo--grupo"
            :class="{ 'menu__selo--mencao': mencoes > 0 }"
            :title="`${somaDoGrupo} não lida(s) neste grupo fechado: `
              + `${naoLidasWhatsapp} no WhatsApp, ${naoLidas} no chat interno, `
              + `${naoLidosEmail} no e-mail`"
          >{{ curto(somaDoGrupo) }}</span>'''

# O selo de cada item: de "so o ATD_6.1" para os tres.
ITEM_ANTES = '''              <span
                v-if="tela.codigo === 'ATD_6.1' && naoLidas > 0"
                class="menu__selo"
                :class="{ 'menu__selo--mencao': mencoes > 0 }"
                :title="mencoes > 0
                  ? `${mencoes} vez(es) em que te chamaram pelo nome, de ${naoLidas} não lida(s)`
                  : `${naoLidas} mensagem(ns) nova(s) no chat interno`"
              >{{ naoLidas > 99 ? '99+' : naoLidas }}</span>'''
ITEM_DEPOIS = '''              <span
                v-if="seloDaTela(tela.codigo) > 0"
                class="menu__selo"
                :class="{
                  'menu__selo--mencao': tela.codigo === 'ATD_6.1' && mencoes > 0,
                }"
                :title="textoDoSelo(tela.codigo)"
              >{{ curto(seloDaTela(tela.codigo)) }}</span>'''


def aplicar(caminho, antes, depois, esperadas, rotulo=""):
    texto = open(caminho, encoding="utf-8").read()
    achadas = texto.count(antes)
    if achadas != esperadas:
        return (f"FALHOU {caminho} {rotulo}: {achadas} ocorrencia(s), "
                f"esperava {esperadas} -- {antes[:70]!r}")
    bak = caminho + ".bak_2026-10-22_atendimento"
    try:
        open(bak, "x", encoding="utf-8").write(texto)
    except FileExistsError:
        pass
    open(caminho, "w", encoding="utf-8").write(
        texto.replace(antes, depois, esperadas))
    return f"ok  {caminho} {rotulo}"


def main() -> int:
    erros = []
    for caminho, antes, depois, n in TROCAS:
        r = aplicar(caminho, antes, depois, n)
        print(r)
        if r.startswith("FALHOU"):
            erros.append(r)

    for antes, depois, rotulo in (
        (MENU_IMPORT_ANTES, MENU_IMPORT_DEPOIS, "(import do estado)"),
        (MENU_SCRIPT_ANTES, MENU_SCRIPT_DEPOIS, "(os tres selos e a soma)"),
        (GRUPO_ANTES, GRUPO_DEPOIS, "(temChatInterno -> temSelo)"),
        (CAB_ANTES, CAB_DEPOIS, "(selo do grupo fechado)"),
        (ITEM_ANTES, ITEM_DEPOIS, "(selo de cada item)"),
    ):
        r = aplicar(MENU, antes, depois, 1, rotulo)
        print(r)
        if r.startswith("FALHOU"):
            erros.append(r)

    # 🚨 `temChatInterno` nao pode sobrar em lugar nenhum: funcao fantasma no
    # template da erro silencioso no Vue (render falha, o menu nao desenha).
    resto = open(MENU, encoding="utf-8").read()
    if "temChatInterno" in resto:
        erros.append("FALHOU: sobrou `temChatInterno` no MenuLateral.vue")
        print(erros[-1])

    if erros:
        print(f"\n--- {len(erros)} falha(s): NAO aplicado por inteiro ---")
        return 1
    print("\ntudo aplicado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
