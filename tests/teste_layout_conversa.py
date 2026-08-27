"""A cadeia de altura da Caixa de entrada — 27/08.

🚨 ESCRITO PORQUE EU DEI POR CONCLUÍDO SEM AUDITAR. Rodei suíte e build, e
**nenhum dos dois vê layout**: a suíte não abre tela e o build só reclama de
sintaxe. Ele viu antes de mim — *"visualmente já vejo erros de scroll,
alinhamento e etc"* — e estava certo.

O defeito era de CADEIA, não de valor solto:

  1. `.painel` pedia `height: 100%` e o pai não tinha altura. Em CSS,
     `height: 100%` sobre pai `auto` resolve para `auto`, **em silêncio**: a
     tela voltava a crescer com o conteúdo e a rolagem ia para a página em vez
     de ir para o fio;
  2. a coluna da conversa tem **nove filhos diretos** num flex-column. Sem
     regra, vários crescem juntos e ninguém rola no lugar certo;
  3. a gaveta da ficha não tinha teto e empurrava fio e compositor para fora.

⚠️ ESTA TRAVA LÊ O CSS, e aqui isso é o certo: o defeito É a regra que falta.
Layout de verdade só um navegador mede, e a conferência final continua sendo
alguém abrir a tela — está dito no relatório, não escondido aqui.
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")

TELA = Path("/home/claude/movizap_painel/frontend/src/telas/CaixaDeEntrada.vue")
APP = Path("/home/claude/movizap_painel/frontend/src/App.vue")
ROUTER = Path("/home/claude/movizap_painel/frontend/src/router/index.js")

pytestmark = pytest.mark.skipif(
    not TELA.exists(), reason="frontend não está neste checkout")


def _estilo(arquivo: Path) -> str:
    fonte = arquivo.read_text(encoding="utf-8")
    bloco = re.search(r"<style[^>]*>(.*)</style>", fonte, re.S)
    assert bloco, f"{arquivo.name} perdeu o bloco <style>"
    return re.sub(r"/\*.*?\*/", "", bloco.group(1), flags=re.S)


def _regra(estilo: str, seletor: str) -> str:
    """O corpo da regra do seletor EXATO.

    ⚠️ ANCORADO NO COMEÇO DA LINHA, e isso não é detalhe: sem a âncora,
    procurar `.conversas` casava com `.coluna > .conversas`, que vem antes no
    arquivo -- e o teste afirmava sobre a regra errada. A trava pegou isso na
    primeira rodada, no meu próprio teste.
    """
    m = re.search(r"^\s*" + re.escape(seletor) + r"\s*(?:,[^{]*)?\{([^}]*)\}",
                  estilo, re.M)
    assert m, f"não achei a regra `{seletor}`"
    return m.group(1)


class TestAAlturaChegaAteOFio:
    """🚨 A cadeia inteira precisa de altura. Um elo em `auto` no meio derruba
    todos os de baixo, sem erro nenhum."""

    def test_a_tela_da_conversa_tem_altura(self):
        regra = _regra(_estilo(TELA), ".tela--conversa")
        assert "height: 100%" in regra, (
            "sem altura aqui, o `.painel` abaixo pede 100% de um pai `auto` e "
            "recebe `auto` -- a tela volta a crescer com o conteúdo")
        assert "min-height: 0" in regra, (
            "sem isto, o filho de flex não encolhe e a rolagem escapa para a página")

    def test_a_tela_da_conversa_ocupa_a_largura(self):
        """O desenho escolhido ocupa a tela toda; `max-width` deixava faixa
        vazia em monitor largo."""
        assert "max-width: none" in _regra(_estilo(TELA), ".tela--conversa")

    def test_o_painel_nao_briga_com_o_flex_do_pai(self):
        """⚠️ `height: 100%` num filho de flex-column briga com a distribuição
        do pai. Quem manda é `flex` + `min-height: 0`."""
        regra = _regra(_estilo(TELA), ".painel")
        assert "min-height: 0" in regra
        assert "height: 100%" not in regra

    def test_a_rota_pede_a_tela_cheia(self):
        """O respiro da página vem do App; sem esta marca, a tela nunca
        alcança a altura toda."""
        rotas = ROUTER.read_text(encoding="utf-8")
        for codigo in ("ATD_1.1", "ATD_1.2"):
            trecho = re.search(r"codigo: '" + codigo + r"'[^}]*\}", rotas)
            assert trecho and "cheio: true" in trecho.group(0), \
                f"{codigo} não está marcada como tela cheia"

    def test_o_app_sabe_tirar_o_respiro(self):
        estilo = _estilo(APP)
        regra = _regra(estilo, ".painel__conteudo--cheio")
        assert "padding: 0" in regra
        assert "overflow: hidden" in regra, (
            "sem isto sobram DUAS rolagens: a da página e a do fio")


class TestSoOFioCresce:
    """🚨 Nove filhos diretos num flex-column. Sem regra, vários crescem
    juntos e a rolagem vai parar no lugar errado."""

    def test_ninguem_cresce_por_padrao_na_conversa(self):
        assert "flex: none" in _regra(_estilo(TELA), ".coluna--larga > *")

    def test_o_fio_e_a_excecao_e_pode_encolher(self):
        regra = _regra(_estilo(TELA), ".coluna--larga > .baloes")
        assert "flex: 1 1 auto" in regra
        assert "min-height: 0" in regra, (
            "sem `min-height: 0` o fio não encolhe e empurra o compositor "
            "para fora da tela em conversa longa")

    def test_o_fio_rola_por_dentro(self):
        assert "overflow-y: auto" in _regra(_estilo(TELA), ".baloes")

    def test_ninguem_cresce_por_padrao_na_lista(self):
        assert "flex: none" in _regra(_estilo(TELA), ".coluna > *")

    def test_a_lista_rola_inteira_e_nao_para_num_vh(self):
        """⚠️ O `max-height: 60vh` saiu: altura em `vh` é chute sobre o
        monitor de quem usa, e sobrava metade da coluna vazia."""
        regra = _regra(_estilo(TELA), ".conversas")
        assert "overflow-y: auto" in regra
        assert "vh" not in regra

    def test_a_gaveta_da_ficha_tem_teto_proprio(self):
        """A ficha do cliente pode ser mais alta que a tela; sem teto, ela
        empurrava fio e compositor para fora."""
        regra = _regra(_estilo(TELA), ".coluna--larga > .gaveta")
        assert "max-height" in regra and "overflow-y: auto" in regra


class TestOAcabamentoDasColunas:
    def test_as_colunas_perdem_a_casca_de_cartao(self):
        regra = _regra(_estilo(TELA), ".painel > .cartao")
        for valor in ("border-radius: 0", "border: 0", "box-shadow: none", "padding: 0"):
            assert valor in regra, f"faltou `{valor}`: a coluna volta a flutuar"

    def test_a_barra_do_topo_nao_guarda_o_raio_do_cartao(self):
        """⚠️ `.cartao__cabecalho` é global e traz `border-radius` nos cantos de
        cima. Com o cartão sem raio, sobravam 12px de curva contra borda reta."""
        assert "border-radius: 0" in _regra(
            _estilo(TELA), ".tela--conversa .cartao__cabecalho")

    def test_os_avisos_nao_colam_na_borda(self):
        """Eles ficam acima das colunas, e a página não tem mais padding."""
        assert "margin" in _regra(_estilo(TELA), ".tela--conversa > .aviso")
