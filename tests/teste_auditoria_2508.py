"""Os defeitos achados na auditoria de 25/08, presos por teste.

🚨 TODOS FORAM ESCRITOS POR MIM NO MESMO DIA, e nenhum apareceu na suíte: eles
não quebravam nada, faziam a coisa errada em silêncio. É a razão de a
auditoria existir separada da entrega.

🚨 Escreve em `conversa`, `mensagem` e `atendente`, tabelas de PRODUÇÃO.
Telefone de DDD inexistente.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import automacao, banco, conversas, evolution  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

PREFIXO = "+559998888%"
LOGIN = "zz_teste_audit_"


def limpar():
    for tabela in ("conversa_participante", "mensagem", "transferencia"):
        banco.executar(
            f"""DELETE FROM {tabela} WHERE conversa_id IN
                (SELECT id FROM conversa WHERE telefone_e164 LIKE %s)""",
            (PREFIXO,))
    banco.executar("DELETE FROM conversa WHERE telefone_e164 LIKE %s", (PREFIXO,))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    antes = banco.varios(
        "SELECT relacao, boas_vindas_ligado, boas_vindas_texto "
        "  FROM relacao_automacao")
    limpar()
    yield
    limpar()
    for l in antes:
        banco.executar(
            """UPDATE relacao_automacao
                  SET boas_vindas_ligado = %s, boas_vindas_texto = %s
                WHERE relacao = %s""",
            (l["boas_vindas_ligado"], l["boas_vindas_texto"], l["relacao"]))
    banco.fechar()


@pytest.fixture(autouse=True)
def sem_whatsapp(monkeypatch):
    saiu = []

    def texto(instancia, numero, txt, citando=None):
        saiu.append({"numero": numero, "texto": txt})
        return {"id_externo": f"zz-aud-{len(saiu)}", "status": "PENDING",
                "bruto": {}}

    monkeypatch.setattr(evolution, "enviar_texto", texto)
    yield saiu


@pytest.fixture()
def cena():
    limpar()
    canal = banco.um(
        "SELECT id FROM canal WHERE tipo = 'atendimento' AND ativo LIMIT 1")
    if not canal:
        pytest.skip("nenhum canal de atendimento ativo")
    eu = banco.um(
        """INSERT INTO atendente (nome, login, email, senha_hash, perfil, ativo)
           VALUES ('Teste audit', %s, %s, 'x', 'atendimento', true) RETURNING id""",
        (LOGIN + "eu", f"{LOGIN}eu@movisat.com.br"))["id"]
    minha = banco.um(
        """INSERT INTO conversa (canal_id, telefone_e164, estado, atendente_id)
           VALUES (%s, %s, 'humano', %s) RETURNING id""",
        (canal["id"], PREFIXO.replace("%", "0001"), eu))["id"]
    # Duas conversas SEM DONO: são 336 assim na base real.
    sem_dono = [
        banco.um(
            """INSERT INTO conversa (canal_id, telefone_e164, estado)
               VALUES (%s, %s, 'nova') RETURNING id""",
            (canal["id"], PREFIXO.replace("%", f"000{n}")))["id"]
        for n in (2, 3)
    ]
    msg = banco.um(
        """INSERT INTO mensagem (conversa_id, id_externo, direcao, autor, tipo,
                                 conteudo, criada_em)
           VALUES (%s, 'zz-audit-1', 'entrada', 'cliente', 'texto',
                   'texto original', now()) RETURNING id""", (minha,))["id"]
    yield {"eu": eu, "minha": minha, "sem_dono": sem_dono, "msg": msg,
           "canal": canal["id"]}
    limpar()


class TestEncaminharNaoTornaNinguemDono:
    """🚨 O DEFEITO: `encaminhar` chamava `responder`, e `responder` tem
    "quem responde assume". Encaminhar para 5 conversas sem dono tornava quem
    clicou dono DAS CINCO, de uma vez, sem pedir nada -- e há 336 conversas
    sem dono na base. Repassar não é atender.
    """

    def test_a_conversa_de_destino_continua_sem_dono(self, cena):
        conversas.encaminhar(cena["msg"], cena["sem_dono"], cena["eu"])
        for destino in cena["sem_dono"]:
            linha = banco.um(
                "SELECT atendente_id FROM conversa WHERE id = %s", (destino,))
            assert linha["atendente_id"] is None, (
                "encaminhar tornou quem clicou dono da conversa de destino")

    def test_mas_a_mensagem_chegou(self, cena, sem_whatsapp):
        r = conversas.encaminhar(cena["msg"], cena["sem_dono"], cena["eu"])
        assert r["enviadas"] == 2
        assert len(sem_whatsapp) == 2

    def test_responder_normal_CONTINUA_assumindo(self, cena):
        """⚠️ A regra original não mudou: quem RESPONDE assume. Sem isto, dois
        atendentes respondem o mesmo cliente sem nunca aparecer dono."""
        alvo = cena["sem_dono"][0]
        conversas.responder(alvo, "oi", cena["eu"])
        assert banco.um("SELECT atendente_id FROM conversa WHERE id = %s",
                        (alvo,))["atendente_id"] == cena["eu"]


class TestBoasVindasSoNaPrimeiraMensagem:
    """🚨 O DEFEITO: a trava era só `boas_vindas_em IS NULL`, e as 332
    conversas que já existiam têm esse campo nulo. Ligar a saudação mandaria
    "olá, seja bem-vindo" para gente NO MEIO de conversa em andamento,
    conforme cada uma escrevesse de novo.
    """

    def _ligar(self):
        automacao.definir("sem_cadastro", boas_vindas_ligado=True,
                          boas_vindas_texto="Olá, seja bem-vindo.")

    def test_conversa_em_andamento_NAO_recebe(self, cena, sem_whatsapp):
        self._ligar()
        alvo = cena["sem_dono"][0]
        for i in range(2):
            banco.executar(
                """INSERT INTO mensagem (conversa_id, id_externo, direcao,
                                         autor, tipo, conteudo, criada_em)
                   VALUES (%s, %s, 'entrada', 'cliente', 'texto', %s, now())""",
                (alvo, f"zz-and-{i}", f"mensagem {i}"))
        r = automacao.boas_vindas(alvo)
        assert r["enviou"] is False
        assert r["motivo"] == "conversa ja em andamento"
        assert sem_whatsapp == []

    def test_conversa_que_ACABOU_de_nascer_recebe(self, cena, sem_whatsapp):
        self._ligar()
        alvo = cena["sem_dono"][1]
        banco.executar(
            """INSERT INTO mensagem (conversa_id, id_externo, direcao, autor,
                                     tipo, conteudo, criada_em)
               VALUES (%s, 'zz-nova-1', 'entrada', 'cliente', 'texto',
                       'oi', now())""", (alvo,))
        assert automacao.boas_vindas(alvo)["enviou"] is True
        assert sem_whatsapp[0]["texto"] == "Olá, seja bem-vindo."


class TestAFilaDaAutomacaoNaoEGlobal:
    """🚨 O DEFEITO: `_boas_vindas_depois` era lista de MÓDULO, e
    `processar_pendentes` roda no laço de 5 s E na rota
    `/api/conversas/processar`. Com as duas ao mesmo tempo, o `clear()` de uma
    apagava os ids que a outra tinha enfileirado -- e o cliente simplesmente
    não receberia a saudação, sem nada acusar.
    """

    def test_o_modulo_nao_guarda_mais_estado_entre_execucoes(self):
        assert not hasattr(conversas, "_boas_vindas_depois"), (
            "a lista voltou a ser de módulo: duas execuções simultâneas se "
            "atrapalham de novo")

    def test_gravar_mensagem_recebe_onde_enfileirar(self):
        import inspect
        assert "depois" in inspect.signature(
            conversas._gravar_mensagem).parameters
