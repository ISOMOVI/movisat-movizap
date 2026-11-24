# -*- coding: utf-8 -*-
"""Tarefa 2.4, lado MoviZap — ponte, rota e o gesto de excluir o card inteiro.

🔵 DELE: *"Excluir o card inteiro devolvendo tudo à coluna 1, com justificativa
única"*.

⚠️ Três camadas e as três andam juntas, porque campo novo não entra sozinho:
a função da ponte, a rota com a permissão da `PNL_1.6`, e o botão.
"""
import pathlib

ALVOS = {}


def abrir(rel):
    p = pathlib.Path(rel)
    bruto = p.read_bytes()
    ALVOS[rel] = {"p": p, "crlf": b"\r\n" in bruto,
                  "t": bruto.decode("utf-8").replace("\r\n", "\n")}
    return rel


def troca(rel, velho, novo, rotulo):
    d = ALVOS[rel]
    assert velho in d["t"], "NAO ACHOU (%s)" % rotulo
    assert d["t"].count(velho) == 1, "AMBIGUO %dx (%s)" % (
        d["t"].count(velho), rotulo)
    d["t"] = d["t"].replace(velho, novo, 1)
    print("  ok:", rotulo)


# ===========================================================================
# 1. A PONTE
# ===========================================================================
PN = abrir("movizap/fpsl_ponte.py")

troca(PN,
      '''def auditar_lote(lote_id: int, *, por: str | None = None) -> dict:''',
      '''def devolver_lote(lote_id: int, justificativa: str, *,
                  por: str | None = None) -> dict:
    """🔵 *"Excluir o card inteiro devolvendo tudo à coluna 1, com
    justificativa única"* -- tarefa 2.4.

    🚨 A MESMA justificativa vai em TODOS os itens, e é o lado do FPSL que
    aplica artefato por artefato, pela regra que já existia. Aqui só se
    transporta -- repartir a decisão em dois lugares faria as duas divergirem.
    """
    return _pagamento("/devolver-lote", {"lote_id": lote_id,
                                         "justificativa": justificativa,
                                         "por": por})


def auditar_lote(lote_id: int, *, por: str | None = None) -> dict:''',
      "1. a funcao da ponte")


# ===========================================================================
# 2. A ROTA, com a permissão da PNL_1.6
# ===========================================================================
MN = abrir("movizap/main.py")

troca(MN,
      '''class ComprovanteDoArtefato(BaseModel):''',
      '''class LoteDevolvido(BaseModel):
    lote_id: int = Field(..., ge=1)
    # ⚠️ Obrigatória, igual à de um item: a mesma frase vai em todos os itens,
    # e é ela que o card da coluna 1 mostra em laranja.
    justificativa: str = Field(..., min_length=1, max_length=400)


class ComprovanteDoArtefato(BaseModel):''',
      "2a. o corpo da requisicao")

troca(MN,
      '''@app.post("/api/paineis/servico-dos-tecnicos/auditar/{lote_id}")''',
      '''@app.post("/api/paineis/servico-dos-tecnicos/devolver-lote")
def devolver_lote_do_servico(
        dados: LoteDevolvido,
        usuario: dict = Depends(auth.requer_tela("PNL_1.6"))):
    """🔵 *"Excluir o card inteiro devolvendo tudo à coluna 1, com
    justificativa única"* -- tarefa 2.4.

    🚨 Vale de QUALQUER coluna, inclusive da 5: 🔵 *"veja que aqui não retorna
    para a anterior e sim para o 1"*. O lote sai do quadro sozinho, porque os
    cards vêm dos artefatos.
    """
    return fpsl_ponte.devolver_lote(dados.lote_id, dados.justificativa,
                                    por=usuario.get("nome"))


@app.post("/api/paineis/servico-dos-tecnicos/auditar/{lote_id}")''',
      "2b. a rota, com requer_tela PNL_1.6")


# ===========================================================================
# 3. O GESTO
# ===========================================================================
TL = abrir("frontend/src/telas/PainelServicoDosTecnicos.vue")

