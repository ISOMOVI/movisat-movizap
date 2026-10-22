"""Patch: as rotas dos formulários (públicas e do painel) e a tela FRM_1.1.

Quatro arquivos, cada um com um motivo:

  · `movizap/telas.py`       -- a FRM_1.1 entra no registro (e é o registro que
                                desenha o menu);
  · `movizap/preferencia.py` -- o interruptor do aviso, por pessoa;
  · `movizap/formularios.py` -- a contagem que o selo usa;
  · `movizap/main.py`        -- as rotas: 3 públicas, 6 do painel, e o selo
                                dentro da rota de notificações que já bate em
                                toda tela.

🚨 Cada emenda confere a âncora ANTES de escrever, e sai sem gravar nada se
não achar. `M15`: ausência só se afirma lendo o arquivo.

Rodar duas vezes não duplica (cada emenda tem a sua marca).
"""
import sys
from pathlib import Path

RAIZ = Path("/home/claude/movizap_painel")


def emendar(caminho: Path, ancora: str, novo: str, marca: str) -> None:
    texto = caminho.read_text(encoding="utf-8")
    if marca in texto:
        print(f"{caminho.name}: {marca!r} ja estava")
        return
    if ancora not in texto:
        sys.exit(f"{caminho.name}: NAO achei a ancora de {marca!r} -- nada escrito")
    if texto.count(ancora) != 1:
        sys.exit(f"{caminho.name}: a ancora de {marca!r} aparece "
                 f"{texto.count(ancora)} vezes -- ambigua, nada escrito")
    caminho.write_text(texto.replace(ancora, novo, 1), encoding="utf-8")
    print(f"{caminho.name}: {marca!r} emendado")


# ================================================================== telas.py
TELAS = RAIZ / "movizap" / "telas.py"
ANCORA_TELAS = '''    {
        "codigo": "CAD_1.1",'''
NOVA_TELA = '''    {
        # 🔵 22/10: a tela que recebe o que chega pelos formularios proprios
        # (`forms.movisat.com.br`). Modulo `FRM`, nao ATD: formulario nao e
        # conversa -- tem definicao, tem campo obrigatorio e tem anexo, e
        # nenhuma dessas tres coisas existe numa mensagem.
        #
        # ⚠️ `permissao: equipe` = owner e admin, a mesma regua da Fila e do
        # Historico. Nao e `atendimento` porque a solicitacao traz dado de
        # cadastro (CNPJ, endereco, valor) de quem ainda nao e cliente.
        #
        # ⚠️ O GRUPO E "Atendimento" DE PROPOSITO, e nao "Paineis": os quatro
        # paineis por situacao da OS sao a Etapa 3, e ate eles existirem o
        # grupo "Paineis" continua vazio -- o MenuLateral nao desenha grupo
        # sem tela visivel.
        "codigo": "FRM_1.1",
        "titulo": "Solicitações",
        "rota": "/solicitacoes",
        "icone": "bi-ui-checks",
        "descricao": "O que chega pelos formulários próprios.",
        "grupo": "Atendimento",
        "permissao": "equipe",
        "fase": 1,
    },
    # ---- CAD: cadastro ----
    {
        "codigo": "CAD_1.1",'''
# ⚠️ A ancora do CAD_1.1 vem logo depois do comentario "---- CAD: cadastro ----",
# que esta DENTRO do texto que vai ser substituido: por isso ele e reescrito
# acima, senao o comentario ficaria orfao antes da tela nova.
texto = TELAS.read_text(encoding="utf-8")
if "FRM_1.1" in texto:
    print("telas.py: FRM_1.1 ja estava")
else:
    velho = '''    # ---- CAD: cadastro ----
    {
        "codigo": "CAD_1.1",'''
    if velho not in texto:
        sys.exit("telas.py: NAO achei a ancora do CAD_1.1 -- nada escrito")
    TELAS.write_text(texto.replace(velho, NOVA_TELA, 1), encoding="utf-8")
    print("telas.py: FRM_1.1 emendada")

