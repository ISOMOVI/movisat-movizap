"""ATD_6.1 — anexo no chat interno. 🔵 Pedido dele em 22/09.

🚨 O TESTE QUE IMPORTA É O DA PERMISSÃO. Até a migração 047 as rotas
`/api/midia/{id}` exigiam só a tela `ATD_1.2` e NÃO conferiam participação.
Numa caixa compartilhada isso passa; num chat de duas pessoas, não — o
`midia_id` é sequencial, e trocar o número no link entregaria o anexo alheio.
`test_quem_NAO_e_da_sala_leva_404` é o que segura isso no lugar.

🚨 Escreve em `atendente`, `chat_*` e `midia`, que são tabelas de PRODUÇÃO.
Logins com prefixo `zz`, conteúdo de arquivo ALEATÓRIO (para o SHA256 nunca
colidir com mídia de verdade) e a fixture apaga o que criou, no banco e no
disco.
"""
import os
import pathlib
import sys

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from fastapi.testclient import TestClient  # noqa: E402

from movizap import auth, banco, chat, main, midia  # noqa: E402

ENV = pathlib.Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

LOGIN = "zz_teste_anexo_chat_"


def limpar():
    """⚠️ APAGA O ARQUIVO DO DISCO TAMBÉM. Limpar só o banco deixaria lixo
    em `/home/claude/movizap_midia` que ninguém mais encontra para apagar —
    a linha era o único ponteiro.

    🚨 A ORDEM É MENSAGEM → MÍDIA → SALA, e foi a 048 que ensinou. A primeira
    versão zerava `midia_id` para soltar a mídia antes de apagá-la, e isso
    estourava no `CHECK chat_mensagem_tem_conteudo`: mensagem que é SÓ anexo
    não pode ficar sem anexo. A restrição estava certa e a limpeza é que
    estava errada — some com a mensagem, não com o vínculo dela.

    ⚠️ AS SALAS SÃO COLHIDAS ANTES. Achá-las por autoria de mensagem depois
    de apagar as mensagens não acharia mais nada, e a sala ficaria para trás.
    """
    salas = [linha["sala_id"] for linha in banco.varios(
        """SELECT sala_id FROM chat_membro WHERE atendente_id IN
             (SELECT id FROM atendente WHERE login LIKE %s)
           UNION
           SELECT sala_id FROM chat_mensagem WHERE atendente_id IN
             (SELECT id FROM atendente WHERE login LIKE %s)""",
        (LOGIN + "%", LOGIN + "%"))]
    if salas:
        for linha in banco.varios(
                "SELECT caminho FROM midia WHERE sala_id = ANY(%s)", (salas,)):
            try:
                os.unlink(linha["caminho"])
            except OSError:
                pass
        banco.executar("DELETE FROM chat_mensagem WHERE sala_id = ANY(%s)", (salas,))
        banco.executar("DELETE FROM midia WHERE sala_id = ANY(%s)", (salas,))
        banco.executar("DELETE FROM chat_sala WHERE id = ANY(%s)", (salas,))
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
    """Ana e Bruno numa sala; Carla de fora, e ela é o ponto do teste."""
    limpar()
    ids = {}
    for papel in ("ana", "bruno", "carla"):
        ids[papel] = banco.um(
            """INSERT INTO atendente (nome, login, email, senha_hash, perfil, ativo)
               VALUES (%s, %s, %s, 'x', 'atendimento', true) RETURNING id""",
            (f"Teste {papel}", LOGIN + papel,
             f"{LOGIN}{papel}@movisat.com.br"))["id"]
    sala = chat.abrir_direta(ids["ana"], ids["bruno"])["sala_id"]
    outra = chat.abrir_direta(ids["ana"], ids["carla"])["sala_id"]
    yield {"sala": sala, "outra": outra, **ids}
    limpar()


def _cliente(sufixo):
    c = TestClient(main.app)
    c.headers.update({"Authorization": f"Bearer {auth.criar_token(LOGIN + sufixo)}"})
    return c


def _arquivo(nome="print.png", tamanho=2048):
    # Conteúdo ALEATÓRIO: garante SHA256 único, então apagar o arquivo na
    # limpeza nunca remove mídia de outra linha que calhasse do mesmo hash.
    return {"arquivo": (nome, os.urandom(tamanho), "image/png")}


