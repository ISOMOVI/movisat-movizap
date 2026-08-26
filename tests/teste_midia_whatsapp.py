"""Reagir, citar, áudio e encaminhar — bloco 8 (25/08).

🚨 NENHUM TESTE FALA COM O WHATSAPP. As rotas do Evolution 2.3.7 foram
medidas na instância real (`sendReaction` e `sendWhatsAppAudio` existem, e
`quoted` é campo do `sendText`, não rota) -- aqui o que se prova é a nossa
regra: de quem é a chave, o que recusa e o que fica gravado.

🚨 Escreve em `conversa`, `mensagem` e `atendente`, tabelas de PRODUÇÃO.
Telefone de DDD inexistente.
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

PREFIXO = "+559996666%"
FONE = "+5599966660001"
FONE2 = "+5599966660002"
LOGIN = "zz_teste_midia_"


def limpar():
    banco.executar(
        """DELETE FROM mensagem WHERE conversa_id IN
           (SELECT id FROM conversa WHERE telefone_e164 LIKE %s)""", (PREFIXO,))
    banco.executar("DELETE FROM conversa WHERE telefone_e164 LIKE %s", (PREFIXO,))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def pool():
    banco.abrir()
    limpar()
    yield
    limpar()
    banco.fechar()


@pytest.fixture(autouse=True)
def sem_whatsapp(monkeypatch):
    """Grava o que teria ido para o Evolution, e não manda nada."""
    saiu = {"texto": [], "reacao": [], "audio": []}

    def texto(instancia, numero, txt, citando=None):
        saiu["texto"].append({"numero": numero, "texto": txt, "citando": citando})
        return {"id_externo": f"zz-mid-{len(saiu['texto'])}",
                "status": "PENDING", "bruto": {}}

    def reacao(instancia, chave, emoji):
        saiu["reacao"].append({"chave": chave, "emoji": emoji})
        return {}

    def audio(instancia, numero, base64_dados):
        saiu["audio"].append({"numero": numero, "bytes": len(base64_dados)})
        return {"id_externo": f"zz-aud-{len(saiu['audio'])}",
                "status": "PENDING", "bruto": {}}

    # ⚠️ A ASSINATURA ACOMPANHA A REAL, como a do `enviar_texto`: mock com
    # assinatura velha reprova código correto e faz procurar defeito onde não
    # há -- a lição de 25/08, registrada logo acima.
    def midia(instancia, numero, base64_dados, mime, nome, legenda):
        saiu["midia"].append({"numero": numero, "mime": mime, "nome": nome,
                              "legenda": legenda, "bytes": len(base64_dados)})
        return {"id_externo": f"zz-mid-arq-{len(saiu['midia'])}",
                "status": "PENDING", "bruto": {}}

    saiu["midia"] = []
    monkeypatch.setattr(evolution, "enviar_texto", texto)
    monkeypatch.setattr(evolution, "enviar_reacao", reacao)
    monkeypatch.setattr(evolution, "enviar_audio", audio)
    monkeypatch.setattr(evolution, "enviar_midia", midia)
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
           VALUES ('Teste midia', %s, %s, 'x', 'atendimento', true) RETURNING id""",
        (LOGIN + "eu", f"{LOGIN}eu@movisat.com.br"))["id"]
    c1 = banco.um(
        """INSERT INTO conversa (canal_id, telefone_e164, estado, atendente_id)
           VALUES (%s, %s, 'humano', %s) RETURNING id""",
        (canal["id"], FONE, eu))["id"]
    c2 = banco.um(
        """INSERT INTO conversa (canal_id, telefone_e164, estado, atendente_id)
           VALUES (%s, %s, 'humano', %s) RETURNING id""",
        (canal["id"], FONE2, eu))["id"]
    # Uma mensagem do cliente, com id externo: é a que se cita e a que se reage.
    do_cliente = banco.um(
        """INSERT INTO mensagem (conversa_id, id_externo, direcao, autor, tipo,
                                 conteudo, criada_em)
           VALUES (%s, 'zz-cliente-1', 'entrada', 'cliente', 'texto',
                   'meu boleto venceu', now()) RETURNING id""", (c1,))["id"]
    # ⚠️ `direcao = 'interna'`, e o banco é quem ensinou: o CHECK
    # `ck_nota_e_interna` exige `(tipo = 'nota') = (direcao = 'interna')`.
    # Escrevi 'saida' na primeira versão e a inserção foi recusada -- a trava
    # de 05/08 fazendo exatamente o que foi escrita para fazer.
    nota = banco.um(
        """INSERT INTO mensagem (conversa_id, direcao, autor, tipo, conteudo,
                                 criada_em)
           VALUES (%s, 'interna', 'atendente', 'nota', 'anotacao', now())
           RETURNING id""", (c1,))["id"]
    yield {"c1": c1, "c2": c2, "eu": eu, "msg": do_cliente, "nota": nota}
    limpar()


