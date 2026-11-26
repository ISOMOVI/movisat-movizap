"""Patch do `main.py`: as duas rotas do anexo do comprovante (aba 2, 25/11).

🚨 PATCH POR SCRIPT PORQUE PRECISA VALIDAR ANTES DE GRAVAR (`M8`): cada troca
exige a âncora **exata e única**; se qualquer uma faltar ou aparecer duas
vezes, nada é gravado e o script diz qual. É o molde dos `editar_*.py` que este
projeto já usa.

🚨 **ORDEM DE REGISTRO**, e isto já custou dois 400 em 19/11: as duas rotas
novas entram **dentro do bloco da `PNL_1.6`**, antes do `{caminho:path}` da SPA
(hoje na 7198). O curinga `/api/paineis/{painel}` (5525) não as alcança — ele é
GET de **um** segmento, e estas têm quatro.
"""
import pathlib
import shutil
import sys
from datetime import datetime

ALVO = pathlib.Path("/home/claude/movizap_painel/movizap/main.py")

IMPORT_DE = "from . import passagem\n"
IMPORT_PARA = "from . import pagamento_anexo\nfrom . import passagem\n"

# ---------------------------------------------------------------- o ajudante
AJUDANTE_DE = '''@app.post("/api/paineis/servico-dos-tecnicos/comprovante")'''

AJUDANTE_PARA = '''def _artefato_no_quadro(artefato_id: int) -> dict:
    """O artefato de pagamento, achado NO QUADRO — ou 404 com a frase.

    🚨 **O QUADRO É A ÚNICA PORTA.** Não existe consulta por id solto: quem
    alcança a `PNL_1.6` só mexe no que já está no quadro dela, e é esta função
    que cobra isso. Sem ela, um id digitado na URL alcançaria artefato de outro
    corte de data -- e, no caso do anexo, gravaria comprovante num artefato que
    a tela nem mostra.

    ⚠️ **502, não quadro vazio**, quando o FPSL não responde: vazio silencioso
    faria o operador concluir que o artefato não existe.
    """
    try:
        quadro = fpsl_ponte.quadro_do_pagamento()
    except fpsl_ponte.FpslIndisponivel as e:
        raise HTTPException(status_code=502, detail=str(e))
    for coluna in quadro.get("colunas") or []:
        for card in coluna.get("cards") or []:
            for a in card.get("artefatos") or []:
                if int(a.get("id") or 0) == artefato_id:
                    return a
    raise HTTPException(
        status_code=404,
        detail="Este artefato de pagamento não está no quadro.")


@app.post("/api/paineis/servico-dos-tecnicos/anexo/{artefato_id}",
          status_code=201)
async def anexar_comprovante_do_servico(
        artefato_id: int, arquivo: UploadFile = File(...),
        usuario: dict = Depends(auth.requer_tela("PNL_1.6"))):
    """O comprovante do pagamento, em arquivo.

    🔵 *"haverá campo para que em cada 1 dos artefatos de pagamento seja
    inserido anexo que comprove o pagamento"*, e 🔵 24/11: **anexo completo,
    não só PDF**.

    🚨 **A TELA RECEBE UM ID, NUNCA UM CAMINHO** -- a régua dos outros três
    anexos do projeto: caminho vindo da tela faria `../../.env` virar anexo.

    🚨 **O ARTEFATO É CONFERIDO PELO QUADRO ANTES DE GRAVAR**: ele vive no
    SQLite do FPSL e esta tabela é Postgres, então não há chave estrangeira
    para recusar id inventado -- a recusa é esta.

    ⚠️ Devolve também a `referencia` (`anexo:<id>`), que é o que a tela manda
    no passo seguinte para o `comprovante` guardar no FPSL. Nenhum byte
    atravessa a ponte.
    """
    _artefato_no_quadro(artefato_id)
    dados = await arquivo.read()
    linha = pagamento_anexo.guardar(artefato_id, arquivo.filename, dados,
                                    arquivo.content_type,
                                    por=usuario.get("nome"))
    return {"ok": True, "id": linha["id"],
            "nome_original": linha["nome_original"], "bytes": linha["bytes"],
            "referencia": pagamento_anexo.referencia(linha["id"])}


@app.get("/api/paineis/servico-dos-tecnicos/anexo/{anexo_id}")
def baixar_comprovante_do_servico(
        anexo_id: int,
        usuario: dict = Depends(auth.requer_tela("PNL_1.6"))):
    """O arquivo do comprovante.

    🚨 **410, NÃO 500, QUANDO O ARQUIVO SUMIU DO DISCO** -- e isso acontece:
    esta pasta **não tem backup**, como as outras três de anexo. A linha no
    banco sobrevive ao que o disco perdeu, e a tela precisa dizer "o arquivo
    não está mais aqui" em vez de estourar. É a régua do
    `/api/paineis/operacao/anexo/{anexo_id}`.
    """
    achado = pagamento_anexo.anexo(anexo_id)
    if not achado:
        raise HTTPException(status_code=404, detail="Anexo não encontrado.")
    caminho = pathlib.Path(achado["caminho"])
    if not caminho.is_file():
        raise HTTPException(
            status_code=410,
            detail="O arquivo não está mais no disco. Esta pasta não tem "
                   "backup -- o registro ficou, o arquivo não.")
    return FileResponse(caminho, filename=achado["nome_original"],
                        media_type=achado["mime"] or "application/octet-stream")


@app.post("/api/paineis/servico-dos-tecnicos/comprovante")'''

