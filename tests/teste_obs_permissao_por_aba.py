# -*- coding: utf-8 -*-
r"""OBSERVAÇÃO: A PERMISSÃO SAI DA ABA DO CARD, E NÃO DA OPERAÇÃO — 27/11.

🔵 Ele, 27/11, decidindo: *"permissões dessa tela devem ficar com as mesmas das
demais -- quem ve usa tudo. E as permissões ficam com a das demais em
CFG_15.1"*.

🚨 **O DEFEITO, MEDIDO.** Em 05/11 as rotas de card passaram a conferir a aba
do PRÓPRIO card em vez de `PNL_1.1` fixo — e o conserto pegou as de escrever,
deixando **três** para trás: anexar na observação, apagar a observação e baixar
o anexo. Resultado: quem tem Contratual, Financeiro, Pós-venda ou Compras
**escreve** observação e toma **403** para anexar, apagar e baixar.

📏 Era invisível porque ele é owner e owner passa por tudo. As observações
**1718** e **1912** são de cards do Contratual (`PNL_1.5`) e provam que o caso
não é hipotético.

⚠️ **O CHECKLIST FICOU DE FORA, E É MEDIÇÃO, NÃO ESQUECIMENTO:** aquelas rotas
são chaveadas por `numero_os` + `situacao_id`, e card de solicitação não tem
OS. Checklist é recurso de OS; passá-lo à aba do card não daria checklist a
Compras, daria uma rota que não resolve nada.

🚨 **E A OS SEM CARD É O RISCO DESTA MUDANÇA.** Medido em 27/11: as
observações recentes de OS (90990, 90996, 17151) **não têm linha em
`pipeline_card`**. Sem um destino para esse caso, elas virariam 403 para todo
mundo — inclusive para o owner — e a Operação quebraria. Daí o recuo para
`PNL_1.1`, que é onde a OS sem card vive.

Roda:  venv/bin/python -m pytest tests/teste_obs_permissao_por_aba.py
"""
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

pytest.importorskip("psycopg")

from fastapi.testclient import TestClient  # noqa: E402

from movizap import auth, banco, main, telas  # noqa: E402
from movizap.config import settings  # noqa: E402

ENV = RAIZ / ".env"
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

ANEXAR = "/api/paineis/operacao/observacao/{}/anexo"
APAGAR = "/api/paineis/operacao/observacao/{}/apagar"
BAIXAR = "/api/paineis/operacao/anexo/{}"


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    yield


@pytest.fixture(scope="module")
def cliente():
    with TestClient(main.app) as c:
        yield c


@pytest.fixture(scope="module")
def cab():
    return {"Authorization":
            f"Bearer {auth.criar_token(settings.admin_login)}"}


@pytest.fixture(scope="module")
def obs_de_outra_aba():
    """Uma observação de card que NÃO é da Operação, lida do banco.

    🚨 Medida, não escrita à mão: o id fixo envelheceria, e um `skip` honesto
    é melhor que uma trava que mede o id errado.
    """
    linha = banco.um(
        """SELECT o.id, a.codigo_tela
             FROM os_observacao o
             JOIN pipeline_card c ON c.solicitacao_id = o.solicitacao_id
             JOIN painel_aba a ON a.id = c.aba_id
            WHERE o.solicitacao_id IS NOT NULL
              AND a.codigo_tela <> 'PNL_1.1'
            ORDER BY o.id LIMIT 1""")
    if not linha:
        pytest.skip("nenhuma observacao de card fora da Operacao para medir")
    return linha


@pytest.fixture
def quem_pode(monkeypatch):
    """Troca o oráculo da permissão e GRAVA o que foi perguntado.

    ⚠️ O dublê fica na BORDA — quem decide permissão —, nunca em cima da regra
    medida, que é *qual tela a rota pergunta*. É esta gravação que pega a
    volta ao `PNL_1.1` fixo: ali o código perguntado seria outro.
    """
    estado = {"perguntados": [], "permitidas": set()}

    def _pode(usuario, codigo):
        estado["perguntados"].append(codigo)
        return codigo in estado["permitidas"]

    monkeypatch.setattr(telas, "pode_acessar", _pode)
    return estado


