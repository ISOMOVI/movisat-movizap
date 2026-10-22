"""A tela: a marca na lista e as acoes que nao existem mais.

🔵 Decisao dele (opcao 1): a mensagem que sumiu do Gmail aparece na **Lixeira**,
marcada como "so a nossa copia". Duas consequencias na tela:

**1. A marca na LISTA.** O aviso de "Removida do Gmail" so existia dentro da
mensagem ABERTA. Com as sumidas agora na Lixeira junto das que ainda dao para
restaurar, e preciso distinguir ANTES de abrir -- senao a unica diferenca que
importa (da para recuperar no Gmail ou nao) exige um clique por mensagem.

**2. 🚨 AS ACOES QUE MENTEM, e fui EU que as tornei alcancaveis.** Para uma
mensagem que nao existe mais no Gmail, toda escrita devolve **404**: "marcar
nao lida", "Arquivar", "Excluir" e "Restaurar" sobem `GmailIndisponivel` e a
tela mostra 503. Pior: o botao **"Restaurar"** ficava LADO A LADO com o aviso
que diz *"Nao da para restaurar la"* -- `M12` na forma mais crua possivel.

Isso era latente antes de hoje (a sumida sem `na_lixeira_desde` ficava presa na
Entrada, onde o botao era "Excluir"). **Mover as sumidas para a Lixeira pos o
"Restaurar" na frente delas**, e consertar isso faz parte da mudanca, nao e
escopo novo: eu criei o alcance.

⚠️ "Responder" FICA. Responder compoe uma mensagem nova e nao toca na original
-- e a unica acao que continua fazendo sentido sobre uma copia orfa.
"""
import shutil
import sys

ALVO = "frontend/src/telas/Email.vue"

# ---- o computed, junto do resto do script ----
COMPUTED_ANTES = "const NOMES = {\n  INBOX: 'Caixa de entrada',"
COMPUTED_DEPOIS = """/* 🚨 22/10: a mensagem que sumiu do Gmail não aceita NENHUMA escrita lá --
   `modify` devolve 404 e o painel mostra 503. Antes de hoje ela ficava presa
   na aba Entrada; agora está na Lixeira, ao lado do botão "Restaurar", e esse
   botão ficava colado num aviso dizendo que restaurar não dá. Um `computed` só
   governa as quatro ações, para não haver quatro condições divergindo. */
const semEscritaNoGmail = computed(() => Boolean(aberta.value?.sumida_do_gmail_em))

const NOMES = {
  INBOX: 'Caixa de entrada',"""

# ---- 1. a marca na lista ----
LISTA_ANTES = """              <span v-if="m.cliente_nome" class="chip chip--pequeno email__cliente">
                {{ m.cliente_nome }}
              </span>"""
LISTA_DEPOIS = """              <span v-if="m.cliente_nome" class="chip chip--pequeno email__cliente">
                {{ m.cliente_nome }}
              </span>
              <!-- 🔵 22/10: na Lixeira convivem duas coisas diferentes -- a
                   que dá para restaurar no Gmail e a que já não existe lá.
                   Sem esta marca, descobrir qual é qual custa um clique por
                   mensagem, e o aviso só aparecia com ela aberta. -->
              <span v-if="m.sumida_do_gmail_em"
                    class="chip chip--pequeno email__orfa"
                    title="Removida do Gmail — esta é a única cópia que existe">
                só a nossa cópia
              </span>"""

# ---- 2. as quatro acoes ----
NAO_LIDA_ANTES = """                <button class="botao botao--pequeno botao--fantasma botao--icone"
                        type="button" title="Marcar como não lida (u)"
                        aria-label="Marcar como não lida"
                        @click="marcarNaoLida(aberta)">
                  <i class="bi bi-envelope" aria-hidden="true"></i>
                </button>"""
NAO_LIDA_DEPOIS = """                <button v-if="!semEscritaNoGmail"
                        class="botao botao--pequeno botao--fantasma botao--icone"
                        type="button" title="Marcar como não lida (u)"
                        aria-label="Marcar como não lida"
                        @click="marcarNaoLida(aberta)">
                  <i class="bi bi-envelope" aria-hidden="true"></i>
                </button>"""

ARQUIVAR_ANTES = """                <button v-if="!aberta.na_lixeira_desde"
                        class="botao botao--pequeno botao--fantasma"
                        type="button" title="Arquivar (e)"
                        @click="arquivarAberta">"""
ARQUIVAR_DEPOIS = """                <button v-if="!aberta.na_lixeira_desde && !semEscritaNoGmail"
                        class="botao botao--pequeno botao--fantasma"
                        type="button" title="Arquivar (e)"
                        @click="arquivarAberta">"""

