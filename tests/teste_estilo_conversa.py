"""O desenho da conversa não pode escapar do sistema — 27/08.

🚨 ESCRITO PORQUE JÁ TINHA ESCAPADO, e na peça mais vista do painel. Até hoje o
balão usava:

  - `border-radius: var(--raio, 12px)` — e **`--raio` NUNCA EXISTIU**. O CSS
    não reclama de token inexistente: ele cai no valor de emergência, em
    silêncio, e ninguém descobre. O balão era o único lugar do projeto com um
    raio que o `tokens.css` não conhecia;
  - três `rgba()` escritos à mão para as cores dos três tipos de balão, fora da
    paleta.

A regra do `tokens.css` está escrita lá desde a primeira tela: *"nenhuma tela
escreve cor, tamanho de fonte, raio ou espaçamento na mão. Se um valor não
existe aqui, ou ele vira token, ou não entra."* Este teste é o que faz a regra
valer para a conversa.

⚠️ MEDE O FONTE DA TELA, e aqui isso é o certo: o defeito É textual (um token
que não existe, uma cor crua). Comentário é retirado antes de varrer — trava
que mede palavra já reprovou código correto oito vezes neste projeto.
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")

RAIZ = Path("/home/claude/movizap_painel/frontend/src")
TELA = RAIZ / "telas/CaixaDeEntrada.vue"
TOKENS = RAIZ / "estilo/tokens.css"

pytestmark = pytest.mark.skipif(
    not TELA.exists(), reason="frontend não está neste checkout")


def _estilo_sem_comentario() -> str:
    """Só o `<style>` da tela, com os comentários fora."""
    fonte = TELA.read_text(encoding="utf-8")
    bloco = re.search(r"<style[^>]*>(.*)</style>", fonte, re.S)
    assert bloco, "a tela perdeu o bloco <style>"
    return re.sub(r"/\*.*?\*/", "", bloco.group(1), flags=re.S)


def _tokens_declarados() -> set[str]:
    return set(re.findall(r"^\s*(--[a-z0-9-]+)\s*:", TOKENS.read_text(encoding="utf-8"),
                          re.M))


class TestTodoTokenUsadoExiste:
    def test_nenhum_var_aponta_para_token_inexistente(self):
        """🚨 O DEFEITO DE ORIGEM. `var(--raio, 12px)` funcionava — e era um
        token fantasma com valor de emergência."""
        declarados = _tokens_declarados()
        usados = set(re.findall(r"var\(\s*(--[a-z0-9-]+)", _estilo_sem_comentario()))
        fantasmas = sorted(usados - declarados)
        assert not fantasmas, (
            f"a tela usa token que o tokens.css não declara: {fantasmas}. "
            f"O CSS não reclama — cai no valor de emergência, em silêncio.")

    def test_os_tokens_da_conversa_existem(self):
        """A escolha dele em 27/08 (opção 'Familiar') virou token, não valor
        solto na tela."""
        declarados = _tokens_declarados()
        for token in ("--conversa-fundo", "--conversa-balao", "--conversa-saida",
                      "--conversa-nota", "--conversa-raio", "--conversa-bico",
                      "--conversa-lida"):
            assert token in declarados, f"{token} não está no tokens.css"


class TestOBalaoNaoTemCorCrua:
    """⚠️ Varre só as regras do balão: o resto da tela tem `rgba()` legítimo
    (sombra, sobreposição), e reprovar tudo faria a trava virar ruído."""

    def _regras_do_balao(self) -> str:
        estilo = _estilo_sem_comentario()
        pedacos = []
        for m in re.finditer(r"(\.balao[^{]*)\{([^}]*)\}", estilo):
            pedacos.append(m.group(2))
        assert pedacos, "não achei as regras do balão"
        return "\n".join(pedacos)

    def test_sem_hexadecimal_solto(self):
        cruas = re.findall(r"#[0-9a-fA-F]{3,8}\b", self._regras_do_balao())
        assert not cruas, (
            f"cor escrita à mão nas regras do balão: {cruas}. "
            f"Vira token no tokens.css, ou não entra.")

    def test_sem_rgb_solto(self):
        cruas = re.findall(r"\brgba?\([^)]*\)", self._regras_do_balao())
        assert not cruas, (
            f"cor escrita à mão nas regras do balão: {cruas}. "
            f"Era exatamente assim que as três cores dos balões viviam.")


class TestAsAcoesDoBalaoSaoAlcancaveis:
    """🚨 MEDIDO EM 27/08: as ações usavam `display: none` + `:hover`, e o
    `.balao__acoes:focus-within` que existia no CSS **nunca disparava** —
    `display:none` tira o elemento do tab order, então nada lá dentro pode
    receber foco. Reagir, citar e encaminhar eram inalcançáveis por teclado, e
    num tablet não há hover nenhum."""

    def _regra(self, seletor: str) -> str:
        estilo = _estilo_sem_comentario()
        m = re.search(re.escape(seletor) + r"\s*\{([^}]*)\}", estilo)
        assert m, f"não achei a regra `{seletor}`"
        return m.group(1)

    def test_as_acoes_nao_usam_display_none(self):
        regra = self._regra(".balao__acoes")
        assert "display: none" not in regra.replace("  ", " "), (
            "voltou o `display: none`: com ele o `:focus-within` é código morto "
            "e as três ações somem do alcance do teclado")

    def test_o_foco_dentro_do_balao_revela_as_acoes(self):
        estilo = _estilo_sem_comentario()
        assert ".balao:focus-within .balao__acoes" in estilo, (
            "sem esta regra, quem chega pelo teclado foca um botão invisível")

    def test_invisivel_nao_continua_clicavel(self):
        """⚠️ `opacity: 0` sozinho deixaria um alvo fantasma cobrindo o balão."""
        assert "pointer-events: none" in self._regra(".balao__acoes")
