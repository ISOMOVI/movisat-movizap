"""Bloco 8: um login por dia — o token vale ate a virada (15/10).

🔵 Decisao dele: *"o login vale ate a virada do dia; o rascunho morre com ele"*.

Idempotente, com ancora conferida. Nao reinicia servico e nao faz build.
Uso: ./venv/bin/python scripts/patch_bloco8_login_do_dia.py [--conferir]
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SO_CONFERIR = "--conferir" in sys.argv

PASSOS = []

# ------------------------------------------------------------------ auth.py
# 1. O fuso e o piso entram junto da constante que sai.
PASSOS.append(("movizap/auth.py", """ALGORITMO = "HS256"
TOKEN_EXPIRA_HORAS = 10
""", '''ALGORITMO = "HS256"

# 🔵 15/10 — UM LOGIN POR DIA. Antes o token valia 10 horas corridas, o que
# fazia a pessoa reentrar no meio da tarde por nada. Agora ele vale até a
# VIRADA DO DIA, e é isso que dá ao rascunho da conversa (Bloco 7) um ciclo de
# vida definido: dentro do dia o rascunho fica; na virada, morre com o login.
#
# 🚨 O FUSO É O DO ESCRITÓRIO, não UTC. Em UTC a virada cairia às 21h de
# Brasília -- em plena tarde de trabalho.
#
# ⚠️ PISO DE 2 HORAS (minha, declarada): quem entra às 23:30 não pode cair às
# 00:00. Nesse caso o token vai até a virada do dia SEGUINTE. Sem o piso, o
# turno da noite é derrubado no meio.
#
# ⚠️ O QUE ISSO CUSTA, por escrito: quem entra às 08:00 passa a ter token de
# 16 h em vez de 10 h -- o token vive mais, e é o preço de um login por dia.
# Continuam valendo as travas que já existem: `atendente.ativo = false`
# derruba na requisição seguinte, perda de permissão vira 403 na hora, e
# rotação do `MOVIZAP_JWT_SECRET` invalida tudo.
FUSO_DO_DIA = ZoneInfo("America/Sao_Paulo")
PISO_HORAS = 2
'''))

# 2. O import do fuso.
PASSOS.append(("movizap/auth.py",
               "from datetime import datetime, timedelta, timezone\n",
               "from datetime import datetime, timedelta, timezone\n"
               "from zoneinfo import ZoneInfo\n"))

# 3. `criar_token` passa a usar a virada, e entrega a expiração a quem quiser.
PASSOS.append(("movizap/auth.py", '''def criar_token(login: str) -> str:
    payload = {
        "sub": login,
        "tipo": "movizap",
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRA_HORAS),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITMO)
''', '''def expira_na_virada(agora: datetime | None = None) -> datetime:
    """Meia-noite seguinte em `America/Sao_Paulo`, com piso de 2 horas.

    Devolve sempre em UTC -- quem assina o token não precisa saber de fuso.
    """
    agora = (agora or datetime.now(timezone.utc)).astimezone(FUSO_DO_DIA)
    virada = (agora + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0)
    if virada - agora < timedelta(hours=PISO_HORAS):
        # Entrou colado na virada: vale até a virada do dia seguinte.
        virada = (virada + timedelta(days=1)).replace(hour=0)
    return virada.astimezone(timezone.utc)


def criar_token_e_expiracao(login: str) -> tuple[str, datetime]:
    """O token e a hora exata em que ele morre.

    Os dois saem da MESMA conta de propósito: calcular a expiração duas vezes
    deixaria a tela dizer uma hora e o token obedecer a outra se a chamada
    atravessasse a meia-noite.
    """
    expira = expira_na_virada()
    token = jwt.encode({"sub": login, "tipo": "movizap", "exp": expira},
                       settings.jwt_secret, algorithm=ALGORITMO)
    return token, expira


def criar_token(login: str) -> str:
    return criar_token_e_expiracao(login)[0]
'''))

# 4. `get_usuario` carrega a expiração do token que acabou de validar, para a
#    barra de status poder dizer a hora de término -- inclusive depois de um
#    F5 e no login pelo Google, que não passa pela rota de senha.
PASSOS.append(("movizap/auth.py", '''    usuario = buscar_usuario(login)
    if not usuario or not usuario["ativo"]:
        raise nao_autorizado
    return usuario
''', '''    usuario = buscar_usuario(login)
    if not usuario or not usuario["ativo"]:
        raise nao_autorizado
    # A expiração vem do token JÁ VALIDADO, e não de uma conta nova: é a hora
    # em que ESTA sessão termina, mesmo que a regra mude no meio do dia.
    usuario["token_exp"] = payload.get("exp")
    return usuario
'''))

# ------------------------------------------------------------------ main.py
# 4b. `datetime`/`timezone` no main: ele só importava `date`.
PASSOS.append(("movizap/main.py", "from datetime import date\n",
               "from datetime import date, datetime, timezone\n"))

# 5. A resposta do login diz a hora, não mais "quantas horas".
PASSOS.append(("movizap/main.py", '''    ratelimit.registrar_sucesso(chave)
    return {
        "token": auth.criar_token(usuario["login"]),
        "expira_em_horas": auth.TOKEN_EXPIRA_HORAS,
''', '''    ratelimit.registrar_sucesso(chave)
    # 🔵 15/10: a sessão é do DIA. A resposta devolve a hora exata do fim, não
    # "quantas horas" -- "10 horas" não dizia nada a quem entrou às 17h.
    token, expira = auth.criar_token_e_expiracao(usuario["login"])
    return {
        "token": token,
        "expira_em": expira.isoformat(),
'''))

# 6. `/api/sessao/eu` também diz quando esta sessão termina: é o que faz a
#    barra funcionar depois de um F5 e para quem entrou pelo Google.
PASSOS.append(("movizap/main.py", '''        "tem_foto": bool((meu or {}).get("foto")),
        "telas": registro_telas.do_usuario(usuario),
    }
''', '''        "tem_foto": bool((meu or {}).get("foto")),
        "telas": registro_telas.do_usuario(usuario),
        # 🔵 15/10: a hora em que esta sessão do dia termina. Vem daqui, e não
        # só da resposta do login, porque um F5 não refaz o login -- e o login
        # pelo Google nem passa pela rota de senha.
        "sessao_expira_em": (
            datetime.fromtimestamp(usuario["token_exp"], timezone.utc).isoformat()
            if usuario.get("token_exp") else None),
    }
'''))


def aplicar(rel: str, velho: str, novo: str) -> str:
    caminho = RAIZ / rel
    texto = caminho.read_text(encoding="utf-8")
    if novo in texto:
        return f"ja aplicado: {rel}"
    if texto.count(velho) != 1:
        raise SystemExit(f"ANCORA {texto.count(velho)}x em {rel}: {velho[:70]!r}")
    candidato = texto.replace(velho, novo, 1)
    # Validar ANTES de gravar, nunca depois (abertura, item 8).
    compile(candidato, str(caminho), "exec")
    if not SO_CONFERIR:
        caminho.write_text(candidato, encoding="utf-8")
    return f"{'conferido' if SO_CONFERIR else 'aplicado'}: {rel}"


for rel, velho, novo in PASSOS:
    print(aplicar(rel, velho, novo))