@pytest.fixture
def sem_escrita(monkeypatch):
    """Segura as três ações, para o teste medir o PORTÃO e não escrever nada."""
    feito = {}

    def _guardar(observacao_id, nome, dados, mime=None):
        feito["anexou"] = observacao_id
        return {"id": 99, "observacao_id": observacao_id,
                "nome_original": nome, "bytes": len(dados), "mime": mime}

    def _apagar(observacao_id, atendente_id):
        feito["apagou"] = observacao_id
        return {"id": observacao_id, "numero_os": None,
                "solicitacao_id": None}

    monkeypatch.setattr(main.passagem, "guardar_anexo", _guardar)
    monkeypatch.setattr(main.passagem, "apagar_observacao", _apagar)
    return feito


# ============================================================================
# 1 — A RESOLUÇÃO: de qual aba é esta observação
# ============================================================================
class TestDeQualAbaEAObservacao:
    def test_observacao_de_card_fora_da_operacao(self, obs_de_outra_aba):
        """🚨 O coração do defeito: esta observação NÃO é da Operação.

        ⚠️ **PLURAL desde 27/11 à tarde**, e foi medição que obrigou: a OS pode
        ter card em DUAS abas (17120 e 17141 têm). Esta é de solicitação, e
        📏 solicitação não atravessa aba -- 0 casos --, então a lista tem um.
        """
        achadas = main._abas_da_observacao(obs_de_outra_aba["id"])
        assert achadas == [obs_de_outra_aba["codigo_tela"]]
        assert "PNL_1.1" not in achadas

    def test_observacao_de_chamado_da_operacao(self):
        linha = banco.um(
            """SELECT o.id FROM os_observacao o
                 JOIN pipeline_card c ON c.solicitacao_id = o.solicitacao_id
                 JOIN painel_aba a ON a.id = c.aba_id
                WHERE a.codigo_tela = 'PNL_1.1' ORDER BY o.id LIMIT 1""")
        if not linha:
            pytest.skip("nenhuma observacao de chamado da Operacao")
        assert main._abas_da_observacao(linha["id"]) == ["PNL_1.1"]

    def test_observacao_de_OS_COM_card_vai_para_a_aba_do_card(self):
        linha = banco.um(
            """SELECT o.id, a.codigo_tela FROM os_observacao o
                 JOIN pipeline_card c ON c.numero_os = o.numero_os
                 JOIN painel_aba a ON a.id = c.aba_id
                WHERE o.numero_os IS NOT NULL ORDER BY o.id LIMIT 1""")
        if not linha:
            pytest.skip("nenhuma observacao de OS com card")
        # ⚠️ `in`, e não `==`: esta é de OS, e OS pode estar em duas abas.
        # A aba do card que a consulta achou tem de estar na lista -- e a
        # lista pode ser maior que um, legitimamente.
        assert linha["codigo_tela"] in main._abas_da_observacao(linha["id"])

    def test_observacao_de_OS_SEM_card_recua_para_a_Operacao(self):
        """🚨 A TRAVA QUE IMPEDE ESTA MUDANÇA DE QUEBRAR A OPERAÇÃO.

        📏 Medido em 27/11: as observações recentes de OS (90990, 90996,
        17151) não têm linha em `pipeline_card`. Devolver `None` aqui faria
        `_exigir_aba` responder 403 **para o owner também**, e anexar na
        Operação pararia de funcionar.
        """
        linha = banco.um(
            """SELECT o.id FROM os_observacao o
                WHERE o.numero_os IS NOT NULL
                  AND NOT EXISTS (SELECT 1 FROM pipeline_card c
                                   WHERE c.numero_os = o.numero_os)
                ORDER BY o.id DESC LIMIT 1""")
        if not linha:
            pytest.skip("nenhuma observacao de OS sem card")
        assert main._abas_da_observacao(linha["id"]) == ["PNL_1.1"]

    def test_observacao_que_nao_existe_nao_tem_aba(self):
        """⚠️ `None`, e o portão transforma isso em 403 -- nunca 404: dizer
        *"não existe"* a quem não pode ver já conta que existe."""
        assert main._abas_da_observacao(999999999) == []


