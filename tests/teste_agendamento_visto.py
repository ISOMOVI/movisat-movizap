# -*- coding: utf-8 -*-
r"""O selo "Visto" da `ATD_7.1` — migração 121, 26/11.

🔵 Pedido dele ao aprovar os cartões: *"pode ter um flag de 'Visto' para que o
usuário saiba o que já viu e o que não, pois podem aparecer agendamentos no dia
mesmo"*. E 🔵 a escolha do lugar foi dele: **no banco, por card e por pessoa**.

🚨 **AS DUAS ROTAS POR HTTP, NÃO POR FUNÇÃO** (`feedback_rota_nova_pede_teste_http`):
contar rota registrada não é pedir uma rota. Foi a ORDEM de registro que fez a
`PNL_1.6` sumir em 19/11 — invisível na leitura do arquivo, e só um pedido a
prova.

🚨 **E A REGRA SE MEDE NO POSTGRES DE VERDADE**, com marca própria
(`Zz Teste Visto`) e tudo apagado no fim. Dublê de banco não mostra o SQL ao
Postgres, e o que este arquivo guarda é exatamente SQL: o `ON CONFLICT DO
NOTHING` e o `ANY(%s)` da fusão.

O que se protege:
  · marcar duas vezes NÃO duplica e NÃO muda a hora da primeira;
  · visto manual não é rebaixado a `automatico` quando o cartão abre depois;
  · `desmarcar` volta ao estado "não visto", e responde igual sem marca;
  · o `do_periodo` devolve o visto DE QUEM PEDIU, nunca o do colega;
  · sem `visto_por`, as chaves NEM APARECEM — nulo diria "não viu".

Roda:  venv/bin/python -m pytest tests/teste_agendamento_visto.py
"""
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
pytest.importorskip("psycopg")

from fastapi.testclient import TestClient  # noqa: E402

from movizap import agendamento, auth, banco, main, operacao  # noqa: E402
from movizap.config import settings  # noqa: E402

ENV = RAIZ / ".env"
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

MARCA = "Zz Teste Visto"
LOGIN = "zz_teste_visto_"
# `harmonit_id` fora da faixa real: os de verdade têm 5 a 7 dígitos.
HARMONIT = "97779001"
ROTA = "/api/agendamentos/{}/visto"
SPA = "/{caminho:path}"


