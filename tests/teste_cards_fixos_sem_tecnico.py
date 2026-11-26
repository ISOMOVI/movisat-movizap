# -*- coding: utf-8 -*-
r"""OS DOIS CARDS FIXOS DO SEM-TECNICO — 25/11.

🔵 Ele: *"vamos montar cards fixos para esses casos? 'SEM IDENTIFICACAO' como
ja tem e 'NAO CADASTRADOS NO HARMONIT' para os sem cadastro - o que nao impede
em juntar as demais informacoes corretamente, pois em caso de correcao e
atualizacao, o card ja direciona"*.
🔵 E, sobre quem tem vinculo mas a OS do Harmonit nao: *"iria para o tipo sem
tecnico que coloquei, e como se fosse um provisorio que satisfaz mas que nao
frequenta OS harmonit"*.
🔵 E sobre pagar: *"nao conhecidos nao paga isso, e nem sem identificacao"*.

📏 MEDIDO antes de escrever: hoje ha **uma** OS sem tecnico no quadro, a 17133,
e o nosso agendamento sabe quem foi -- Jonas Claudio dos Santos (contato
127322), com `harmonit_tecnico_id` **nulo**. E o caso puro do segundo card, por
dado e nao por suposicao.

🚨 O FPSL NAO MUDA: o `tecnico_id` do artefato segue **nulo**, que e a verdade
(o Harmonit nao sabe). A divisao e de APRESENTACAO, deste lado, onde o
agendamento mora. E quando a OS do Harmonit ganhar o tecnico, a varredura
**adota** e o artefato muda de card sozinho -- a adocao e a mesma que consertou
a 17131.

🚨 O DUBLE FICA NA BORDA: o que se troca e a CONSULTA do agendamento
(`banco.varios`). A regra -- quem vai para qual card, o nome provisorio por
artefato, os dois com `pode_preparar` falso -- roda de verdade.

Roda:  venv/bin/python -m pytest tests/teste_cards_fixos_sem_tecnico.py
"""
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from movizap import main  # noqa: E402

SEM_ID = "sem técnico identificado"
SEM_CADASTRO = "não cadastrados no Harmonit"


def _quadro(*artefatos_sem_tecnico, com_tecnico=()):
    """Um quadro no formato que o FPSL devolve, com a coluna 1 montada."""
    cards = []
    if com_tecnico:
        cards.append({"tecnico_id": 14262, "tecnico_nome": "Franck",
                      "pode_preparar": True, "total_pagamento": 100.0,
                      "total_km": 0.0, "artefatos": list(com_tecnico)})
    if artefatos_sem_tecnico:
        cards.append({"tecnico_id": None, "tecnico_nome": SEM_ID,
                      "pode_preparar": False, "total_pagamento": 0.0,
                      "total_km": 0.0,
                      "artefatos": list(artefatos_sem_tecnico)})
    return {"colunas": [{"chave": "movimentacao", "cards": cards},
                        {"chave": "preparacao", "cards": []}]}


def _art(numero, valor=10.0, km=0.0):
    return {"id": numero, "numero_os": numero, "tecnico_id": None,
            "valor_pagamento": valor, "valor_km": km}


def _cards(quadro):
    return {c["tecnico_nome"]: c for c in quadro["colunas"][0]["cards"]}


@pytest.fixture
def agendamentos(monkeypatch):
    """A borda: o que o nosso agendamento sabe, por OS."""
    estado = {"por_os": {}, "pedidos": []}

    def duble(sql, params=()):
        estado["pedidos"].append((" ".join(sql.split()), params))
        numeros = params[0] if params else []
        return [{"numero_os": n, "nome": nome,
                 "harmonit_tecnico_id": vinculo}
                for n, (nome, vinculo) in estado["por_os"].items()
                if n in numeros]

    monkeypatch.setattr(main.banco, "varios", duble)
    return estado


def teste_quem_o_NOSSO_agendamento_conhece_vai_para_o_card_novo(agendamentos):
    """🔵 O caso da 17133, com o nome que o agendamento sabe."""
    agendamentos["por_os"] = {17133: ("Jonas Claudio dos Santos", None)}
    q = _quadro(_art(17133, valor=89.10))
    main._dividir_sem_tecnico(q)
    cards = _cards(q)
    assert SEM_CADASTRO in cards
    assert SEM_ID not in cards, "ninguém sobrou para o card antigo"
    novo = cards[SEM_CADASTRO]
    assert [a["numero_os"] for a in novo["artefatos"]] == [17133]
    # 🚨 O NOME FICA NO ARTEFATO, não no card: o card é FIXO e pode juntar
    # vários provisórios diferentes -- um nome no título mentiria a partir do
    # segundo.
    assert novo["artefatos"][0]["tecnico_provisorio"] == "Jonas Claudio dos Santos"
    assert novo["total_pagamento"] == pytest.approx(89.10)