# =========================================================== preferencia.py
PREF = RAIZ / "movizap" / "preferencia.py"
FIM_PREF = '''

# ============================================================================
# AVISO DE SOLICITAÇÃO DE FORMULÁRIO — 22/10
# ============================================================================
# 🔵 Pedido dele: *"Item 1, porem controle de notificações no 'minha conta' de
# cada usuário, igual as demais"*.
#
# 🚨 NASCE LIGADO, e é a exceção consciente à regra de "recurso novo nasce
# desligado": o aviso É o pedido. Quem não quiser o desliga na CFG_11.1.
# Ausência de linha, aqui, significa LIGADO -- como no `enviar_com_enter`.
#
# ⚠️ ELE SÓ VALE PARA QUEM TEM A TELA. Quem não tem a FRM_1.1 recebe 0 de
# qualquer forma: o interruptor esconde um selo, nunca dá acesso.
CHAVE_AVISO_SOLICITACAO = "aviso_solicitacao"


def aviso_solicitacao(atendente_id: int | None) -> bool:
    if not atendente_id:
        return False
    return _ler(atendente_id, CHAVE_AVISO_SOLICITACAO) != "false"


def definir_aviso_solicitacao(atendente_id: int, ligado: bool) -> dict:
    _gravar(atendente_id, CHAVE_AVISO_SOLICITACAO, "true" if ligado else "false")
    return {"ok": True, "aviso_solicitacao": bool(ligado)}
'''
texto = PREF.read_text(encoding="utf-8")
if "CHAVE_AVISO_SOLICITACAO" in texto:
    print("preferencia.py: ja estava")
else:
    PREF.write_text(texto.rstrip("\n") + FIM_PREF, encoding="utf-8")
    print("preferencia.py: interruptor do aviso no fim do arquivo")

# =========================================================== formularios.py
FORM = RAIZ / "movizap" / "formularios.py"
FIM_FORM = '''

def contar_novas() -> int:
    """Quantas solicitações ainda estão em `nova` — o selo do menu.

    🚨 UMA FONTE SÓ. O selo e a tela contam pela MESMA coluna `estado`, e é de
    propósito: em 22/10 um selo de e-mail nasceu de uma CÓPIA do `WHERE` da
    aba e mostrou 61 onde a verdade era 5. Selo que discorda da lista manda a
    pessoa procurar o que a tela não mostra.
    """
    linha = banco.um("SELECT count(*) AS n FROM formulario_solicitacao "
                     "WHERE estado = 'nova'")
    return int(linha["n"] if linha else 0)
'''
texto = FORM.read_text(encoding="utf-8")
if "def contar_novas" in texto:
    print("formularios.py: contar_novas ja estava")
else:
    FORM.write_text(texto.rstrip("\n") + FIM_FORM, encoding="utf-8")
    print("formularios.py: contar_novas no fim do arquivo")

# ================================================================== main.py
MAIN = RAIZ / "movizap" / "main.py"

# ⚠️ `json` NAO estava importado no main.py (so asyncio/logging/pathlib/
# secrets/time): o envio publico le `valores` como JSON, entao entra aqui.
emendar(MAIN,
        "import logging\nimport pathlib",
        "import json\nimport logging\nimport pathlib",
        "import json")

emendar(MAIN,
        "from . import fpsl_ponte",
        "from . import formularios as formularios_mod\nfrom . import fpsl_ponte",
        "formularios as formularios_mod")

# ---- o selo, dentro da rota que já bate em toda tela ----
emendar(
    MAIN,
    '''        # 🔵 22/10: o terceiro selo do menu. Sai daqui, e nao de rota
        # propria, porque esta rota ja bate em toda tela -- um ritmo so.
        "email_nao_lidos": _email_nao_lidos(eu),''',
    '''        # 🔵 22/10: o terceiro selo do menu. Sai daqui, e nao de rota
        # propria, porque esta rota ja bate em toda tela -- um ritmo so.
        "email_nao_lidos": _email_nao_lidos(eu),
        # 🔵 22/10: o QUARTO selo -- solicitacoes de formulario ainda novas.
        # 🚨 Duas travas no mesmo numero: so quem tem a FRM_1.1 e so quem nao
        # desligou o aviso na CFG_11.1. Sem a primeira, o selo contaria para
        # quem clicaria e tomaria 403; sem a segunda, o pedido dele de
        # *"controle de notificações... igual as demais"* nao existiria.
        "solicitacoes_novas": (
            formularios_mod.contar_novas()
            if registro_telas.pode_acessar(usuario, "FRM_1.1")
            and preferencia.aviso_solicitacao(eu) else 0),''',
    "solicitacoes_novas")

