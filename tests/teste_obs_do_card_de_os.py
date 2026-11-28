# -*- coding: utf-8 -*-
r"""O OBS DO CARD DE OS — o defeito que a Karla achou, 27/11.

🔵 Ele: *"verifique o pq o OBS dos cards do financeiro nao esta salvando ao
clicar em salvar - reportado por Karla"*.

🚨 **O DEFEITO, MEDIDO E EM DUAS CAMADAS.**

📏 Primeiro o dado: o Financeiro (`PNL_1.4`) tem **13 cards que são SÓ OS** --
`numero_os` preenchido e `solicitacao_id` nulo -- de 19. O Contratual tem
**zero**, e é por isso que ninguém viu o defeito lá.

**Camada 1, a tela:** o `salvarRecado` do `DialogoDeChamado` só sabia gravar
observação de CHAMADO. Ele lia `ficha.chamado.solicitacao_id` e, num card de
OS, a ficha não traz `chamado` nenhum -- então `sid` vinha vazio e a função
**retornava em silêncio**. O botão Salvar não fazia nada, sem erro na tela.
⚠️ É ANTERIOR à minha mexida de hoje: o backup de antes tem o mesmo
`if (!texto || !sid) return`.

**Camada 2, a porta:** mesmo com a tela consertada, a rota que grava
observação de OS exigia `requer_tela("PNL_1.1")` -- e a Karla tem o
**Financeiro**. É a quarta rota da mesma família que 05/11 deixou para trás, e
a decisão dele de hoje resolve: *"quem vê usa tudo"*.

🚨 **CONSERTAR SÓ A TELA TROCARIA O SILÊNCIO POR UM 403**, que é melhor mas
ainda não salva. É por isso que as duas camadas vão juntas.

Roda:  venv/bin/python -m pytest tests/teste_obs_do_card_de_os.py
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

OBSERVAR_OS = "/api/paineis/operacao/observacao"


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
def card_de_os_fora_da_operacao():
    """Um card que é SÓ OS e não está na Operação -- o caso da Karla.

    🚨 Medido, não escrito à mão.
    """
    linha = banco.um(
        """SELECT c.numero_os, a.codigo_tela
             FROM pipeline_card c
             JOIN painel_aba a ON a.id = c.aba_id
            WHERE c.numero_os IS NOT NULL
              AND c.solicitacao_id IS NULL
              AND a.codigo_tela <> 'PNL_1.1'
            ORDER BY c.id DESC LIMIT 1""")
    if not linha:
        pytest.skip("nenhum card so-de-OS fora da Operacao para medir")
    return linha


@pytest.fixture
def quem_pode(monkeypatch):
    estado = {"perguntados": [], "permitidas": set()}

    def _pode(usuario, codigo):
        estado["perguntados"].append(codigo)
        return codigo in estado["permitidas"]

    monkeypatch.setattr(telas, "pode_acessar", _pode)
    return estado


@pytest.fixture
def sem_escrita(monkeypatch):
    """Segura a gravação: o que se mede é o PORTÃO."""
    visto = {}

    def _observar(numero_os, texto, atendente_id=None):
        visto["numero_os"] = numero_os
        visto["texto"] = texto
        return {"id": 99}

    monkeypatch.setattr(main.passagem, "observar", _observar)
    monkeypatch.setattr(main.passagem, "observacoes",
                        lambda numero_os, eu=None: [])
    return visto


# ============================================================================
# A PORTA: quem vê o card do Financeiro grava observação nele
# ============================================================================
def teste_a_aba_do_card_pode_observar_a_OS_dele(
        cliente, cab, quem_pode, sem_escrita, card_de_os_fora_da_operacao):
    """🚨 VERMELHO ANTES DO CONSERTO: a rota exigia `PNL_1.1`, e a Karla tem o
    Financeiro. Era o 403 escondido atrás do silêncio da tela."""
    quem_pode["permitidas"] = {card_de_os_fora_da_operacao["codigo_tela"]}
    r = cliente.post(OBSERVAR_OS,
                     json={"numero_os": card_de_os_fora_da_operacao["numero_os"],
                           "texto": "Conferido com o financeiro."},
                     headers=cab)
    assert r.status_code == 200, r.text[:300]
    assert sem_escrita["numero_os"] == card_de_os_fora_da_operacao["numero_os"]
    assert card_de_os_fora_da_operacao["codigo_tela"] in quem_pode["perguntados"]


def teste_quem_tem_so_a_Operacao_nao_observa_card_de_outra_aba(
        cliente, cab, quem_pode, sem_escrita, card_de_os_fora_da_operacao):
    """⚠️ *"Quem vê usa tudo"* não é *"qualquer um usa tudo"*."""
    quem_pode["permitidas"] = {"PNL_1.1"}
    r = cliente.post(OBSERVAR_OS,
                     json={"numero_os": card_de_os_fora_da_operacao["numero_os"],
                           "texto": "x"},
                     headers=cab)
    assert r.status_code == 403, r.text[:300]
    assert "numero_os" not in sem_escrita


def teste_OS_sem_card_continua_sendo_da_Operacao(cliente, cab, quem_pode,
                                                 sem_escrita):
    """🚨 O MESMO RECUO DAS OUTRAS TRÊS, e pelo mesmo motivo medido: há OS com
    observação e **sem linha em `pipeline_card`**. Sem o recuo, observar essas
    viraria 403 para todo mundo -- inclusive para o owner -- e a Operação
    perderia o recado que ela sempre pôde escrever."""
    linha = banco.um(
        """SELECT o.numero_os FROM os_observacao o
            WHERE o.numero_os IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM pipeline_card c
                               WHERE c.numero_os = o.numero_os)
            ORDER BY o.id DESC LIMIT 1""")
    if not linha:
        pytest.skip("nenhuma OS com observacao e sem card")
    quem_pode["permitidas"] = {"PNL_1.1"}
    r = cliente.post(OBSERVAR_OS,
                     json={"numero_os": linha["numero_os"], "texto": "x"},
                     headers=cab)
    assert r.status_code == 200, r.text[:300]


def teste_a_Operacao_continua_observando_os_cards_dela(cliente, cab,
                                                       quem_pode,
                                                       sem_escrita):
    """⚠️ A OUTRA METADE: o que já funcionava não pode mudar."""
    linha = banco.um(
        """SELECT c.numero_os FROM pipeline_card c
             JOIN painel_aba a ON a.id = c.aba_id
            WHERE c.numero_os IS NOT NULL AND a.codigo_tela = 'PNL_1.1'
            ORDER BY c.id DESC LIMIT 1""")
    if not linha:
        pytest.skip("nenhum card de OS na Operacao")
    quem_pode["permitidas"] = {"PNL_1.1"}
    r = cliente.post(OBSERVAR_OS,
                     json={"numero_os": linha["numero_os"], "texto": "x"},
                     headers=cab)
    assert r.status_code == 200, r.text[:300]


# ============================================================================
# O DADO QUE EXPLICA O DEFEITO
# ============================================================================
def teste_o_Financeiro_tem_card_so_de_OS_e_o_Contratual_nao():
    """📏 A medição que explica por que o defeito apareceu no Financeiro e não
    no Contratual -- e por que ele ficou meses invisível.

    ⚠️ Mede a EXISTÊNCIA do caso, não a contagem exata: card entra e sai do
    quadro todo dia, e prender o número faria esta trava reprovar por trabalho
    normal dele.
    """
    por_aba = {l["codigo_tela"]: l["so_os"] for l in banco.varios(
        """SELECT a.codigo_tela,
                  count(*) FILTER (WHERE c.numero_os IS NOT NULL
                                     AND c.solicitacao_id IS NULL) AS so_os
             FROM pipeline_card c JOIN painel_aba a ON a.id = c.aba_id
            GROUP BY 1""")}
    assert por_aba.get("PNL_1.4", 0) > 0, (
        "o Financeiro deixou de ter card so-de-OS: o caso da Karla mudou de "
        "forma, e esta trava precisa ser relida antes de confiar nela")
