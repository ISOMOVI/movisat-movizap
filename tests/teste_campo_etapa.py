"""O CAMPO DE TEXTO DA ETAPA — Rastreamento e Devolução (11/11).

🚨 ESCREVE EM TABELAS DE PRODUÇÃO (`os_campo_da_etapa`, `os_observacao`,
`atendente`) e apaga tudo no fim. Marcas deste teste: OS na faixa **99.903.x**
e login `zz_teste_campo_`.

O que estes testes guardam:
  · a etapa decide qual campo aparece, e etapa sem campo não desenha nada;
  · gravar **nunca dá UPDATE**: cada escrita é linha nova e o anterior fica;
  · gravar gera **observação do sistema** com o código e o autor;
  · chave inventada é recusada — **pelo código E pelo banco**;
  · o rastreio **vai ao cliente** e a devolução **não**, e isso é dado, não
    comentário;
  · nada aqui fala com o Harmonit.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")
pytest.importorskip("psycopg")

from movizap import banco, campo_etapa, operacao  # noqa: E402
from movizap.operacao import DadoInvalido  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
pytestmark = pytest.mark.skipif(
    not ENV.exists() or "MOVIZAP_DB_SENHA" not in ENV.read_text(encoding="utf-8"),
    reason="banco nao configurado no .env")

LOGIN = "zz_teste_campo_"
OS1, OS2 = 99_903_101, 99_903_102
CORREIO = 677    # Enviar por correio/transportadora
DEVOLUCAO = 15696  # Aguardando devolução de equipamento


def limpar():
    banco.executar("DELETE FROM os_campo_da_etapa WHERE numero_os = ANY(%s)",
                   ([OS1, OS2],))
    banco.executar("DELETE FROM os_observacao WHERE numero_os = ANY(%s)",
                   ([OS1, OS2],))
    banco.executar("DELETE FROM atendente WHERE login LIKE %s", (LOGIN + "%",))


@pytest.fixture(scope="module", autouse=True)
def base():
    banco.abrir()
    limpar()
    yield
    banco.abrir()
    limpar()


@pytest.fixture
def pessoa():
    limpar()
    return operacao.criar_atendente("Zz Teste Campo", LOGIN + "1",
                                    LOGIN + "1@teste.invalid")


class TestQualCampoAEtapaPede:
    def test_a_677_pede_rastreamento_e_ele_vai_ao_cliente(self):
        c = campo_etapa.da_situacao(CORREIO)
        assert c["chave"] == "rastreio"
        assert c["rotulo"] == "Rastreamento"
        assert c["ao_cliente"] is True

    def test_a_15696_pede_devolucao_e_ela_NAO_vai_ao_cliente(self):
        """🚨 *"Apenas para consulta interna da operadora"* -- decisão dele, e
        é dado, não comentário: é o que impede a primeira automação de disparo
        mandar o código de devolução para o cliente."""
        c = campo_etapa.da_situacao(DEVOLUCAO)
        assert c["chave"] == "devolucao"
        assert c["rotulo"] == "Devolução"
        assert c["ao_cliente"] is False

    def test_etapa_sem_campo_devolve_nada(self):
        """E é isto que faz a tela não desenhar caixa onde ninguém pediu."""
        for etapa in (38, 251, 16488, 890, 1316, 15694):
            assert campo_etapa.da_situacao(etapa) is None, etapa
        assert campo_etapa.da_situacao(None) is None

    def test_as_chaves_do_codigo_sao_as_do_CHECK_do_banco(self):
        """⚠️ Chave nova sem migração é recusada pelo banco, de propósito --
        esta trava é o que faz alguém lembrar de mexer nos dois lugares."""
        d = banco.um(
            """SELECT pg_get_constraintdef(oid) AS def FROM pg_constraint
                WHERE conname = 'os_campo_chave_check'""")
        for chave in campo_etapa.CAMPOS:
            assert chave in d["def"], chave


class TestGravar:
    def test_grava_com_autor_e_hora_e_le_de_volta(self, pessoa):
        campo_etapa.gravar(OS1, "rastreio", "AA123456789BR", pessoa["id"])
        atual = campo_etapa.atuais(OS1)["rastreio"]
        assert atual["valor"] == "AA123456789BR"
        assert atual["quem"] == "Zz Teste Campo"
        assert atual["em"] is not None

    def test_gravar_de_novo_NAO_apaga_o_anterior(self, pessoa):
        """🚨 O código trocado pode JÁ TER IDO para o cliente. O valor de agora
        é o mais recente; o anterior fica como histórico."""
        campo_etapa.gravar(OS1, "rastreio", "PRIMEIRO1BR", pessoa["id"])
        campo_etapa.gravar(OS1, "rastreio", "SEGUNDO22BR", pessoa["id"])
        assert campo_etapa.atuais(OS1)["rastreio"]["valor"] == "SEGUNDO22BR"
        h = campo_etapa.historico(OS1, "rastreio")
        assert [x["valor"] for x in h] == ["SEGUNDO22BR", "PRIMEIRO1BR"]

    def test_as_duas_chaves_convivem_na_mesma_OS(self, pessoa):
        campo_etapa.gravar(OS1, "rastreio", "IDA1234567BR", pessoa["id"])
        campo_etapa.gravar(OS1, "devolucao", "VOLTA98765BR", pessoa["id"])
        atuais = campo_etapa.atuais(OS1)
        assert atuais["rastreio"]["valor"] == "IDA1234567BR"
        assert atuais["devolucao"]["valor"] == "VOLTA98765BR"

    def test_OS_sem_nada_devolve_dicionario_vazio(self):
        assert campo_etapa.atuais(OS2) == {}

    def test_chave_inventada_recusa_com_frase(self, pessoa):
        with pytest.raises(DadoInvalido) as e:
            campo_etapa.gravar(OS1, "cor_favorita", "azul", pessoa["id"])
        assert "não existe nesta etapa" in str(e.value)

    def test_vazio_recusa_dizendo_o_que_escrever(self, pessoa):
        with pytest.raises(DadoInvalido) as e:
            campo_etapa.gravar(OS1, "rastreio", "   ", pessoa["id"])
        assert "rastreamento" in str(e.value).lower()

    def test_passa_do_teto_recusa(self, pessoa):
        with pytest.raises(DadoInvalido) as e:
            campo_etapa.gravar(OS1, "rastreio", "X" * (campo_etapa.TETO + 1),
                               pessoa["id"])
        assert str(campo_etapa.TETO) in str(e.value)

    def test_o_valor_e_guardado_SEM_espaco_nas_bordas(self, pessoa):
        campo_etapa.gravar(OS1, "rastreio",
                           "  BB999999999BR " + chr(10),
                           pessoa["id"])
        assert campo_etapa.atuais(OS1)["rastreio"]["valor"] == "BB999999999BR"


class TestAObservacaoDoSistema:
    """🔵 *"O mesmo para os dados de 'Rastreamento' (...) o mesmo para o campo
    de 'Devolução'"* -- gerar OBS."""

    def test_gravar_gera_observacao_com_o_codigo(self, pessoa):
        campo_etapa.gravar(OS1, "rastreio", "CC111111111BR", pessoa["id"])
        obs = banco.varios(
            "SELECT texto FROM os_observacao WHERE numero_os = %s", (OS1,))
        textos = [o["texto"] for o in obs]
        assert "[sistema] Rastreamento: CC111111111BR" in textos

    def test_a_OBS_usa_o_rotulo_de_CADA_campo(self, pessoa):
        campo_etapa.gravar(OS1, "devolucao", "DD222222222BR", pessoa["id"])
        obs = banco.varios(
            "SELECT texto FROM os_observacao WHERE numero_os = %s", (OS1,))
        assert any("[sistema] Devolução: DD222222222BR" in o["texto"]
                   for o in obs)

    def test_cada_gravacao_gera_a_SUA_observacao(self, pessoa):
        """Trocar o código duas vezes deixa as duas trocas na linha do tempo --
        é o que permite dizer depois "mandei o errado"."""
        campo_etapa.gravar(OS1, "rastreio", "EE111111111BR", pessoa["id"])
        campo_etapa.gravar(OS1, "rastreio", "EE222222222BR", pessoa["id"])
        n = banco.um(
            """SELECT count(*) n FROM os_observacao
                WHERE numero_os = %s AND texto LIKE '[sistema] Rastreamento:%%'""",
            (OS1,))
        assert n["n"] == 2

    def test_a_OBS_falhar_NAO_desfaz_a_gravacao(self, pessoa, monkeypatch):
        """⚠️ O código é o dado; a OBS é o rastro. Perder o rastro é ruim;
        perder o código que o cliente vai receber é pior."""
        from movizap import passagem

        def estoura(*a, **k):
            raise RuntimeError("banco de observacao fora do ar")

        monkeypatch.setattr(passagem, "observar", estoura)
        campo_etapa.gravar(OS1, "rastreio", "FF333333333BR", pessoa["id"])
        assert campo_etapa.atuais(OS1)["rastreio"]["valor"] == "FF333333333BR"


class TestNaoFalaComOErp:
    def test_o_modulo_nao_importa_a_ponte(self):
        """🚨 Escrever o código na OS exigiria `SalvarOrdemServico` -- a OS
        INTEIRA --, que é a armadilha do endereço e da situação. A trava é
        estrutural para que ninguém a caia sem perceber."""
        import inspect
        fonte = inspect.getsource(campo_etapa)
        # 🚨 SÓ AS LINHAS DE IMPORT. Ler o arquivo inteiro reprovava por causa
        # do próprio comentário que explica a regra -- é o erro de 05/11
        # (varredura de texto em arquivo inteiro acha o texto certo no lugar
        # errado), e eu o repeti aqui.
        imports = [linha for linha in fonte.splitlines()
                   if linha.startswith(("import ", "from "))]
        assert imports, "nao achei linha de import nenhuma"
        for linha in imports:
            assert "fpsl_ponte" not in linha, linha
            assert "harmonit" not in linha.lower(), linha
        # E a prova de comportamento, não só de forma: o módulo não tem o
        # atributo, então não há como chamar a ponte nem por acidente.
        assert not hasattr(campo_etapa, "fpsl_ponte")
