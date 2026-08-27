"""A leitura do Gmail pagina, e o `puxar_desde` vale — 27/08.

Pedido dele: *"pagine o gmail, o puxar_desde tem que valer"*.

🚨 O DEFEITO ERA SILENCIOSO. A listagem pedia `maxResults=min(limite, 500)` e
parava na primeira página. O Gmail devolve os mais RECENTES primeiro, então a
cada 2 minutos o cron relia os mesmos 40 e contava o resto como "repetidas" --
com log de sucesso, sem erro nenhum. Faltavam **111 mensagens** que nunca
entrariam.

🚨 A CORREÇÃO É A DISTINÇÃO ENTRE LISTAR E BAIXAR. Listar ids é uma chamada por
500 mensagens; baixar o corpo é uma chamada POR MENSAGEM. O teto por execução
estava no lugar errado -- ele cortava a listagem, e com isso escondia o resto
da caixa. Agora corta os downloads.

⚠️ UM NÚMERO MEU QUE A MEDIÇÃO DERRUBOU, e fica registrado: eu disse que o
sistema "nunca alcançou janeiro", olhando `recebido_em`. Essa coluna é
`now()` -- a data em que o painel IMPORTOU. A data do e-mail é `enviado_em`, e
ela ia de 02/01 desde sempre. O `puxar_desde` funcionava melhor do que eu
afirmei; o que faltava era completar as últimas 111.
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")

FONTE = Path("/home/claude/movizap_painel/movizap/gmail.py")

pytestmark = pytest.mark.skipif(not FONTE.exists(), reason="sem o modulo")


def _sem_comentario() -> str:
    texto = FONTE.read_text(encoding="utf-8")
    texto = re.sub(r'"""[\s\S]*?"""', "", texto)
    return re.sub(r"#.*", "", texto)


class TestAListagemPagina:
    def test_a_funcao_de_listar_tudo_existe_e_segue_o_token(self):
        from movizap import gmail
        assert hasattr(gmail, "_listar_tudo")
        corpo = _sem_comentario()
        m = re.search(r"def _listar_tudo\(.*?\n(?=def )", corpo, re.S)
        assert m, "não achei o corpo de _listar_tudo"
        assert "nextPageToken" in m.group(0), (
            "sem seguir o token, a listagem para na primeira página e o "
            "`puxar_desde` volta a não valer")
        assert "pageToken" in m.group(0)

    def test_a_leitura_usa_a_listagem_paginada(self):
        """⚠️ Mede a LIGAÇÃO: a função existir e não ser chamada seria o mesmo
        que não existir."""
        corpo = _sem_comentario()
        m = re.search(r"def ler\(.*", corpo, re.S)
        assert m and "_listar_tudo(" in m.group(0)

    def test_a_listagem_tem_teto_de_paginas(self):
        """Para o dia em que alguém puser `puxar_desde` em 2015: a listagem
        sozinha viraria dezenas de chamadas antes de qualquer proveito, e o
        cron roda a cada 2 minutos."""
        from movizap import gmail
        assert gmail.TETO_PAGINAS >= 10


class TestOTetoCaiNosDownloads:
    def test_a_listagem_NAO_e_mais_cortada_pelo_limite(self):
        """🚨 O defeito de origem, fixado pelo nome para não voltar."""
        corpo = _sem_comentario()
        assert "maxResults=min(limite" not in corpo, (
            "o teto voltou para a listagem -- é isso que fazia o cron reler "
            "eternamente o topo da caixa")

    def test_o_limite_corta_os_que_faltam(self):
        corpo = _sem_comentario()
        m = re.search(r"def ler\(.*", corpo, re.S)
        assert "len(faltam) > limite" in m.group(0), (
            "sem teto nos downloads, uma caixa grande viraria centenas de "
            "chamadas numa rodada de 2 minutos")

    def test_baixa_das_mais_antigas_primeiro(self):
        """⚠️ O Gmail devolve o topo primeiro. Sem inverter, cada rodada
        baixaria de novo a mesma ponta recente e nunca chegaria ao fundo."""
        corpo = _sem_comentario()
        assert "faltam[-limite:]" in corpo

    def test_pergunta_ao_banco_de_uma_vez_so(self):
        """Com a listagem paginada são centenas de ids; um `SELECT` por item
        dentro do laço viraria centenas de idas ao banco só para descobrir que
        já temos tudo."""
        corpo = _sem_comentario()
        m = re.search(r"def ler\(.*", corpo, re.S)
        assert "vistos = {" in m.group(0)


class TestAsDuasDatasNaoSeConfundem:
    """🚨 `recebido_em` é `now()` -- quando o painel importou. `enviado_em` é a
    data do e-mail. Confundi as duas na auditoria e quase reportei um defeito
    que não existia."""

    def test_o_que_e_gravado_como_enviado_em_vem_do_cabecalho_Date(self):
        # ⚠️ O `_sem_comentario` tira docstrings, e o SQL do INSERT vive numa
        # tripla aspa -- ele sumia junto. Aqui o fonte vai inteiro.
        corpo = FONTE.read_text(encoding="utf-8")
        i = corpo.index("INSERT INTO email_mensagem")
        trecho = corpo[i:i + 1400]
        assert '_quando(_cabecalho(cabecalhos, "Date"))' in trecho, (
            "`enviado_em` deixou de vir do cabecalho Date -- a caixa passaria "
            "a ordenar pela data de importacao")

    def test_a_lista_ordena_pela_data_do_EMAIL(self):
        """Ordenar por `recebido_em` faria a caixa inteira parecer do dia da
        importação -- e é exatamente o que eu achei que estava acontecendo."""
        main = Path("/home/claude/movizap_painel/movizap/main.py") \
            .read_text(encoding="utf-8")
        assert "ORDER BY e.enviado_em DESC" in main
