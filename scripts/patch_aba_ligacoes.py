"""Bloco 4: a aba Ligações (LIG_1.1) — registro, rotas, menu e roteador.

Idempotente, com âncora conferida. Não reinicia serviço e não faz build.
Uso: ./venv/bin/python scripts/patch_aba_ligacoes.py [--conferir]
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SO_CONFERIR = "--conferir" in sys.argv

# ------------------------------------------------------------------ telas.py
TELAS_ANCORA = '''    {
        "codigo": "REL_1.1",
'''
TELAS_NOVO = '''    # ---- LIG: ligações do MicroSIP ----
    {
        # 🔵 15/10: *"considere que vamos precisar de uma aba nova no Movizap
        # para 'Ligações' - a idéia é um grid simples que tenha as ligações do
        # historico do MicroSip, consultadas por cliente - ja da base Movizap,
        # ou por Atendente, ou por data ou por numero, etc"*.
        #
        # 🚨 PERMISSÃO PRÓPRIA, e NENHUM perfil em PERFIS a lista: a aba nasce
        # **só do owner**, que é a decisão dele de 15/10. Conceder depois é
        # acrescentar "ligacoes" a um perfil -- uma linha.
        #
        # ⚠️ Módulo novo (LIG): `MenuLateral.NOME_DO_MODULO` precisa conhecê-lo,
        # senão o menu mostra o prefixo cru.
        "codigo": "LIG_1.1",
        "titulo": "Ligações",
        "rota": "/ligacoes",
        "icone": "bi-telephone",
        "descricao": "Ligações do MicroSIP: por cliente, atendente, data ou número.",
        "permissao": "ligacoes",
        "fase": 1,
    },
'''

# ------------------------------------------------------------------ main.py
IMPORT_ANCORA = "from . import ligacoes_consulta\n"
IMPORT_NOVO = "from . import relatorio_csv\n"

ROTAS_ANCORA = "# ── Alistamento do agente por SENHA (15/10/2026) ────────────────────────────\n"
ROTAS_NOVO = '''# ── Aba Ligações (LIG_1.1, 15/10) ───────────────────────────────────────────
#
# 🔵 *"um grid simples ... exportar e importar e um botão para baixar a ligação
# se quiser ou reproduzir por lá"*.
#
# 🚨 A aba é `LIG_1.1`, permissão que nenhum perfil tem: nasce só do owner.
# O modal da ficha é outra rota, sob `ATD_1.2` -- quem atende vê as ligações do
# número que está atendendo, sem ver a aba.


@app.get("/api/ligacoes")
def listar_ligacoes(de: str | None = None, ate: str | None = None,
                    atendente_id: int | None = None, ramal: str | None = None,
                    sentido: str | None = None, numero: str | None = None,
                    cliente_id: int | None = None, com_gravacao: bool | None = None,
                    pagina: int = 1,
                    por_pagina: int = ligacoes_consulta.POR_PAGINA,
                    usuario: dict = Depends(auth.requer_tela("LIG_1.1"))):
    """O grid da aba. Os totais vêm do filtro inteiro, não da página."""
    return ligacoes_consulta.consultar(
        pagina=pagina, por_pagina=por_pagina, de=de, ate=ate,
        atendente_id=atendente_id, ramal=ramal, sentido=sentido, numero=numero,
        cliente_id=cliente_id, com_gravacao=com_gravacao)


@app.get("/api/ligacoes/agentes")
def agentes_de_ligacao(usuario: dict = Depends(auth.requer_tela("LIG_1.1"))):
    """Quem tem agente e desde quando.

    🚨 É o que impede a aba de mentir por omissão: ausência de ligação de
    alguém significa "aquele PC não tem agente", não "não ligou".
    """
    return {"agentes": ligacoes_consulta.agentes()}


@app.get("/api/ligacoes/exportar.csv")
def exportar_ligacoes(de: str | None = None, ate: str | None = None,
                      atendente_id: int | None = None, ramal: str | None = None,
                      sentido: str | None = None, numero: str | None = None,
                      cliente_id: int | None = None, com_gravacao: bool | None = None,
                      usuario: dict = Depends(auth.requer_tela("LIG_1.1"))):
    """O CSV do que está filtrado.

    🚨 Registra quem exportou, quando, com que filtros e quantas linhas:
    exportar ligação é número de telefone e áudio de conversa saindo do
    sistema, e sem rastro não há como responder depois quem levou o quê.
    """
    import json

    filtros = {"de": de, "ate": ate, "atendente_id": atendente_id, "ramal": ramal,
               "sentido": sentido, "numero": numero, "cliente_id": cliente_id,
               "com_gravacao": com_gravacao}
    linhas = ligacoes_consulta.para_csv(**filtros)
    for linha in linhas:
        # O banco devolve timestamptz no fuso da sessão (America/Sao_Paulo):
        # não há o que converter aqui.
        linha["quando"] = linha["inicio"].strftime("%d/%m/%Y %H:%M")
        linha["duracao"] = linha["duracao_s"]
        linha["cliente"] = " | ".join(c["nome"] for c in linha["clientes"]) or "sem cadastro"
        linha["contato"] = " | ".join(
            c["contato_nome"] for c in linha["clientes"] if c.get("contato_nome"))
        linha["gravacao"] = len(linha["gravacoes"])
    dados = relatorio_csv.gerar([
        ("quando", "Quando"), ("sentido", "Sentido"), ("situacao", "Situação"),
        ("telefone_e164", "Número"), ("cliente", "Cliente"), ("contato", "Contato"),
        ("atendente", "Atendente"), ("ramal", "Ramal"),
        ("duracao", "Duração (s)"), ("gravacao", "Gravações"), ("pc", "PC"),
    ], linhas)
    atendente_id_dono = _atendente_do_usuario(usuario)
    if atendente_id_dono:
        banco.executar(
            """INSERT INTO ligacao_exportacao (atendente_id, filtros, linhas)
               VALUES (%s, %s, %s)""",
            (atendente_id_dono, json.dumps(filtros, default=str), len(linhas)))
    nome = f"ligacoes-{date.today():%Y-%m-%d}.csv"
    return Response(content=dados, media_type="text/csv; charset=utf-8",
                    headers=relatorio_csv.cabecalhos(nome))


@app.get("/api/ligacoes/gravacao/{gravacao_id}")
def ouvir_gravacao(gravacao_id: int, usuario: dict = Depends(auth.get_usuario)):
    """O mp3, para tocar no navegador ou baixar.

    🚨 A autorização é DENTRO e devolve **404, não 403**, no molde de
    `/api/midia/{id}/ver`: "existe mas não é seu" não se anuncia.

    🚨 Quem pode ouvir: quem tem a aba (`LIG_1.1`) **ou** quem atende
    (`ATD_1.2`) -- senão o player do modal da ficha não funcionaria para
    ninguém além do owner.

    O `FileResponse` do Starlette já responde `Range`/206, então arrastar o
    áudio funciona sem código nosso.
    """
    pode = (registro_telas.pode_acessar(usuario, "LIG_1.1")
            or registro_telas.pode_acessar(usuario, "ATD_1.2"))
    if not pode:
        raise HTTPException(status_code=404, detail="Gravação não encontrada.")
    g = ligacoes_consulta.gravacao(gravacao_id)
    if not g:
        raise HTTPException(status_code=404, detail="Gravação não encontrada.")
    caminho = pathlib.Path(g["caminho"])
    if not caminho.exists():
        raise HTTPException(status_code=404, detail="Arquivo não está no disco.")
    return FileResponse(caminho, media_type="audio/mpeg")


'''

# ------------------------------------------------------------- MenuLateral.vue
MENU_ANCORA = """const NOME_DO_MODULO = {
  ATD: 'Atendimento',
  CAD: 'Cadastro',
  CFG: 'Configuração',
  REL: 'Relatórios',
}"""
MENU_NOVO = """const NOME_DO_MODULO = {
  ATD: 'Atendimento',
  CAD: 'Cadastro',
  CFG: 'Configuração',
  LIG: 'Ligações',
  REL: 'Relatórios',
}"""

# ------------------------------------------------------------ router/index.js
ROUTER_IMPORT_ANCORA = "import Historico from '../telas/Historico.vue'\n"
ROUTER_IMPORT_NOVO = "import Ligacoes from '../telas/Ligacoes.vue'\n"

ROUTER_ROTA_ANCORA = """    path: '/atendimento/historico',
    name: 'ATD_5.1',
    component: Historico,
    meta: { codigo: 'ATD_5.1', titulo: 'Histórico' },
  },
