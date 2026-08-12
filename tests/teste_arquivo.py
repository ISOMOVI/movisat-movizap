"""Envio de arquivo para o cliente — o que era "Fase 2" até 12/08.

🚨 O ENVIO É SEMPRE DUBLADO. O canal `atendimento` TEM instância, então um
teste que chamasse o Evolution de verdade mandaria WhatsApp a cada execução —
o erro que este projeto já cometeu em 12/08 e corrigiu no mesmo dia.

🚨 Escreve em `conversa`, `mensagem`, `midia` e `atendente`, tabelas de
PRODUÇÃO. Telefone de DDD inexistente e login com prefixo `zz`.
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

FONE = "+5599966660000"
LOGIN = "zz_teste_arq_"
PNG = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)


def limpar():
    banco.executar(
        """DELETE FROM mensagem WHERE conversa_id IN
           (SELECT id FROM conversa WHERE telefone_e164 = %s)""", (FONE,))
    banco.executar(
        """DELETE FROM midia WHERE conversa_id IN
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
def cena(monkeypatch):
    limpar()
    canal = banco.um("SELECT id FROM canal WHERE instancia = 'atendimento'")
    if not canal:
        pytest.skip("canal atendimento não cadastrado")
    dono = banco.um(
        """INSERT INTO atendente (nome, login, email, senha_hash, perfil, ativo)
           VALUES ('Teste Arq', %s, %s, 'x', 'atendimento', true) RETURNING id""",
        (LOGIN + "dono", LOGIN + "dono@movisat.com.br"))["id"]
    conversa = banco.um(
        """INSERT INTO conversa (canal_id, telefone_e164, estado, atendente_id)
           VALUES (%s, %s, 'humano', %s) RETURNING id""",
        (canal["id"], FONE, dono))["id"]

    enviados = []

    def fingir(instancia, e164, base64_dados, mime, nome, legenda=""):
        enviados.append({"instancia": instancia, "e164": e164, "mime": mime,
                         "nome": nome, "legenda": legenda,
                         "base64": base64_dados})
        return {"id_externo": f"TESTE_ARQ_{len(enviados)}", "status": "PENDING"}

    monkeypatch.setattr(evolution, "enviar_midia", fingir)
    yield {"conversa": conversa, "dono": dono, "enviados": enviados}
    limpar()


class TestTipoDeMidia:
    """⚠️ Vocabulário FECHADO do Evolution. Valor errado não dá erro claro --
    dá mensagem que não chega."""

    @pytest.mark.parametrize("mime,esperado", [
        ("image/jpeg", "image"), ("image/png", "image"),
        ("video/mp4", "video"), ("audio/ogg", "audio"),
        ("application/pdf", "document"),
        ("text/plain", "document"),
        ("", "document"), (None, "document"),
    ])
    def test_mapeia_pelo_MIME(self, mime, esperado):
        assert evolution.tipo_de_midia(mime) == esperado


