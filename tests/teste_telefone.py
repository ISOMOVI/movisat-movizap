"""Testes do normalizador de telefone.

Metodologia §6: normalização de telefone é teste do dia 1, porque "é a chave de
tudo e o erro aqui é invisível e caro".

O número da Pastelaria Velasco (+55 18 99811-6168) aparece de propósito: é a
empresa de teste oficial, e o mesmo número tem que ser reconhecido escrito de
todo jeito que a vida escreve.
"""

import pytest

from movizap import telefone
from movizap.telefone import FIXO, INTERNACIONAL, INVALIDO, MOVEL

VELASCO = "+5518998116168"


class TestNonoDigito:
    """🚨 A razão de o módulo existir."""

    def test_com_e_sem_o_nono_digito_sao_a_mesma_pessoa(self):
        com = telefone.normalizar("+55 18 99811-6168")
        sem = telefone.normalizar("+55 18 9811-6168")
        assert com == sem == VELASCO

    def test_a_forma_canonica_sempre_tem_o_nono_digito(self):
        # É isso que permite o índice em `e164` bastar, sem coluna colapsada.
        assert telefone.normalizar("1898116168") == VELASCO
        assert telefone.normalizar("18998116168") == VELASCO

    def test_diz_quando_acrescentou_o_nono_digito(self):
        # Sem essa marca, ninguém sabe que o e164 gravado é um palpite.
        assert telefone.analisar("1898116168").nono_digito_acrescentado is True
        assert telefone.analisar("18998116168").nono_digito_acrescentado is False

    def test_fixo_nunca_ganha_nono_digito(self):
        analise = telefone.analisar("18 3221-4455")
        assert analise.e164 == "+551832214455"
        assert analise.tipo == FIXO
        assert analise.nono_digito_acrescentado is False


class TestSujeiraDeEntrada:
    """A faxina ajuda; o que imuniza é a leitura tolerante."""

    @pytest.mark.parametrize(
        "bruto",
        [
            "+5518998116168",
            "5518998116168",
            "+55 (18) 99811-6168",
            "(18) 99811-6168",
            "18 99811 6168",
            "18.99811.6168",
            "  18 99811 6168  ",
            "0 18 99811 6168",
            "0 18 9811 6168",
            "018998116168",
            "015 18 99811 6168",
            "01518998116168",
        ],
    )
    def test_toda_grafia_chega_no_mesmo_lugar(self, bruto):
        assert telefone.normalizar(bruto) == VELASCO

    def test_jid_do_evolution(self):
        # Chega assim em TODO webhook.
        assert telefone.normalizar("5518998116168@s.whatsapp.net") == VELASCO

    def test_jid_com_sufixo_de_dispositivo(self):
        assert telefone.normalizar("5518998116168:12@s.whatsapp.net") == VELASCO


class TestRecusa:
    """Recusar é melhor que gravar lixo que nunca vai casar com nada."""

    @pytest.mark.parametrize("bruto", [None, "", "   ", "abc", "-", "()"])
    def test_vazio_e_lixo_nao_viram_telefone(self, bruto):
        assert telefone.normalizar(bruto) is None

    def test_ddd_que_nao_existe_e_recusado(self):
        analise = telefone.analisar("20 99811-6168")
        assert analise.e164 is None
        assert "DDD 20" in analise.motivo

    def test_numero_curto_demais(self):
        assert telefone.normalizar("99811") is None

    def test_repetido_nao_passa_por_ser_repetido(self):
        # "99999999999" tem 11 dígitos e DDD 99 existe (PA). Não dá para
        # recusar por formato -- e é justamente por isso que o teste existe:
        # para ninguém "consertar" o módulo achando que deveria recusar.
        assert telefone.normalizar("99999999999") == "+5599999999999"

    def test_o_motivo_da_recusa_e_sempre_dito(self):
        for bruto in [None, "", "abc", "20 99811-6168", "99811"]:
            analise = telefone.analisar(bruto)
            assert analise.e164 is None
            assert analise.motivo, f"recusou {bruto!r} sem dizer por quê"
            assert analise.tipo == INVALIDO


