"""Os ajustes que ele pediu em 27/08 — D4 a D7.

Cada um nasceu de uma frase dele, e a frase está no teste. Nenhum é meu.
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")

RAIZ = Path("/home/claude/movizap_painel/frontend/src")
EMAIL = RAIZ / "telas/Email.vue"
CAIXA = RAIZ / "telas/CaixaDeEntrada.vue"

pytestmark = pytest.mark.skipif(
    not EMAIL.exists(), reason="frontend não está neste checkout")


def _sem_comentario(arquivo: Path) -> str:
    fonte = arquivo.read_text(encoding="utf-8")
    fonte = re.sub(r"<!--.*?-->", "", fonte, flags=re.S)
    return re.sub(r"/\*.*?\*/", "", fonte, flags=re.S)


class TestD4EstrelaColorida:
    """*"e-mail o tip 'YELLOS_STAR' ajustar para 'Com estrela' como no gmail"*.

    🚨 A saída não foi traduzir: o Gmail tem 12 marcadores de estrela e todos
    apontam para a MESMA lista que o `STARRED` já mostra como "Com estrela".
    Dois itens com o mesmo nome seriam pior que um id feio.
    """

    def test_as_estrelas_coloridas_nao_aparecem(self):
        fonte = _sem_comentario(EMAIL)
        m = re.search(r"const ESTRELAS_DO_GMAIL = \[(.*?)\]", fonte, re.S)
        assert m, "a lista das estrelas do Gmail sumiu"
        for cor in ("YELLOW_STAR", "RED_STAR", "BLUE_STAR", "GREEN_CHECK"):
            assert cor in m.group(1), f"{cor} voltaria a aparecer cru na tela"

    def test_a_lista_de_escondidos_inclui_as_estrelas(self):
        fonte = _sem_comentario(EMAIL)
        assert "...ESTRELAS_DO_GMAIL" in fonte, (
            "as estrelas coloridas precisam entrar em ESCONDIDOS -- senão a "
            "lista volta a mostrar `YELLOW_STAR`")

    def test_o_STARRED_continua_com_nome_legivel(self):
        """⚠️ A outra metade: esconder as coloridas não pode esconder a lista
        de verdade."""
        fonte = _sem_comentario(EMAIL)
        assert re.search(r"STARRED:\s*'Com estrela'", fonte)
        m = re.search(r"const ESTRELAS_DO_GMAIL = \[(.*?)\]", fonte, re.S)
        assert "'STARRED'" not in m.group(1)


class TestD5TirarEstrelaSaiDaLista:
    """*"tirar estrela não removeu ele da lista"*."""

    def test_dentro_de_com_estrela_a_mensagem_sai(self):
        fonte = _sem_comentario(EMAIL)
        assert "marcadorAtual.value === 'STARRED'" in fonte, (
            "sem esta condição, tirar a estrela deixa a mensagem numa lista "
            "chamada 'Com estrela' -- a tela contradizendo o próprio título")

    def test_so_nessa_lista_e_nao_em_toda_parte(self):
        """⚠️ Na caixa de entrada, tirar a estrela não muda nada sobre estar
        na caixa: remover ali faria a mensagem sumir por um motivo que não tem
        a ver com o lugar onde ela está."""
        fonte = _sem_comentario(EMAIL)
        trecho = fonte[fonte.index("async function alternarEstrela"):]
        trecho = trecho[:trecho.index("async function lote")]
        # o filtro tem de estar DENTRO da condição do marcador
        i_cond = trecho.index("marcadorAtual.value === 'STARRED'")
        i_filtro = trecho.index("mensagens.value.filter")
        assert i_cond < i_filtro

    def test_a_que_estava_aberta_fecha_junto(self):
        fonte = _sem_comentario(EMAIL)
        assert "aberta.value = null" in fonte


class TestD6AssinaturaPorImagem:
    """*"assinatura por upload de imagem oculto? onde foi parar"*.

    🚨 O backend estava INTEIRO desde a migração 017 -- rota de subir, de
    tirar, pasta por atendente, e o envio já embutia por CID. Faltava só o
    controle na tela, e sem ele o recurso existia e ninguém podia usar.
    """

    def test_a_tela_deixa_subir(self):
        fonte = _sem_comentario(EMAIL)
        assert "/api/eu/assinatura/imagem" in fonte
        assert 'type="file"' in fonte

    def test_a_tela_deixa_tirar(self):
        assert "tirarImagem" in _sem_comentario(EMAIL)

    def test_o_upload_nao_passa_pelo_api_post(self):
        """⚠️ `api.post` serializa JSON. FormData precisa que o navegador monte
        o `boundary` -- definir o cabeçalho à mão quebra em silêncio, com o
        servidor recebendo corpo vazio."""
        fonte = _sem_comentario(EMAIL)
        trecho = fonte[fonte.index("async function subirImagem"):]
        trecho = trecho[:trecho.index("async function tirarImagem")]
        assert "FormData" in trecho and "fetch(" in trecho
        assert "api.post" not in trecho

    def test_o_motivo_da_recusa_chega_na_tela(self):
        """O backend recusa com motivo (não é imagem, passa de 2 MB, conta sem
        linha em `atendente`). "Não consegui" perderia o porquê."""
        fonte = _sem_comentario(EMAIL)
        trecho = fonte[fonte.index("async function subirImagem"):]
        assert "detail" in trecho[:trecho.index("async function tirarImagem")]

    def test_rele_o_estado_em_vez_de_confiar_no_200(self):
        fonte = _sem_comentario(EMAIL)
        trecho = fonte[fonte.index("async function subirImagem"):]
        assert "carregarAssinatura()" in trecho[:trecho.index("async function tirarImagem")]


class TestD7TipoSemCadastro:
    """*"Lista para selecionar o tipo 'técnico,cliente,teste,etc' ainda não
    aparece na Ficha do contato"*.

    🚨 Medido: `relacao` é coluna de CONTATO, e **63% das conversas abertas
    não têm contato** (234 de 374). A ficha ficava muda no caso mais comum.
    """

    def test_a_ficha_sem_cadastro_mostra_o_tipo(self):
        fonte = CAIXA.read_text(encoding="utf-8")
        # o bloco do `v-else` (sem vínculo) precisa falar de Tipo
        i = fonte.index("SEM vínculo: o caso comum")
        trecho = fonte[i:i + 2600]
        assert "<dt>Tipo</dt>" in trecho, (
            "a ficha continua muda justamente no caso mais comum")
        assert "Sem cadastro" in trecho

    def test_e_diz_o_que_falta_para_trocar(self):
        """⚠️ A regra que ele aprovou na escada da IA: o que não dá para mudar
        aparece dizendo o que falta para destravar."""
        fonte = CAIXA.read_text(encoding="utf-8")
        i = fonte.index("SEM vínculo: o caso comum")
        assert "vincule" in fonte[i:i + 2600].lower()

    def test_sem_cadastro_NAO_entra_no_seletor(self):
        """🚨 `contato.relacao` tem 8 valores no CHECK do banco, e este não é
        um deles -- ele é chave da `relacao_automacao`. Pôr no seletor faria a
        tela oferecer um valor que o banco recusa."""
        fonte = _sem_comentario(CAIXA)
        m = re.search(r"const RELACOES = \[(.*?)\]\n", fonte, re.S)
        assert m, "não achei RELACOES"
        assert "sem_cadastro" not in m.group(1)

    def test_a_lista_da_tela_espelha_o_CHECK_do_banco(self):
        """A mesma dívida que a migração 029 já cobrou uma vez: o CHECK
        ampliou e a lista do código ficou para trás."""
        psycopg = pytest.importorskip("psycopg")  # noqa: F841
        env = Path("/home/claude/movizap_painel/.env")
        if not env.exists() or "MOVIZAP_DB_SENHA" not in env.read_text(encoding="utf-8"):
            pytest.skip("banco nao configurado")
        from movizap import banco
        banco.abrir()
        try:
            r = banco.um("SELECT pg_get_constraintdef(oid) d FROM pg_constraint "
                         " WHERE conname LIKE %s", ("%contato_relacao%",))
        finally:
            banco.fechar()
        do_banco = set(re.findall(r"'([a-z_]+)'::text", r["d"]))
        fonte = _sem_comentario(CAIXA)
        m = re.search(r"const RELACOES = \[(.*?)\]\n", fonte, re.S)
        da_tela = set(re.findall(r"\['([a-z_]+)'", m.group(1)))
        assert da_tela == do_banco, (
            f"a tela e o banco divergem. só na tela: {da_tela - do_banco}; "
            f"só no banco: {do_banco - da_tela}")