class TestEnvioDeArquivo:
    def test_envia_e_grava_a_mensagem(self, cena):
        r = conversas.responder_com_arquivo(
            cena["conversa"], PNG, "image/png", "foto.png", "olha aí",
            cena["dono"])
        assert r["ok"] is True, r.get("motivo")

        linha = banco.um(
            "SELECT tipo, conteudo, direcao, midia_id, id_externo, atendente_id "
            "  FROM mensagem WHERE id = %s", (r["mensagem_id"],))
        assert linha["direcao"] == "saida"
        assert linha["tipo"] == "imagem"
        assert linha["conteudo"] == "olha aí", "a legenda tem de virar o texto"
        assert linha["midia_id"] is not None, "o balão ficaria sem o anexo"
        assert linha["atendente_id"] == cena["dono"]

    def test_o_numero_sai_da_CONVERSA(self, cena):
        """🚨 A linha que impede o painel de virar ferramenta de disparo."""
        conversas.responder_com_arquivo(
            cena["conversa"], PNG, "image/png", "x.png", "", cena["dono"])
        assert cena["enviados"][0]["e164"] == FONE

    def test_grava_o_id_externo_que_o_whatsapp_devolveu(self, cena):
        """Sem ele, o eco do Evolution vira um segundo balão igual."""
        r = conversas.responder_com_arquivo(
            cena["conversa"], PNG, "image/png", "x.png", "", cena["dono"])
        assert r["id_externo"] == "TESTE_ARQ_1"
        assert banco.um("SELECT id_externo FROM mensagem WHERE id = %s",
                        (r["mensagem_id"],))["id_externo"] == "TESTE_ARQ_1"

    def test_o_arquivo_vai_para_o_disco_e_para_a_tabela_midia(self, cena):
        r = conversas.responder_com_arquivo(
            cena["conversa"], PNG, "image/png", "foto.png", "", cena["dono"])
        m = banco.um("SELECT mime, tamanho, caminho, nome_original FROM midia "
                     " WHERE id = %s", (r["midia_id"],))
        assert m["mime"] == "image/png"
        assert m["tamanho"] == len(PNG)
        assert m["nome_original"] == "foto.png"
        assert Path(m["caminho"]).exists(), "gravou a linha e não o arquivo"

    def test_pdf_vai_como_documento_com_o_nome(self, cena):
        """⚠️ `fileName` é o nome que o cliente vê para abrir o PDF."""
        r = conversas.responder_com_arquivo(
            cena["conversa"], b"%PDF-1.4 fake", "application/pdf",
            "contrato.pdf", "", cena["dono"])
        assert r["ok"] is True
        assert cena["enviados"][0]["nome"] == "contrato.pdf"
        assert banco.um("SELECT tipo FROM mensagem WHERE id = %s",
                        (r["mensagem_id"],))["tipo"] == "documento"

    def test_sem_legenda_o_conteudo_fica_NULO(self, cena):
        r = conversas.responder_com_arquivo(
            cena["conversa"], PNG, "image/png", "x.png", "   ", cena["dono"])
        assert banco.um("SELECT conteudo FROM mensagem WHERE id = %s",
                        (r["mensagem_id"],))["conteudo"] is None


class TestOTetoEDoUsuario:
    def test_o_teto_e_25_MB(self):
        """Decisão do usuário em 12/08. Eu tinha posto 16 por conta própria,
        e teto é decisão dele -- regra que ele já tinha dado no dia anterior.
        Este teste existe para o número não voltar a mudar sozinho."""
        assert conversas.TETO_ARQUIVO_MB == 25
        assert conversas.TETO_ARQUIVO == 25 * 1024 * 1024