class TestDDD55:
    """🚨 O DDD 55 (Santa Maria/RS) parece o DDI 55. Não pode ser comido."""

    def test_ddd_55_com_nove_digitos(self):
        assert telefone.normalizar("55 99811-6168") == "+5555998116168"

    def test_ddd_55_com_oito_digitos(self):
        assert telefone.normalizar("55 9811-6168") == "+5555998116168"

    def test_ddi_55_mais_ddd_55(self):
        assert telefone.normalizar("+55 55 99811-6168") == "+5555998116168"

    def test_fixo_no_ddd_55(self):
        assert telefone.normalizar("+55 55 3221-4455") == "+555532214455"


class TestInternacional:
    def test_com_mais_e_ddi_estrangeiro(self):
        analise = telefone.analisar("+1 415 555 0132")
        assert analise.tipo == INTERNACIONAL
        assert analise.e164 == "+14155550132"

    def test_sem_o_mais_nao_se_chuta_pais(self):
        # 12 dígitos sem "+" e sem 55: não dá para saber o país. Recusa.
        assert telefone.normalizar("441234567890") is None


class TestDePartes:
    """A forma que o Harmonit devolve: ddi, ddd e phone separados."""

    def test_forma_normal(self):
        assert telefone.de_partes(ddi="55", ddd="18", numero="998116168").e164 == VELASCO

    def test_sem_ddi(self):
        assert telefone.de_partes(ddd="18", numero="998116168").e164 == VELASCO

    def test_com_oito_digitos(self):
        assert telefone.de_partes(ddi="55", ddd="18", numero="98116168").e164 == VELASCO

    def test_ddd_vazio_com_ddd_grudado_no_numero(self):
        # ⚠️ Acontece no Harmonit.
        assert telefone.de_partes(ddi="55", ddd="", numero="18998116168").e164 == VELASCO

    def test_numero_vazio(self):
        analise = telefone.de_partes(ddi="55", ddd="18", numero="")
        assert analise.e164 is None
        assert analise.motivo == "vazio"

    def test_partes_todas_None(self):
        assert telefone.de_partes().e164 is None


class TestVariantes:
    """Para PERGUNTAR para fora, onde não há garantia de grafia."""

    def test_celular_tem_as_duas_grafias(self):
        assert telefone.variantes(VELASCO) == {VELASCO, "+551898116168"}

    def test_a_partir_da_grafia_curta_da_o_mesmo_par(self):
        assert telefone.variantes("+551898116168") == {VELASCO, "+551898116168"}

    def test_fixo_tem_uma_grafia_so(self):
        assert telefone.variantes("+551832214455") == {"+551832214455"}

    def test_invalido_nao_tem_variante(self):
        assert telefone.variantes("abc") == set()


class TestNaoEConstante:
    """🚨 Metodologia §6: a asserção precisa detectar VALOR CONSTANTE.

    `bateria = 0` em 100% das linhas passa batido num teste de nulidade. Um
    normalizador que devolvesse sempre a mesma coisa passaria em quase todo
    teste acima -- menos neste.
    """

    def test_numeros_diferentes_dao_resultados_diferentes(self):
        brutos = [
            "18 99811-6168",
            "18 99811-6169",
            "11 99811-6168",
            "18 3221-4455",
            "+1 415 555 0132",
        ]
        saidas = [telefone.normalizar(b) for b in brutos]
        assert None not in saidas
        assert len(set(saidas)) == len(brutos)

    def test_e_movel_separa_de_verdade(self):
        assert telefone.e_movel(VELASCO) is True
        assert telefone.e_movel("+551832214455") is False
        assert telefone.e_movel(None) is False


class TestContratoDaAnalise:
    def test_analise_valida_e_verdadeira(self):
        assert bool(telefone.analisar(VELASCO)) is True

    def test_analise_invalida_e_falsa(self):
        assert bool(telefone.analisar("abc")) is False

    def test_valido_nao_tem_motivo(self):
        assert telefone.analisar(VELASCO).motivo == ""