def teste_quem_NINGUEM_conhece_fica_no_card_de_sempre(agendamentos):
    agendamentos["por_os"] = {}
    q = _quadro(_art(99001))
    main._dividir_sem_tecnico(q)
    cards = _cards(q)
    assert SEM_ID in cards and SEM_CADASTRO not in cards
    assert "tecnico_provisorio" not in cards[SEM_ID]["artefatos"][0]


def teste_o_card_SE_PARTE_quando_ha_dos_dois_tipos(agendamentos):
    """⚠️ Um card só com OS de origens diferentes era o que escondia o caso: a
    divisão é por ARTEFATO, não por card."""
    agendamentos["por_os"] = {17133: ("Jonas", None)}
    q = _quadro(_art(17133, valor=89.10), _art(99001, valor=50.0))
    main._dividir_sem_tecnico(q)
    cards = _cards(q)
    assert set(cards) == {SEM_ID, SEM_CADASTRO}
    assert [a["numero_os"] for a in cards[SEM_CADASTRO]["artefatos"]] == [17133]
    assert [a["numero_os"] for a in cards[SEM_ID]["artefatos"]] == [99001]
    assert cards[SEM_CADASTRO]["total_pagamento"] == pytest.approx(89.10)
    assert cards[SEM_ID]["total_pagamento"] == pytest.approx(50.0)


def teste_quem_TEM_vinculo_tambem_vai_para_o_card_novo(agendamentos):
    """🔵 *"iria para o tipo sem tecnico que coloquei, e como se fosse um
    provisorio que satisfaz mas que nao frequenta OS harmonit"*. Ter vínculo
    com o Harmonit não muda o card: o que falta é o técnico NA OS."""
    agendamentos["por_os"] = {17140: ("Alguém Vinculado", 14262)}
    q = _quadro(_art(17140))
    main._dividir_sem_tecnico(q)
    assert SEM_CADASTRO in _cards(q)


def teste_NENHUM_DOS_DOIS_PAGA(agendamentos):
    """🔵 *"nao conhecidos nao paga isso, e nem sem identificacao"*."""
    agendamentos["por_os"] = {17133: ("Jonas", None)}
    q = _quadro(_art(17133), _art(99001))
    main._dividir_sem_tecnico(q)
    for nome, card in _cards(q).items():
        assert card["pode_preparar"] is False, nome
        assert card["tecnico_id"] is None, nome


def teste_o_card_COM_tecnico_nao_e_tocado(agendamentos):
    """🚨 A divisão não pode encostar em quem tem a quem pagar."""
    agendamentos["por_os"] = {17133: ("Jonas", None)}
    com = [{"id": 1, "numero_os": 17120, "tecnico_id": 14262,
            "valor_pagamento": 100.0, "valor_km": 0.0}]
    q = _quadro(_art(17133), com_tecnico=com)
    main._dividir_sem_tecnico(q)
    cards = _cards(q)
    assert cards["Franck"]["pode_preparar"] is True
    assert cards["Franck"]["artefatos"] == com


def teste_sem_OS_sem_tecnico_nao_consulta_o_banco(agendamentos):
    """⚠️ Quadro sem card de sem-técnico não vira consulta -- é o estado normal
    do dia em que todo mundo estiver identificado."""
    com = [{"id": 1, "numero_os": 17120, "tecnico_id": 14262,
            "valor_pagamento": 100.0, "valor_km": 0.0}]
    q = _quadro(com_tecnico=com)
    main._dividir_sem_tecnico(q)
    assert agendamentos["pedidos"] == []
    assert len(q["colunas"][0]["cards"]) == 1


def teste_a_consulta_vai_pelo_elo_medido(agendamentos):
    """📏 `agendamento_os.numero_os` -> `agendamento.tecnico_contato_id` ->
    `contato`. Se alguém trocar o elo por adivinhação, isto reprova."""
    agendamentos["por_os"] = {17133: ("Jonas", None)}
    q = _quadro(_art(17133))
    main._dividir_sem_tecnico(q)
    sql, params = agendamentos["pedidos"][0]
    assert "agendamento_os" in sql and "tecnico_contato_id" in sql
    assert "contato" in sql
    assert params == ([17133],)


def teste_banco_mudo_nao_derruba_o_quadro(monkeypatch):
    """🚨 Quadro vazio NUNCA (a razão da coluna 1 existir). Se a consulta do
    agendamento falhar, o card antigo fica inteiro e a tela segue."""
    def explode(sql, params=()):
        raise RuntimeError("banco fora")
    monkeypatch.setattr(main.banco, "varios", explode)
    q = _quadro(_art(17133), _art(99001))
    main._dividir_sem_tecnico(q)
    cards = _cards(q)
    assert SEM_ID in cards
    assert len(cards[SEM_ID]["artefatos"]) == 2
