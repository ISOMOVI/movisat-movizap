"""O `docs/02` é espelho do banco — e agora há teste que prende isso.

🚨 POR QUE ESTE ARQUIVO EXISTE. Em 25/08 documentei as migrações 029 e 031 na
hora e esqueci as 030, 032, 033 e 034: quatro tabelas e cinco colunas ficaram
só no `.sql`. Percebi no fim do dia, por acaso. No mesmo dia eu já tinha
esquecido de atualizar `cadastro.RELACOES` depois de ampliar um CHECK -- a
rota recusava um valor que o banco aceita.

O `docs/03` (registro de telas) não sofre disso porque `teste_telas.py`
reprova quando o doc e o código divergem. Este é o mesmo remédio para o
`docs/02`.

⚠️ O QUE ESTE TESTE **NÃO** FAZ: julgar o texto. Ele só garante que o nome
existe no documento -- quem escreve o "por quê" é gente. Trava que tenta medir
qualidade de texto vira trava que grita à toa, e trava que grita à toa todo
mundo aprende a ignorar.
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")

RAIZ = Path("/home/claude/movizap_painel")
MIGRACOES = RAIZ / "migracoes"
DOC = RAIZ / "docs/02_Modelo_Dados.md"

pytestmark = pytest.mark.skipif(
    not MIGRACOES.exists() or not DOC.exists(),
    reason="projeto não encontrado no caminho esperado")

# 🚨 A LINHA DE CORTE É DECLARADA, NÃO ESCONDIDA. As migrações até a 028 são
# anteriores a esta trava: várias mexem em índice, constraint e coluna de
# apoio que o documento descreve em prosa, sem citar o nome. Reescrevê-las
# hoje seria arqueologia, e travar por elas faria o teste nascer vermelho --
# que é a forma mais rápida de um teste ser ignorado.
#
# ⚠️ Da 029 em diante, tudo que nasce entra no documento.
PRIMEIRA_COBRADA = 29

# Estruturas internas que o documento não descreve por nome, de propósito.
DISPENSADAS = {
    "schema_migracao",   # a tabela do próprio versionamento
}


def _versao(caminho: Path) -> int:
    achado = re.match(r"(\d+)_", caminho.name)
    return int(achado.group(1)) if achado else 0


def _nomes_criados(sql: str) -> set[str]:
    """Tabelas e colunas que esta migração acrescenta."""
    nomes = set()
    for tabela in re.findall(
            r"CREATE TABLE(?:\s+IF NOT EXISTS)?\s+([a-z_]+)", sql, re.I):
        nomes.add(tabela.lower())
    for coluna in re.findall(
            r"ADD COLUMN(?:\s+IF NOT EXISTS)?\s+([a-z_]+)", sql, re.I):
        nomes.add(coluna.lower())
    return {n for n in nomes if n not in DISPENSADAS}


def _migracoes_cobradas():
    return sorted(
        (p for p in MIGRACOES.glob("*.sql") if _versao(p) >= PRIMEIRA_COBRADA),
        key=_versao)


class TestOModeloEstaDocumentado:
    def test_existe_migracao_para_conferir(self):
        """Se o glob quebrar, o teste passaria vazio e não protegeria nada."""
        assert _migracoes_cobradas(), "nenhuma migração encontrada"

    @pytest.mark.parametrize("caminho", _migracoes_cobradas(),
                             ids=lambda p: p.name)
    def test_o_que_a_migracao_cria_aparece_no_doc(self, caminho):
        """🚨 Tabela ou coluna nova tem de estar no `docs/02`.

        Não é burocracia: modelo de dados que não está no documento é modelo
        que ninguém acha -- e foi assim que `contato.relacao` passou meses
        valendo uma coisa no banco e outra na cabeça de quem lia.
        """
        doc = DOC.read_text(encoding="utf-8")
        criados = _nomes_criados(caminho.read_text(encoding="utf-8"))
        faltando = sorted(n for n in criados if n not in doc)
        assert not faltando, (
            f"{caminho.name} cria {faltando} e o docs/02 não menciona. "
            f"Documente antes de seguir -- o documento é o espelho do banco.")


class TestOVocabularioEspelhaOCHECK:
    """🚨 A OUTRA METADE DO MESMO DEFEITO. Em 25/08 a migração 029 ampliou o
    CHECK de `contato.relacao` e `cadastro.RELACOES` ficou para trás: a rota
    recusava, com "relação inválida", um valor que o banco aceita.
    """

    def test_relacoes_do_codigo_estao_no_check_do_banco(self):
        psycopg = pytest.importorskip("psycopg")  # noqa: F841
        from movizap import banco, cadastro

        env = RAIZ / ".env"
        if not env.exists() or "MOVIZAP_DB_SENHA" not in env.read_text(
                encoding="utf-8"):
            pytest.skip("banco nao configurado no .env")

        banco.abrir()
        try:
            bruto = banco.um(
                """SELECT pg_get_constraintdef(oid) AS d FROM pg_constraint
                    WHERE conname = 'contato_relacao_check'""")["d"]
        finally:
            banco.fechar()
        for valor in cadastro.RELACOES:
            assert f"'{valor}'" in bruto, f"{valor} não está no CHECK do banco"
