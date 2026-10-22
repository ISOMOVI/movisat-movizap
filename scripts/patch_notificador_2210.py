"""O elo que faltava: quem ESCREVE o `email_nao_lidos` no estado.

🚨 BURACO MEU, E A SUITE VERDE NAO IA PEGAR. O `MenuLateral` passou a LER
`notificacoes.email_nao_lidos`, a rota passou a DEVOLVER o numero, e nada no
meio gravava: o `Notificador` copiava `ativa`, `tom`, `volume`, `abas` e
`assumidas` campo a campo, e campo novo nao entra sozinho. Em producao o selo
do e-mail ficaria SEMPRE em branco e a soma do grupo fechado sairia sem a
parcela dele.

⚠️ E NAO IA APARECER EM TESTE NENHUM: os meus setam `notificacoes.email_nao_lidos`
a mao antes de montar o menu, porque o que eles defendem e o DESENHO do selo.
Eles continuariam verdes com o selo morto na tela -- a familia do `M9`, mas
por dentro do estado em vez do layout. Achado lendo a cadeia inteira (quem
devolve -> quem grava -> quem le) antes do build, que e o que o `M9` manda
fazer antes de abrir a tela.

E a mesma licao que o `do_usuario` do `telas.py` carrega escrita no corpo
desde 27/08: "esta funcao monta a resposta A MAO, e e por isso que o campo
novo precisa estar listado aqui".
"""
import shutil
import sys

ESTADO = "frontend/src/estado/notificacoes.js"
NOTIFICADOR = "frontend/src/componentes/Notificador.vue"

ESTADO_ANTES = """  abas: { minhas: 0, time: 0 },
  assumidasNaoLidas: 0,"""
ESTADO_DEPOIS = """  abas: { minhas: 0, time: 0 },
  /* 🔵 22/10: os não lidos da ENTRADA do e-mail, para o selo do menu. Mora
     aqui, e não numa chamada do MenuLateral, porque este estado já é
     preenchido de 8 em 8 s em toda tela -- o selo do e-mail e o do WhatsApp
     são o mesmo dado, lido uma vez.

     🚨 DECLARADO AQUI DE PROPÓSITO, mesmo sendo `reactive`. Campo que só
     existe depois da primeira resposta faz o menu desenhar `undefined` no
     primeiro quadro, e deixa o arquivo que É a lista do estado sem dizer que
     ele existe. */
  email_nao_lidos: 0,
  assumidasNaoLidas: 0,"""

NOTIF_ANTES = """  notificacoes.abas = r.abas || { minhas: 0, time: 0 }
  notificacoes.assumidasNaoLidas = (r.assumidas || []).length"""
NOTIF_DEPOIS = """  notificacoes.abas = r.abas || { minhas: 0, time: 0 }
  /* 🚨 ESTA CÓPIA É CAMPO A CAMPO, e é por isso que esta linha tem de existir.
     Em 22/10 o selo do e-mail no menu ficou em branco por ela faltar: a rota
     devolvia o número e o menu o lia, mas nada no meio gravava. Suíte verde
     dos dois lados -- quem pega isto é ler a cadeia, não o placar. */
  notificacoes.email_nao_lidos = r.email_nao_lidos || 0
  notificacoes.assumidasNaoLidas = (r.assumidas || []).length"""


def aplicar(caminho, antes, depois):
    texto = open(caminho, encoding="utf-8").read()
    if texto.count(antes) != 1:
        raise SystemExit(
            f"FALHOU {caminho}: {texto.count(antes)} ocorrencias, esperava 1")
    bak = caminho + ".bak_2026-10-22_atendimento"
    try:
        open(bak, "x", encoding="utf-8").write(texto)
    except FileExistsError:
        pass
    open(caminho, "w", encoding="utf-8").write(texto.replace(antes, depois, 1))
    print(f"ok  {caminho}")


def main() -> int:
    aplicar(ESTADO, ESTADO_ANTES, ESTADO_DEPOIS)
    aplicar(NOTIFICADOR, NOTIF_ANTES, NOTIF_DEPOIS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
