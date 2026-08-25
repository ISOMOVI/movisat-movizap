"""O botão `+` — falar primeiro com quem ainda não escreveu (25/08).

Até aqui a conversa só nascia quando CHEGAVA mensagem: `garantir_conversa`
roda dentro do webhook. Não havia caminho de saída.

🚨 NENHUM TESTE FALA COM O WHATSAPP. As duas fixtures que mockam
(`sem_enviar` e `whatsapp_responde`) são `autouse` de propósito: depender de
alguém lembrar de aplicá-las é o mesmo que não ter.

⚠️ Telefone de DDD inexistente (+55 99 …) para nunca colidir com número real.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, conversas, evolution  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

PREFIXO = "+559994444%"
NUMERO = "+5599944440001"
LOGIN = "zz_teste_nova_"


def limpar():
    banco.executar(
        """DELETE FROM mensagem WHERE conversa_id IN
           (SELECT id FROM conversa WHERE telefone_e164 LIKE %s)""", (PREFIXO,))
    banco.executar(
        """DELETE FROM conversa_participante WHERE conversa_id IN
           (SELECT id FROM conversa WHERE telefone_e164 LIKE %s)""", (PREFIXO,))
    banco.executar(
        """DELETE FROM transferencia WHERE conversa_id IN
           (SELECT id FROM conversa WHERE telefone_e164 LIKE %s)""", (PREFIXO,))
    banco.executar("DELETE FROM conversa WHERE telefone_e164 LIKE %s", (PREFIXO,))
    banco.executar(
        """DELETE FROM contato_telefone WHERE contato_id IN
           (SELECT id FROM contato WHERE nome LIKE %s)""", ("zz teste nova%",))
    banco.executar("DELETE FROM contato WHERE nome LIKE %s", ("zz teste nova%",))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()


@pytest.fixture(autouse=True)
def sem_enviar(monkeypatch):
    """🚨 Nenhum teste manda mensagem de verdade."""
    enviadas = []

    # ⚠️ A ASSINATURA ACOMPANHA A REAL. `citando` entrou em 25/08, com o
    # responder citando; mock que não aceita o argumento reprova código
    # correto e faz procurar defeito onde não há.
    def falso(instancia, numero, texto, citando=None):
        # 🚨 UM `id_externo` POR ENVIO. Um mock que devolve sempre o mesmo id
        # faz a segunda mensagem ser DESCARTADA pela trava de idempotência --
        # e o teste acusa o código por um defeito do próprio teste. Foi o que
        # aconteceu ao escrever este arquivo: `mensagem` tem UNIQUE em
        # `id_externo` justamente porque o Evolution reentrega.
        enviadas.append({"numero": numero, "texto": texto})
        return {"id_externo": f"zz-nova-{len(enviadas)}",
                "status": "PENDING", "bruto": {}}

    monkeypatch.setattr(evolution, "enviar_texto", falso)
    yield enviadas


@pytest.fixture(autouse=True)
def whatsapp_responde(monkeypatch):
    """Por padrão o número existe. Cada teste que precisar troca a resposta."""
    monkeypatch.setattr(evolution, "tem_whatsapp", lambda inst, e164: True)


@pytest.fixture()
def cena():
    limpar()
    canal = banco.um(
        "SELECT id FROM canal WHERE tipo = 'atendimento' AND ativo LIMIT 1")
    if not canal:
        pytest.skip("nenhum canal de atendimento ativo")
    eu = banco.um(
        """INSERT INTO atendente (nome, login, email, senha_hash, perfil, ativo)
           VALUES ('Teste nova', %s, %s, 'x', 'atendimento', true)
           RETURNING id""",
        (LOGIN + "eu", f"{LOGIN}eu@movisat.com.br"))["id"]
    yield {"canal": canal["id"], "eu": eu}
    limpar()


class TestPerguntaAntesDeGravar:
    def test_numero_sem_whatsapp_nao_cria_conversa(self, cena, monkeypatch):
        """🚨 O PASSO QUE EVITA LIXO NA CAIXA. Criar a conversa e só então
        descobrir que o número não tem WhatsApp deixaria uma conversa órfã,
        sem mensagem nenhuma, para alguém limpar à mão depois."""
        monkeypatch.setattr(evolution, "tem_whatsapp", lambda i, e: False)
        r = conversas.iniciar_conversa(cena["canal"], NUMERO, "oi", cena["eu"])
        assert r["ok"] is False
        assert r["sem_whatsapp"] is True
        assert banco.um("SELECT count(*) n FROM conversa "
                        " WHERE telefone_e164 = %s", (NUMERO,))["n"] == 0

    def test_a_recusa_manda_conferir_e_testar_no_celular(self, cena, monkeypatch):
        """Texto pedido pelo usuário em 25/08: dizer o motivo e o que fazer."""
        monkeypatch.setattr(evolution, "tem_whatsapp", lambda i, e: False)
        motivo = conversas.iniciar_conversa(
            cena["canal"], NUMERO, "oi", cena["eu"])["motivo"]
        assert "não tem WhatsApp" in motivo
        assert "celular" in motivo

    def test_sem_resposta_do_evolution_nao_envia_nem_grava(self, cena, monkeypatch):
        """🚨 `None` NÃO É `False`. Silêncio do Evolution é "não sei" -- tratar
        como "não tem" recusaria envio legítimo por falha de rede, e tratar
        como "tem" mandaria mensagem para o vazio."""
        monkeypatch.setattr(evolution, "tem_whatsapp", lambda i, e: None)
        r = conversas.iniciar_conversa(cena["canal"], NUMERO, "oi", cena["eu"])
        assert r["ok"] is False
        assert "não respondeu" in r["motivo"]
        assert banco.um("SELECT count(*) n FROM conversa "
                        " WHERE telefone_e164 = %s", (NUMERO,))["n"] == 0

    def test_numero_impossivel_e_recusado_antes_de_tudo(self, cena):
        r = conversas.iniciar_conversa(cena["canal"], "123", "oi", cena["eu"])
        assert r["ok"] is False
        assert "número" in r["motivo"].lower()

    def test_mensagem_vazia_e_recusada(self, cena):
        assert conversas.iniciar_conversa(
            cena["canal"], NUMERO, "   ", cena["eu"])["ok"] is False


class TestOEnvioAcontece:
    def test_cria_a_conversa_ja_com_dono(self, cena):
        r = conversas.iniciar_conversa(cena["canal"], NUMERO, "bom dia", cena["eu"])
        assert r["ok"] is True and r["nasceu"] is True
        linha = banco.um("SELECT atendente_id, estado FROM conversa WHERE id = %s",
                         (r["conversa_id"],))
        assert linha["atendente_id"] == cena["eu"]
        assert linha["estado"] == "humano"

    def test_a_mensagem_sai_para_o_numero_normalizado(self, cena, sem_enviar):
        conversas.iniciar_conversa(cena["canal"], "(99) 9444-40001", "oi",
                                   cena["eu"])
        assert len(sem_enviar) == 1
        assert "999444" in sem_enviar[0]["numero"]

    def test_a_mensagem_fica_gravada_na_conversa(self, cena):
        r = conversas.iniciar_conversa(cena["canal"], NUMERO, "bom dia", cena["eu"])
        msgs = conversas.mensagens(r["conversa_id"])
        assert [m["conteudo"] for m in msgs] == ["bom dia"]
        assert msgs[0]["direcao"] == "saida"


class TestConversaAbertaNaoViraDuas:
    """⚠️ `ux_conversa_aberta` é único por (canal, número) enquanto a conversa
    não está resolvida. Criar outra estouraria o índice NO MEIO DO ENVIO, que
    é a pior hora para falhar."""

    def test_a_segunda_chamada_abre_a_mesma_conversa(self, cena):
        primeira = conversas.iniciar_conversa(
            cena["canal"], NUMERO, "oi", cena["eu"])
        segunda = conversas.iniciar_conversa(
            cena["canal"], NUMERO, "de novo", cena["eu"])
        assert segunda["ok"] is True
        assert segunda["nasceu"] is False
        assert segunda["conversa_id"] == primeira["conversa_id"]

    def test_as_duas_mensagens_ficam_na_mesma_conversa(self, cena):
        r = conversas.iniciar_conversa(cena["canal"], NUMERO, "oi", cena["eu"])
        conversas.iniciar_conversa(cena["canal"], NUMERO, "de novo", cena["eu"])
        assert len(conversas.mensagens(r["conversa_id"])) == 2

    def test_nunca_existem_duas_conversas_abertas_do_mesmo_numero(self, cena):
        conversas.iniciar_conversa(cena["canal"], NUMERO, "oi", cena["eu"])
        conversas.iniciar_conversa(cena["canal"], NUMERO, "de novo", cena["eu"])
        assert banco.um(
            """SELECT count(*) n FROM conversa
                WHERE telefone_e164 = %s AND estado <> 'resolvida'""",
            (NUMERO,))["n"] == 1


class TestIdentificarDepoisDoEnvio:
    def test_numero_no_cadastro_ja_nasce_vinculado(self, cena):
        """Pedido do usuário: "se depois da mensagem for encontrado na base,
        já vincula"."""
        contato = banco.um(
            """INSERT INTO contato (nome, relacao, origem)
               VALUES ('zz teste nova contato', 'cliente', 'movizap')
               RETURNING id""")["id"]
        banco.executar(
            """INSERT INTO contato_telefone (contato_id, e164, bruto, principal)
               VALUES (%s, %s, %s, true)""", (contato, NUMERO, NUMERO))

        r = conversas.iniciar_conversa(cena["canal"], NUMERO, "oi", cena["eu"])
        assert r["identificada"] is True
        assert r["contato_nome"] == "zz teste nova contato"

    def test_numero_desconhecido_fica_sem_ficha_e_isso_e_normal(self, cena):
        """🚨 64% das conversas estão assim. Não é exceção: é a regra, e
        chutar de quem é produziria ficha errada."""
        r = conversas.iniciar_conversa(cena["canal"], NUMERO, "oi", cena["eu"])
        assert r["identificada"] is False
        assert r["contato_nome"] is None


