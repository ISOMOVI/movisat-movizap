# -*- coding: utf-8 -*-
"""O ressarcimento virando card de chamado na Operação.

🔵 11/11: *"ressarcimento gera card de chamado com a OBS dos dados do termo"*.
🔵 12/11: *"os dados devem vir da OS"*, *"pode seguir a partir do card-OS,
delay de 2min é suficiente"*.

🚨 AS TRAVAS QUE IMPORTAM AQUI SÃO AS DE NÃO-ACONTECIMENTO. Criar o card é o
caminho feliz e qualquer teste pega; o que derruba em produção é o card que
nasce DUAS vezes, o que RENASCE depois de tratado, e o que nasce cedo demais
com a descrição ainda vazia.
"""
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

pytest.importorskip("psycopg")

from movizap import banco  # noqa: E402

from scripts import card_de_ressarcimento as cr  # noqa: E402

MARCA = "zz_teste_ressarcimento"


@pytest.fixture(scope="module", autouse=True)
def base():
    banco.abrir()
    yield


@pytest.fixture(autouse=True)
def limpar():
    """🚨 A suíte roda contra a base de PRODUÇÃO. Tudo que este arquivo cria
    sai pelo `id`, antes e depois -- a lição de 11/11, quando ler um quadro
    passou a escrever e doze cards vazaram."""
    def _apagar():
        banco.executar(
            "DELETE FROM os_observacao WHERE numero_os BETWEEN 990000 AND 999999")
        banco.executar(
            "DELETE FROM pipeline_card WHERE numero_os BETWEEN 990000 AND 999999")
    _apagar()
    yield
    _apagar()


def _chamados():
    d = cr._aba_e_etapa_dos_chamados()
    assert d is not None, "a Operação tem de ter coluna de chamados"
    return d


class TestATriagem:
    def test_e_o_PROBLEMA_que_diz_se_e_ressarcimento_nao_o_texto(self):
        """📏 Medido em 12/11 nas 19 OS da situação 15746: `problema` 7524 é
        ressarcimento, 11701 é o financeiro comum.

        🚨 O texto NÃO pode ser o critério: texto muda com o tempo e com quem
        digita; id de problema é cadastro. Esta trava fixa a escolha.
        """
        assert cr.PROBLEMA_RESSARCIMENTO == 7524
        assert cr.SITUACAO_FINANCEIRO == 15746

    def test_a_espera_e_a_que_ele_pediu(self):
        """🔵 *"delay de 2min é suficiente"*."""
        assert cr.ESPERA_SEGUNDOS == 120


class TestOCardNaoNasceDUASVEZES:
    def test_card_que_JA_existe_faz_pular(self):
        aba, etapa = _chamados()
        banco.executar(
            """INSERT INTO pipeline_card (aba_id, etapa_id, numero_os)
               VALUES (%s, %s, 990001)""", (aba, etapa))
        assert cr._ja_tem_card(aba, 990001) is True

    def test_card_JA_FINALIZADO_tambem_faz_pular(self):
        """🚨 ESTE É O DEFEITO QUE O SEMEADOR JÁ TEVE: o índice único só vale
        para `desfecho IS NULL`, então um card tratado e fechado renasceria a
        cada rodada -- de dois em dois minutos, para sempre."""
        aba, etapa = _chamados()
        banco.executar(
            """INSERT INTO pipeline_card
                   (aba_id, etapa_id, numero_os, desfecho, desfecho_em)
               VALUES (%s, %s, 990002, 'resolvido', now())""", (aba, etapa))
        assert cr._ja_tem_card(aba, 990002) is True

    def test_sem_card_nenhum_nao_pula(self):
        aba, _ = _chamados()
        assert cr._ja_tem_card(aba, 990003) is False


class TestOCardNasceDoCardOS:
    def test_sem_card_no_FINANCEIRO_nao_ha_de_onde_seguir(self):
        """🔵 *"pode seguir a partir do card-OS"*. Sem ele, a rotina espera a
        próxima rodada em vez de inventar um começo."""
        assert cr._card_do_financeiro(990004) is None

    def test_o_card_do_financeiro_e_achado_e_tem_IDADE(self):
        aba = banco.um(
            "SELECT id FROM painel_aba WHERE codigo_tela = 'PNL_1.4'")["id"]
        etapa = banco.um(
            "SELECT id FROM pipeline_etapa WHERE aba_id = %s ORDER BY ordem "
            "LIMIT 1", (aba,))["id"]
        banco.executar(
            """INSERT INTO pipeline_card (aba_id, etapa_id, numero_os)
               VALUES (%s, %s, 990005)""", (aba, etapa))
        achado = cr._card_do_financeiro(990005)
        assert achado is not None
        # recém-criado: a idade tem de ser menor que a espera, e é isso que
        # segura o card novo demais.
        assert float(achado["idade"]) < cr.ESPERA_SEGUNDOS

    def test_card_RECEM_criado_nao_passa_da_espera(self):
        """⚠️ A trava do atraso, medida e não suposta: card de agora tem idade
        menor que 120 s, então a rodada o deixa para depois."""
        aba = banco.um(
            "SELECT id FROM painel_aba WHERE codigo_tela = 'PNL_1.4'")["id"]
        etapa = banco.um(
            "SELECT id FROM pipeline_etapa WHERE aba_id = %s ORDER BY ordem "
            "LIMIT 1", (aba,))["id"]
        banco.executar(
            """INSERT INTO pipeline_card (aba_id, etapa_id, numero_os)
               VALUES (%s, %s, 990006)""", (aba, etapa))
        idade = float(cr._card_do_financeiro(990006)["idade"])
        assert idade < cr.ESPERA_SEGUNDOS, (
            "card de agora passando na espera: o atraso de 2 min nao existe")


class TestAObservacaoDeOrigem:
    def test_leva_o_numero_da_OS_e_a_descricao_inteira(self):
        desc = "RESSARCIMENTO: placas: RVF 5G49 | 007933929 | O.S: 17120"
        texto = cr._texto_da_origem(17120, desc)
        assert "17120" in texto
        assert desc in texto
        assert "ressarcimento" in texto.lower()

    def test_diz_que_veio_do_FINANCEIRO(self):
        """⚠️ Quem abrir o card daqui a seis meses precisa saber de onde ele
        veio sem perguntar a ninguém."""
        texto = cr._texto_da_origem(1, "qualquer")
        assert "Financeiro" in texto


class TestOQueElaNAOFaz:
    def test_o_ENSAIO_nao_escreve_nada(self):
        """🚨 Sem `--aplicar`, nem card nem observação. É o que permite rodar
        contra produção para ver o que ela faria."""
        antes_card = banco.um(
            "SELECT count(*) AS n FROM pipeline_card")["n"]
        antes_obs = banco.um(
            "SELECT count(*) AS n FROM os_observacao")["n"]
        cr.rodar(aplicar=False, desde_dias=60)
        assert banco.um("SELECT count(*) AS n FROM pipeline_card")["n"] == antes_card
        assert banco.um("SELECT count(*) AS n FROM os_observacao")["n"] == antes_obs

    def test_nao_existe_envio_de_mensagem_no_modulo(self):
        """🚨 Ela cria card e escreve observação. Quem fala com cliente é
        gente. Se um dia alguém acrescentar um envio aqui, esta trava cai."""
        fonte = Path(cr.__file__).read_text(encoding="utf-8")
        for proibido in ("enviar_texto", "evolution", "wa.me",
                         "enviar_mensagem", "disparo"):
            assert proibido not in fonte.lower(), proibido
