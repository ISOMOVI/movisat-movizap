"""As quatro caixas pelo modelo do Gmail -- 22/10, terceira volta.

🔵 Dois pedidos dele, no mesmo passo:

  1. *"siga com a 2"* -- a Entrada (e o selo) passam a exigir o rotulo `INBOX`.
     Sem isso o selo contava uma mensagem **arquivada no Gmail**: o "Alerta de
     seguranca" do Google, nao lida desde 22/04, sem `INBOX` desde a
     importacao. O selo dizia 1 onde o Gmail diz 0.
  2. *"enviadas devem ter seu proprio grupo, igual no Gmail"* -- `SENT` virou
     CAIXA, nao marcador.

🚨 A DUPLICACAO QUE ISSO MATA. "Entrada" aparecia em DOIS controles: as abas de
caixa (Entrada/Arquivadas/Lixeira) e a lista de marcadores (Entrada/Enviados/
Com estrela/...). Dois lugares para dizer "onde estou", e a tela mandava os
dois juntos: `caixa=lixeira&marcador=INBOX`. Era isso que deixava **11
enviadas na lixeira invisiveis** -- a Lixeira filtrava pelo rotulo da Entrada.

Agora, como no Gmail: **caixa e lugar, marcador e etiqueta.** `INBOX` e `SENT`
saem da lista de marcadores porque viraram lugar.

🚨 TODA MENSAGEM CAI EM EXATAMENTE UMA CAIXA, e a ordem abaixo e o que garante
isso -- medido na caixa real: **1** mensagem tem `INBOX` e `SENT` ao mesmo
tempo (a Entrada ganha dela) e **1** nao tem nenhum dos dois (vai para
Arquivadas, senao desaparecia -- o mesmo defeito das 73 sumidas, que custou a
volta anterior).

⚠️ A nossa coluna `arquivada` CONTINUA valendo, e tem precedencia: arquivar
pelo painel chama o Gmail para tirar o `INBOX` la, mas **nao atualiza o
marcador local** (so o `UNREAD` e apagado localmente, em `marcar_lida`). Sem a
coluna no filtro, a mensagem arquivada pelo painel voltaria para a Entrada.
"""
import shutil
import sys

ALVO = "movizap/main.py"

ANTES = '''FILTRO_ENTRADA = ("NOT e.arquivada AND e.na_lixeira_desde IS NULL "
                  "AND e.sumida_do_gmail_em IS NULL")
FILTRO_ARQUIVADAS = ("e.arquivada AND e.na_lixeira_desde IS NULL "
                     "AND e.sumida_do_gmail_em IS NULL")
FILTRO_LIXEIRA = ("(e.na_lixeira_desde IS NOT NULL "
                  "OR e.sumida_do_gmail_em IS NOT NULL)")


def filtro_da_caixa(caixa: str) -> str:
    """O `WHERE` da aba pedida. Aba desconhecida cai na entrada, como antes."""
    if caixa == "lixeira":
        return FILTRO_LIXEIRA
    if caixa == "arquivadas":
        return FILTRO_ARQUIVADAS
    return FILTRO_ENTRADA'''

