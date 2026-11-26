# -*- coding: utf-8 -*-
"""O COMPROVANTE DE PAGAMENTO EM ARQUIVO — aba 2 do Financeiro, 25/11/2026.

🔵 Dele, 18/11: *"haverá campo para que em cada 1 dos artefatos de pagamento
seja inserido anexo que comprove o pagamento. Após o envio do anexo, abre o
campo que pede o valor inserido no documento."*
🔵 E em 24/11: o anexo é **do MoviZap, no padrão da observação da Operação**, e
é **anexo completo — não só PDF**.

🚨 **MOLDE DO `passagem.guardar_anexo`, E A LISTA DE EXTENSÕES É A MESMA.** Ela
é **importada**, não recopiada: lista duplicada divergiria na primeira vez que
alguém acrescentasse um formato num dos dois lugares — e o jeito de descobrir
seria um operador com um arquivo recusado na mão.

🚨 **RECUSA ANTES DE ESCREVER NO DISCO.** Extensão, teto e arquivo vazio são
conferidos primeiro, para não deixar arquivo solto quando a linha não vai
existir.

🚨 **O ARTEFATO VIVE NO SQLITE DO FPSL, ENTÃO NÃO HÁ FK.** Quem confere a
existência é a rota, pelo quadro da ponte — e é por isso que este módulo
**exige o id já conferido**: ele não adivinha, não consulta o FPSL e não
inventa garantia que o banco não dá.
"""
import logging
import pathlib
import uuid

from . import banco
# ⚠️ `DadoInvalido` sai da `operacao`, que é onde ela mora — não da `passagem`,
# que só a importa. Importar de quem importa esconde o dono e quebra calado no
# dia em que a `passagem` deixar de precisar dela.
from .operacao import DadoInvalido
from .passagem import EXTENSOES_DA_OBS

log = logging.getLogger(__name__)

# ⚠️ Pasta própria, fora do repositório, um diretório sorteado por arquivo — o
# nome original é preservado só para exibir e para o download.
PASTA = pathlib.Path("/home/claude/movizap_pagamento_comprovantes")

# 🚨 O MESMO TETO DA OBSERVAÇÃO E DO FORMULÁRIO. Comprovante é recibo, não
# acervo: 10 MB já aceita PDF digitalizado e foto de celular.
TETO = 10 * 1024 * 1024

# 🔵 *"anexo completo — não só PDF"*: o conjunto da observação, inteiro.
EXTENSOES = EXTENSOES_DA_OBS


def guardar(artefato_id: int, nome: str, dados: bytes,
            mime: str | None = None, por: str | None = None) -> dict:
    """Guarda o comprovante e devolve a linha gravada (com o `id`).

    ⚠️ **NÃO confere se o artefato existe** — isso é da rota, que tem o quadro.
    Conferir aqui exigiria deste módulo uma chamada HTTP ao FPSL por upload.
    """
    limpo = pathlib.Path(nome or "").name.strip() or "arquivo"
    extensao = pathlib.Path(limpo).suffix.lower()
    if extensao not in EXTENSOES:
        raise DadoInvalido(
            f"{extensao or 'arquivo sem extensão'} não é um tipo aceito aqui. "
            f"Aceito: {', '.join(sorted(EXTENSOES))}.")
    if len(dados) > TETO:
        raise DadoInvalido(
            f"O arquivo tem {len(dados) // 1024} KB e o limite é "
            f"{TETO // 1024 // 1024} MB.")
    if not dados:
        raise DadoInvalido("O arquivo veio vazio.")

    pasta = PASTA / uuid.uuid4().hex
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / limpo
    destino.write_bytes(dados)

    linha = banco.um(
        """INSERT INTO pagamento_comprovante_arquivo
               (artefato_id, nome_original, caminho, bytes, mime, por)
           VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
        (artefato_id, limpo, str(destino), len(dados), mime, por))
    log.info("artefato %s: comprovante %s guardado (%s bytes) por %s",
             artefato_id, linha["id"], len(dados), por)
    return anexo(linha["id"])


def anexo(anexo_id: int) -> dict | None:
    return banco.um(
        """SELECT id, artefato_id, nome_original, caminho, bytes, mime,
                  criado_em, por
             FROM pagamento_comprovante_arquivo WHERE id = %s""", (anexo_id,))


def de_artefatos(artefato_ids: list[int]) -> dict:
    """`{artefato_id: [anexos]}` — UMA consulta para o quadro todo.

    ⚠️ O `caminho` NÃO sai daqui para a tela: é caminho de disco, e a tela não
    tem o que fazer com ele. Quem baixa usa o id — a régua do `anexos_de`.
    """
    if not artefato_ids:
        return {}
    por_artefato: dict = {}
    for r in banco.varios(
            """SELECT id, artefato_id, nome_original, bytes, mime, criado_em
                 FROM pagamento_comprovante_arquivo
                WHERE artefato_id = ANY(%s)
                ORDER BY id""", (list(artefato_ids),)):
        por_artefato.setdefault(r["artefato_id"], []).append(r)
    return por_artefato


def referencia(anexo_id: int) -> str:
    """O que vai para o `comprovante_arquivo` do FPSL: `anexo:<id>`.

    🚨 **TEXTO, NUNCA BYTES, E NUNCA CAMINHO.** A ponte é JSON
    servidor-a-servidor; caminho de disco atravessando a ponte faria o FPSL
    guardar algo que só este servidor sabe ler, e bytes fariam a ponte carregar
    arquivo que ela não foi feita para carregar. O FPSL guarda a referência no
    campo de texto que **já existe**, sem migração nenhuma daquele lado.
    """
    return f"anexo:{int(anexo_id)}"
