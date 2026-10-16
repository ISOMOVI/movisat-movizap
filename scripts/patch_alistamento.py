"""Aplica as duas inserções do Bloco 1 em arquivos que já existem.

Idempotente: rodar duas vezes não duplica nada. Não reinicia serviço nenhum —
o uvicorn sobe sem `--reload`, então nada disso entra no ar antes do restart.

  1. `movizap/config.py`   — a variável do segredo das senhas de alistamento.
  2. `movizap/main.py`     — o import e a rota `POST /api/ligacoes/agente/alistar`.

Uso: ./venv/bin/python scripts/patch_alistamento.py [--conferir]
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SO_CONFERIR = "--conferir" in sys.argv

CONFIG_ANCORA = '    webhook_segredo_anterior: str = _ler("MOVIZAP_WEBHOOK_SEGREDO_ANTERIOR")\n'
CONFIG_NOVO = '''
    # ---- Ligações do MicroSIP: alistamento por senha (15/10/2026) ----
    # 🔵 *"validar o atendente do MicroSip com uma senha que será gerada
    # sempre via algoritmo e é mutável para rodar"*.
    #
    # 🚨 SEGREDO PRÓPRIO, nunca o `jwt_secret`. Dele saem as senhas de
    # alistamento (HMAC sobre ramal + janela de 10 min), e ele JAMAIS sai da
    # VPS: o instalador no PC não deriva senha, só manda o que foi digitado.
    # Trocar este valor invalida toda senha em circulação -- é a saída se uma
    # vazar.
    ligacoes_senha_segredo: str = _ler("MOVIZAP_LIGACOES_SENHA_SEGREDO")
'''

MAIN_IMPORT_ANCORA = "from . import ligacoes\n"
MAIN_IMPORT_NOVO = "from . import ligacoes_alistar\n"

MAIN_ROTA_ANCORA = "class NotificacaoAtiva(BaseModel):\n"
MAIN_ROTA_NOVA = '''# ── Alistamento do agente por SENHA (15/10/2026) ────────────────────────────
#
# 🔵 *"o .exe deve rodar livre assim, porém validar o atendente do MicroSip
# com uma senha que será gerada sempre via algoritmo e é mutável para rodar"*
# e *"se trocarem de PC é só executar novamente e me pedir a senha de uso"*.
#
# 🚨 ESTA ROTA MORA AQUI, NO PAINEL, e não na porta própria (8010): lá o nginx
# exige certificado de cliente, e um PC que está se alistando ainda NÃO TEM
# certificado -- não conseguiria nem abrir a conexão. Alistar aqui também é o
# que mantém a promessa do kit: nenhum passo precisa de root nem toca o nginx.
#
# 🚨 Sem `requer_tela`: quem fala é o PC da pessoa, e a prova é a senha de uso
# único (`movizap/ligacoes_alistar.py`). Tentativa errada cai no `ratelimit`,
# o mesmo que trava o login.


class AlistarEntrada(BaseModel):
    ramal: str = Field(max_length=10)
    senha: str = Field(max_length=30)
    pedido: str = Field(max_length=8000)   # o CSR que o `certreq` gerou no PC
    pc: str | None = Field(default=None, max_length=100)


@app.post("/api/ligacoes/agente/alistar")
def alistar_agente(dados: AlistarEntrada, request: Request):
    """Uma chamada e o PC está pronto: confere a senha, queima a janela,
    revoga o PC anterior do ramal, cria a chave e assina o certificado deste
    PC. Devolve a chave e o certificado -- é a única vez que a chave aparece."""
    try:
        return ligacoes_alistar.alistar(
            dados.ramal, dados.senha, dados.pedido, dados.pc,
            ratelimit.ip_do_cliente(request))
    except ligacoes_alistar.SenhaInvalida as e:
        raise HTTPException(status_code=401, detail=str(e)) from e


'''


def aplicar(caminho: Path, ancora: str, novo: str, marca: str, depois: bool) -> str:
    texto = caminho.read_text(encoding="utf-8")
    if marca in texto:
        return f"já estava: {caminho.name} ({marca})"
    if ancora not in texto:
        raise SystemExit(f"ÂNCORA NÃO ACHADA em {caminho.name}: {ancora!r}")
    if texto.count(ancora) != 1:
        raise SystemExit(f"ÂNCORA AMBÍGUA em {caminho.name} "
                         f"({texto.count(ancora)}×): {ancora!r}")
    trocado = texto.replace(ancora, ancora + novo if depois else novo + ancora)
    if not SO_CONFERIR:
        caminho.write_text(trocado, encoding="utf-8")
    return f"{'conferido' if SO_CONFERIR else 'aplicado'}: {caminho.name} ({marca})"


for recado in (
    aplicar(RAIZ / "movizap/config.py", CONFIG_ANCORA, CONFIG_NOVO,
            "ligacoes_senha_segredo", depois=True),
    aplicar(RAIZ / "movizap/main.py", MAIN_IMPORT_ANCORA, MAIN_IMPORT_NOVO,
            "from . import ligacoes_alistar", depois=True),
    aplicar(RAIZ / "movizap/main.py", MAIN_ROTA_ANCORA, MAIN_ROTA_NOVA,
            "/api/ligacoes/agente/alistar", depois=False),
):
    print(recado)