class TestAnexoNaNotaInterna:
    """Anexo vale nos DOIS modos — decisão do usuário em 12/08."""

    def test_anexa_e_grava_como_nota(self, cena):
        r = conversas.anotar_com_arquivo(
            cena["conversa"], PNG, "image/png", "print.png",
            "erro que o cliente mandou", cena["dono"])
        assert r["ok"] is True
        linha = banco.um(
            "SELECT direcao, tipo, conteudo, midia_id, atendente_id "
            "  FROM mensagem WHERE id = %s", (r["mensagem_id"],))
        assert linha["direcao"] == "interna"
        assert linha["tipo"] == "nota", "o CHECK ck_nota_e_interna exige isso"
        assert linha["conteudo"] == "erro que o cliente mandou"
        assert linha["midia_id"] is not None
        assert linha["atendente_id"] == cena["dono"]

    def test_NAO_chama_o_evolution(self, cena):
        """🚨 A garantia de que a nota não vaza para o cliente. O dublê da
        fixture registra toda chamada -- se algo for enviado, aparece aqui."""
        conversas.anotar_com_arquivo(
            cena["conversa"], PNG, "image/png", "x.png", "", cena["dono"])
        assert cena["enviados"] == [], "a nota interna saiu para o WhatsApp"

    def test_o_arquivo_vai_para_o_disco(self, cena):
        r = conversas.anotar_com_arquivo(
            cena["conversa"], PNG, "image/png", "print.png", "", cena["dono"])
        m = banco.um("SELECT caminho, nome_original FROM midia WHERE id = %s",
                     (r["midia_id"],))
        assert Path(m["caminho"]).exists()
        assert m["nome_original"] == "print.png"

    def test_nota_sem_texto_so_com_arquivo(self, cena):
        r = conversas.anotar_com_arquivo(
            cena["conversa"], PNG, "image/png", "x.png", "  ", cena["dono"])
        assert r["ok"] is True
        assert banco.um("SELECT conteudo FROM mensagem WHERE id = %s",
                        (r["mensagem_id"],))["conteudo"] is None

    def test_respeita_o_mesmo_teto(self, cena):
        grande = b"\x00" * (conversas.TETO_ARQUIVO + 1)
        r = conversas.anotar_com_arquivo(
            cena["conversa"], grande, "image/png", "x.png", "", cena["dono"])
        assert r["ok"] is False
        assert "teto" in r["motivo"].lower()

    def test_arquivo_vazio_e_recusado(self, cena):
        assert conversas.anotar_com_arquivo(
            cena["conversa"], b"", "image/png", "x.png", "",
            cena["dono"])["ok"] is False

    def test_conversa_inexistente(self, cena):
        assert conversas.anotar_com_arquivo(
            -1, PNG, "image/png", "x.png", "", cena["dono"])["ok"] is False

    def test_nota_com_anexo_funciona_em_conversa_ENCERRADA(self, cena):
        """⚠️ Diferente do envio: anotar não depende do canal, e registrar
        algo numa conversa já encerrada é legítimo."""
        banco.executar(
            "UPDATE conversa SET estado = 'resolvida', resolvida_em = now() "
            " WHERE id = %s", (cena["conversa"],))
        assert conversas.anotar_com_arquivo(
            cena["conversa"], PNG, "image/png", "x.png", "depois do fim",
            cena["dono"])["ok"] is True


class TestOQueEleRECUSA:
    def test_arquivo_vazio(self, cena):
        r = conversas.responder_com_arquivo(
            cena["conversa"], b"", "image/png", "x.png", "", cena["dono"])
        assert r["ok"] is False
        assert not cena["enviados"], "chamou o Evolution com arquivo vazio"

    def test_acima_do_teto(self, cena):
        grande = b"\x00" * (conversas.TETO_ARQUIVO + 1)
        r = conversas.responder_com_arquivo(
            cena["conversa"], grande, "image/png", "x.png", "", cena["dono"])
        assert r["ok"] is False
        assert "teto" in r["motivo"].lower()
        assert not cena["enviados"], "subiu o arquivo antes de conferir o teto"

    def test_conversa_ENCERRADA(self, cena):
        banco.executar(
            "UPDATE conversa SET estado = 'resolvida', resolvida_em = now() "
            " WHERE id = %s", (cena["conversa"],))
        r = conversas.responder_com_arquivo(
            cena["conversa"], PNG, "image/png", "x.png", "", cena["dono"])
        assert r["ok"] is False
        assert not cena["enviados"]

    def test_conversa_inexistente(self, cena):
        r = conversas.responder_com_arquivo(
            -1, PNG, "image/png", "x.png", "", cena["dono"])
        assert r["ok"] is False
        assert not cena["enviados"]

    def test_recusa_do_whatsapp_NAO_grava_mensagem(self, cena, monkeypatch):
        """🚨 ENVIA PRIMEIRO, GRAVA DEPOIS. O contrário registraria como
        enviado um arquivo que o WhatsApp recusou."""
        def estourar(*a, **k):
            raise evolution.ErroEvolution("tipo não suportado", 400)
        monkeypatch.setattr(evolution, "enviar_midia", estourar)

        antes = banco.um("SELECT count(*) n FROM mensagem WHERE conversa_id = %s",
                         (cena["conversa"],))["n"]
        r = conversas.responder_com_arquivo(
            cena["conversa"], PNG, "image/png", "x.png", "", cena["dono"])
        assert r["ok"] is False
        assert "recusou" in r["motivo"]
        depois = banco.um("SELECT count(*) n FROM mensagem WHERE conversa_id = %s",
                          (cena["conversa"],))["n"]
        assert depois == antes, "gravou mensagem de um envio que falhou"