class TestAChaveDaMensagem:
    """🚨 A CHAVE É RECONSTRUÍDA, NÃO GUARDADA: `id_externo` + a direção +
    o destino da conversa. Guardar o trio seria copiar o que já está aqui."""

    def test_monta_o_trio_do_whatsapp(self, cena):
        chave = conversas._chave_da_mensagem(cena["msg"])
        assert chave["id"] == "zz-cliente-1"
        assert chave["fromMe"] is False
        assert chave["remoteJid"].endswith("@s.whatsapp.net")

    def test_nota_interna_NAO_tem_chave(self, cena):
        """Ela nunca foi ao WhatsApp: não há o que apontar."""
        assert conversas._chave_da_mensagem(cena["nota"]) is None


def _reacoes(mensagem_id):
    """⚠️ A COLUNA `mensagem.reacao` SAIU NA MIGRAÇÃO 036. A verdade agora é
    `mensagem_reacao`, uma linha por (mensagem, quem) — porque o cliente
    passou a reagir também, e 40% das reações são em GRUPO, onde uma coluna
    guardaria o último e apagaria os outros em silêncio."""
    return banco.varios(
        "SELECT quem, emoji FROM mensagem_reacao WHERE mensagem_id = %s "
        " ORDER BY quem", (mensagem_id,))


class TestReagir:
    def test_reage_e_grava(self, cena, sem_whatsapp):
        r = conversas.reagir(cena["c1"], cena["msg"], "👍")
        assert r["ok"] is True
        assert sem_whatsapp["reacao"][0]["emoji"] == "👍"
        assert _reacoes(cena["msg"]) == [{"quem": "nos", "emoji": "👍"}]

    def test_reagir_de_novo_TROCA_nao_soma(self, cena, sem_whatsapp):
        conversas.reagir(cena["c1"], cena["msg"], "👍")
        conversas.reagir(cena["c1"], cena["msg"], "❤️")
        assert _reacoes(cena["msg"]) == [{"quem": "nos", "emoji": "❤️"}]

    def test_emoji_vazio_TIRA_a_reacao(self, cena, sem_whatsapp):
        """É assim que o WhatsApp desfaz: não existe "remover", existe reagir
        com nada. Por isso string vazia é caminho normal, não erro."""
        conversas.reagir(cena["c1"], cena["msg"], "👍")
        r = conversas.reagir(cena["c1"], cena["msg"], "")
        assert r["ok"] is True
        assert _reacoes(cena["msg"]) == []

    def test_nota_interna_nao_recebe_reacao(self, cena, sem_whatsapp):
        r = conversas.reagir(cena["c1"], cena["nota"], "👍")
        assert r["ok"] is False
        assert sem_whatsapp["reacao"] == []


class TestCitar:
    def test_a_citacao_vai_no_envio_e_fica_gravada(self, cena, sem_whatsapp):
        r = conversas.responder(cena["c1"], "já vou ver", cena["eu"],
                                citando_id=cena["msg"])
        assert r["ok"] is True
        assert sem_whatsapp["texto"][0]["citando"]["id"] == "zz-cliente-1"
        assert banco.um("SELECT citada_id FROM mensagem WHERE id = %s",
                        (r["mensagem_id"],))["citada_id"] == cena["msg"]

    def test_citar_mensagem_de_OUTRA_conversa_e_recusado(self, cena,
                                                         sem_whatsapp):
        """🚨 A chave carrega o `remoteJid` da conversa dela: citar de fora
        produziria uma citação que o destinatário não consegue abrir."""
        r = conversas.responder(cena["c2"], "oi", cena["eu"],
                                citando_id=cena["msg"])
        assert r["ok"] is False
        assert "desta conversa" in r["motivo"]
        assert sem_whatsapp["texto"] == []

    def test_citar_nota_interna_e_recusado(self, cena, sem_whatsapp):
        r = conversas.responder(cena["c1"], "oi", cena["eu"],
                                citando_id=cena["nota"])
        assert r["ok"] is False
        assert sem_whatsapp["texto"] == []

    def test_sem_citacao_o_envio_continua_igual(self, cena, sem_whatsapp):
        r = conversas.responder(cena["c1"], "oi", cena["eu"])
        assert r["ok"] is True
        assert sem_whatsapp["texto"][0]["citando"] is None


