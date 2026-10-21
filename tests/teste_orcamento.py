"""Orçamento de serviço técnico — numeração, conta e PDF (21/10).

🚨 ESCREVE EM `orcamento`, `orcamento_item` e NO `config` — e é por isso que a
numeração aqui é **salva e devolvida** no fim de cada teste que a mexe. Foi um
teste meu escrevendo direto na `config` de produção que desligou a
distribuição por nove minutos em 19/10. A chave daqui
(`orcamento_proximo_numero`) não liga nem desliga nada, mas a régua é a
mesma: teste não deixa rastro em configuração.

🚨 E NÃO MANDA NADA PARA O WHATSAPP. `emitir` recebe o envio por parâmetro, e
o teste passa uma função que só guarda o que receberia.

O que estes testes guardam:
  · o total bate com a soma dos itens, em centavos (nada de float);
  · a numeração **não pula e não repete**, e o número só é gasto com PDF
    pronto -- falha ao montar o documento não consome número;
  · 🔵 deslocamento é por km: 1,00 x 77,7 km = 77,70, e o PDF escreve
    "77,7 km" (o documento de hoje escreve "77.7 un");
  · o catálogo é a lista fechada que ele decidiu: deslocamento e pagamento de
    técnico, com os nomes do Harmonit;
  · linha sem serviço, quantidade zero e unidade inventada são recusadas.
"""
import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")
pytest.importorskip("fpdf")

from movizap import banco, orcamento  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

CLIENTE = "Zz Teste Orcamento"
LOGIN = "zz_teste_orc_"

ITENS = [
    {"servico": "KM DESLOCAMENTO", "preco_unit": "1.00",
     "quantidade": "77.7", "unidade": "km"},
    {"servico": "PAGAMENTO DE TECNICO", "preco_unit": "100.00",
     "quantidade": "1", "unidade": "un"},
]


def limpar():
    banco.executar(
        """DELETE FROM orcamento_item WHERE orcamento_id IN
            (SELECT o.id FROM orcamento o JOIN atendente a ON a.id = o.criado_por
              WHERE a.login LIKE %s)""", (LOGIN + "%",))
    banco.executar(
        """DELETE FROM orcamento WHERE criado_por IN
            (SELECT id FROM atendente WHERE login LIKE %s)""", (LOGIN + "%",))
    banco.executar(
        """DELETE FROM conversa WHERE contato_id IN
            (SELECT id FROM contato WHERE nome LIKE %s)""", (CLIENTE + "%",))
    banco.executar("DELETE FROM contato WHERE nome LIKE %s", (CLIENTE + "%",))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def base():
    banco.abrir()
    limpar()
    # 🚨 O retrato da numeração ANTES de qualquer teste. É ele que volta no
    # fim -- a confirmação é reler o estado, nunca o retorno do comando.
    numero_antes = orcamento.proximo_numero()

    with banco.cursor() as cur:
        cur.execute("""INSERT INTO atendente (nome, login, email, senha_hash,
                                              perfil, ativo)
                       VALUES (%s,%s,%s,'x','atendimento',true) RETURNING id""",
                    ("Zz Orcamento", LOGIN + "1", LOGIN + "1@teste.invalid"))
        atendente = cur.fetchone()["id"]
        cur.execute("""INSERT INTO contato (nome, relacao, origem, ativo)
                       VALUES (%s,'tecnico','movizap',true) RETURNING id""",
                    (CLIENTE + " Tecnico",))
        tecnico = cur.fetchone()["id"]
        cur.execute("SELECT id FROM canal WHERE instancia = 'atendimento'")
        canal = cur.fetchone()
        if not canal:
            pytest.skip("canal atendimento não cadastrado")
        cur.execute("""INSERT INTO conversa (canal_id, contato_id, telefone_e164,
                                             estado, ultima_atividade_em, criada_em)
                       VALUES (%s,%s,%s,'humano',now(),now()) RETURNING id""",
                    (canal["id"], tecnico, "+5518977778888"))
        conversa = cur.fetchone()["id"]

    yield {"atendente": atendente, "tecnico": tecnico, "conversa": conversa}

    limpar()
    orcamento.definir_proximo_numero(numero_antes)
    assert orcamento.proximo_numero() == numero_antes, (
        "a numeração não voltou ao que era antes do teste")


def _emitir(base, itens=None, ordens=(17015,), recebidos=None):
    def enviar(dados, mime, nome, legenda):
        if recebidos is not None:
            recebidos.append({"bytes": len(dados), "mime": mime, "nome": nome,
                              "legenda": legenda})
        # Sem `midia_id`: o teste não grava mídia nem fala com o WhatsApp.
        return {"ok": True}

    return orcamento.emitir(
        conversa_id=base["conversa"], tecnico_contato_id=base["tecnico"],
        tecnico_nome="Franck Salustiano", ordens=list(ordens),
        itens=itens or ITENS, criado_por=base["atendente"],
        enviar_na_conversa=enviar,
    )


