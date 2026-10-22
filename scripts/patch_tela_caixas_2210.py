"""A tela: Enviados como caixa, e o fim da duplicacao "onde estou".

🔵 *"enviadas devem ter seu proprio grupo, igual no Gmail"*.

🚨 O QUE ESTAVA ERRADO NA NAVEGACAO, e nao era so a falta da aba. "Entrada"
existia em DOIS controles -- as abas de caixa e a lista de marcadores -- e a
tela mandava os dois ao servidor de uma vez (`caixa=lixeira&marcador=INBOX`,
visto no log). Consequencia medida: **11 enviadas na lixeira invisiveis**,
porque a Lixeira era filtrada pelo rotulo da Entrada.

Pelo modelo do Gmail, que e o que ele pediu: **caixa e LUGAR, marcador e
ETIQUETA.** `INBOX` e `SENT` saem da lista de marcadores porque viraram lugar;
sobram "Com estrela", "Importantes" e as etiquetas dele, que e o que etiqueta
deve ser.
"""
import shutil
import sys

ALVO = "frontend/src/telas/Email.vue"

# ---------------------------------------------------------------------------
# 1. `INBOX` e `SENT` saem da lista de marcadores -- viraram caixa.
# ---------------------------------------------------------------------------
ESCONDIDOS_ANTES = (
    "const ESCONDIDOS = ['SPAM', 'TRASH', 'CHAT', 'DRAFT', ...ESTRELAS_DO_GMAIL]")
ESCONDIDOS_DEPOIS = """/* 🚨 22/10: `INBOX` e `SENT` ENTRARAM NESTA LISTA porque viraram CAIXA, não
   etiqueta (*"enviadas devem ter seu proprio grupo, igual no Gmail"*). Antes
   "Entrada" aparecia em dois controles ao mesmo tempo, e a tela mandava os
   dois juntos -- era isso que escondia 11 enviadas dentro da Lixeira. */
const ESCONDIDOS = ['SPAM', 'TRASH', 'CHAT', 'DRAFT', 'INBOX', 'SENT',
                    ...ESTRELAS_DO_GMAIL]"""

# ---------------------------------------------------------------------------
# 2. O marcador deixa de comecar em INBOX: quem diz o lugar e a caixa.
# ---------------------------------------------------------------------------
PADRAO_ANTES = "const marcadorAtual = ref('INBOX')"
PADRAO_DEPOIS = """/* 🚨 VAZIO, não 'INBOX'. Quem diz em que LUGAR estou é `caixaAtual`; o
   marcador é etiqueta, e começar numa etiqueta filtrava a caixa toda por ela.
   Vazio = "sem filtro de etiqueta", e o backend pula o `EXISTS` quando vem
   assim. */
const marcadorAtual = ref('')"""

RESET_CONTA_ANTES = """  marcadas.value = []
  marcadorAtual.value = 'INBOX'
  await carregarMarcadores()"""
RESET_CONTA_DEPOIS = """  marcadas.value = []
  marcadorAtual.value = ''
  caixaAtual.value = 'entrada'
  await carregarMarcadores()"""

# 🚨 Trocar de caixa tem de SOLTAR a etiqueta -- era isto que escondia as 11.
ABA_ANTES = """function trocarAba(id) {
  caixaAtual.value = id
  aberta.value = null
  carregar()"""
ABA_DEPOIS = """function trocarAba(id) {
  caixaAtual.value = id
  aberta.value = null
  /* 🚨 SOLTAR A ETIQUETA AO TROCAR DE LUGAR. Sem esta linha, ir para a
     Lixeira mantinha `marcador=INBOX` e a Lixeira mostrava só o que tinha o
     rótulo da Entrada -- 11 mensagens enviadas ficavam invisíveis lá dentro
     (medido em 22/10). Etiqueta escolhida num lugar não segue para o outro. */
  marcadorAtual.value = ''
  marcadas.value = []
  carregar()"""

# Escolher etiqueta tambem limpa a selecao, pela mesma razao do `trocarAba`.
TROCAR_ANTES = """function trocar(id) {
  marcadorAtual.value = id
  aberta.value = null
  carregar()
}"""
TROCAR_DEPOIS = """function trocar(id) {
  marcadorAtual.value = id
  aberta.value = null
  marcadas.value = []
  carregar()
}"""

# ---------------------------------------------------------------------------
# 3. A aba Enviados, entre Entrada e Arquivadas -- a ordem do Gmail.
# ---------------------------------------------------------------------------
ABAS_ANTES = """    <!-- 🔵 17/09: Entrada, Arquivadas e Lixeira. As duas últimas não tinham
         tela nenhuma antes -- "arquivada" só tirava da vista, sem lugar
         para ver de novo, e exclusão no Gmail nem era detectada. -->
    <div class="caixas caixas--secundaria" role="tablist">
      <button v-for="ab in [
                { id: 'entrada', rotulo: 'Entrada', icone: 'bi-inbox' },
                { id: 'arquivadas', rotulo: 'Arquivadas', icone: 'bi-archive' },
                { id: 'lixeira', rotulo: 'Lixeira', icone: 'bi-trash' },
              ]\""""
