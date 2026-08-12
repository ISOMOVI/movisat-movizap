"""Reabrir conversa encerrada, e a relação do contato — as duas de 12/08.

Encerrar era porta só de ida: `responder` recusa conversa resolvida e a tela
escondia a barra inteira, então o único jeito de voltar a falar era o cliente
escrever primeiro. Assumir uma conversa encerrada passou a reabri-la.

🚨 Escreve em `conversa`, `contato` e `atendente`, que são tabelas de
PRODUÇÃO. Mesma disciplina do `teste_participantes.py`: telefone de DDD
inexistente (+55 99 ...), login marcado, e a fixture apaga só o que criou.

⚠️ A lição de 06/08 vale aqui inteira: fixture que reusa linha de produção
passa com o banco vazio e começa a ler dado real assim que a base cresce. Nada
neste arquivo toca em contato, cliente ou atendente que já existisse.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, cadastro, conversas  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

FONE = "+5599933330000"
LOGIN = "zz_teste_reabrir_"
NOME_CONTATO = "zz teste reabrir contato"


def limpar():
    banco.executar(
        """DELETE FROM transferencia WHERE conversa_id IN
           (SELECT id FROM conversa WHERE telefone_e164 = %s)""", (FONE,))
    banco.executar(
        """DELETE FROM mensagem WHERE conversa_id IN
           (SELECT id FROM conversa WHERE telefone_e164 = %s)""", (FONE,))
    banco.executar("DELETE FROM conversa WHERE telefone_e164 = %s", (FONE,))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))
    banco.executar("DELETE FROM contato WHERE nome = %s", (NOME_CONTATO,))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()


@pytest.fixture()
def cena():
    """Uma conversa ENCERRADA, com quem a encerrou, e um segundo atendente."""
    limpar()
    canal = banco.um("SELECT id FROM canal WHERE instancia = 'atendimento'")
    if not canal:
        pytest.skip("canal atendimento não cadastrado")

    ids = []
    for n in ("fechou", "outro"):
        ids.append(banco.um(
            """INSERT INTO atendente (nome, login, senha_hash, perfil, ativo)
               VALUES (%s, %s, 'x', 'atendimento', true) RETURNING id""",
            (f"Teste {n}", LOGIN + n))["id"])

    conversa = banco.um(
        """INSERT INTO conversa (canal_id, telefone_e164, estado, atendente_id,
                                 resolvida_em, segundos_total)
           VALUES (%s, %s, 'resolvida', %s, now(), 4242) RETURNING id""",
        (canal["id"], FONE, ids[0]))["id"]
    yield {"conversa": conversa, "canal": canal["id"],
           "fechou": ids[0], "outro": ids[1]}
    limpar()


def estado_de(conversa_id):
    return banco.um(
        "SELECT estado, atendente_id, resolvida_em, segundos_total "
        "FROM conversa WHERE id = %s", (conversa_id,))


class TestReabrir:
    def test_assumir_encerrada_reabre_e_troca_o_dono(self, cena):
        r = conversas.assumir(cena["conversa"], cena["outro"])
        assert r["ok"] is True
        assert r["reaberta"] is True

        # 🚨 A prova é RELER O ESTADO, não o `ok` que a função devolveu.
        agora = estado_de(cena["conversa"])
        assert agora["estado"] == "humano"
        assert agora["atendente_id"] == cena["outro"]

    def test_reabrir_limpa_as_metricas_congeladas_no_fechamento(self, cena):
        """`resolvida_em` e `segundos_total` são congeladas ao encerrar.

        Deixá-las preenchidas numa conversa que voltou a andar faria a ATD_5.1
        listar como encerrada uma conversa aberta -- ela filtra por
        `estado = 'resolvida'` e ordena por `resolvida_em`.
        """
        antes = estado_de(cena["conversa"])
        assert antes["resolvida_em"] is not None
        assert antes["segundos_total"] == 4242

        conversas.assumir(cena["conversa"], cena["outro"])

        depois = estado_de(cena["conversa"])
        assert depois["resolvida_em"] is None
        assert depois["segundos_total"] is None

    def test_reaberta_sai_do_historico(self, cena):
        """O Histórico (ATD_5.1) não pode continuar mostrando o que reabriu."""
        assert any(c["id"] == cena["conversa"] for c in conversas.historico())
        conversas.assumir(cena["conversa"], cena["outro"])
        assert not any(c["id"] == cena["conversa"] for c in conversas.historico())

    def test_reabrir_e_responder_deixa_de_ser_recusado(self, cena, monkeypatch):
        """O motivo de tudo isto: `responder` recusa conversa resolvida.

        🚨 O ENVIO É DUBLADO DE PROPÓSITO. A primeira versão deste teste
        chamava `responder` de verdade depois de reabrir -- e o canal
        'atendimento' TEM instância, então a suíte passou a bater no Evolution
        e a tentar mandar WhatsApp para o número falso, a cada execução. Passou
        verde só porque o WhatsApp recusou o número. Teste que depende de um
        gateway externo recusar não é teste, é sorte -- e um dígito trocado na
        fixture viraria mensagem para gente de verdade.
        """
        # Antes de reabrir a recusa nem chega no envio: o estado barra primeiro.
        recusado = conversas.responder(cena["conversa"], "oi", cena["outro"])
        assert recusado["ok"] is False
        assert "encerrada" in recusado["motivo"].lower()

        conversas.assumir(cena["conversa"], cena["outro"])

        from movizap import evolution
        enviados = []

        def fingir(instancia, e164, texto):
            enviados.append((instancia, e164, texto))
            return {"id_externo": "TESTE_REABRIR_1"}

        monkeypatch.setattr(evolution, "enviar_texto", fingir)

        depois = conversas.responder(cena["conversa"], "oi", cena["outro"])
        assert depois["ok"] is True, depois.get("motivo")
        assert enviados and enviados[0][1] == FONE, "o número sai da CONVERSA"

    def test_nao_reabre_quando_o_numero_ja_tem_conversa_viva(self, cena):
        """🚨 `ux_conversa_aberta` é único em (canal, telefone) WHERE não
        resolvida -- é o que faz o cliente que volta REABRIR em vez de
        duplicar. Se ele já escreveu depois do encerramento, existe outra
        conversa aberta e reabrir esta estouraria o índice.

        Forçar aqui não daria "erro de negócio": daria UniqueViolation crua,
        500 na tela e nada explicado a quem clicou.
        """
        viva = banco.um(
            """INSERT INTO conversa (canal_id, telefone_e164, estado)
               VALUES (%s, %s, 'nova') RETURNING id""",
            (cena["canal"], FONE))["id"]

        r = conversas.assumir(cena["conversa"], cena["outro"])
        assert r["ok"] is False
        assert r["conversa_aberta_id"] == viva
        assert str(viva) in r["motivo"], "a mensagem tem de dizer QUAL conversa"

        # E a encerrada continua encerrada: nada foi tocado pela metade.
        assert estado_de(cena["conversa"])["estado"] == "resolvida"

    def test_assumir_conversa_aberta_com_dono_continua_recusando(self, cena):
        """Reabrir não podia afrouxar a trava de posse do caso comum."""
        banco.executar(
            "UPDATE conversa SET estado = 'humano', resolvida_em = NULL "
            "WHERE id = %s", (cena["conversa"],))
        r = conversas.assumir(cena["conversa"], cena["outro"])
        assert r["ok"] is False
        assert "já foi assumida" in r["motivo"]
        assert estado_de(cena["conversa"])["atendente_id"] == cena["fechou"]

    def test_assumir_sem_dono_nao_marca_reaberta(self, cena):
        """O caso comum não pode passar a dizer que reabriu alguma coisa."""
        banco.executar(
            "UPDATE conversa SET estado = 'fila', atendente_id = NULL, "
            "resolvida_em = NULL WHERE id = %s", (cena["conversa"],))
        r = conversas.assumir(cena["conversa"], cena["outro"])
        assert r["ok"] is True
        assert r["reaberta"] is False


class TestRelacaoDoContato:
    """O campo existia desde a migração 001 e nunca teve rota de escrita."""

    @pytest.fixture()
    def contato_id(self):
        banco.executar("DELETE FROM contato WHERE nome = %s", (NOME_CONTATO,))
        novo = banco.um(
            """INSERT INTO contato (nome, relacao, origem, ativo)
               VALUES (%s, 'cliente', 'movizap', true) RETURNING id""",
            (NOME_CONTATO,))["id"]
        yield novo
        banco.executar("DELETE FROM contato WHERE id = %s", (novo,))

    def test_marca_como_fornecedor(self, contato_id):
        r = cadastro.definir_relacao(contato_id, "fornecedor")
        assert r["ok"] is True
        lido = banco.um("SELECT relacao FROM contato WHERE id = %s", (contato_id,))
        assert lido["relacao"] == "fornecedor"

    def test_aceita_os_dois_valores_que_a_migracao_023_criou(self, contato_id):
        for novo in ("colaborador", "teste"):
            assert cadastro.definir_relacao(contato_id, novo)["ok"] is True
            assert banco.um("SELECT relacao FROM contato WHERE id = %s",
                            (contato_id,))["relacao"] == novo

    def test_valor_fora_do_vocabulario_e_recusado_antes_do_banco(self, contato_id):
        """⚠️ Sem esta guarda o psycopg devolveria CheckViolation crua — 500 na
        tela, em vez de "vale uma de: ..."."""
        r = cadastro.definir_relacao(contato_id, "amigo")
        assert r["ok"] is False
        assert "inválida" in r["motivo"]
        assert banco.um("SELECT relacao FROM contato WHERE id = %s",
                        (contato_id,))["relacao"] == "cliente"

    def test_a_lista_do_codigo_bate_com_o_CHECK_do_banco(self):
        """🚨 Três listas dizem o mesmo vocabulário: o CHECK, `cadastro.RELACOES`
        e o <select> da CAD_1.2. Se o código oferecer um valor que o banco
        recusa, a tela grava e falha -- então o banco é lido, não suposto."""
        definicao = banco.um(
            "SELECT pg_get_constraintdef(oid) AS d FROM pg_constraint "
            "WHERE conname = 'contato_relacao_check'")["d"]
        for valor in cadastro.RELACOES:
            assert f"'{valor}'" in definicao, f"{valor} não está no CHECK"

    def test_contato_inexistente(self):
        r = cadastro.definir_relacao(-1, "cliente")
        assert r["ok"] is False
        assert "não encontrado" in r["motivo"]