EXCLUIR_ANTES = """                <button v-if="!aberta.na_lixeira_desde"
                        class="botao botao--pequeno botao--fantasma"
                        type="button" title="Excluir"
                        @click="excluirAberta">
                  <i class="bi bi-trash" aria-hidden="true"></i>
                  Excluir
                </button>
                <button v-else
                        class="botao botao--pequeno botao--contorno"
                        type="button" title="Restaurar para a Caixa"
                        @click="restaurarAberta">
                  <i class="bi bi-arrow-counterclockwise" aria-hidden="true"></i>
                  Restaurar
                </button>"""
EXCLUIR_DEPOIS = """                <button v-if="!aberta.na_lixeira_desde && !semEscritaNoGmail"
                        class="botao botao--pequeno botao--fantasma"
                        type="button" title="Excluir"
                        @click="excluirAberta">
                  <i class="bi bi-trash" aria-hidden="true"></i>
                  Excluir
                </button>
                <!-- 🚨 NADA DE "RESTAURAR" NUMA MENSAGEM QUE NÃO EXISTE MAIS.
                     Este botão ficava colado no aviso logo abaixo, que diz
                     exatamente que restaurar não dá -- e o Gmail devolve 404.
                     O aviso explica; o botão só prometia. -->
                <button v-else-if="!semEscritaNoGmail"
                        class="botao botao--pequeno botao--contorno"
                        type="button" title="Restaurar para a Caixa"
                        @click="restaurarAberta">
                  <i class="bi bi-arrow-counterclockwise" aria-hidden="true"></i>
                  Restaurar
                </button>"""

# ---- 3. o aviso, que agora e a unica explicacao e precisa dizer tudo ----
AVISO_ANTES = """              <p v-if="aberta.sumida_do_gmail_em" class="aviso aviso--erro pequeno">
                <i class="bi bi-exclamation-triangle" aria-hidden="true"></i>
                Removida do Gmail — esta é a cópia que já tínhamos. Não dá
                para restaurar lá.
              </p>"""
AVISO_DEPOIS = """              <!-- 🚨 ESTE AVISO FICOU SENDO A ÚNICA EXPLICAÇÃO, desde que os
                   botões que não funcionam saíram (22/10). Então ele diz o que
                   some e por quê -- botão que desaparece sem palavra é o
                   mesmo defeito do rótulo que mente, pelo avesso. -->
              <p v-if="aberta.sumida_do_gmail_em" class="aviso aviso--erro pequeno">
                <i class="bi bi-exclamation-triangle" aria-hidden="true"></i>
                Removida do Gmail — esta é a única cópia que existe. Não dá
                para restaurar, arquivar nem excluir lá; só responder.
              </p>"""

# ---- 4. o estilo do chip ----
# ⚠️ `.email__cliente {` aparece DUAS vezes (a segunda e a versao estreita).
# A ancora e a linha inteira da primeira, que e unica.
ESTILO_ANTES = (".email__cliente { flex: none; max-width: 130px; overflow: hidden;"
                " text-overflow: ellipsis; white-space: nowrap; }")
ESTILO_DEPOIS = """/* 🔵 22/10: a marca da mensagem órfã, na Lixeira. Mesma forma do chip do
   cliente, cor de aviso -- é informação de ESTADO, não de identidade, e o
   chip do cliente ao lado continua sendo quem a mensagem é. */
.email__orfa { flex: none; white-space: nowrap; background: var(--aviso-fundo, #fdecea); color: var(--aviso-texto, #a32018); }
.email__cliente { flex: none; max-width: 130px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }"""


def main() -> int:
    texto = open(ALVO, encoding="utf-8").read()
    if "semEscritaNoGmail" in texto:
        raise SystemExit("ja aplicado")

    passos = [
        (COMPUTED_ANTES, COMPUTED_DEPOIS, "o computed das acoes"),
        (LISTA_ANTES, LISTA_DEPOIS, "1. a marca na lista"),
        (NAO_LIDA_ANTES, NAO_LIDA_DEPOIS, "2a. marcar nao lida"),
        (ARQUIVAR_ANTES, ARQUIVAR_DEPOIS, "2b. arquivar"),
        (EXCLUIR_ANTES, EXCLUIR_DEPOIS, "2c. excluir e restaurar"),
        (AVISO_ANTES, AVISO_DEPOIS, "3. o aviso completo"),
        (ESTILO_ANTES, ESTILO_DEPOIS, "4. o estilo do chip"),
    ]
    for antes, depois, rotulo in passos:
        n = texto.count(antes)
        if n != 1:
            raise SystemExit(f"FALHOU {rotulo}: {n} ocorrencias, esperava 1")
        texto = texto.replace(antes, depois, 1)
        print(f"ok  {rotulo}")

    # 🚨 `computed` tem de estar importado, senao a tela quebra ao abrir.
    if "computed" not in texto.split("</script>")[0].split("from 'vue'")[0]:
        raise SystemExit("`computed` nao parece importado de 'vue' -- conferir a mao")

    shutil.copyfile(ALVO, ALVO + ".bak_2026-10-22_sumida")
    open(ALVO, "w", encoding="utf-8").write(texto)
    print("gravado (com .bak_2026-10-22_sumida)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