troca(TL,
      '''function pedirDevolucao(linha) {
  devolvendo.value = linha
  justificativa.value = ''
}''',
      '''function pedirDevolucao(linha) {
  devolvendo.value = linha
  justificativa.value = ''
}

/* 🔵 Tarefa 2.4: *"Excluir o card inteiro devolvendo tudo à coluna 1, com
   justificativa única"*.
   🚨 REUSA O MESMO DIÁLOGO da devolução de um item -- `devolvendoLote` só diz
   que o alvo é o lote. Um segundo diálogo com o mesmo texto divergiria do
   primeiro na primeira palavra que ele mudasse. */
const devolvendoLote = ref(null)

function pedirExclusaoDoCard(card) {
  devolvendoLote.value = card
  justificativa.value = ''
}

async function devolverLote() {
  const alvo = devolvendoLote.value
  if (!alvo) return
  const r = await chamar('/devolver-lote', {
    lote_id: alvo.lote_id, justificativa: justificativa.value,
  })
  if (r) {
    devolvendoLote.value = null
    /* ⚠️ Fecha o card aberto: ele acabou de ficar sem item nenhum, e deixá-lo
       aberto mostraria uma lista vazia sem dizer por quê. */
    fecharCardDoTecnico()
    aviso.value = r.ok
      ? `${r.devolvidos} item(ns) voltaram para a Movimentação.`
      : (r.motivo || 'nada foi devolvido')
    await carregar()
  }
}''',
      "3a. o gesto, reusando o dialogo")

troca(TL,
      '''                    <template v-if="colunaAberta === 'procfy'">''',
      '''                    <!-- 🔵 Tarefa 2.4: excluir o card inteiro. Vale de
                         qualquer coluna de lote (2 a 5) -- na coluna 1 o card
                         é o técnico, permanente, e não há lote para excluir.
                         🚨 Fica junto dos outros gestos do card, e não entre
                         os itens: o alvo aqui é o CARD. -->
                    <button v-if="colunaAberta !== 'movimentacao'"
                            class="botao botao--fraco" type="button"
                            @click="pedirExclusaoDoCard(cardAberto)">
                      Excluir o card
                    </button>

                    <template v-if="colunaAberta === 'procfy'">''',
      "3b. o botao Excluir o card")

troca(TL,
      '''    <!-- 🔵 19/11 — O COMPROVANTE: *"haverá campo para que em cada 1 dos''',
      '''    <!-- 🔵 Tarefa 2.4: a justificativa ÚNICA do card inteiro. -->
    <div v-if="devolvendoLote" class="modal" role="dialog" aria-modal="true">
      <div class="modal__caixa modal__caixa--curta">
        <h2>Excluir o card inteiro?</h2>
        <p class="nota pequeno">
          Todos os itens deste lote voltam para a Movimentação em laranja, com
          esta mesma justificativa à vista.
        </p>
        <!-- 🚨 O NÚMERO À VISTA: "todos os itens" sem dizer quantos deixaria a
             pessoa decidir no escuro. -->
        <p class="nota pequeno">
          <span class="selo selo--laranja">atenção</span>
          {{ (devolvendoLote.artefatos || []).length }} item(ns) ·
          {{ colunaAberta === 'enviado'
             ? 'o arquivo deste lote já foi marcado como enviado, e remover '
               + 'aqui não desfaz o envio — o acerto é no Procfy.'
             : (colunaAberta === 'procfy'
                ? 'o arquivo deste lote já foi montado; depois de excluir, '
                  + 'monte o arquivo de novo.'
                : 'o lote sai do quadro.') }}
        </p>
        <input v-model="justificativa" class="campo" maxlength="400"
               placeholder="ex.: lote montado com o técnico errado" />
        <div class="modal__acoes">
          <button class="botao botao--fraco" type="button"
                  @click="devolvendoLote = null">Cancelar</button>
          <button class="botao" type="button" :disabled="!justificativa.trim()"
                  @click="devolverLote">Excluir o card</button>
        </div>
      </div>
    </div>

    <!-- 🔵 19/11 — O COMPROVANTE: *"haverá campo para que em cada 1 dos''',
      "3c. o dialogo da justificativa unica")


for rel, d in ALVOS.items():
    saida = d["t"].replace("\n", "\r\n") if d["crlf"] else d["t"]
    d["p"].write_bytes(saida.encode("utf-8"))
    print("gravado:", rel, len(saida), "bytes")