class TestFiltroPorTipoDeCadastro:
    """🚨 "sem cadastro" e "sem identificação" são coisas DIFERENTES, e o
    usuário fez questão da distinção em 25/08."""

    def test_sem_cadastro_acha_a_conversa_sem_contato(self, cena):
        r = conversas.iniciar_conversa(cena["canal"], NUMERO, "oi", cena["eu"])
        achadas = [c["id"] for c in
                   conversas.listar(relacoes=["sem_cadastro"], limite=500)]
        assert r["conversa_id"] in achadas

    def test_filtrar_por_cliente_NAO_traz_a_conversa_sem_cadastro(self, cena):
        r = conversas.iniciar_conversa(cena["canal"], NUMERO, "oi", cena["eu"])
        achadas = [c["id"] for c in
                   conversas.listar(relacoes=["cliente"], limite=500)]
        assert r["conversa_id"] not in achadas

    def test_filtrar_pela_relacao_do_contato_vinculado(self, cena):
        contato = banco.um(
            """INSERT INTO contato (nome, relacao, origem)
               VALUES ('zz teste nova fornecedor', 'fornecedor', 'movizap')
               RETURNING id""")["id"]
        banco.executar(
            """INSERT INTO contato_telefone (contato_id, e164, bruto, principal)
               VALUES (%s, %s, %s, true)""", (contato, NUMERO, NUMERO))
        r = conversas.iniciar_conversa(cena["canal"], NUMERO, "oi", cena["eu"])

        achadas = [c["id"] for c in
                   conversas.listar(relacoes=["fornecedor"], limite=500)]
        assert r["conversa_id"] in achadas
        # E não aparece quando se pede outro tipo.
        outras = [c["id"] for c in
                  conversas.listar(relacoes=["tecnico"], limite=500)]
        assert r["conversa_id"] not in outras

    def test_os_chips_somam_em_OR(self, cena):
        r = conversas.iniciar_conversa(cena["canal"], NUMERO, "oi", cena["eu"])
        achadas = [c["id"] for c in conversas.listar(
            relacoes=["cliente", "sem_cadastro"], limite=500)]
        assert r["conversa_id"] in achadas

    def test_sem_chip_nenhum_a_lista_nao_muda(self, cena):
        r = conversas.iniciar_conversa(cena["canal"], NUMERO, "oi", cena["eu"])
        assert r["conversa_id"] in [
            c["id"] for c in conversas.listar(relacoes=[], limite=500)]
