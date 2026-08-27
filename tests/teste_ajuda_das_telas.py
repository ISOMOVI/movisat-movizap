"""O texto explicativo virou ícone, e não pode ter sumido — 27/08.

Pedido dele: *"as abas tem textos explicativos do que as telas são, o que fazem
e o que falta... transforme em balões ícones apenas, se passar mouse aparece os
textos; documentar ícone no registro de telas"*.

🚨 O RISCO DESTA MUDANÇA É ESCONDER E PERDER. Trocar 13 parágrafos por um ícone
num script é o tipo de edição em que o texto some sem ninguém notar -- o build
passa, a tela abre, e a explicação simplesmente não está mais lá. Estas travas
medem o oposto: que **cada tela que tinha texto continua tendo**, dentro do
componente.

⚠️ MEDE A LIGAÇÃO, NÃO A PALAVRA: procura o componente sendo USADO (a tag) e o
import que o resolve. Um `grep` por "AjudaDaTela" casaria com um comentário.
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")

RAIZ = Path("/home/claude/movizap_painel/frontend/src")
TELAS = RAIZ / "telas"
COMPONENTE = RAIZ / "componentes/AjudaDaTela.vue"

pytestmark = pytest.mark.skipif(
    not COMPONENTE.exists(), reason="frontend não está neste checkout")

# As telas que TÊM cabeçalho com explicação. As de fora estão listadas de
# propósito: Caixa de entrada, Chat interno, E-mail, Configurações, Início e as
# auxiliares não têm o parágrafo que este ícone substitui.
COM_AJUDA = [
    "Atendentes.vue", "Automacao.vue", "Canais.vue", "Classificacoes.vue",
    "Clientes.vue", "Contatos.vue", "Fila.vue", "Historico.vue",
    "IaPrompt.vue", "Informativos.vue", "RegistroDeTelas.vue",
    "Sincronizacao.vue", "Times.vue",
]


def _sem_comentario(fonte: str) -> str:
    fonte = re.sub(r"<!--.*?-->", "", fonte, flags=re.S)
    return re.sub(r"/\*.*?\*/", "", fonte, flags=re.S)


class TestOTextoContinuaLa:
    @pytest.mark.parametrize("nome", COM_AJUDA)
    def test_a_tela_usa_o_componente(self, nome):
        fonte = _sem_comentario((TELAS / nome).read_text(encoding="utf-8"))
        assert "<AjudaDaTela>" in fonte, f"{nome} perdeu o ícone de ajuda"
        assert "componentes/AjudaDaTela.vue" in fonte, \
            f"{nome} usa a tag sem importar o componente -- a tela quebra ao abrir"

    @pytest.mark.parametrize("nome", COM_AJUDA)
    def test_o_texto_nao_ficou_vazio(self, nome):
        """🚨 O DEFEITO QUE ISTO IMPEDE: o ícone existir e não devolver nada.
        Esconder informação atrás de um símbolo mudo é pior que o parágrafo."""
        fonte = (TELAS / nome).read_text(encoding="utf-8")
        m = re.search(r"<AjudaDaTela>(.*?)</AjudaDaTela>", fonte, re.S)
        assert m, f"{nome}: não achei o conteúdo da ajuda"
        texto = " ".join(m.group(1).split())
        assert len(texto) >= 25, (
            f"{nome}: a ajuda tem só {len(texto)} caracteres -- o texto se "
            f"perdeu na troca")

    @pytest.mark.parametrize("nome", COM_AJUDA)
    def test_o_paragrafo_antigo_nao_ficou_duplicado(self, nome):
        """Se a troca falhasse pela metade, a tela mostraria o texto DUAS
        vezes: no parágrafo e no balão."""
        fonte = _sem_comentario((TELAS / nome).read_text(encoding="utf-8"))
        cabecalho = re.search(r"<h1>.*?</h1>\s*(.{0,120})", fonte, re.S)
        assert cabecalho
        assert 'class="fraco pequeno"' not in cabecalho.group(1), \
            f"{nome}: sobrou o parágrafo antigo ao lado do ícone"


class TestOComponenteEAcessivel:
    """⚠️ É a lição das ações do balão, que ficaram inalcançáveis por teclado
    até 27/08. Um balão que só abre no hover repete o mesmo erro."""

    def _estilo(self) -> str:
        fonte = COMPONENTE.read_text(encoding="utf-8")
        bloco = re.search(r"<style[^>]*>(.*)</style>", fonte, re.S)
        assert bloco
        return re.sub(r"/\*.*?\*/", "", bloco.group(1), flags=re.S)

    def test_abre_no_foco_e_nao_so_no_hover(self):
        assert ":focus-within .ajuda__balao" in self._estilo(), (
            "sem isto, quem usa teclado nunca lê o texto que o ícone escondeu")

    def test_nao_usa_display_none(self):
        """`display:none` tira o conteúdo da árvore, e alguns leitores de tela
        deixam de anunciá-lo -- exatamente o que escondeu as ações do balão."""
        m = re.search(r"\.ajuda__balao\s*\{([^}]*)\}", self._estilo())
        assert m and "display: none" not in m.group(1)

    def test_o_gatilho_tem_nome_para_quem_nao_ve_o_icone(self):
        fonte = COMPONENTE.read_text(encoding="utf-8")
        assert "aria-label" in fonte, "um `?` sozinho não diz nada a um leitor de tela"


class TestODocConheceOIcone:
    def test_o_registro_documenta_o_icone_da_ajuda(self):
        """Pedido dele no mesmo dia: *"documentar ícone no registro de telas"*."""
        doc = Path("/home/claude/movizap_painel/docs/03_Registro_Telas.md")
        texto = doc.read_text(encoding="utf-8")
        assert "bi-question-circle" in texto
        assert "AjudaDaTela" in texto

    def test_o_doc_lista_o_icone_de_cada_tela_ativa(self):
        """O `icone` do registro é a fonte única do que o menu desenha; o doc
        tem de conhecer todos."""
        from movizap import telas
        doc = Path("/home/claude/movizap_painel/docs/03_Registro_Telas.md") \
            .read_text(encoding="utf-8")
        faltando = [t["icone"] for t in telas.ativas() if t["icone"] not in doc]
        assert not faltando, f"ícones que o docs/03 não menciona: {sorted(set(faltando))}"
