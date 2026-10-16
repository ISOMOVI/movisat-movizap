"""A senha de alistamento passa a valer 1 DIA (15/10, pedido dele).

🔵 *"dos ramais, podemos prolongar as senhas para 1 dia por enquanto?"*

🚨 O QUE **NAO** MUDA: o `.exe`. A senha e derivada inteiramente na VPS
(`senha_da_janela`); o instalador apenas manda o que a pessoa digitou. Nenhum
PC precisa ser reinstalado, nem o nginx tocado.

🚨 E A JANELA DE GERACAO TAMBEM NAO MUDA, e isso e o ponto. Trocar
`JANELA_S` de 600 para 86400 pareceria o caminho obvio e criaria um defeito
grave: como `UNIQUE (ramal, janela)` e o que faz a senha servir uma vez, uma
janela de um dia significaria **um alistamento por ramal por dia**. Se o
alistamento falhasse depois de a janela queimar (erro de certificado, rede
caindo no meio), "peca outra senha" devolveria a MESMA senha, ja queimada, e o
ramal ficaria travado ate o dia seguinte.

O que muda e so quantas janelas sao ACEITAS: a senha continua trocando a cada
10 minutos (entao uma falha custa 10 minutos, como hoje), e as senhas das
ultimas 24 horas continuam valendo.

Idempotente. Uso: ./venv/bin/python scripts/patch_senha_1dia.py [--conferir]
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SO_CONFERIR = "--conferir" in sys.argv

PASSOS: list[tuple[str, str, str, str]] = []


def passo(rel, nome, velho, novo):
    PASSOS.append((rel, nome, velho, novo))


passo("movizap/ligacoes_alistar.py", "a janela de aceitacao vai a 1 dia",
      """JANELA_S = 600               # 10 minutos
JANELAS_ACEITAS = 2          # a atual e a anterior (relógio do PC adianta/atrasa)""",
      """JANELA_S = 600               # 10 minutos: é de quanto em quanto tempo a senha TROCA

# 🔵 15/10, pedido dele: *"podemos prolongar as senhas para 1 dia por
# enquanto?"*. São as últimas 24 h de senhas daquele ramal.
#
# 🚨 QUEM MUDA É A ACEITAÇÃO, NUNCA A JANELA DE GERAÇÃO. `JANELA_S = 86400`
# pareceria o caminho óbvio e seria defeito grave: `UNIQUE (ramal, janela)` é o
# que faz a senha servir UMA VEZ, então uma janela de um dia viraria **um
# alistamento por ramal por dia** -- e um alistamento que falhasse depois de a
# janela queimar (erro de certificado, rede caindo no meio) deixaria o ramal
# travado até o dia seguinte, porque "peça outra senha" devolveria a mesma
# senha já queimada. Com a geração de 10 min, uma falha custa 10 minutos.
#
# ⚠️ O QUE ISSO CUSTA, por escrito: uma senha ditada e NÃO usada continua
# servindo por até um dia, em vez de 20 minutos. Ela continua de uso único (a
# primeira utilização queima a janela), continua só alistando, e 5 erros
# seguidos continuam trancando o IP. O risco que cresce é o de alguém que
# ouviu a senha alistar o PC errado antes da pessoa certa -- e isso aparece na
# hora, porque alistar revoga o PC anterior e o vigia acusa o PC que parou de
# falar.
#
# ⚠️ Para voltar a 20 minutos é esta linha, e só ela: `JANELAS_ACEITAS = 2`.
JANELAS_ACEITAS = 144        # 144 × 10 min = 24 h""")

passo("movizap/ligacoes_alistar.py", "o docstring do modulo conta a verdade nova",
      """🚨 USO ÚNICO. A janela gasta vira linha em `alistamento_queimado`, e
`UNIQUE (ramal, janela)` é a trava: senha ditada por WhatsApp que continuasse
valendo seria senha vazada. Duas janelas são aceitas (a atual e a anterior),
por tolerância de relógio -- no pior caso a senha vale 20 minutos.""",
      """🚨 USO ÚNICO. A janela gasta vira linha em `alistamento_queimado`, e
`UNIQUE (ramal, janela)` é a trava: a mesma senha não alista duas vezes.

⏱️ **A senha vale 1 DIA** (pedido dele em 15/10). Ela TROCA a cada 10 minutos,
e as senhas das últimas 24 h continuam sendo aceitas -- as duas coisas são
diferentes, e é essa separação que mantém a retentativa custando 10 minutos.
Ver o comentário de `JANELAS_ACEITAS`, que explica por que mexer na janela de
geração seria defeito.""")

passo("movizap/ligacoes_alistar.py", "a validade informada deixa de ser a do fim da janela",
      """def segundos_restantes(janela: int | None = None) -> int:
    janela = janela if janela is not None else janela_de()
    return int((janela + 1) * JANELA_S - time.time())""",
      """def segundos_restantes(janela: int | None = None) -> int:
    \"\"\"Quanto tempo esta senha AINDA SERVE.

    🚨 É até o fim da última janela que ainda a aceita, e não até o fim da
    janela em que ela nasceu. Enquanto media só a janela de geração, a
    ferramenta dizia "vale por 7 min" de uma senha que valia um dia -- e
    ferramenta que mente sobre o próprio prazo faz ele pedir senha nova sem
    precisar, ou desistir de uma que ainda servia.
    \"\"\"
    janela = janela if janela is not None else janela_de()
    return int((janela + JANELAS_ACEITAS) * JANELA_S - time.time())""")

passo("scripts/senha_alistamento.py", "a ferramenta diz horas quando ha horas",
      """minutos, segundos = divmod(max(0, r["segundos"]), 60)
print(f"Vale por {minutos} min {segundos:02d} s. Depois disso, rode de novo.")""",
      """# 🔵 15/10: a senha passou a valer 1 dia, então "min" sozinho não serve mais.
horas, resto = divmod(max(0, r["segundos"]), 3600)
minutos, segundos = divmod(resto, 60)
quanto = (f"{horas} h {minutos:02d} min" if horas
          else f"{minutos} min {segundos:02d} s")
print(f"Vale por {quanto}. Depois disso, rode de novo.")
print("Serve UMA VEZ: a primeira utilizacao a queima.")""")


def aplicar():
    por_arquivo: dict[str, str] = {}
    feitos, pulados = [], []
    for rel, nome, velho, novo in PASSOS:
        caminho = RAIZ / rel
        if rel not in por_arquivo:
            por_arquivo[rel] = caminho.read_text(encoding="utf-8")
        texto = por_arquivo[rel]
        if novo in texto:
            pulados.append(f"{rel}: {nome}")
            continue
        n = texto.count(velho)
        if n != 1:
            raise SystemExit(f"ANCORA {n}x em {rel} '{nome}': {velho[:70]!r}")
        por_arquivo[rel] = texto.replace(velho, novo, 1)
        feitos.append(f"{rel}: {nome}")

    for rel, texto in por_arquivo.items():
        # Validar ANTES de gravar, nunca depois (abertura, item 8).
        compile(texto, str(RAIZ / rel), "exec")
    if not SO_CONFERIR:
        for rel, texto in por_arquivo.items():
            (RAIZ / rel).write_text(texto, encoding="utf-8")
    for n in feitos:
        print(f"  {'conferido' if SO_CONFERIR else 'aplicado'}: {n}")
    for n in pulados:
        print(f"  ja aplicado: {n}")


aplicar()
