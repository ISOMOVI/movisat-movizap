"""Acrescenta ao `docs/02` o que faltava na definicao das duas flags.

A tabela de 17/09 descreve corretamente o que cada coluna SIGNIFICA, e nao
ficou defasada. O que ela nao dizia -- e o que custou o defeito de 22/10 -- e
**em qual aba cada estado aparece**. Quem leu a tabela ficou sabendo o que
`sumida_do_gmail_em` quer dizer, e nao que ela precisa entrar no filtro.
"""
import shutil
import sys

ALVO = "docs/02_Modelo_Dados.md"

ANTES = """🚨 **NUNCA PERDEMOS O CONTEÚDO**, e é a diferença para o caso análogo do
WhatsApp (045): texto, HTML e anexos já foram baixados na importação."""

DEPOIS = """### 🚨 Em qual aba cada estado aparece — e o filtro que decide isso (22/10)

A tabela acima diz o que cada coluna **significa**. Faltava o que custou um
defeito em 22/10: **em qual aba cada estado cai.** São três estados e três
abas, e o filtro tem de conhecer os três.

| estado | `na_lixeira_desde` | `sumida_do_gmail_em` | aba |
|---|---|---|---|
| ativa no Gmail | NULL | NULL | **Entrada** (ou Arquivadas, se `arquivada`) |
| na lixeira / spam | preenchido | NULL | **Lixeira** |
| sumiu da lixeira | preenchido | preenchido | **Lixeira** |
| **sumiu sem passar pela lixeira** | **NULL** | preenchido | **Lixeira** (🔵 decisão dele, 22/10) |

🚨 **A ÚLTIMA LINHA É A QUE ENGANA, e enganou.** "Sumida" **não** é "na
lixeira": a mensagem pode ir de ativa a inexistente **entre duas varreduras**
(apagada de vez, ou purgada pelos 30 dias do Gmail) e nunca ser vista na
lixeira. Até 22/10 a aba Entrada só excluía `na_lixeira_desde` e a aba Lixeira
só olhava essa mesma flag — então **73 mensagens que já não existiam no Gmail
ficaram presas na Entrada**, e o selo do menu contava 56 delas como não lidas
(dizia 61 onde a verdade eram 5).

🚨 **O FILTRO MORA NUM LUGAR SÓ**, em `movizap/main.py`: `FILTRO_ENTRADA`,
`FILTRO_ARQUIVADAS`, `FILTRO_LIXEIRA` e `filtro_da_caixa()`. Ele estava
**copiado à mão** na rota da lista e no contador do selo, e foi a cópia que
divergiu. Quem precisar do filtro **lê a constante** — há teste que reprova
quem escrever as condições de novo (`tests/teste_filtro_sumida.py`,
`TestOFiltroEUmSo`).

⚠️ **E a mensagem sumida não aceita escrita no Gmail:** `messages/{id}/modify`
devolve 404. A tela esconde "marcar não lida", "Arquivar", "Excluir" e
"Restaurar" para ela, e deixa só "Responder" (que compõe mensagem nova e não
toca na original) — ver `semEscritaNoGmail` no `Email.vue`.

🚨 **NUNCA PERDEMOS O CONTEÚDO**, e é a diferença para o caso análogo do
WhatsApp (045): texto, HTML e anexos já foram baixados na importação."""


def main() -> int:
    texto = open(ALVO, encoding="utf-8").read()
    if "Em qual aba cada estado aparece" in texto:
        raise SystemExit("ja aplicado")
    if texto.count(ANTES) != 1:
        raise SystemExit(f"ancora com {texto.count(ANTES)} ocorrencias, esperava 1")
    shutil.copyfile(ALVO, ALVO + ".bak_2026-10-22_sumida")
    open(ALVO, "w", encoding="utf-8").write(texto.replace(ANTES, DEPOIS, 1))
    print(f"ok  {ALVO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