class TestOAnexoEntra:
    def test_grava_a_midia_na_SALA_e_amarra_na_mensagem(self, cena):
        r = _cliente("ana").post(f"/api/chat/salas/{cena['sala']}/arquivo",
                                 files=_arquivo(), data={"legenda": "o print"})
        assert r.status_code == 200, r.text
        midia_id = r.json()["midia_id"]

        linha = banco.um("SELECT conversa_id, sala_id FROM midia WHERE id = %s",
                         (midia_id,))
        assert linha["sala_id"] == cena["sala"]
        assert linha["conversa_id"] is None

        msgs = chat.mensagens(cena["sala"], cena["ana"])
        assert msgs[-1]["midia_id"] == midia_id
        assert msgs[-1]["midia_mime"] == "image/png"
        assert msgs[-1]["midia_nome"] == "print.png"
        assert msgs[-1]["texto"] == "o print"

    def test_mensagem_pode_ser_SO_o_anexo(self, cena):
        """Quem manda um print raramente escreve legenda."""
        r = _cliente("ana").post(f"/api/chat/salas/{cena['sala']}/arquivo",
                                 files=_arquivo())
        assert r.status_code == 200, r.text
        assert chat.mensagens(cena["sala"], cena["ana"])[-1]["texto"] == ""

    def test_o_arquivo_existe_no_disco(self, cena):
        r = _cliente("ana").post(f"/api/chat/salas/{cena['sala']}/arquivo",
                                 files=_arquivo())
        caminho = banco.um("SELECT caminho FROM midia WHERE id = %s",
                           (r.json()["midia_id"],))["caminho"]
        assert pathlib.Path(caminho).exists()


class TestQuemPodeVer:
    def test_quem_e_da_sala_ve(self, cena):
        midia_id = _cliente("ana").post(
            f"/api/chat/salas/{cena['sala']}/arquivo",
            files=_arquivo()).json()["midia_id"]
        assert _cliente("bruno").get(f"/api/midia/{midia_id}/ver").status_code == 200

    def test_quem_NAO_e_da_sala_leva_404(self, cena):
        """🚨 A razão de existir desta rodada.

        Carla é atendente, tem a tela `ATD_1.2` como todo mundo, e não está
        na sala. Antes de 22/09 ela veria o arquivo só trocando o número no
        link. 404 e não 403: 403 confirmaria que o id existe, e isso já é
        informação sobre a conversa dos outros.
        """
        midia_id = _cliente("ana").post(
            f"/api/chat/salas/{cena['sala']}/arquivo",
            files=_arquivo()).json()["midia_id"]
        assert _cliente("carla").get(f"/api/midia/{midia_id}/ver").status_code == 404
        assert _cliente("carla").get(f"/api/midia/{midia_id}").status_code == 404

    def test_a_midia_da_CONVERSA_continua_servindo(self, cena):
        """⚠️ A regra da Caixa de entrada NÃO mudou, e este teste é o que
        prova. Apertar a conversa junto seria mudar uma regra que ninguém
        pediu — e 2.586 mídias de cliente dependem dela."""
        antiga = banco.um(
            "SELECT id FROM midia WHERE conversa_id IS NOT NULL ORDER BY id LIMIT 1")
        if not antiga:
            pytest.skip("nenhuma midia de conversa nesta base")
        assert _cliente("carla").get(
            f"/api/midia/{antiga['id']}/ver").status_code == 200

    def test_quem_nao_esta_na_sala_nao_MANDA_arquivo(self, cena):
        r = _cliente("carla").post(f"/api/chat/salas/{cena['sala']}/arquivo",
                                   files=_arquivo())
        assert r.status_code == 404


class TestDedupePorDono:
    def test_o_mesmo_arquivo_duas_vezes_na_MESMA_sala_e_uma_midia(self, cena):
        arq = os.urandom(1024)
        c = _cliente("ana")
        a = c.post(f"/api/chat/salas/{cena['sala']}/arquivo",
                   files={"arquivo": ("x.png", arq, "image/png")}).json()["midia_id"]
        b = c.post(f"/api/chat/salas/{cena['sala']}/arquivo",
                   files={"arquivo": ("x.png", arq, "image/png")}).json()["midia_id"]
        assert a == b

    def test_o_mesmo_arquivo_em_SALAS_diferentes_sao_duas(self, cena):
        """⚠️ Unificar daria a quem vê uma sala o direito de ver a outra."""
        arq = os.urandom(1024)
        c = _cliente("ana")
        a = c.post(f"/api/chat/salas/{cena['sala']}/arquivo",
                   files={"arquivo": ("x.png", arq, "image/png")}).json()["midia_id"]
        b = c.post(f"/api/chat/salas/{cena['outra']}/arquivo",
                   files={"arquivo": ("x.png", arq, "image/png")}).json()["midia_id"]
        assert a != b


class TestOsLimites:
    def test_acima_do_teto_e_413(self, cena):
        grande = b"\0" * (chat.TETO_ARQUIVO + 1)
        r = _cliente("ana").post(f"/api/chat/salas/{cena['sala']}/arquivo",
                                 files={"arquivo": ("g.bin", grande,
                                                    "application/octet-stream")})
        assert r.status_code == 413
        assert str(chat.TETO_ARQUIVO_MB) in r.text

    def test_guardar_exige_UM_dono(self):
        """Dois donos ou nenhum estoura aqui, não lá na frente com uma linha
        órfã que ninguém sabe de quem é."""
        with pytest.raises(ValueError):
            midia.guardar(None, {"dados": b"x", "mime": "image/png",
                                 "tipo": "imagem", "nome_original": "x.png"})
        with pytest.raises(ValueError):
            midia.guardar(None, {"dados": b"x", "mime": "image/png",
                                 "tipo": "imagem", "nome_original": "x.png"},
                          conversa_id=1, sala_id=1)
