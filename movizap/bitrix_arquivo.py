"""Leitura do arquivo que o Bitrix exporta. SÓ LÊ — não toca em banco nenhum.

O Bitrix chama o arquivo de `.xls`, mas ele é **HTML**: um `<table>` com
`<thead>`, UTF-8 com BOM. Nenhuma biblioteca de planilha abre isso; quem tenta
recebe "formato desconhecido". Por isso o parser é de HTML, e é aqui — os dois
importadores (CONTACT e COMPANY) usam o mesmo, senão a próxima exportação
ganha um terceiro parser ligeiramente diferente.

🚨 A NORMALIZAÇÃO DE DOCUMENTO PRESERVA LETRAS. O CNPJ alfanumérico já existe
na base (`WQ0P6GLD000108`) e `re.sub(r"\\D", "", ...)` o transformaria em
`000108` -- que não casa com nada e não acusa erro nenhum. Só os dois dígitos
verificadores, no fim, são obrigatoriamente numéricos.
"""
import html
import pathlib
import re

# 11 dígitos = CPF. 14 = CNPJ, cujos 12 primeiros caracteres podem ser letras
# desde o formato alfanumérico, e os 2 últimos são sempre dígitos.
CPF = re.compile(r"\d{11}")
CNPJ = re.compile(r"[0-9A-Z]{12}\d{2}")


def _dv(valores, pesos) -> int:
    resto = sum(v * p for v, p in zip(valores, pesos)) % 11
    return 0 if resto < 2 else 11 - resto


def _cpf_ok(limpo: str) -> bool:
    """🚨 Os pesos do CPF vão de 10 a 2 e NÃO ciclam — diferente do CNPJ.

    Usar a ciclagem 2→9 do CNPJ aqui dá um dígito errado e reprova CPF válido.
    """
    if len(set(limpo)) == 1:          # 000…, 111… fecham a conta e não existem
        return False
    v = [int(c) for c in limpo]
    return (v[9] == _dv(v[:9], range(10, 1, -1))
            and v[10] == _dv(v[:10], range(11, 1, -1)))


def _cnpj_ok(limpo: str) -> bool:
    """Pesos ciclam 2→9. `ord(c) - 48` vale para dígito e para letra, que é o
    que faz o mesmo cálculo servir ao formato alfanumérico."""
    if len(set(limpo)) == 1:
        return False
    v = [ord(c) - 48 for c in limpo]
    return (v[12] == _dv(v[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
            and v[13] == _dv(v[:13], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]))

_TAG = re.compile(r"<[^>]*>")
_CELULA = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
_LINHA = re.compile(r"<tr[^>]*>")


def celulas(linha: str) -> list[str]:
    """As células de um `<tr>`, sem marcação e com entidades resolvidas."""
    return [html.unescape(_TAG.sub("", c)).strip()
            for c in _CELULA.findall(linha)]


def ler(caminho: str | pathlib.Path) -> tuple[list[str], list[list[str]]]:
    """Devolve (cabeçalho, linhas). Erro claro se o arquivo não for o esperado.

    ⚠️ Lê o arquivo inteiro na memória. São 35 MB no CONTACT e menos no
    COMPANY -- e um parser incremental de HTML custaria muito mais do que a
    memória que economiza numa importação que roda uma vez.
    """
    bruto = pathlib.Path(caminho).read_text(encoding="utf-8", errors="replace")
    partes = _LINHA.split(bruto)[1:]
    if not partes:
        raise ValueError(
            f"{caminho} não tem nenhum <tr> — isto não é uma exportação do "
            "Bitrix. Se o arquivo abre no Excel, foi salvo de novo como xlsx "
            "e o parser de HTML não serve; exporte outra vez do Bitrix.")
    cabecalho = celulas(partes[0])
    if not cabecalho:
        raise ValueError(f"{caminho}: primeira linha sem células — sem cabeçalho")
    return cabecalho, [celulas(p) for p in partes[1:]]


def normalizar_documento(valor: str | None) -> str | None:
    """CPF/CNPJ como o cadastro guarda: sem pontuação, maiúsculo, ou None.

    🚨 Devolve None em vez de "o que deu" de propósito. Documento pela metade
    não casa com nada e sujaria a tabela de observação com lixo que parece
    dado. O que não vira documento aqui aparece no relatório como descartado.

    🚨 O DÍGITO VERIFICADOR NÃO É PURISMO AQUI, É O QUE SEPARA CPF DE CELULAR.
    Um celular brasileiro escrito sem o +55 tem **onze dígitos** -- o mesmo
    tamanho de um CPF. Sem conferir o DV, `(18) 99811-6168` viraria o
    "documento" 18998116168, e como documento é a única chave que vincula
    sozinha, um telefone na coluna errada bastaria para casar empresas que não
    têm nada a ver uma com a outra.
    """
    if not valor:
        return None
    limpo = re.sub(r"[^0-9A-Za-z]", "", valor).upper()
    if CPF.fullmatch(limpo) and _cpf_ok(limpo):
        return limpo
    if CNPJ.fullmatch(limpo) and _cnpj_ok(limpo):
        return limpo
    return None


def indice(cabecalho: list[str], *nomes: str) -> int | None:
    """A posição da 1ª coluna que casa (exato, depois por conteúdo), ou None.

    O Bitrix traduz cabeçalho conforme o idioma da conta e campos
    personalizados aparecem com o rótulo que alguém digitou. Casar só por
    igualdade exata quebraria com "CNPJ " ou "CNPJ da empresa".
    """
    baixo = [c.strip().lower() for c in cabecalho]
    for n in nomes:
        alvo = n.strip().lower()
        if alvo in baixo:
            return baixo.index(alvo)
    for n in nomes:
        alvo = n.strip().lower()
        for i, c in enumerate(baixo):
            if alvo and alvo in c:
                return i
    return None


def farejar_documento(cabecalho: list[str], linhas: list[list[str]],
                      amostra: int = 2000) -> list[tuple[str, int, int]]:
    """Quais colunas PARECEM conter documento: [(coluna, quantos, indice)].

    🚨 Existe por causa da pior falha possível aqui: importar 3.884 empresas,
    gravar 0 documentos e o script dizer "concluído". O CNPJ no Bitrix mora nos
    *requisitos*, que saem com o rótulo que a conta usa -- pode ser "CNPJ",
    "INN", "Requisitos" ou `UF_CRM_1699...`. Em vez de adivinhar o nome, olha
    o VALOR: se uma coluna tem documento válido, ela aparece aqui.
    """
    achados = []
    for i, nome in enumerate(cabecalho):
        n = sum(1 for linha in linhas[:amostra]
                if i < len(linha) and normalizar_documento(linha[i]))
        if n:
            achados.append((nome, n, i))
    return sorted(achados, key=lambda x: -x[1])
