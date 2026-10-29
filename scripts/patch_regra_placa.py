# -*- coding: utf-8 -*-
"""Patch 29/10 (parte 8): A REGRA DA PLACA.

🔵 Regra dele, dita em uma linha: *"so e possivel abrir chamados para placas
ativas na weso. o match e basicamente de 100% mesmo. essa e a regra"*.

🚨 ISTO INVERTE O QUE EU TINHA ESCRITO. Eu havia tratado a lista como
SUGESTAO -- *"lista nossa incompleta nao pode barrar chamado"* -- e a frase
dele diz o contrario: a placa ativa na WESO e a condicao do chamado. Entao a
lista passa a ser a REGRA, e a digitacao passa a ser CONFERIDA contra a WESO em
vez de aceita de olhos fechados.

🚨 E A MINHA CONTA DE 95% ESTAVA GROSSEIRA. Medido hoje, normalizando a placa
dos dois lados (maiuscula, sem espaco e sem traco), das 1.998 linhas da WESO:
  · 1.918 casam com o Harmonit;
  · 50 NAO SAO PLACA -- a coluna `placa` da WESO tem chassi e numero de serie
    (`9BM951104TB416686`, `292054068`);
  · 30 sao placa de verdade que o Harmonit nao tem.
Ou seja: entre as que SAO placa, o casamento e 1.918 de 1.948 = **98,5%**, e os
80 restantes nao sao "cliente sem cadastro", sao **dado sujo de um lado so**.
A frase dele sobre "basicamente 100%" bate com o dado; o meu "1 em 20 vai
digitar" nao batia.

⚠️ POR QUE A CONFERENCIA NAO ENTRA NO `validar`: `validar` e sincrono, puro e
roda na suite sem rede. Pendurar nele uma chamada HTTP a outro servico faria
1.874 testes dependerem do FPSL de pe. A conferencia mora na ROTA, ao lado da
guarda de anexo.

🚨 E SE A PONTE CAIR, O CHAMADO PASSA -- marcado. Recusar por causa de uma
indisponibilidade NOSSA seria transformar o nosso problema no problema do
cliente. A solicitacao guarda `placas_conferidas: false`, e quem atende ve.
"""
import pathlib
import sys

FPSL = pathlib.Path("/home/claude/fpsl_weso")
MOVI = pathlib.Path("/home/claude/movizap_painel")


def trocar(caminho: pathlib.Path, velho: str, novo: str, rotulo: str) -> None:
    texto = caminho.read_text(encoding="utf-8")
    if novo in texto:
        print(f"  = {rotulo}: ja aplicado")
        return
    if texto.count(velho) != 1:
        sys.exit(f"  ! {rotulo}: achei {texto.count(velho)} ocorrencias, "
                 f"esperava 1 -- PAREI sem gravar nada")
    caminho.write_text(texto.replace(velho, novo), encoding="utf-8")
    print(f"  + {rotulo}")


# ---------------------------------------------------------------------------
# 1. O FPSL responde se a placa esta ativa
# ---------------------------------------------------------------------------
p = FPSL / "fpsl_weso" / "routers" / "os_ponte.py"
print(p.name)
trocar(p, '''@router.get("/clientes-com-os")''',
       '''@router.post("/placas-ativas/conferir")
async def conferir_placas_ativas(corpo: dict):
    """Quais destas placas estão ATIVAS na WESO. 🔵 Regra dele, 29/10: *"só é
    possível abrir chamados para placas ativas na weso"*.

    🚨 QUEM DIZ "ATIVA" É A WESO, SOZINHA -- e aqui está a diferença em relação
    a `/placas-ativas`: lá o Harmonit entra para dizer **de quem** é a placa;
    aqui a pergunta é outra, *"esta placa tem rastreador instalado?"*, e isso é
    só WESO. Exigir o Harmonit nesta conferência recusaria as **30 placas**
    (medido em 29/10) que estão ativas na WESO e **não** estão no cadastro do
    Harmonit -- e pela regra dele essas podem abrir chamado.

    ⚠️ A CHAVE É NORMALIZADA (maiúscula, só letra e dígito), porque a WESO
    grava `BYL 2170` e a pessoa digita `byl-2170`.

    Devolve `{"placas": {<como veio>: {ativa, apelido}}}` -- a chave é o texto
    que o cliente escreveu, para quem chamou não ter de casar de volta.
    """
    pedidas = [str(x) for x in (corpo.get("placas") or [])][:50]
    if not pedidas:
        return {"placas": {}}

    def so_alfanum(texto: str) -> str:
        return "".join(c for c in (texto or "").upper() if c.isalnum())

    with storage._connect() as conn:
        linhas = conn.execute(
            "SELECT placa, apelido FROM weso_equipamentos "
            " WHERE placa IS NOT NULL AND trim(placa) <> ''").fetchall()
    ativas = {so_alfanum(placa): (apelido or "").strip() or None
              for placa, apelido in linhas}

    # 🚨 A PESSOA PODE ESCREVER "SAVEIRO ABC1234", e isso é resposta certa: o
    # campo pede *"Veículo e Placa"*. Então procura-se cada pedaço do texto,
    # não só o texto inteiro.
    saida = {}
    for escrito in pedidas:
        achou = None
        pedacos = [so_alfanum(t) for t in escrito.replace("-", " ").split()]
        for pedaco in [so_alfanum(escrito), *pedacos]:
            if pedaco in ativas:
                achou = pedaco
                break
        saida[escrito] = {"ativa": achou is not None,
                          "apelido": ativas.get(achou) if achou else None}
    return {"placas": saida}


@router.get("/clientes-com-os")''',
       "fpsl: rota /api/os/placas-ativas/conferir")

# ---------------------------------------------------------------------------
# 2. A ponte
# ---------------------------------------------------------------------------
b = MOVI / "movizap" / "fpsl_ponte.py"
print(b.name)
trocar(b, '''def _postar(caminho: str, corpo: dict) -> dict:''',
       '''def conferir_placas(placas: list[str]) -> dict:
    """`{placa escrita: {ativa, apelido}}`. 🔵 Regra dele: chamado só para placa
    ativa na WESO.

    🚨 Erro NÃO vira "nenhuma ativa": sobe `FpslIndisponivel`, e quem chama
    decide -- e a decisão tomada na rota é **deixar passar marcado**, porque
    indisponibilidade nossa não pode barrar o chamado do cliente.
    """
    corpo = _postar("/api/os/placas-ativas/conferir", {"placas": placas})
    return corpo.get("placas") or {}


def _postar(caminho: str, corpo: dict) -> dict:''',
       "movizap: ponte conferir_placas")

print()
print("ok -- falta a rota e a tela")
