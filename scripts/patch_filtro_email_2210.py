"""O filtro das abas de e-mail: uma fonte so, e a mensagem sumida no lugar certo.

🚨 A CAUSA, MEDIDA EM 22/10. A varredura do Gmail (`sincronizar_lixeira`, de 15
em 15 min) grava TRES estados, e o filtro das abas so conhecia dois:

  - ativa no Gmail .............. limpa as duas flags
  - na lixeira/spam ............. `na_lixeira_desde`
  - NAO EXISTE MAIS no Gmail .... `sumida_do_gmail_em`

A aba "Entrada" excluia `na_lixeira_desde` e **nao excluia
`sumida_do_gmail_em`**: 73 mensagens que ja nao existem no Gmail apareciam como
se estivessem na caixa, 56 delas nao lidas. O selo do menu (22/10) copiou esse
mesmo `WHERE` de proposito -- "a bolinha nao pode discordar da aba" -- e herdou
o defeito: mostrava **61** onde a verdade sao **5**.

E havia um segundo buraco: a aba Lixeira filtra por `na_lixeira_desde IS NOT
NULL`, entao a mensagem que foi de ativa para inexistente ENTRE DUAS VARREDURAS
(apagada de vez no Gmail, ou purgada pelos 30 dias) nao caia nela. Ficava presa
na Entrada para sempre -- as 73.

🔵 Decisao dele (22/10), opcao 1: a sumida vai para a **Lixeira**, marcada como
"so a nossa copia". E o que o comentario do proprio `SELECT` ja dizia ser a
intencao desde 17/09, e preserva o acesso a uma copia que o Gmail nao tem mais.

🚨 A PARTE QUE IMPORTA MAIS QUE AS DUAS CORRECOES: o filtro existia COPIADO A
MAO em dois lugares, e foi isso que deixou o selo errar junto. Agora e UM
fragmento nomeado, usado pela lista e pelo contador. Um teste afirma que os
dois dao o mesmo numero -- e e esse teste, nao o cuidado de quem edita, que
impede a divergencia voltar.
"""
import shutil
import sys

ALVO = "movizap/main.py"

# ---------------------------------------------------------------------------
# C: o fragmento unico, logo antes de `_caixas_do_usuario`.
# ---------------------------------------------------------------------------

FRAGMENTO = '''# ---------------------------------------------------------------------------
# 🚨 O FILTRO DAS ABAS DE E-MAIL MORA AQUI, UMA VEZ SÓ.
#
# Até 22/10 ele estava copiado à mão: uma vez em `/api/email/mensagens` e,
# depois do selo do menu, outra em `_email_nao_lidos`. As duas cópias
# discordaram no mesmo dia em que a segunda nasceu -- o selo mostrava 61 onde
# a verdade eram 5, porque a cópia não conhecia `sumida_do_gmail_em`.
#
# A varredura do Gmail (`gmail.sincronizar_exclusoes`, cron de 15 min) grava
# TRÊS estados, e qualquer filtro de aba tem de conhecer os três:
#
#   ativa no Gmail .............. as duas flags em NULL
#   na lixeira ou no spam ....... `na_lixeira_desde`
#   não existe mais no Gmail .... `sumida_do_gmail_em`
#
# ⚠️ "Sumida" NÃO é "na lixeira", e foi essa confusão que custou o defeito:
# ela pode ir de ativa a inexistente ENTRE DUAS VARREDURAS (apagada de vez, ou
# purgada pelos 30 dias do Gmail) e nunca ser vista na lixeira. Por isso a
# Lixeira olha as DUAS flags: senão a mensagem não cai em aba nenhuma.
#
# 🔵 Decisão dele (22/10): a sumida aparece na Lixeira, marcada como "só a
# nossa cópia" -- é a única cópia que existe, e esconder seria perdê-la de
# vista.
FILTRO_ENTRADA = ("NOT e.arquivada AND e.na_lixeira_desde IS NULL "
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
    return FILTRO_ENTRADA


'''

ANCORA_FRAGMENTO = "def _caixas_do_usuario(usuario: dict) -> list[dict]:\n"

# ---------------------------------------------------------------------------
# A: a lista passa a usar o fragmento.
# ---------------------------------------------------------------------------

