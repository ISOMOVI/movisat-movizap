# -*- coding: utf-8 -*-
"""Patch 29/10 (parte 7): as PLACAS ATIVAS do cliente no formulario.

🔵 Pedido dele: *"se ja tem o cliente validado, ja podemos trazer no campo de
veiculo placa os veiculos que ele tem ativo na Weso, se nao me engano temos uma
rotina que roda isso [...] se for pelo movizap, ja tem como trazer e se for
manual, tbm ja tem a esse ponto"* -- e *"ter um botao de 'meu veiculo nao esta
na lista' onde ele pode digitar a placa"*.

🚨 A ROTINA EXISTE, E A WESO SOZINHA NAO SERVE -- medido em 23/10 e reconfirmado
hoje:
  · `harmonit_veiculos` (9.114 placas) e quem sabe DE QUEM e a placa
    (`clienteId`); a WESO **nao tem cliente** (`cliente_id` nulo nos 1.9k);
  · `weso_equipamentos` (1.998) e quem diz que a placa esta ATIVA -- e quem tem
    rastreador instalado --, e e quem tem o APELIDO ("SAVEIRO / BRUNO").
Entao a lista e o CRUZAMENTO das duas, e e por isso que ela nasce no FPSL (onde
as duas bases vivem) e nao no MoviZap.

🚨 LISTA VAZIA E FPSL FORA DO AR SAO COISAS DIFERENTES. A ponte sobe falha como
`FpslIndisponivel` e a tela diz que nao deu para consultar -- nunca "voce nao
tem veiculo".
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
# 1. O FPSL passa a responder as placas ativas de um cliente
# ---------------------------------------------------------------------------
p = FPSL / "fpsl_weso" / "routers" / "os_ponte.py"
print(p.name)
trocar(p, '''@router.get("/clientes-com-os")''',
       '''@router.get("/placas-ativas")
async def placas_ativas_do_cliente(
    cliente_id: int = Query(..., description="id do cliente NO HARMONIT"),
):
    """As placas que o cliente tem ATIVAS, para o formulário do MoviZap.

    🔵 Pedido dele em 29/10, no formulário de Suporte: trazer os veículos que o
    cliente tem ativos na WESO em vez de pedir que ele digite a placa.

    🚨 SÃO DUAS BASES, E NENHUMA RESPONDE SOZINHA (medido em 23/10):
      · quem sabe **de quem** é a placa é o Harmonit (`harmonit_veiculos`,
        9.114 linhas, com `clienteId`);
      · quem diz que a placa está **ativa** é a WESO (`weso_equipamentos`,
        1.998) -- é ela que tem rastreador instalado --, e é ela que tem o
        **apelido** ("SAVEIRO / BRUNO"), que o Harmonit não tem (lá o nome é o
        modelo, "Ford Courier").
    Por isso a lista é o cruzamento, e por isso ela nasce aqui: as duas bases
    vivem neste projeto.

    ⚠️ A CHAVE DE PLACA SE NORMALIZA DOS DOIS LADOS (maiúscula, sem espaço e
    sem traço): em 23/10 mediu-se **95%** de cruzamento (1.828 de 1.921), e
    parte do que não casava era espaço no meio da placa.

    Devolve sempre `{"cliente_id", "placas": [...]}`. Lista vazia significa
    "este cliente não tem veículo ativo", e é por isso que o cliente HTTP do
    outro lado nunca converte erro de rede em lista vazia.
    """
    chave = ("upper(replace(replace({c}, ' ', ''), '-', ''))")
    sql = f"""
        SELECT h.placa, h.veiculo, w.apelido
          FROM harmonit_veiculos h
          JOIN weso_equipamentos w
            ON {chave.format(c='w.placa')} = {chave.format(c='h.placa')}
         WHERE h.clienteId = ?
         ORDER BY h.placa
    """
    with storage._connect() as conn:
        linhas = conn.execute(sql, (cliente_id,)).fetchall()

    return {
        "cliente_id": cliente_id,
        "placas": [
            {
                "placa": (placa or "").strip().upper(),
                # ⚠️ O apelido é o que a pessoa reconhece; o modelo do Harmonit
                # é o reforço. Os dois podem vir vazios, e aí sobra a placa --
                # que é o que importa.
                "apelido": (apelido or "").strip() or None,
                "veiculo": (veiculo or "").strip() or None,
            }
            for placa, veiculo, apelido in linhas
        ],
    }


@router.get("/clientes-com-os")''',
       "fpsl: rota /api/os/placas-ativas")

# ---------------------------------------------------------------------------
# 2. A ponte do MoviZap
# ---------------------------------------------------------------------------
b = MOVI / "movizap" / "fpsl_ponte.py"
print(b.name)
trocar(b, '''def _postar(caminho: str, corpo: dict) -> dict:''',
       '''def placas_ativas(harmonit_id: str) -> list[dict]:
    """As placas ativas do cliente, pelo cruzamento Harmonit x WESO do FPSL.

    🚨 Erro NÃO vira lista vazia: sobe `FpslIndisponivel`, e quem chama diz
    "não deu para consultar" em vez de "você não tem veículo" -- a mesma razão
    de `os_do_cliente` existir aqui em vez de um `httpx.get` solto.
    """
    corpo = _pedir("/api/os/placas-ativas", {"cliente_id": int(harmonit_id)})
    return corpo.get("placas") or []


def _postar(caminho: str, corpo: dict) -> dict:''',
       "movizap: ponte placas_ativas")

# ---------------------------------------------------------------------------
# 3. A busca por documento devolve as placas
# ---------------------------------------------------------------------------
f = MOVI / "movizap" / "formularios.py"
print(f.name)
trocar(f, '''    linhas = banco.varios(
        """SELECT nome, nome_fantasia FROM cliente''',
       '''    linhas = banco.varios(
        """SELECT nome, nome_fantasia, harmonit_id FROM cliente''',
       "formularios.py: busca traz o harmonit_id")

trocar(f, '''    # 🚨 MAIS DE UM COM O MESMO DOCUMENTO EXISTE (10 pares na base). A tela diz
    # que há mais de um em vez de escolher calada.
    return {"achou": True, "nome": linhas[0]["nome"],
            "varios": len(linhas) > 1}''',
       '''    # 🚨 MAIS DE UM COM O MESMO DOCUMENTO EXISTE (10 pares na base). A tela diz
    # que há mais de um em vez de escolher calada.
    achado = {"achou": True, "nome": linhas[0]["nome"],
              "varios": len(linhas) > 1}

    # 🔵 As placas ativas, pedido dele em 29/10. ⚠️ `harmonit_id` NÃO SAI na
    # resposta -- é id interno; o que sai são as placas.
    #
    # 🚨 FALHA DA PONTE NÃO VIRA "SEM VEÍCULO": `placas_erro` existe para a
    # tela dizer *"não deu para consultar seus veículos"* e deixar digitar. Um
    # `[]` silencioso faria o cliente concluir que a frota dele saiu do ar.
    if linhas[0]["harmonit_id"]:
        try:
            achado["placas"] = fpsl_ponte.placas_ativas(linhas[0]["harmonit_id"])
        except Exception as e:  # noqa: BLE001 -- qualquer falha da ponte
            log.warning("placas do cliente %s: %s", linhas[0]["harmonit_id"], e)
            achado["placas"] = []
            achado["placas_erro"] = True
    else:
        # ⚠️ 1 dos 960 clientes não tem `harmonit_id` -- cadastro nascido no
        # MoviZap. Sem id não há frota para cruzar, e isso não é erro.
        achado["placas"] = []
    return achado''',
       "formularios.py: busca devolve as placas")

trocar(f, '''from . import banco, ratelimit, telefone''',
       '''from . import banco, fpsl_ponte, ratelimit, telefone''',
       "formularios.py: import da ponte")

print()
print("ok")