DEPOIS = '''def _tem_rotulo(id_externo: str) -> str:
    """Trecho que diz "esta mensagem carrega este rótulo do Gmail".

    🚨 O rótulo é a VERDADE DO GMAIL; as colunas `arquivada`,
    `na_lixeira_desde` e `sumida_do_gmail_em` são a nossa. Onde as duas
    discordam, quem manda sobre "em que lugar isto está" é o Gmail -- foi
    discordância assim que fez o selo contar uma mensagem que o Gmail já tinha
    arquivado (22/10).

    ⚠️ LIMITE MEDIDO, e ele importa: os rótulos são gravados **uma vez, na
    importação, e nunca mais atualizados** -- há um único `INSERT` (no caminho
    de importação de `gmail.ler`) e um único `DELETE` (do `UNREAD`, em
    `marcar_lida`). A varredura de 15 min compara só **ids**, não rótulos.
    Então `INBOX` aqui é a foto do dia em que a mensagem entrou: arquivar no
    Gmail DEPOIS disso não chega até nós. Ressincronizar rótulos é frente
    própria -- está anotada, e é mais caro (listar é barato, baixar é caro).
    """
    return ("EXISTS (SELECT 1 FROM email_mensagem_marcador mm "
            "          JOIN email_marcador mk ON mk.id = mm.marcador_id "
            "         WHERE mm.mensagem_id = e.id "
            f"          AND mk.id_externo = '{id_externo}')")


# Nem na lixeira, nem apagada de vez: a mensagem ainda é de alguma caixa.
_VIVA = "e.na_lixeira_desde IS NULL AND e.sumida_do_gmail_em IS NULL"

# 🚨 A ORDEM DESTAS QUATRO É O QUE GARANTE "EXATAMENTE UMA CAIXA".
#
#   arquivada pelo painel ....... Arquivadas  (a nossa coluna tem precedência)
#   tem INBOX ................... Entrada
#   tem SENT e não tem INBOX .... Enviados
#   não tem nenhum dos dois ..... Arquivadas  (= arquivada no Gmail)
#   na lixeira ou sumida ........ Lixeira     (ganha de todas)
#
# Medido na caixa real em 22/10: 1 mensagem tem INBOX **e** SENT (a Entrada
# ganha dela, e por isso Enviados exige `NOT tem(INBOX)`), e 1 não tem nenhum
# dos dois -- é o "Alerta de segurança" do Google, arquivado no Gmail. Sem a
# última linha da tabela ela cairia em caixa NENHUMA, que é exatamente o
# defeito das 73 sumidas da volta anterior.
FILTRO_ENTRADA = (f"NOT e.arquivada AND {_VIVA} AND {_tem_rotulo('INBOX')}")
FILTRO_ENVIADOS = (f"NOT e.arquivada AND {_VIVA} "
                   f"AND {_tem_rotulo('SENT')} AND NOT {_tem_rotulo('INBOX')}")
FILTRO_ARQUIVADAS = (
    f"{_VIVA} AND (e.arquivada OR "
    f"(NOT {_tem_rotulo('INBOX')} AND NOT {_tem_rotulo('SENT')}))")
FILTRO_LIXEIRA = ("(e.na_lixeira_desde IS NOT NULL "
                  "OR e.sumida_do_gmail_em IS NOT NULL)")

# As quatro, na ordem em que a tela as desenha.
CAIXAS = ("entrada", "enviados", "arquivadas", "lixeira")


def filtro_da_caixa(caixa: str) -> str:
    """O `WHERE` da caixa pedida. Caixa desconhecida cai na entrada."""
    if caixa == "lixeira":
        return FILTRO_LIXEIRA
    if caixa == "arquivadas":
        return FILTRO_ARQUIVADAS
    if caixa == "enviados":
        return FILTRO_ENVIADOS
    return FILTRO_ENTRADA'''


def main() -> int:
    texto = open(ALVO, encoding="utf-8").read()
    if "FILTRO_ENVIADOS" in texto:
        raise SystemExit("ja aplicado")
    if texto.count(ANTES) != 1:
        raise SystemExit(f"ancora com {texto.count(ANTES)} ocorrencias, esperava 1")
    texto = texto.replace(ANTES, DEPOIS, 1)

    # A docstring da rota da lista promete tres abas; agora sao quatro.
    doc_antes = '"""A lista da caixa, com três abas -- `caixa=entrada|arquivadas|lixeira`.'
    doc_depois = ('"""A lista da caixa, com quatro abas -- '
                  '`caixa=entrada|enviados|arquivadas|lixeira`.')
    if texto.count(doc_antes) != 1:
        raise SystemExit("nao achei a docstring da rota da lista")
    texto = texto.replace(doc_antes, doc_depois, 1)

    shutil.copyfile(ALVO, ALVO + ".bak_2026-10-22_caixas")
    open(ALVO, "w", encoding="utf-8").write(texto)
    print("ok  movizap/main.py (com .bak_2026-10-22_caixas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
