# -*- coding: utf-8 -*-
"""O ciclo inteiro de Compras numa COPIA, com as quatro colunas. 27/11.

🚨 Roda contra `MOVIZAP_DB_NOME` -- aponte para a copia ANTES de chamar:

    MOVIZAP_DB_NOME=movizap_ontem_2711 venv/bin/python scripts/ensaio_123.py

⚠️ ELE LIGA O FORMULARIO NA COPIA, e isso e legitimo aqui: em producao ligar e
gesto dele, e esta base e descartavel. A ultima linha confere que a producao
NAO foi tocada.

O que prova, em ordem: validar -> registrar -> etapa_de_destino -> criar ->
quadro -> MOVER para a coluna 2 -> reler o estado.
"""
import os
import sys

sys.path.insert(0, "/home/claude/movizap_painel")

BANCO = os.environ.get("MOVIZAP_DB_NOME", "")
if not BANCO.endswith("_2711"):
    raise SystemExit(
        "RECUSADO: MOVIZAP_DB_NOME e '" + (BANCO or "(vazio)") + "'. "
        "Este ensaio escreve, e so roda em banco de copia (sufixo _2711).")

from movizap import banco, formularios, paineis, pipeline  # noqa: E402

banco.abrir()


def passo(titulo):
    print("\n--- " + titulo + " ---")


passo("o formulario, ligado SO nesta copia")
banco.executar("UPDATE formulario SET ativo = true WHERE codigo = 'COMPRAS'")
d = formularios.definicao("compras")
print("campos:", [c["nome"] for c in d["campos"]])
print("interno:", d["interno"], "| gera_os:", d["gera_os"])

passo("validar -- a validacao do SERVIDOR, com o valor")
enviados = {
    "SUGESTAO": "Cabo de rede cat6, 20 metros, para o rack da sala 2",
    "VALOR": "R$ 184,00",
    "CONTACT_NAME": "Iago (do ensaio)",
}
limpo = formularios.validar(d, enviados, {})
print("limpo:", limpo)

passo("registrar")
r = formularios.registrar(d, limpo, [], ip=None)
print("solicitacao:", r["id"])

passo("etapa_de_destino -> pipeline.criar")
destino = formularios.etapa_de_destino("compras")
print("destino:", destino["titulo"] if destino else None)
card = pipeline.criar(destino["aba_id"], destino["id"],
                      solicitacao_id=r["id"], cliente_id=None,
                      atendente_id=None)
print("card:", card["id"])

passo("o quadro, como a tela o recebe")
q = paineis.quadro_da_aba("PNL_1.7", so_abertas=False)
print("painel:", q["painel"], "| titulo:", q["titulo"],
      "| pode_mover:", q["pode_mover"])
for col in q["colunas"]:
    print("  coluna:", col["ordem"] if "ordem" in col else "",
          col["titulo"], "| total:", col["total"], "| final:", col["final"])
print("etapas que o <select> oferece:", [e["titulo"] for e in q["etapas"]])

achado = None
for col in q["colunas"]:
    for c in col["cards"]:
        if c["id"] == card["id"]:
            achado = c
if not achado:
    raise SystemExit("o card nao apareceu no quadro")
print("\nO CARD FECHADO:")
for chave in ("origem", "cliente", "resumo", "formulario", "anexos",
              "numero_os", "numero_ordem", "situacao_id", "etapa_id"):
    print(f"  {chave:14s} = {achado.get(chave)!r}")

passo("🚨 O GESTO NOVO: mover para a coluna 2")
segunda = [e for e in q["etapas"] if e["titulo"] == "Em cotação"][0]
pipeline.mover(card["id"], segunda["id"], atendente_id=None)

passo("o ESTADO relido, nao o retorno")
linha = banco.um(
    """SELECT c.id, e.titulo AS etapa, e.ordem, e.final,
              (SELECT count(*) FROM pipeline_passagem p
                WHERE p.card_id = c.id) AS passagens
         FROM pipeline_card c JOIN pipeline_etapa e ON e.id = c.etapa_id
        WHERE c.id = %s""", (card["id"],))
print("card agora:", linha)
if linha["etapa"] != "Em cotação":
    raise SystemExit("o card NAO mudou de coluna")
if linha["passagens"] < 2:
    raise SystemExit("a passagem nao foi gravada -- o historico ficaria mudo")

passo("e a ultima coluna FECHA o card")
ultima = [e for e in q["etapas"] if e["titulo"] == "Comprado"][0]
pipeline.mover(card["id"], ultima["id"], atendente_id=None)
linha = banco.um(
    """SELECT e.titulo AS etapa, e.final FROM pipeline_card c
         JOIN pipeline_etapa e ON e.id = c.etapa_id WHERE c.id = %s""",
    (card["id"],))
print("card no fim:", linha)
if not linha["final"]:
    raise SystemExit("a ultima coluna nao e final -- o card nao tem desfecho")

passo("a PRODUCAO nao foi tocada")
print("banco deste ensaio:", BANCO)
banco.fechar()
print("\nENSAIO OK")