def limpar():
    banco.executar(
        """DELETE FROM agendamento_visto WHERE agendamento_id IN
            (SELECT id FROM agendamento WHERE cliente_harmonit_id = %s)""",
        (HARMONIT,))
    banco.executar("DELETE FROM agendamento WHERE cliente_harmonit_id = %s",
                   (HARMONIT,))
    # 🚨 A CONVERSA SAI ANTES DO CONTATO: o técnico é contato sem cliente
    # (desenho de 07/10), e o DELETE do contato quebra na chave estrangeira.
    banco.executar(
        """DELETE FROM conversa WHERE contato_id IN
            (SELECT id FROM contato WHERE nome LIKE %s)""", (MARCA + "%",))
    banco.executar("DELETE FROM contato WHERE nome LIKE %s", (MARCA + "%",))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def base():
    banco.abrir()
    limpar()

    # Duas pessoas, porque o selo é POR PESSOA e um teste com uma só não
    # distinguiria "ninguém viu" de "o colega viu".
    eu = operacao.criar_atendente(MARCA + " Eu", LOGIN + "1",
                                  LOGIN + "1@teste.invalid")
    colega = operacao.criar_atendente(MARCA + " Colega", LOGIN + "2",
                                      LOGIN + "2@teste.invalid")
    with banco.cursor() as cur:
        cur.execute("""INSERT INTO contato (nome, relacao, origem, ativo)
                       VALUES (%s, 'tecnico', 'movizap', true) RETURNING id""",
                    (MARCA + " Tecnico",))
        tecnico = cur.fetchone()["id"]
        cur.execute("SELECT id FROM canal WHERE instancia = 'atendimento'")
        canal = cur.fetchone()
        if not canal:
            pytest.skip("canal atendimento não cadastrado")
        cur.execute("""INSERT INTO conversa (canal_id, contato_id, telefone_e164,
                                             estado, ultima_atividade_em, criada_em)
                       VALUES (%s, %s, %s, 'humano', now(), now()) RETURNING id""",
                    (canal["id"], tecnico, "+5518977778888"))
        conversa = cur.fetchone()["id"]

    quando = datetime.now(timezone.utc) + timedelta(days=1)
    with banco.cursor() as cur:
        # 🚨 INSERT direto, e não `agendamento.criar`: o que se mede aqui é o
        # visto, e `criar` arrasta a reserva de OS e a ponte do FPSL -- ruído
        # que faria este arquivo falhar por motivo alheio ao que ele guarda.
        cur.execute("""INSERT INTO agendamento
                         (conversa_id, tecnico_contato_id, cliente_harmonit_id,
                          cliente_nome, inicio, criado_por)
                       VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
                    (conversa, tecnico, HARMONIT, MARCA + " Cliente",
                     quando, eu["id"]))
        compromisso = cur.fetchone()["id"]

    yield {"eu": eu["id"], "colega": colega["id"], "compromisso": compromisso,
           "quando": quando}
    # 🚨 ARMADILHA MEDIDA EM 26/11: o `TestClient(main.app)` como gerenciador de
    # contexto roda o LIFESPAN do app -- e o encerramento dele chama
    # `banco.fechar()`. Como a fixture `cliente` e montada DEPOIS desta, ela e
    # desmontada ANTES, e a limpeza daqui estourava com *"banco nao foi aberto"*.
    # ⚠️ `abrir()` e idempotente (sai na hora se o pool existe), entao isto nao
    # abre um segundo pool quando o teste roda sozinho.
    banco.abrir()
    limpar()


@pytest.fixture(autouse=True)
def sem_marca(base):
    """Cada teste começa sem nenhum visto: marca que sobra do anterior passaria
    na primeira rodada e reprovaria na segunda."""
    banco.executar("DELETE FROM agendamento_visto WHERE agendamento_id = %s",
                   (base["compromisso"],))


@pytest.fixture(scope="module")
def cliente():
    with TestClient(main.app) as c:
        yield c


@pytest.fixture(scope="module")
def cab():
    return {"Authorization": f"Bearer {auth.criar_token(settings.admin_login)}"}


# ============================================================================
# A ORDEM E A PORTA — travas que não dependem do banco
# ============================================================================
def teste_as_duas_rotas_vem_ANTES_do_curinga_da_spa():
    """🚨 Registrada abaixo do `{caminho:path}`, a rota cairia no index.html e
    a tela receberia HTML onde esperava JSON."""
    caminhos = [getattr(r, "path", None) for r in main.app.routes]
    alvo = "/api/agendamentos/{agendamento_id}/visto"
    assert alvo in caminhos, "a rota do visto sumiu do app"
    assert SPA in caminhos, "o curinga da SPA mudou de forma; reveja o teste"
    assert caminhos.index(alvo) < caminhos.index(SPA)


def teste_sem_login_nenhuma_das_duas_responde(cliente, base):
    assert cliente.post(ROTA.format(base["compromisso"]),
                        json={"automatico": False}).status_code == 401
    assert cliente.delete(ROTA.format(base["compromisso"])).status_code == 401


def teste_compromisso_que_nao_existe_e_404(cliente, cab):
    r = cliente.post(ROTA.format(99999999), headers=cab,
                     json={"automatico": False})
    assert r.status_code == 404, r.text


# ============================================================================
# MARCAR — idempotente, e a hora é a da PRIMEIRA vez
# ============================================================================
def teste_marca_e_devolve_a_hora(cliente, cab, base):
    r = cliente.post(ROTA.format(base["compromisso"]), headers=cab,
                     json={"automatico": False})
    assert r.status_code == 200, r.text
    assert r.json()["visto_em"]
    assert r.json()["visto_automatico"] is False


def teste_marcar_DUAS_vezes_nao_duplica_nem_muda_a_hora(base):
    """🚨 `ON CONFLICT DO NOTHING`, e não `DO UPDATE`. O selo diz "Visto
    08:12", e 08:12 é quando a pessoa viu da PRIMEIRA vez -- reabrir o cartão
    não pode reescrever isso."""
    primeira = agendamento.marcar_visto(base["compromisso"], base["eu"])
    segunda = agendamento.marcar_visto(base["compromisso"], base["eu"])
    assert segunda["visto_em"] == primeira["visto_em"]
    quantas = banco.um(
        "SELECT count(*) AS n FROM agendamento_visto WHERE agendamento_id = %s",
        (base["compromisso"],))
    assert quantas["n"] == 1, "a PK composta é o que impede a segunda linha"


def teste_visto_MANUAL_nao_e_rebaixado_a_automatico(base):
    """⚠️ A pessoa disse que viu; o cartão abrir depois não apaga isso. Se um
    dia alguém trocar o `DO NOTHING` por `DO UPDATE`, é aqui que aparece."""
    agendamento.marcar_visto(base["compromisso"], base["eu"], automatico=False)
    agendamento.marcar_visto(base["compromisso"], base["eu"], automatico=True)
    linha = banco.um(
        "SELECT automatico FROM agendamento_visto "
        " WHERE agendamento_id = %s AND atendente_id = %s",
        (base["compromisso"], base["eu"]))
    assert linha["automatico"] is False


def teste_o_automatico_atravessa_quando_e_a_primeira_marca(base):
    """A outra ponta: abrir o cartão marca, e o dado diz que foi automático --
    é o que permite à tela avisar *"marquei porque você abriu"*."""
    agendamento.marcar_visto(base["compromisso"], base["eu"], automatico=True)
    linha = banco.um(
        "SELECT automatico FROM agendamento_visto "
        " WHERE agendamento_id = %s AND atendente_id = %s",
        (base["compromisso"], base["eu"]))
    assert linha["automatico"] is True


# ============================================================================
# DESFAZER
# ============================================================================
def teste_desmarcar_volta_ao_nao_visto(cliente, cab, base):
    cliente.post(ROTA.format(base["compromisso"]), headers=cab,
                 json={"automatico": False})
    r = cliente.delete(ROTA.format(base["compromisso"]), headers=cab)
    assert r.status_code == 200, r.text
    assert r.json()["visto_em"] is None
    assert not banco.varios(
        "SELECT 1 FROM agendamento_visto WHERE agendamento_id = %s",
        (base["compromisso"],))


def teste_desmarcar_SEM_marca_responde_igual(cliente, cab, base):
    """⚠️ 200, nunca 409: desfazer o que já está desfeito entrega o estado que
    a pessoa queria, e um erro vermelho aqui seria numa ação que deu certo."""
    r = cliente.delete(ROTA.format(base["compromisso"]), headers=cab)
    assert r.status_code == 200, r.text
    assert r.json()["visto_em"] is None


# ============================================================================
# A FUSÃO — o visto é DE QUEM PEDIU
# ============================================================================
def _dia(base):
    """🚨 O DIA QUE O BANCO VAI REPORTAR, não o que o Python calcula. O
    `do_periodo` compara `a.inicio::date`, e o Postgres resolve o cast no fuso
    da sessão (`America/Sao_Paulo`) -- perguntar em UTC fazia teste irmão
    reprovar das 21h à meia-noite."""
    return banco.um("SELECT (%s AT TIME ZONE current_setting('TimeZone'))::date AS d",
                    (base["quando"],))["d"]


def teste_o_visto_que_volta_e_o_DE_QUEM_PEDIU(base):
    """🚨 O defeito que isto impede: o selo do colega aparecendo como meu. Um
    só `atendente_id` no teste não distinguiria."""
    agendamento.marcar_visto(base["compromisso"], base["colega"])
    dia = _dia(base)

    meus = {x["id"]: x for x in agendamento.do_periodo(dia, dia,
                                                      visto_por=base["eu"])}
    assert meus[base["compromisso"]]["visto_em"] is None, (
        "o visto do colega não é o meu")

    dele = {x["id"]: x for x in agendamento.do_periodo(dia, dia,
                                                      visto_por=base["colega"])}
    assert dele[base["compromisso"]]["visto_em"] is not None


def teste_sem_visto_por_as_chaves_NEM_APARECEM(base):
    """⚠️ Nulo diria *"esta pessoa não viu"*, e a verdade é *"ninguém perguntou
    por pessoa"*. Chave ausente é a única resposta honesta -- e é o que deixa a
    aba Confirmar seguir usando o mesmo módulo sem atendente no contexto."""
    agendamento.marcar_visto(base["compromisso"], base["eu"])
    dia = _dia(base)
    linhas = {x["id"]: x for x in agendamento.do_periodo(dia, dia)}
    alvo = linhas[base["compromisso"]]
    assert "visto_em" not in alvo
    assert "visto_automatico" not in alvo


def teste_a_rota_do_periodo_devolve_o_visto_por_http(cliente, cab, base):
    """A ponta que a tela realmente consome, de ponta a ponta: marca pelo POST
    e lê pelo GET, como a MESMA pessoa (o token é um só).

    ⚠️ ESTE TESTE REPROVOU NA PRIMEIRA RODADA, e a asserção errada era minha:
    eu havia escrito que o selo voltaria vazio *"porque o `admin_login` não é
    nenhum dos dois atendentes do teste"* -- e esqueci que quem tinha acabado
    de marcar, no POST da linha de cima, era justamente ele. O código estava
    certo; o teste afirmava o contrário do que o gesto faz.
    """
    cliente.post(ROTA.format(base["compromisso"]), headers=cab,
                 json={"automatico": True})
    dia = _dia(base)
    r = cliente.get(f"/api/agendamentos?de={dia}&ate={dia}", headers=cab)
    assert r.status_code == 200, r.text
    achado = [a for a in r.json()["agendamentos"]
              if a["id"] == base["compromisso"]]
    assert achado, "o compromisso do teste não veio no período"
    assert achado[0]["visto_em"], "quem marcou tem de ver o selo"
    assert achado[0]["visto_automatico"] is True, (
        "marcado com automatico=True: é o que deixa a tela dizer "
        "'marquei porque você abriu'")


def teste_o_visto_do_admin_nao_vaza_para_os_outros(cliente, cab, base):
    """A outra metade da anterior: marcado pelo token, o selo NÃO aparece para
    os dois atendentes do teste. É a mesma regra, medida do lado de fora."""
    cliente.post(ROTA.format(base["compromisso"]), headers=cab,
                 json={"automatico": True})
    dia = _dia(base)
    for quem in ("eu", "colega"):
        linhas = {x["id"]: x for x in agendamento.do_periodo(
            dia, dia, visto_por=base[quem])}
        assert linhas[base["compromisso"]]["visto_em"] is None, (
            f"o visto do admin apareceu como sendo do {quem}")


def teste_banco_mudo_nao_derruba_a_lista(base, monkeypatch):
    """🚨 Perder o *"Visto"* é aceitável; perder a agenda do dia não é."""
    dia = _dia(base)
    real = banco.varios
    chamadas = {"n": 0}

    def duble(sql, params=()):
        chamadas["n"] += 1
        if "agendamento_visto" in sql:
            raise RuntimeError("zz banco mudo de propósito")
        return real(sql, params)

    monkeypatch.setattr(banco, "varios", duble)
    linhas = agendamento.do_periodo(dia, dia, visto_por=base["eu"])
    assert any(x["id"] == base["compromisso"] for x in linhas), (
        "a lista tem de voltar inteira, só sem o selo")
    assert chamadas["n"] >= 2, "a consulta do visto tem de ter sido tentada"