ABAS_DEPOIS = """    <!-- 🔵 17/09: Entrada, Arquivadas e Lixeira. As duas últimas não tinham
         tela nenhuma antes -- "arquivada" só tirava da vista, sem lugar
         para ver de novo, e exclusão no Gmail nem era detectada.

         🔵 22/10: entrou **Enviados**, pedido dele (*"enviadas devem ter seu
         proprio grupo, igual no Gmail"*), na posição que o Gmail usa. Ela
         existia só como marcador, e por isso o único jeito de ver as
         enviadas era trocar de etiqueta -- com "Entrada" aparecendo nos dois
         controles ao mesmo tempo. -->
    <div class="caixas caixas--secundaria" role="tablist">
      <button v-for="ab in [
                { id: 'entrada', rotulo: 'Entrada', icone: 'bi-inbox' },
                { id: 'enviados', rotulo: 'Enviados', icone: 'bi-send' },
                { id: 'arquivadas', rotulo: 'Arquivadas', icone: 'bi-archive' },
                { id: 'lixeira', rotulo: 'Lixeira', icone: 'bi-trash' },
              ]\""""

# ---------------------------------------------------------------------------
# 4. A barra "onde estou" dizia a ETIQUETA; passa a dizer o LUGAR.
# ---------------------------------------------------------------------------
BARRA_ANTES = """        <strong>{{ NOMES[marcadorAtual] || marcadorAtual || 'Todas' }}</strong>"""
BARRA_DEPOIS = """        <!-- 🚨 ESTA LINHA DIZIA A ETIQUETA, NÃO O LUGAR, e com o marcador
             começando em 'INBOX' ela escrevia "Caixa de entrada" mesmo com a
             aba Lixeira aberta: `M12`, e ninguém tinha visto porque os dois
             controles concordavam por acidente. Agora diz o lugar, e a
             etiqueta só entra quando há uma escolhida. -->
        <strong>{{ ondeEstou }}</strong>"""

# O `computed` da barra, logo depois do `marcadorAtual`.
ONDE_ANTES = """const marcadorAtual = ref('')"""
ONDE_DEPOIS = """const marcadorAtual = ref('')

/* O nome do LUGAR onde estou, mais a etiqueta se houver uma escolhida. */
const NOMES_DE_CAIXA = {
  entrada: 'Entrada', enviados: 'Enviados',
  arquivadas: 'Arquivadas', lixeira: 'Lixeira',
}"""

COMPUTED_ONDE_ANTES = """function rotulo(m) {
  return NOMES[m.id_externo] || m.nome
}"""
COMPUTED_ONDE_DEPOIS = """function rotulo(m) {
  return NOMES[m.id_externo] || m.nome
}

const ondeEstou = computed(() => {
  const lugar = NOMES_DE_CAIXA[caixaAtual.value] || 'Entrada'
  const etiqueta = marcadorAtual.value
  if (!etiqueta) return lugar
  return `${lugar} › ${NOMES[etiqueta] || etiqueta}`
})"""


def main() -> int:
    texto = open(ALVO, encoding="utf-8").read()
    if "NOMES_DE_CAIXA" in texto:
        raise SystemExit("ja aplicado")

    passos = [
        (ESCONDIDOS_ANTES, ESCONDIDOS_DEPOIS, "1. INBOX e SENT saem dos marcadores"),
        (PADRAO_ANTES, PADRAO_DEPOIS, "2a. o marcador comeca vazio"),
        (ONDE_ANTES, ONDE_DEPOIS, "2b. os nomes das caixas"),
        (COMPUTED_ONDE_ANTES, COMPUTED_ONDE_DEPOIS, "2c. o computed `ondeEstou`"),
        (RESET_CONTA_ANTES, RESET_CONTA_DEPOIS, "2d. trocar de conta volta para a Entrada"),
        (ABA_ANTES, ABA_DEPOIS, "2e. trocar de caixa solta a etiqueta"),
        (TROCAR_ANTES, TROCAR_DEPOIS, "2f. trocar de etiqueta limpa a selecao"),
        (ABAS_ANTES, ABAS_DEPOIS, "3. a aba Enviados"),
        (BARRA_ANTES, BARRA_DEPOIS, "4. a barra diz o lugar"),
    ]
    for antes, depois, rotulo_passo in passos:
        n = texto.count(antes)
        if n != 1:
            raise SystemExit(f"FALHOU {rotulo_passo}: {n} ocorrencias, esperava 1")
        texto = texto.replace(antes, depois, 1)
        print(f"ok  {rotulo_passo}")

    shutil.copyfile(ALVO, ALVO + ".bak_2026-10-22_caixas")
    open(ALVO, "w", encoding="utf-8").write(texto)
    print("gravado (com .bak_2026-10-22_caixas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