# ---- o interruptor por pessoa ----
emendar(
    MAIN,
    '''@app.get("/api/notificacoes/equipe")''',
    '''class MeuAvisoSolicitacao(BaseModel):
    ligado: bool


@app.put("/api/eu/aviso-solicitacao")
def definir_meu_aviso_de_solicitacao(dados: MeuAvisoSolicitacao,
                                     usuario: dict = Depends(auth.get_usuario)):
    """🔵 22/10: *"controle de notificações no 'minha conta' de cada usuário,
    igual as demais"*. Sem `requer_tela`, como as outras de `/api/eu/...`: é a
    pessoa ajustando a si mesma."""
    eu = _atendente_do_usuario(usuario)
    if not eu:
        raise HTTPException(status_code=400,
                            detail="Sua conta não está vinculada a um atendente.")
    return preferencia.definir_aviso_solicitacao(eu, dados.ligado)


@app.get("/api/notificacoes/equipe")''',
    "aviso-solicitacao")

# ---- as rotas públicas e as do painel, antes do frontend ----
ROTAS = '''# ---------------------------------------------------- formulários próprios
#
# 🔵 Etapa 1 (22/10): os formulários genéricos, em `forms.movisat.com.br`.
#
# 🚨 TRÊS ROTAS PÚBLICAS, E SÃO ESSAS TRÊS. O nginx do host público só deixa
# passar `/f/`, `/pub/assets/` e `/api/publico/` -- todo o resto responde 403
# lá. Aqui elas também não ganham `Depends(auth...)`: formulário aberto é
# aberto, e o que protege o resto do painel é a permissão de cada rota, não a
# obscuridade do caminho.
#
# ⚠️ POR QUE UM BUNDLE SEPARADO (`frontend/dist_publico`): o bundle do painel
# publica `sourcemap: true`. Uma rota pública dentro do SPA faria qualquer
# anônimo baixar o painel inteiro COM o código-fonte. A pergunta foi dele
# (*"qual a mais segura para os links que terão acesso externos"*) e esta é a
# resposta.


def _publico_do_formulario(d: dict, ip: str | None) -> dict:
    """O que a página pública pode ver -- e nada além.

    🚨 `nosso_nome`, `bitrix_id`, `problema_id` e companhia NÃO SAEM DAQUI.
    São nomes internos e números de catálogo do Harmonit; quem preenche o
    formulário não tem o que fazer com eles, e o que não sai não vaza.
    """
    return {
        "slug": d["slug"], "titulo": d["titulo"], "botao": d["botao"],
        "descricao": d["descricao"],
        "campos": [{"nome": c["nome"], "rotulo": c["rotulo"], "tipo": c["tipo"],
                    "obrigatorio": c["obrigatorio"], "multiplo": c["multiplo"],
                    "visivel": c["visivel"], "opcoes": c["opcoes"],
                    "ajuda": c["ajuda"]}
                   for c in d["campos"]],
        "regras": [{"lista": r["lista"]} for r in d["regras"]],
        "abertura": formularios_mod.abertura(),
        "desafio": (formularios_mod.novo_desafio()
                    if formularios_mod.exige_desafio(ip) else None),
    }


@app.get("/api/publico/formulario/{slug}")
def formulario_publico(slug: str, request: Request):
    try:
        d = formularios_mod.definicao(slug)
    except formularios_mod.FormularioNaoExiste:
        raise HTTPException(status_code=404, detail="Formulário não encontrado.")
    return _publico_do_formulario(d, ratelimit.ip_do_cliente(request))


@app.get("/api/publico/desafio")
def desafio_publico():
    """Outra conta de somar, para quem errou a primeira."""
    return formularios_mod.novo_desafio()


@app.post("/api/publico/formulario/{slug}", status_code=201)
async def enviar_formulario_publico(
        slug: str, request: Request,
        valores: str = Form("{}"),
        abertura: str = Form(""),
        isca: str = Form(""),
        desafio_token: str = Form(""),
        desafio_resposta: str = Form(""),
        campos: list[str] = Form(default=[]),
        arquivos: list[UploadFile] = File(default=[])):
    """O envio. 🚨 A VALIDAÇÃO É AQUI, e é o ponto do módulo inteiro.

    Medido em 22/10: o Bitrix aceitou `values=[]` vazio e criou o registro
    15620. Lá a validação toda era no navegador -- e navegador é do cliente.
    """
    ip = ratelimit.ip_do_cliente(request)
    try:
        d = formularios_mod.definicao(slug)
    except formularios_mod.FormularioNaoExiste:
        raise HTTPException(status_code=404, detail="Formulário não encontrado.")

    # 🚨 A ISCA RECUSA EM SILÊNCIO, e responde o mesmo "recebemos" de sempre:
    # robô que toma erro aprende a tentar de outro jeito. Nada é gravado.
    if (isca or "").strip():
        log.info("formulario %s: isca preenchida, envio descartado (ip %s)", slug, ip)
        return {"ok": True, "mensagem": "Recebemos sua solicitação. "
                                        "Em breve entraremos em contato."}

    formularios_mod.conferir_abertura(abertura)
    if formularios_mod.exige_desafio(ip):
        formularios_mod.conferir_desafio(desafio_token, desafio_resposta)

    try:
        enviados = json.loads(valores or "{}")
    except ValueError:
        raise operacao.DadoInvalido("Não entendi os dados enviados.")
    if not isinstance(enviados, dict):
        raise operacao.DadoInvalido("Não entendi os dados enviados.")

    # ⚠️ Os anexos chegam em duas listas paralelas (`campos` e `arquivos`),
    # porque multipart com nome de campo dinâmico não dá para declarar. O
    # servidor confere o par, e só aceita campo que EXISTE e é do tipo file.
    de_arquivo = {c["nome"] for c in d["campos"] if c["tipo"] == "file"}
    guardados: list[dict] = []
    por_campo: dict = {}
    total = 0
    for i, enviado in enumerate(arquivos or []):
        campo = campos[i] if i < len(campos) else ""
        if campo not in de_arquivo:
            raise operacao.DadoInvalido("Anexo em campo que não aceita arquivo.")
        dados = await enviado.read()
        total += len(dados)
        if total > formularios_mod.TETO_ENVIO:
            raise operacao.DadoInvalido(
                f"Os anexos somam mais de "
                f"{formularios_mod.TETO_ENVIO // (1024 * 1024)} MB.")
        guardado = formularios_mod.guardar_arquivo(enviado.filename or "arquivo", dados)
        guardado["campo"] = campo
        guardado["mime"] = enviado.content_type
        guardados.append(guardado)
        por_campo.setdefault(campo, []).append(guardado)

    limpo = formularios_mod.validar(d, enviados, por_campo)
    r = formularios_mod.registrar(d, limpo, guardados, ip=ip)
    formularios_mod.registrar_envio(ip)
    return {"ok": True, "id": r["id"], "mensagem": r["mensagem"]}


# ---- o painel (FRM_1.1) ----

@app.get("/api/formularios")
def listar_formularios(usuario: dict = Depends(auth.requer_tela("FRM_1.1"))):
    return formularios_mod.lista_para_o_painel()


@app.get("/api/formularios/{slug}/definicao")
def definicao_do_formulario(slug: str,
                            usuario: dict = Depends(auth.requer_tela("FRM_1.1"))):
    """A definição inteira, inclusive de formulário DESLIGADO -- é por aqui que
    ele confere o que vai publicar antes de ligar."""
    try:
        return formularios_mod.definicao(slug, so_ativo=False)
    except formularios_mod.FormularioNaoExiste:
        raise HTTPException(status_code=404, detail="Formulário não encontrado.")


class FormularioAtivo(BaseModel):
    ativo: bool


@app.put("/api/formularios/{codigo}/ativo")
def ligar_formulario(codigo: str, dados: FormularioAtivo,
                     usuario: dict = Depends(auth.requer_tela("FRM_1.1"))):
    """🚨 SÓ O OWNER PUBLICA. Ligar um formulário é abrir uma porta para a
    internet, e a lista de quem pode fazer isso é de um."""
    _so_owner(usuario)
    linha = banco.um(
        """UPDATE formulario SET ativo = %s, atualizado_em = now()
            WHERE codigo = %s RETURNING codigo, slug, ativo""",
        (dados.ativo, codigo.upper()))
    if not linha:
        raise HTTPException(status_code=404, detail="Formulário não encontrado.")
    log.info("formulario %s %s por %s", linha["codigo"],
             "ligado" if linha["ativo"] else "desligado", usuario.get("login"))
    return linha


@app.get("/api/solicitacoes")
def listar_solicitacoes(formulario: str | None = None, estado: str | None = None,
                        antes_de: int | None = None, limite: int = 50,
                        usuario: dict = Depends(auth.requer_tela("FRM_1.1"))):
    return formularios_mod.listar_solicitacoes(slug=formulario, estado=estado,
                                               limite=limite, antes_de=antes_de)


@app.get("/api/solicitacoes/{solicitacao_id}")
def ver_solicitacao(solicitacao_id: int,
                    usuario: dict = Depends(auth.requer_tela("FRM_1.1"))):
    r = formularios_mod.uma(solicitacao_id)
    if not r:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")
    return r


class EstadoDaSolicitacao(BaseModel):
    estado: str


@app.put("/api/solicitacoes/{solicitacao_id}/estado")
def mudar_estado_da_solicitacao(solicitacao_id: int, dados: EstadoDaSolicitacao,
                                usuario: dict = Depends(auth.requer_tela("FRM_1.1"))):
    return formularios_mod.definir_estado(solicitacao_id, dados.estado,
                                          _atendente_do_usuario(usuario))


@app.get("/api/solicitacoes/{solicitacao_id}/arquivo/{arquivo_id}")
def baixar_anexo_da_solicitacao(solicitacao_id: int, arquivo_id: int,
                                usuario: dict = Depends(auth.requer_tela("FRM_1.1"))):
    """🚨 O HOST PÚBLICO NUNCA SERVE ANEXO -- quem envia é a internet, quem lê
    é a casa. E o caminho vem do BANCO, nunca da URL."""
    r = formularios_mod.arquivo(solicitacao_id, arquivo_id)
    if not r:
        raise HTTPException(status_code=404, detail="Anexo não encontrado.")
    caminho = pathlib.Path(r["caminho"])
    if not caminho.is_file():
        raise HTTPException(status_code=410, detail="O arquivo não está mais no disco.")
    return FileResponse(caminho, filename=r["nome_original"],
                        media_type=r["mime"] or "application/octet-stream")


class DesafioSempre(BaseModel):
    ligado: bool


@app.get("/api/config/formulario-desafio")
def ver_desafio_do_formulario(usuario: dict = Depends(auth.requer_tela("CFG_7.1"))):
    return {"desafio_sempre": formularios_mod.desafio_sempre()}


@app.put("/api/config/formulario-desafio")
def definir_desafio_do_formulario(dados: DesafioSempre,
                                  usuario: dict = Depends(auth.requer_tela("CFG_7.1"))):
    """⚠️ Interruptor do SISTEMA, por isso em `/config › Geral` -- e nasce
    desligado. Ligado, a conta de somar aparece em TODO envio; desligado, só
    depois de 5 envios do mesmo IP na hora."""
    return formularios_mod.definir_desafio_sempre(dados.ligado)


# ------------------------------------------------- a página pública do form
PUBLICO = RAIZ / "frontend" / "dist_publico"

if PUBLICO.exists():
    app.mount("/pub/assets", StaticFiles(directory=PUBLICO / "assets"),
              name="pub_assets")

    @app.get("/f/{slug}")
    def pagina_do_formulario(slug: str):
        """A página do formulário. 🚨 O MESMO `index.html` para todos os slugs:
        quem busca a definição é a página, pela rota de API -- e é ela que dá
        404 quando o formulário não existe ou está desligado."""
        return FileResponse(PUBLICO / "index.html",
                            headers={"Cache-Control": "no-cache"})


# ---------------------------------------------------------------- frontend
'''
emendar(MAIN,
        "# ---------------------------------------------------------------- frontend\n",
        ROTAS,
        "formulários próprios")

# A prova: reler o estado. Importar o módulo levanta erro de sintaxe e de
# nome, e conta as rotas que de fato existem.
sys.path.insert(0, str(RAIZ))
from movizap.main import app  # noqa: E402

caminhos = sorted({r.path for r in app.routes
                   if "formulario" in r.path or "solicitac" in r.path
                   or r.path.startswith("/f/") or r.path.startswith("/pub/")})
print()
for c in caminhos:
    print("  rota:", c)

from movizap import telas as registro  # noqa: E402

frm = [t for t in registro.TELAS if t["codigo"] == "FRM_1.1"]
print("\\nFRM_1.1 no registro:", bool(frm),
      "| grupo:", frm[0]["grupo"] if frm else "-",
      "| permissao:", frm[0]["permissao"] if frm else "-")