class TestAudio:
    def test_manda_como_voz_e_grava_como_audio(self, cena, sem_whatsapp):
        r = conversas.responder_com_audio(cena["c1"], b"ogg-falso", cena["eu"])
        assert r["ok"] is True
        assert len(sem_whatsapp["audio"]) == 1
        assert banco.um("SELECT tipo FROM mensagem WHERE id = %s",
                        (r["mensagem_id"],))["tipo"] == "audio"

    def test_audio_vazio_e_recusado(self, cena, sem_whatsapp):
        assert conversas.responder_com_audio(cena["c1"], b"", cena["eu"])["ok"] is False
        assert sem_whatsapp["audio"] == []

    def test_audio_acima_do_teto_e_recusado(self, cena, sem_whatsapp):
        gordo = b"0" * (conversas.TETO_AUDIO + 10)
        assert conversas.responder_com_audio(cena["c1"], gordo, cena["eu"])["ok"] is False
        assert sem_whatsapp["audio"] == []

    def test_conversa_concluida_nao_recebe_audio(self, cena, sem_whatsapp):
        conversas.encerrar(cena["c1"], atendente_id=cena["eu"])
        r = conversas.responder_com_audio(cena["c1"], b"ogg", cena["eu"])
        assert r["ok"] is False
        assert sem_whatsapp["audio"] == []


class TestEncaminhar:
    def test_repassa_e_marca_a_origem(self, cena, sem_whatsapp):
        """⚠️ Seis meses depois, ninguém sabe se a frase foi escrita para este
        cliente ou repassada -- e a diferença importa quando alguém reclama."""
        r = conversas.encaminhar(cena["msg"], [cena["c2"]], cena["eu"])
        assert r["ok"] is True and r["enviadas"] == 1
        nova = banco.um(
            """SELECT conteudo, encaminhada_de FROM mensagem
                WHERE conversa_id = %s ORDER BY id DESC LIMIT 1""", (cena["c2"],))
        assert nova["conteudo"] == "meu boleto venceu"
        assert nova["encaminhada_de"] == cena["msg"]

    def test_um_destino_ruim_nao_derruba_os_outros(self, cena, sem_whatsapp):
        """Cada destino é um envio; um falhar não pode fazer os outros não
        acontecerem."""
        conversas.encerrar(cena["c1"], atendente_id=cena["eu"])
        r = conversas.encaminhar(cena["msg"], [cena["c2"], cena["c1"]],
                                 cena["eu"])
        assert r["enviadas"] == 1
        assert len(r["falhas"]) == 1

    def test_sem_destino_e_recusado(self, cena):
        assert conversas.encaminhar(cena["msg"], [], cena["eu"])["ok"] is False