class TestAConta:
    def test_total_bate_com_a_soma_em_centavos(self):
        itens, total = orcamento.calcular(ITENS)
        assert total == sum(i["valor_centavos"] for i in itens)
        assert total == 17770, "1,00 x 77,7 km + 100,00 = 177,70"
        assert orcamento.reais(total) == "177,70"

    def test_deslocamento_por_km_nao_arredonda_errado(self):
        """🔵 Decisão 13 dele: R$ 1,00 x 77,7 km = R$ 77,70."""
        itens, _ = orcamento.calcular([ITENS[0]])
        assert itens[0]["valor_centavos"] == 7770
        assert itens[0]["unidade"] == "km"

    def test_o_valor_da_linha_e_calculado_aqui(self):
        """Conta que chega pronta da tela é conta que alguém pode ter editado."""
        itens, _ = orcamento.calcular([
            {"servico": "X", "preco_unit": "33.33", "quantidade": "3",
             "unidade": "un", "valor_centavos": 1},
        ])
        assert itens[0]["valor_centavos"] == 9999

    def test_centavos_arredonda_meio_pra_cima(self):
        assert orcamento.centavos("0.005") == 1
        assert orcamento.centavos("1.004") == 100

    def test_reais_escreve_como_se_le_em_portugues(self):
        assert orcamento.reais(177_70) == "177,70"
        assert orcamento.reais(123456789) == "1.234.567,89"
        assert orcamento.reais(5) == "0,05"

    @pytest.mark.parametrize("ruim", [
        [{"servico": "  ", "preco_unit": "1", "quantidade": "1"}],
        [{"servico": "X", "preco_unit": "1", "quantidade": "0"}],
        [{"servico": "X", "preco_unit": "1", "quantidade": "-2"}],
        [{"servico": "X", "preco_unit": "1", "quantidade": "1", "unidade": "cx"}],
        [],
    ])
    def test_linha_invalida_e_recusada(self, ruim):
        with pytest.raises(ValueError):
            orcamento.calcular(ruim)


class TestOCatalogo:
    def test_e_a_lista_fechada_que_ele_decidiu(self):
        """🔵 Decisão 12: só deslocamento e pagamento de técnico."""
        nomes = [i["servico"] for i in orcamento.catalogo()]
        assert nomes == ["KM DESLOCAMENTO", "PAGAMENTO DE TECNICO"]

    def test_traz_o_id_do_harmonit_e_a_unidade(self):
        por_nome = {i["servico"]: i for i in orcamento.catalogo()}
        assert por_nome["KM DESLOCAMENTO"]["harmonit_id"] == 6971
        assert por_nome["KM DESLOCAMENTO"]["unidade"] == "km"
        assert por_nome["PAGAMENTO DE TECNICO"]["harmonit_id"] == 653939

    def test_o_catalogo_nao_e_editavel_por_quem_chama(self):
        copia = orcamento.catalogo()
        copia[0]["servico"] = "mexido"
        assert orcamento.catalogo()[0]["servico"] == "KM DESLOCAMENTO"


class TestONumero:
    def test_emitir_gasta_o_numero_e_so_uma_vez(self, base):
        antes = orcamento.proximo_numero()
        emitido = _emitir(base)
        assert emitido["numero"] == antes
        assert orcamento.proximo_numero() == antes + 1

    def test_a_sequencia_nao_pula_nem_repete(self, base):
        antes = orcamento.proximo_numero()
        numeros = [_emitir(base)["numero"] for _ in range(3)]
        assert numeros == [antes, antes + 1, antes + 2]
        assert len(set(numeros)) == 3

    def test_numero_so_se_gasta_com_PDF_pronto(self, base, monkeypatch):
        """🚨 A regra que evita buraco na sequência."""
        antes = orcamento.proximo_numero()

        def falha(**kwargs):
            raise RuntimeError("o PDF não foi")

        monkeypatch.setattr(orcamento, "montar_pdf", falha)
        with pytest.raises(RuntimeError):
            _emitir(base)
        assert orcamento.proximo_numero() == antes, (
            "o número foi gasto sem documento do lado")

    def test_linha_invalida_tambem_nao_gasta_numero(self, base):
        antes = orcamento.proximo_numero()
        with pytest.raises(ValueError):
            _emitir(base, itens=[{"servico": "", "preco_unit": "1",
                                  "quantidade": "1"}])
        assert orcamento.proximo_numero() == antes

    def test_numero_zero_ou_negativo_e_recusado(self):
        with pytest.raises(ValueError):
            orcamento.definir_proximo_numero(0)