# ============================================================================
# 2 — O PORTÃO: as três rotas perguntam pela aba do card
# ============================================================================
class TestAsTresRotasPerguntamPelaAbaDoCard:
    def test_anexar_aceita_quem_tem_a_aba_do_card(
            self, cliente, cab, quem_pode, sem_escrita, obs_de_outra_aba):
        """🚨 VERMELHO ANTES DO CONSERTO: a rota pedia `PNL_1.1`."""
        quem_pode["permitidas"] = {obs_de_outra_aba["codigo_tela"]}
        r = cliente.post(ANEXAR.format(obs_de_outra_aba["id"]),
                         files={"arquivo": ("orcamento.pdf", b"%PDF-1.4 x",
                                            "application/pdf")},
                         headers=cab)
        assert r.status_code == 201, r.text[:300]
        assert obs_de_outra_aba["codigo_tela"] in quem_pode["perguntados"]
        assert "PNL_1.1" not in quem_pode["perguntados"]

    def test_apagar_aceita_quem_tem_a_aba_do_card(
            self, cliente, cab, quem_pode, sem_escrita, obs_de_outra_aba):
        quem_pode["permitidas"] = {obs_de_outra_aba["codigo_tela"]}
        r = cliente.post(APAGAR.format(obs_de_outra_aba["id"]), headers=cab)
        assert r.status_code == 200, r.text[:300]
        assert sem_escrita.get("apagou") == obs_de_outra_aba["id"]
        assert "PNL_1.1" not in quem_pode["perguntados"]

    def test_baixar_o_anexo_pergunta_pela_aba_da_observacao_dele(
            self, cliente, cab, quem_pode, monkeypatch, obs_de_outra_aba):
        """⚠️ O caminho é mais longo: do anexo para a observação, e só então
        para a aba. O dublê diz de quem é o anexo; o resto é de verdade."""
        monkeypatch.setattr(
            main.passagem, "anexo",
            lambda anexo_id: {"id": anexo_id,
                              "observacao_id": obs_de_outra_aba["id"],
                              "nome_original": "orcamento.pdf",
                              "caminho": "/caminho/que/nao/existe.pdf",
                              "bytes": 10, "mime": "application/pdf"})
        quem_pode["permitidas"] = {obs_de_outra_aba["codigo_tela"]}
        r = cliente.get(BAIXAR.format(4242), headers=cab)
        # 🚨 O que se mede é o PORTÃO, não o arquivo: o caminho é falso de
        # propósito, então 410 (sumiu do disco) é passar pelo portão. 403 é
        # reprovar.
        assert r.status_code != 403, r.text[:300]
        assert obs_de_outra_aba["codigo_tela"] in quem_pode["perguntados"]
        assert "PNL_1.1" not in quem_pode["perguntados"]


# ============================================================================
# 3 — A OUTRA METADE: "quem vê usa tudo" não é "qualquer um usa tudo"
# ============================================================================
class TestQuemNaoTemAAbaContinuaDeFora:
    def test_so_a_Operacao_nao_abre_observacao_de_outra_aba(
            self, cliente, cab, quem_pode, sem_escrita, obs_de_outra_aba):
        """🚨 Trava que recusa tudo não é trava, e trava que aceita tudo é
        pior. Quem tem SÓ a Operação não mexe no recado do Contratual."""
        quem_pode["permitidas"] = {"PNL_1.1"}
        r = cliente.post(APAGAR.format(obs_de_outra_aba["id"]), headers=cab)
        assert r.status_code == 403, r.text[:300]
        assert "apagou" not in sem_escrita

    def test_observacao_inexistente_responde_403_e_nao_404(
            self, cliente, cab, quem_pode, sem_escrita):
        quem_pode["permitidas"] = {"PNL_1.1", "PNL_1.5", "PNL_1.7"}
        r = cliente.post(APAGAR.format(999999999), headers=cab)
        assert r.status_code == 403
        assert "apagou" not in sem_escrita