class TestEncaminharArquivo:
    """🚨 O ARQUIVO PASSOU A IR JUNTO EM 26/08. Até 25/08 encaminhar recusava
    mídia -- honesto, mas continuava sendo "não dá"."""

    @pytest.fixture()
    def com_arquivo(self, cena, tmp_path):
        caminho = tmp_path / "erro.png"
        caminho.write_bytes(b"\x89PNG-conteudo-de-teste")
        midia = banco.um(
            """INSERT INTO midia (conversa_id, caminho, mime, tamanho,
                                  nome_original, hash)
               VALUES (%s, %s, 'image/png', 22, 'erro.png', %s) RETURNING id""",
            (cena["c1"], str(caminho), "zz-hash-teste"))["id"]
        msg = banco.um(
            """INSERT INTO mensagem (conversa_id, id_externo, direcao, autor,
                                     tipo, conteudo, midia_id, criada_em)
               VALUES (%s, 'zz-img-1', 'entrada', 'cliente', 'imagem',
                       'olha o erro', %s, now()) RETURNING id""",
            (cena["c1"], midia))["id"]
        yield {"mensagem": msg, "midia": midia}
        banco.executar("DELETE FROM mensagem WHERE id = %s", (msg,))
        banco.executar("DELETE FROM midia WHERE id = %s", (midia,))

    def test_o_arquivo_vai_junto_com_a_legenda(self, cena, com_arquivo,
                                               sem_whatsapp):
        r = conversas.encaminhar(com_arquivo["mensagem"], [cena["c2"]], cena["eu"])
        assert r["ok"] is True and r["enviadas"] == 1
        assert len(sem_whatsapp["midia"]) == 1
        assert sem_whatsapp["midia"][0]["mime"] == "image/png"
        assert sem_whatsapp["midia"][0]["nome"] == "erro.png"
        assert sem_whatsapp["midia"][0]["legenda"] == "olha o erro"

    def test_a_nova_fica_marcada_como_encaminhada_e_com_anexo(
            self, cena, com_arquivo, sem_whatsapp):
        """⚠️ Sem `midia_id` na nova, o balão diria "encaminhada" e chegaria
        sem anexo -- o outro lado acharia que recebeu tudo."""
        conversas.encaminhar(com_arquivo["mensagem"], [cena["c2"]], cena["eu"])
        nova = banco.um(
            """SELECT tipo, midia_id, encaminhada_de FROM mensagem
                WHERE conversa_id = %s ORDER BY id DESC LIMIT 1""", (cena["c2"],))
        assert nova["encaminhada_de"] == com_arquivo["mensagem"]
        assert nova["midia_id"] is not None
        assert nova["tipo"] == "imagem"

    def test_encaminhar_arquivo_NAO_torna_ninguem_dono(self, cena, com_arquivo,
                                                       sem_whatsapp):
        """🚨 A auditoria de 25/08 achou que encaminhar tornava quem clicou
        dono de até 5 conversas. O texto ganhou `assumir=False`; o arquivo não
        tinha o parâmetro, e sem ele o defeito voltaria pela outra porta."""
        banco.executar("UPDATE conversa SET atendente_id = NULL WHERE id = %s",
                       (cena["c2"],))
        conversas.encaminhar(com_arquivo["mensagem"], [cena["c2"]], cena["eu"])
        assert banco.um("SELECT atendente_id FROM conversa WHERE id = %s",
                        (cena["c2"],))["atendente_id"] is None

    def test_um_arquivo_para_dois_destinos_nao_duplica_no_disco(
            self, cena, com_arquivo, sem_whatsapp):
        """⚠️ `midia.guardar` grava por SHA256 e só escreve se o caminho não
        existir: N conversas, N vínculos, UM arquivo."""
        conversas.encaminhar(com_arquivo["mensagem"], [cena["c2"]], cena["eu"])
        caminhos = banco.varios(
            "SELECT DISTINCT caminho FROM midia WHERE hash = %s",
            (banco.um("SELECT hash FROM midia WHERE id = %s",
                      (com_arquivo["midia"],))["hash"],))
        assert len(caminhos) == 1

    def test_arquivo_que_sumiu_do_disco_e_RECUSADO(self, cena, sem_whatsapp):
        """🚨 A linha existe e o arquivo não. Mandar só a legenda deixaria o
        outro lado sem o anexo sem ninguém saber -- e o balão diria
        "encaminhada"."""
        midia = banco.um(
            """INSERT INTO midia (conversa_id, caminho, mime, tamanho)
               VALUES (%s, '/tmp/zz-nao-existe', 'image/png', 10) RETURNING id""",
            (cena["c1"],))["id"]
        msg = banco.um(
            """INSERT INTO mensagem (conversa_id, id_externo, direcao, autor,
                                     tipo, conteudo, midia_id, criada_em)
               VALUES (%s, 'zz-img-2', 'entrada', 'cliente', 'imagem',
                       'olha', %s, now()) RETURNING id""",
            (cena["c1"], midia))["id"]
        try:
            r = conversas.encaminhar(msg, [cena["c2"]], cena["eu"])
            assert r["ok"] is False
            assert "disco" in r["motivo"]
            assert sem_whatsapp["midia"] == []
            assert sem_whatsapp["texto"] == [], \
                "mandou a legenda sem o anexo"
        finally:
            banco.executar("DELETE FROM mensagem WHERE id = %s", (msg,))
            banco.executar("DELETE FROM midia WHERE id = %s", (midia,))
