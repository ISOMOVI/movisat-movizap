"""CSV para download, do jeito que o Excel brasileiro abre (Bloco 3, 15/10).

Não havia nada de CSV no projeto (procurei: zero ocorrências de `csv`,
`text/csv` ou `StreamingResponse` em `movizap/`). Este é o primeiro, e nasce
genérico porque a aba Ligações não vai ser a última a exportar.

Três escolhas que evitam chamado:

  · **`;` como separador.** O Excel em português usa ponto e vírgula; com
    vírgula, a planilha abre com tudo numa coluna só.
  · **BOM no começo** (`utf-8-sig`). Sem ele o Excel lê o arquivo como ANSI e
    "Ligações" aparece "LigaÃ§Ãµes".
  · **CRLF**, que é o que a RFC 4180 pede e o que o Excel espera.

🚨 Fórmula não se abre sozinha: valor que começa com `=`, `+`, `-` ou `@` vira
texto com um apóstrofo na frente. Sem isso, um nome de contato como
`=cmd|...` viraria execução ao abrir a planilha (injeção de CSV).
"""
import csv
import io

SEPARADOR = ";"
PERIGOSOS = ("=", "+", "-", "@")


def _seguro(valor) -> str:
    if valor is None:
        return ""
    texto = str(valor)
    if texto[:1] in PERIGOSOS:
        return "'" + texto
    return texto


def gerar(colunas: list[tuple[str, str]], linhas: list[dict]) -> bytes:
    """`colunas` é [(chave, título)]; a ordem do cabeçalho é a ordem daqui."""
    buffer = io.StringIO(newline="")
    escritor = csv.writer(buffer, delimiter=SEPARADOR, quoting=csv.QUOTE_MINIMAL,
                          lineterminator="\r\n")
    escritor.writerow([titulo for _, titulo in colunas])
    for linha in linhas:
        escritor.writerow([_seguro(linha.get(chave)) for chave, _ in colunas])
    return buffer.getvalue().encode("utf-8-sig")


def cabecalhos(nome_arquivo: str) -> dict[str, str]:
    """⚠️ As aspas no `filename` são obrigatórias: sem elas, nome com espaço
    chega truncado no navegador (mesma pegadinha do anexo de e-mail)."""
    return {"Content-Disposition": f'attachment; filename="{nome_arquivo}"'}
