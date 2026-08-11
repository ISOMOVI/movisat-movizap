"""Testes da leitura do arquivo do Bitrix e da régua de documento.

O Bitrix é o sistema que está saindo, e a importação dele roda poucas vezes --
o que é exatamente o motivo de ter teste: um erro aqui não aparece amanhã na
tela, aparece daqui a meses como cliente vinculado à empresa errada.

🚨 O caso que dá nome a este arquivo é o CNPJ alfanumérico. O importador de
contatos usa `re.sub(r"\\D", "", ...)`, que transforma `WQ0P6GLD000108` em
`000108` -- não casa com nada, não levanta exceção, e o relatório diz
"concluído". A empresa de teste oficial tem exatamente esse documento.
"""
import pytest

from movizap import bitrix_arquivo

VELASCO = "WQ0P6GLD000108"          # CNPJ alfanumérico, empresa de teste oficial

CABECALHO = ["ID", "Nome da empresa", "Tipo de empresa", "CNPJ", "Telefone"]
LINHAS = [
    ["101", "Pastelaria Velasco", "Cliente", "WQ.0P6.GLD/0001-08", "+5518998116168"],
    ["102", "Transportes Silva", "Cliente", "13.691.561/0001-26", "1832214455"],
    ["103", "Prospect Sem Doc", "Prospect", "", ""],
]


def montar(cabecalho=CABECALHO, linhas=LINHAS, com_bom=True):
    """Monta um arquivo no formato REAL: HTML com extensão .xls, BOM, entidades."""
    def tr(celulas, tag):
        return "<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in celulas) + "</tr>"
    corpo = (('﻿' if com_bom else '')
             + '<meta http-equiv="Content-type" content="text/html;charset=UTF-8" />'
             + '<table border="1"><thead>' + tr(cabecalho, "th") + "</thead><tbody>"
             + "".join(tr(l, "td") for l in linhas) + "</tbody></table>")
    return corpo


@pytest.fixture()
def arquivo(tmp_path):
    p = tmp_path / "COMPANY_teste.xls"
    p.write_text(montar(), encoding="utf-8")
    return p


class TestNormalizarDocumento:
    """A régua começa aqui: sem documento certo, não há prova nenhuma."""

    def test_cnpj_alfanumerico_sobrevive(self):
        # 🚨 O teste mais importante do arquivo. Só-dígitos devolveria '000108'.
        assert bitrix_arquivo.normalizar_documento("WQ.0P6.GLD/0001-08") == VELASCO
        assert bitrix_arquivo.normalizar_documento("wq0p6gld000108") == VELASCO

    def test_cnpj_e_cpf_normais(self):
        assert bitrix_arquivo.normalizar_documento("13.691.561/0001-26") == "13691561000126"
        assert bitrix_arquivo.normalizar_documento("123.456.789-09") == "12345678909"

    def test_o_que_nao_e_documento_vira_None(self):
        # Devolver "o que deu" encheria a tabela de lixo com cara de dado.
        for lixo in ("", None, "—", "n/a", "1234", "0000000000000000000",
                     "(18) 99811-6168"):
            assert bitrix_arquivo.normalizar_documento(lixo) is None

    def test_verificador_do_cnpj_e_sempre_numerico(self):
        # O formato alfanumérico permite letra nos 12 primeiros, nunca nos 2
        # últimos. Aceitar letra ali abriria a porta para código interno.
        assert bitrix_arquivo.normalizar_documento("WQ0P6GLD0001AB") is None

    def test_telefone_nao_vira_documento(self):
        # 13 dígitos: se caísse como documento, casaria empresa por telefone.
        assert bitrix_arquivo.normalizar_documento("+55 18 99811-6168") is None

    def test_celular_sem_o_55_tem_11_digitos_como_um_CPF(self):
        # 🚨 Este teste reprovou o código na primeira execução, e é a razão de
        # o dígito verificador existir aqui. Documento é a ÚNICA chave que
        # vincula sozinha: um telefone na coluna errada casaria empresas que
        # não têm nada a ver uma com a outra.
        assert bitrix_arquivo.normalizar_documento("(18) 99811-6168") is None
        assert bitrix_arquivo.normalizar_documento("18998116168") is None

    def test_documento_com_digito_verificador_errado_e_recusado(self):
        assert bitrix_arquivo.normalizar_documento("13.691.561/0001-27") is None
        assert bitrix_arquivo.normalizar_documento("123.456.789-00") is None


class TestLerArquivo:
    def test_le_cabecalho_e_linhas(self, arquivo):
        cabecalho, linhas = bitrix_arquivo.ler(arquivo)
        assert cabecalho == CABECALHO
        assert len(linhas) == 3
        assert linhas[0][1] == "Pastelaria Velasco"

    def test_resolve_entidades_e_acento(self, tmp_path):
        p = tmp_path / "a.xls"
        p.write_text(montar(cabecalho=["ID", "Posi&ccedil;&atilde;o"],
                            linhas=[["1", "S&oacute;cio &amp; Diretor"]]),
                     encoding="utf-8")
        cabecalho, linhas = bitrix_arquivo.ler(p)
        assert cabecalho == ["ID", "Posição"]
        assert linhas[0][1] == "Sócio & Diretor"

    def test_arquivo_que_nao_e_do_bitrix_diz_o_que_houve(self, tmp_path):
        # Falhar com "list index out of range" mandaria alguém depurar o
        # parser quando o problema é o arquivo.
        p = tmp_path / "planilha.xlsx"
        p.write_text("PK\x03\x04 conteudo binario de xlsx", encoding="utf-8")
        with pytest.raises(ValueError, match="não é uma exportação do Bitrix"):
            bitrix_arquivo.ler(p)


class TestAcharColuna:
    def test_casa_exato_antes_de_parcial(self):
        cabecalho = ["ID da empresa associada", "ID"]
        assert bitrix_arquivo.indice(cabecalho, "ID") == 1

    def test_casa_por_conteudo_quando_nao_ha_exato(self):
        # "CNPJ da empresa" tem que ser encontrado por quem procura "CNPJ".
        assert bitrix_arquivo.indice(["ID", "CNPJ da empresa"], "CNPJ") == 1

    def test_devolve_None_quando_nao_existe(self):
        assert bitrix_arquivo.indice(["ID", "Nome"], "CNPJ", "INN") is None


class TestFarejarDocumento:
    """🚨 A defesa contra a falha silenciosa: importar tudo e 0 documentos."""

    def test_acha_a_coluna_pelo_valor_mesmo_com_rotulo_estranho(self):
        cabecalho = ["ID", "Nome", "UF_CRM_1699887766", "Telefone"]
        linhas = [["1", "A", "13.691.561/0001-26", "1832214455"],
                  ["2", "B", "11.180.397/0001-67", "1832214456"]]
        achados = bitrix_arquivo.farejar_documento(cabecalho, linhas)
        assert achados[0][0] == "UF_CRM_1699887766"
        assert achados[0][1] == 2

    def test_nao_aponta_nada_quando_o_export_veio_sem_requisitos(self):
        cabecalho = ["ID", "Nome", "Telefone"]
        linhas = [["1", "A", "1832214455"], ["2", "B", "+5518998116168"]]
        assert bitrix_arquivo.farejar_documento(cabecalho, linhas) == []