class TestOQueFicaGravado:
    def test_o_orcamento_guarda_itens_total_e_tecnico(self, base):
        emitido = _emitir(base)
        guardado = orcamento.por_id(emitido["id"])
        assert guardado["total_centavos"] == 17770
        assert guardado["tecnico_nome"].startswith(CLIENTE)
        assert [i["servico"] for i in guardado["itens"]] == [
            "KM DESLOCAMENTO", "PAGAMENTO DE TECNICO"]
        # A quantidade continua decimal no banco -- 77,7 não vira 78.
        assert Decimal(str(guardado["itens"][0]["quantidade"])) == Decimal("77.7")

    def test_a_conversa_lista_os_proprios_orcamentos(self, base):
        emitido = _emitir(base)
        numeros = [o["numero"] for o in orcamento.da_conversa(base["conversa"])]
        assert emitido["numero"] in numeros

    def test_o_PDF_vai_para_a_conversa_com_nome_de_documento(self, base):
        recebidos = []
        emitido = _emitir(base, recebidos=recebidos)
        assert len(recebidos) == 1
        assert recebidos[0]["mime"] == "application/pdf"
        assert recebidos[0]["nome"] == f"Orcamento_{emitido['numero']}.pdf"
        assert recebidos[0]["bytes"] > 1000
        # A legenda diz o que é, no balão: anexo sem legenda vira "o que é
        # este PDF?" três mensagens depois.
        assert recebidos[0]["legenda"] == f"Orçamento nº {emitido['numero']}"


class TestQuandoOEnvioFALHA:
    """🚨 O defeito que o primeiro uso real dele achou, em 21/10.

    A chamada do envio estava errada (`legenda` é posicional), e o erro
    estourava DEPOIS do commit: o orçamento nº 1 existia, o número já tinha
    sido gasto, e a tela só dizia "erro ao gerar PDF". Quem emite tem de
    receber o documento que existe, e o aviso de que o envio não foi.
    """

    def test_falha_no_envio_nao_derruba_a_emissao(self, base):
        def explode(dados, mime, nome, legenda):
            raise TypeError("responder_com_arquivo() missing 1 required "
                            "positional argument: 'legenda'")

        antes = orcamento.proximo_numero()
        emitido = orcamento.emitir(
            conversa_id=base["conversa"], tecnico_contato_id=base["tecnico"],
            tecnico_nome="Franck", ordens=[17015], itens=ITENS,
            criado_por=base["atendente"], enviar_na_conversa=explode)
        # O documento existe, com número.
        assert emitido["numero"] == antes
        assert orcamento.por_id(emitido["id"]) is not None
        # E o aviso diz o que houve, em vez de sumir.
        assert emitido["enviado"]["ok"] is False
        assert "envio" in emitido["enviado"]["motivo"]

    def test_reenviar_manda_o_MESMO_papel_e_nao_gasta_numero(self, base):
        papeis = []

        def guardar(dados, mime, nome, legenda):
            papeis.append({"nome": nome, "bytes": len(dados)})
            return {"ok": True}

        emitido = _emitir(base, ordens=(17015, 17016))
        antes = orcamento.proximo_numero()
        devolta = orcamento.reenviar(emitido["id"], guardar)
        assert devolta["numero"] == emitido["numero"]
        assert orcamento.proximo_numero() == antes, "reenviar gastou número"
        assert papeis[-1]["nome"] == f"Orcamento_{emitido['numero']}.pdf"

    def test_as_OS_ficam_gravadas_para_o_reenvio_sair_igual(self, base):
        """🚨 Sem isto o reenvio imprimiria "Ordem(ns) de serviço(s): -".

        Documento numerado que muda de conteúdo é pior que documento que não
        sai -- e as OS só existiam no pedido que gerou o PDF.
        """
        emitido = _emitir(base, ordens=(17015, 17016))
        guardado = orcamento.por_id(emitido["id"])
        assert list(guardado["ordens_os"]) == [17015, 17016]

    def test_reenviar_orcamento_que_nao_existe_e_recusado(self):
        with pytest.raises(ValueError):
            orcamento.reenviar(999_999_999, lambda *a: {"ok": True})


class TestOPDF:
    def test_sai_um_pdf_de_verdade(self):
        itens, total = orcamento.calcular(ITENS)
        pdf = orcamento.montar_pdf(numero=1668, tecnico="Franck Salustiano",
                                   ordens=[17015], itens=itens,
                                   total_centavos=total)
        assert pdf[:4] == b"%PDF"
        assert len(pdf) > 1000

    def test_a_quantidade_sai_com_a_unidade_certa(self):
        """⚠️ "77,7 km", e não "77.7 un" -- o conserto da coluna trocada."""
        assert orcamento._quantidade_texto(Decimal("77.7"), "km") == "77,7 km"
        assert orcamento._quantidade_texto(Decimal("1"), "un") == "1 un"
        assert orcamento._quantidade_texto(Decimal("1.50"), "km") == "1,5 km"

    def test_sem_logo_o_documento_sai_do_mesmo_jeito(self, monkeypatch):
        """Orçamento preso por causa de uma imagem seria o pior dos mundos."""
        monkeypatch.setattr(orcamento, "LOGO", Path("/nao/existe/logo.png"))
        itens, total = orcamento.calcular(ITENS)
        pdf = orcamento.montar_pdf(numero=1, tecnico="T", ordens=[1],
                                   itens=itens, total_centavos=total)
        assert pdf[:4] == b"%PDF"

    def test_o_logo_do_painel_esta_onde_o_codigo_espera(self):
        """Se o arquivo mudar de lugar, isto acusa antes do cliente ver."""
        assert orcamento.LOGO.exists(), f"logo não está em {orcamento.LOGO}"
