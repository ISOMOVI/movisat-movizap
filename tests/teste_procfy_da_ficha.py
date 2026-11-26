# -*- coding: utf-8 -*-
r"""O PROCFY PEGA O QUE A FICHA DO TÉCNICO SABE — 25/11.

🔵 Ele: *"do procfy da para pegar esses dados da ficha do tecnico se tiver, se
não sai em branco mesmo"*.

📏 Medido antes de escrever: o elo é `contato.harmonit_tecnico_id`; a ficha
(`tecnico_ficha`, 289 linhas) tem `pagamento_forma` e `pagamento_dados`; e
**0 das 289** estão preenchidas hoje. Então estas travas prendem o CAMINHO: no
dia em que alguém preencher a ficha, o arquivo sai preenchido sem tocar em
código — e se o caminho quebrar, elas reprovam.

🚨 **O DUBLÊ FICA NA BORDA** (`feedback_duplo_se_poe_na_borda`): o que se troca
é a CONSULTA (`banco.um`), e a regra — a ficha ganhar do `/config`, campo vazio
não apagar valor existente, categoria e centro de custo continuarem em branco —
roda de verdade.
"""
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from movizap import fpsl_ponte  # noqa: E402

FRANCK = 14262
# 🚨 A lista vem DO CÓDIGO, não da minha memória: ela tem `procfy_tags` além
# das quatro, e escrever a minha versão aqui fez esta trava reprovar um
# comportamento certo (`feedback_pendencia_se_mede_nao_se_copia`).
CHAVES = fpsl_ponte.CHAVES_DO_PROCFY


@pytest.fixture
def ficha(monkeypatch):
    """A borda: o que o banco devolveria para aquele técnico."""
    estado = {"linha": None, "pedidos": []}

    def duble(sql, params=()):
        estado["pedidos"].append((" ".join(sql.split()), params))
        return estado["linha"]

    monkeypatch.setattr(fpsl_ponte.banco, "um", duble)
    return estado


def teste_a_ficha_preenchida_vira_as_colunas_do_procfy(ficha):
    ficha["linha"] = {"pagamento_forma": "PIX",
                      "pagamento_dados": "19998887766"}
    achado = fpsl_ponte.procfy_da_ficha(FRANCK)
    assert achado == {"procfy_modo_pagamento": "PIX",
                      "procfy_conta_bancaria": "19998887766"}
    # 🚨 A consulta vai pelo ELO medido, não por adivinhação de nome.
    sql, params = ficha["pedidos"][0]
    assert "harmonit_tecnico_id" in sql
    assert "tecnico_ficha" in sql and "contato" in sql
    assert params == (FRANCK,)


def teste_campo_VAZIO_nao_entra_e_nao_apaga_o_config(ficha):
    """⚠️ "não sei" não pode sobrescrever "sei"."""
    ficha["linha"] = {"pagamento_forma": "   ", "pagamento_dados": None}
    assert fpsl_ponte.procfy_da_ficha(FRANCK) == {}

    cfg = {c: "" for c in CHAVES}
    cfg["procfy_conta_bancaria"] = "conta do /config"
    saida = fpsl_ponte._config_do_procfy(cfg, FRANCK)
    assert saida["procfy_conta_bancaria"] == "conta do /config"


def teste_sem_ficha_nenhuma_sai_em_branco(ficha):
    """🔵 *"se não tiver, sai em branco mesmo"* — e isso não é erro."""
    ficha["linha"] = None
    assert fpsl_ponte.procfy_da_ficha(FRANCK) == {}
    saida = fpsl_ponte._config_do_procfy({c: "" for c in CHAVES}, FRANCK)
    assert saida == {c: "" for c in CHAVES}


def teste_a_ficha_GANHA_do_config_global(ficha):
    """🚨 Dado por técnico é mais específico que um valor para todos."""
    ficha["linha"] = {"pagamento_forma": "TED", "pagamento_dados": "ag 1 cc 2"}
    cfg = {"procfy_categoria": "Serviços",
           "procfy_conta_bancaria": "conta geral",
           "procfy_modo_pagamento": "Boleto",
           "procfy_centro_de_custo": "Operação"}
    saida = fpsl_ponte._config_do_procfy(cfg, FRANCK)
    assert saida["procfy_modo_pagamento"] == "TED"
    assert saida["procfy_conta_bancaria"] == "ag 1 cc 2"
    # ⚠️ E o que a ficha NÃO sabe fica como estava.
    assert saida["procfy_categoria"] == "Serviços"
    assert saida["procfy_centro_de_custo"] == "Operação"


def teste_categoria_e_centro_de_custo_NUNCA_vem_da_ficha(ficha):
    """📏 Medido: a `tecnico_ficha` não tem esses dois campos. Se alguém os
    acrescentar algum dia, que seja por decisão dele -- não por acidente."""
    ficha["linha"] = {"pagamento_forma": "PIX", "pagamento_dados": "x",
                      "categoria": "inventada", "centro_de_custo": "inventado"}
    achado = fpsl_ponte.procfy_da_ficha(FRANCK)
    assert "procfy_categoria" not in achado
    assert "procfy_centro_de_custo" not in achado


def teste_tecnico_sem_id_nao_consulta_o_banco(ficha):
    """⚠️ Card sem técnico (o da Movisat, por exemplo) não vira consulta."""
    for vazio in (None, 0, "", "abc"):
        assert fpsl_ponte.procfy_da_ficha(vazio) == {}
    assert ficha["pedidos"] == []


def teste_a_previa_e_o_arquivo_usam_a_MESMA_config(monkeypatch):
    """🚨 Prévia que mostra coluna vazia e arquivo que sai preenchido é a tela
    mentindo sobre o que vai acontecer."""
    vistos = []
    monkeypatch.setattr(fpsl_ponte, "_pagamento",
                        lambda caminho, corpo: vistos.append((caminho, corpo)))
    monkeypatch.setattr(fpsl_ponte, "procfy_da_ficha",
                        lambda tid: {"procfy_modo_pagamento": "PIX"})
    cfg = {c: "" for c in CHAVES}
    fpsl_ponte.previa_do_arquivo(7, cfg=cfg, tecnico_id=FRANCK)
    fpsl_ponte.montar_arquivo(7, por="Iago", cfg=cfg, tecnico_id=FRANCK)
    assert vistos[0][1]["config"] == vistos[1][1]["config"]
    assert vistos[0][1]["config"]["procfy_modo_pagamento"] == "PIX"
