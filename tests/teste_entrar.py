"""Estar na conversa para poder agir — o isolamento que não existia.

Encontrado pelo usuário em 12/08, usando a tela: ele saiu de uma conversa,
abriu de novo pelo painel e o botão *Encerrar* continuava funcionando. A
auditoria de 11/08 já tinha registrado que "as rotas de atendimento exigem só
`ATD_1.2` e nenhuma pergunta quem é o dono" -- estava escrito e não estava
consertado.

🚨 Escreve em `conversa`, `conversa_participante` e `atendente`, tabelas de
PRODUÇÃO. Telefone de DDD inexistente e login com prefixo `zz`.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, conversas  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

FONE = "+5599955550000"
LOGIN = "zz_teste_entrar_"


def limpar():
    banco.executar(
        """DELETE FROM conversa_participante WHERE conversa_id IN
           (SELECT id FROM conversa WHERE telefone_e164 = %s)""", (FONE,))
    banco.executar(
        """DELETE FROM transferencia WHERE conversa_id IN
           (SELECT id FROM conversa WHERE telefone_e164 = %s)""", (FONE,))
    banco.executar(
        """DELETE FROM mensagem WHERE conversa_id IN
           (SELECT id FROM conversa WHERE telefone_e164 = %s)""", (FONE,))
    banco.executar("DELETE FROM conversa WHERE telefone_e164 = %s", (FONE,))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()


@pytest.fixture()
def cena():
    """Conversa COM dono, mais um atendente que está de fora."""
    limpar()
    canal = banco.um("SELECT id FROM canal WHERE instancia = 'atendimento'")
    if not canal:
        pytest.skip("canal atendimento não cadastrado")
    ids = []
    for n in ("dono", "defora"):
        ids.append(banco.um(
            """INSERT INTO atendente (nome, login, email, senha_hash, perfil, ativo)
               VALUES (%s, %s, %s, 'x', 'atendimento', true) RETURNING id""",
            (f"Teste {n}", LOGIN + n, f"{LOGIN}{n}@movisat.com.br"))["id"])
    conversa = banco.um(
        """INSERT INTO conversa (canal_id, telefone_e164, estado, atendente_id)
           VALUES (%s, %s, 'humano', %s) RETURNING id""",
        (canal["id"], FONE, ids[0]))["id"]
    yield {"conversa": conversa, "dono": ids[0], "defora": ids[1]}
    limpar()


class TestQuemEstaNaConversa:
    def test_o_dono_esta(self, cena):
        assert conversas.esta_na_conversa(cena["conversa"], cena["dono"]) is True

    def test_quem_nunca_entrou_NAO_esta(self, cena):
        assert conversas.esta_na_conversa(cena["conversa"], cena["defora"]) is False

    def test_participante_convidado_esta(self, cena):
        conversas.convidar(cena["conversa"], cena["defora"], cena["dono"])
        assert conversas.esta_na_conversa(cena["conversa"], cena["defora"]) is True

    def test_quem_SAIU_deixa_de_estar(self, cena):
        """🚨 O caso que o usuário reproduziu: sair e reabrir pelo painel."""
        conversas.convidar(cena["conversa"], cena["defora"], cena["dono"])
        conversas.sair(cena["conversa"], cena["defora"])
        assert conversas.esta_na_conversa(cena["conversa"], cena["defora"]) is False

    def test_sem_atendente_nunca_esta(self, cena):
        """A conta do .env sem vínculo não age em conversa nenhuma."""
        assert conversas.esta_na_conversa(cena["conversa"], None) is False


class TestEntrarPorContaPropria:
    def test_entra_como_PARTICIPANTE_e_o_dono_nao_muda(self, cena):
        r = conversas.entrar(cena["conversa"], cena["defora"])
        assert r["ok"] is True
        assert r["papel"] == "participante"
        assert banco.um("SELECT atendente_id FROM conversa WHERE id = %s",
                        (cena["conversa"],))["atendente_id"] == cena["dono"], \
            "entrar virou assumir -- roubou a conversa do dono"
        assert conversas.esta_na_conversa(cena["conversa"], cena["defora"]) is True

    def test_o_dono_entrando_e_inofensivo(self, cena):
        r = conversas.entrar(cena["conversa"], cena["dono"])
        assert r["ok"] is True
        assert r["papel"] == "dono"
        # 🚨 Não pode virar participante: o dono é `conversa.atendente_id`, e
        # existir nos dois lugares faria a saída dele ser resolvida duas vezes.
        assert conversas.participantes(cena["conversa"]) == []

    def test_voltar_depois_de_sair(self, cena):
        conversas.convidar(cena["conversa"], cena["defora"], cena["dono"])
        conversas.sair(cena["conversa"], cena["defora"])
        assert conversas.entrar(cena["conversa"], cena["defora"])["ok"] is True
        assert conversas.esta_na_conversa(cena["conversa"], cena["defora"]) is True

    def test_conversa_SEM_dono_manda_usar_assumir(self, cena):
        """Entrar não é o caminho da fila -- lá o certo é virar dono."""
        banco.executar(
            "UPDATE conversa SET atendente_id = NULL, estado = 'fila' "
            " WHERE id = %s", (cena["conversa"],))
        r = conversas.entrar(cena["conversa"], cena["defora"])
        assert r["ok"] is False
        assert "assumir" in r["motivo"].lower()

    def test_conversa_ENCERRADA_manda_reabrir(self, cena):
        banco.executar(
            "UPDATE conversa SET estado = 'resolvida', resolvida_em = now() "
            " WHERE id = %s", (cena["conversa"],))
        r = conversas.entrar(cena["conversa"], cena["defora"])
        assert r["ok"] is False
        assert "reabra" in r["motivo"].lower()

    def test_conversa_inexistente(self):
        assert conversas.entrar(-1, 1)["ok"] is False


class TestAsRotasRecusamQuemEstaDeFora:
    """🚨 ESCONDER O BOTÃO NÃO É PERMISSÃO. A rota responde a quem a chamar.

    Estes testes batem na camada HTTP de propósito: os testes de serviço
    (`conversas.encerrar`) continuam passando com quem está de fora, porque a
    regra não é do serviço -- é da rota.
    """

    @pytest.fixture()
    def cliente(self, cena):
        from fastapi.testclient import TestClient

        from movizap import auth, main

        # ⚠️ `TestClient(app)` fora de um `with` não roda o lifespan -- lição
        # que já custou caro neste projeto.
        #
        # 🚨 E O LIFESPAN FECHA O POOL NA SAÍDA. A fixture do módulo abriu o
        # banco; ao sair deste `with`, o `ciclo_de_vida` chama `banco.fechar()`
        # e todo teste seguinte morre com "banco não foi aberto". Reabrir aqui
        # é o preço de exercitar a camada HTTP no meio de uma suíte que fala
        # com o banco direto.
        with TestClient(main.app) as c:
            token = auth.criar_token(LOGIN + "defora")
            c.headers.update({"Authorization": f"Bearer {token}"})
            yield c, cena
        banco.abrir()

    def _acoes(self, conversa_id):
        return [
            ("encerrar", f"/api/conversas/{conversa_id}/encerrar", {}),
            ("devolver", f"/api/conversas/{conversa_id}/devolver", None),
            ("transferir", f"/api/conversas/{conversa_id}/transferir",
             {"time_id": None}),
            ("nota", f"/api/conversas/{conversa_id}/nota", {"texto": "oi"}),
        ]

    def test_de_fora_toda_acao_e_recusada(self, cliente):
        c, cena = cliente
        for nome, url, corpo in self._acoes(cena["conversa"]):
            r = c.post(url, json=corpo) if corpo is not None else c.post(url)
            assert r.status_code == 409, f"{nome} passou com {r.status_code}"
            assert "não está nesta conversa" in r.json()["detail"], nome

        # E o estado não mudou: nada foi feito pela metade.
        atual = banco.um("SELECT estado, atendente_id FROM conversa WHERE id = %s",
                         (cena["conversa"],))
        assert atual["estado"] == "humano"
        assert atual["atendente_id"] == cena["dono"]

    def test_LER_continua_livre(self, cliente):
        """Isto não fecha a conversa para consulta -- só para ação."""
        c, cena = cliente
        assert c.get(f"/api/conversas/{cena['conversa']}").status_code == 200
        assert c.get(
            f"/api/conversas/{cena['conversa']}/participantes").status_code == 200

    def test_depois_de_ENTRAR_a_acao_passa(self, cliente):
        c, cena = cliente
        assert c.post(f"/api/conversas/{cena['conversa']}/entrar").status_code == 200
        r = c.post(f"/api/conversas/{cena['conversa']}/nota", json={"texto": "oi"})
        assert r.status_code == 200, r.text
        assert conversas.esta_na_conversa(cena["conversa"], cena["defora"])