# ------------------------------------------------- o quadro leva os anexos
QUADRO_DE = '''    quadro["titulo"] = "Serviço dos técnicos"
    return quadro'''

QUADRO_PARA = '''    quadro["titulo"] = "Serviço dos técnicos"
    # 🚨 O NOME E O TAMANHO DO ANEXO SAEM DAQUI, NÃO DE UMA CHAMADA POR CARD.
    # O FPSL guarda só a referência (`anexo:<id>`) no `comprovante_arquivo`;
    # quem sabe o nome do arquivo é este lado. Uma consulta para o quadro
    # inteiro, no molde do `anexos_de` da Operação -- por card seria N+1 num
    # quadro de 9 cards que vai crescer.
    # ⚠️ O `caminho` NÃO vai para a tela: quem baixa usa o id.
    _anexar_comprovantes_no_quadro(quadro)
    return quadro


def _anexar_comprovantes_no_quadro(quadro: dict) -> None:
    """Põe `comprovante_anexo` (nome, bytes) em cada artefato que tem arquivo.

    ⚠️ Referência torta no FPSL **não derruba o quadro**: o artefato fica sem
    o bloco do anexo e a tela segue mostrando o resto. Quadro que estoura por
    causa de um campo de texto seria pior que o campo errado.
    """
    por_id: dict = {}
    for coluna in quadro.get("colunas") or []:
        for card in coluna.get("cards") or []:
            for a in card.get("artefatos") or []:
                bruto = str(a.get("comprovante_arquivo") or "")
                if not bruto.startswith("anexo:"):
                    continue
                try:
                    por_id.setdefault(int(bruto.split(":", 1)[1]), []).append(a)
                except (TypeError, ValueError):
                    continue
    if not por_id:
        return
    for linha in banco.varios(
            """SELECT id, nome_original, bytes, mime
                 FROM pagamento_comprovante_arquivo WHERE id = ANY(%s)""",
            (list(por_id),)):
        for a in por_id.get(linha["id"], []):
            a["comprovante_anexo"] = {"id": linha["id"],
                                      "nome_original": linha["nome_original"],
                                      "bytes": linha["bytes"],
                                      "mime": linha["mime"]}'''

TROCAS = [("o import do módulo do anexo", IMPORT_DE, IMPORT_PARA),
          ("as duas rotas e o ajudante do quadro", AJUDANTE_DE, AJUDANTE_PARA),
          ("o quadro levando nome e tamanho do anexo", QUADRO_DE, QUADRO_PARA)]


def main() -> int:
    texto = ALVO.read_text(encoding="utf-8")
    for rotulo, de, _para in TROCAS:
        vezes = texto.count(de)
        if vezes != 1:
            print(f"ABORTADO em '{rotulo}': a ancora aparece {vezes} vezes, "
                  f"e tem de aparecer 1. Nada foi gravado.", file=sys.stderr)
            return 1
    novo = texto
    for _rotulo, de, para in TROCAS:
        novo = novo.replace(de, para, 1)

    marca = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    copia = ALVO.with_suffix(ALVO.suffix + f".bak_{marca}_anexo_comprovante")
    shutil.copy2(ALVO, copia)
    ALVO.write_text(novo, encoding="utf-8")
    print(f"copia de seguranca: {copia}")
    print(f"linhas: {len(texto.splitlines())} -> {len(novo.splitlines())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