LISTA_ANTES = '''    if caixa == "lixeira":
        condicoes = ["e.na_lixeira_desde IS NOT NULL", "e.conta_id = ANY(%s)"]
    elif caixa == "arquivadas":
        condicoes = ["e.arquivada", "e.na_lixeira_desde IS NULL",
                     "e.conta_id = ANY(%s)"]
    else:
        condicoes = ["NOT e.arquivada", "e.na_lixeira_desde IS NULL",
                     "e.conta_id = ANY(%s)"]'''

LISTA_DEPOIS = '''    # 🚨 22/10: as três condições saíam escritas aqui, e a cópia feita em
    # `_email_nao_lidos` divergiu no mesmo dia. Agora vêm do `filtro_da_caixa`,
    # que é o único lugar onde elas existem -- ver o bloco acima dele.
    condicoes = [filtro_da_caixa(caixa), "e.conta_id = ANY(%s)"]'''

# ---------------------------------------------------------------------------
# B: o contador do selo usa o MESMO fragmento.
# ---------------------------------------------------------------------------

CONTADOR_ANTES = '''    linha = banco.um(
        """SELECT count(*) AS quantas
             FROM email_mensagem e
            WHERE e.conta_id IN (SELECT id FROM email_conta
                                  WHERE atendente_id = %s AND ativa)
              AND NOT e.lida
              AND NOT e.arquivada
              AND e.na_lixeira_desde IS NULL""", (eu,))
    return int(linha["quantas"] if linha else 0)'''

CONTADOR_DEPOIS = '''    linha = banco.um(
        f"""SELECT count(*) AS quantas
             FROM email_mensagem e
            WHERE e.conta_id IN (SELECT id FROM email_conta
                                  WHERE atendente_id = %s AND ativa)
              AND NOT e.lida
              AND {FILTRO_ENTRADA}""", (eu,))
    return int(linha["quantas"] if linha else 0)'''

# E a docstring do contador, que ficou incompleta: ela prometia "mesmo filtro
# da aba Entrada" sendo que a copia nao tinha a terceira condicao. Texto que
# promete o que o codigo nao faz e `M12`.
DOC_ANTES = '''    🚨 MESMO FILTRO DA ABA "ENTRADA" (`/api/email/mensagens`): fora o
    arquivado e fora a lixeira. Selo que conta arquivada mandaria a pessoa
    abrir a tela para procurar uma mensagem que a tela nao mostra -- e o
    `abas.minhas` existe desde 24/09 justamente com a regra de que a bolinha
    conta pela MESMA regua da lista.'''

DOC_DEPOIS = '''    🚨 MESMO FILTRO DA ABA "ENTRADA", E AGORA LITERALMENTE O MESMO: os dois
    leem `FILTRO_ENTRADA`, que existe num lugar só. Até 22/10 esta função
    tinha uma CÓPIA do `WHERE` da aba, e a cópia não conhecia
    `sumida_do_gmail_em` -- o selo mostrava 61 não lidas onde a verdade eram
    5, porque 56 delas já não existiam no Gmail. A docstring prometia "mesmo
    filtro" enquanto o código fazia outro: `M12` dentro do próprio comentário
    que eu escrevi.

    ⚠️ Selo que conta arquivada, lixeira ou sumida manda a pessoa abrir a tela
    para procurar uma mensagem que a tela não mostra. O `abas.minhas` existe
    desde 24/09 com essa regra: a bolinha conta pela MESMA régua da lista.'''


def main() -> int:
    texto = open(ALVO, encoding="utf-8").read()

    if "FILTRO_ENTRADA" in texto:
        raise SystemExit("ja aplicado")

    passos = [
        (ANCORA_FRAGMENTO, FRAGMENTO + ANCORA_FRAGMENTO, "C: o fragmento unico"),
        (LISTA_ANTES, LISTA_DEPOIS, "A: a lista usa o fragmento"),
        (CONTADOR_ANTES, CONTADOR_DEPOIS, "B: o contador usa o fragmento"),
        (DOC_ANTES, DOC_DEPOIS, "a docstring que prometia demais"),
    ]
    for antes, depois, rotulo in passos:
        if texto.count(antes) != 1:
            raise SystemExit(
                f"FALHOU {rotulo}: {texto.count(antes)} ocorrencias, esperava 1")
        texto = texto.replace(antes, depois, 1)
        print(f"ok  {rotulo}")

    shutil.copyfile(ALVO, ALVO + ".bak_2026-10-22_filtro_email")
    open(ALVO, "w", encoding="utf-8").write(texto)
    print("gravado (com .bak_2026-10-22_filtro_email)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