"""
ROUTER_ROTA_NOVO = """    path: '/atendimento/historico',
    name: 'ATD_5.1',
    component: Historico,
    meta: { codigo: 'ATD_5.1', titulo: 'Histórico' },
  },
  {
    // Fora de /atendimento: ligação do MicroSIP não é conversa de WhatsApp, e
    // a aba é de auditoria (só do owner), não de atendimento.
    path: '/ligacoes',
    name: 'LIG_1.1',
    component: Ligacoes,
    meta: { codigo: 'LIG_1.1', titulo: 'Ligações' },
  },
"""

PASSOS = [
    ("telas.py: LIG_1.1", "movizap/telas.py", TELAS_ANCORA, TELAS_NOVO + TELAS_ANCORA,
     '"codigo": "LIG_1.1"'),
    ("main.py: import do relatorio_csv", "movizap/main.py", IMPORT_ANCORA,
     IMPORT_ANCORA + IMPORT_NOVO, "from . import relatorio_csv"),
    ("main.py: as 4 rotas", "movizap/main.py", ROTAS_ANCORA, ROTAS_NOVO + ROTAS_ANCORA,
     '@app.get("/api/ligacoes")'),
    ("MenuLateral: modulo LIG", "frontend/src/componentes/MenuLateral.vue",
     MENU_ANCORA, MENU_NOVO, "LIG: 'Ligações'"),
    ("router: import", "frontend/src/router/index.js",
     ROUTER_IMPORT_ANCORA, ROUTER_IMPORT_ANCORA + ROUTER_IMPORT_NOVO,
     "import Ligacoes from"),
    ("router: rota /ligacoes", "frontend/src/router/index.js",
     ROUTER_ROTA_ANCORA, ROUTER_ROTA_NOVO, "name: 'LIG_1.1'"),
]

for nome, arquivo, ancora, novo, marca in PASSOS:
    alvo = RAIZ / arquivo
    texto = alvo.read_text(encoding="utf-8")
    if marca in texto:
        print(f"já estava: {nome}")
        continue
    if ancora not in texto:
        raise SystemExit(f"ÂNCORA NÃO ACHADA ({nome}): {ancora[:70]!r}")
    if texto.count(ancora) != 1:
        raise SystemExit(f"ÂNCORA AMBÍGUA ({nome}): {texto.count(ancora)}×")
    if not SO_CONFERIR:
        alvo.write_text(texto.replace(ancora, novo), encoding="utf-8")
    print(f"{'conferido' if SO_CONFERIR else 'aplicado'}: {nome}")
