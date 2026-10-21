"""Orçamento de serviço técnico — numeração, documento e PDF.

🔵 Decisão 9 dele (19/10): numeração **própria** do MoviZap, com aba de
configuração exclusiva do owner. 🔵 Decisão 12: o catálogo sai dos itens de
serviço do Harmonit, **uma vez**, só para a nomenclatura bater, e fica
limitado a **deslocamento** e **pagamento de técnico** -- sem API fixa, para
emitir orçamento não depender do Harmonit estar no ar. 🔵 Decisão 13:
deslocamento é **por km**.

🚨 O NÚMERO SÓ SE GASTA QUANDO O PDF EXISTE. Reservar antes deixa buraco na
sequência toda vez que alguém abre o modal e desiste -- e buraco em documento
numerado é o tipo de coisa que aparece numa conferência meses depois, sem
ninguém saber explicar.

⚠️ O documento de hoje (modelo `Orçamento Parceiros 1668.pdf`) imprime
"77.7 un" na linha de deslocamento. É isso que faz a coluna parecer trocada:
são 77,7 **km** a R$ 1,00. Aqui a unidade é dado da linha, e o PDF imprime
"77,7 km".

🚨 DINHEIRO EM CENTAVOS, INTEIRO, do começo ao fim. Entra em centavos, soma em
centavos, e só vira texto na hora de imprimir.
"""
import logging
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from . import banco

log = logging.getLogger(__name__)

CHAVE_NUMERO = "orcamento_proximo_numero"

# O logo que o painel já usa. Mesmo arquivo do menu -- lá ele é invertido por
# CSS porque o menu é escuro; no papel vai como é.
LOGO = Path(__file__).parent.parent / "frontend" / "public" / "movisat-logo.png"

# 🔵 Decisão 12 dele. Os nomes foram tirados do Harmonit em 21/10, UMA VEZ,
# por `/Produto/ObterServicos` -- e os ids são os mesmos que o Painel
# Financeiro do FPSL já usa (PAGAMENTO=653939, KM=6971). Ficam gravados aqui
# de propósito: emitir orçamento não pode depender do Harmonit responder.
CATALOGO = [
    {"servico": "KM DESLOCAMENTO", "harmonit_id": 6971, "unidade": "km"},
    {"servico": "PAGAMENTO DE TECNICO", "harmonit_id": 653939, "unidade": "un"},
]
UNIDADES = ("un", "km")


class SemNumeracao(RuntimeError):
    """A chave da numeração sumiu do `config`. Não se inventa número."""


def catalogo() -> list[dict]:
    """Os serviços que o modal oferece. Lista fechada, por decisão dele."""
    return [dict(i) for i in CATALOGO]


def proximo_numero() -> int:
    linha = banco.um("SELECT valor FROM config WHERE chave = %s", (CHAVE_NUMERO,))
    if not linha:
        raise SemNumeracao(
            f"a chave {CHAVE_NUMERO} não está no config -- ver migração 069")
    return int(linha["valor"])


def definir_proximo_numero(numero: int, *, cur=None) -> None:
    """Muda o próximo número. **Só o owner chega aqui** (aba do /config).

    ⚠️ A aba avisa, em texto, que isto pode repetir documento já emitido pelo
    sistema atual, que segue existindo fora desta VPS.
    """
    if numero < 1:
        raise ValueError("número de orçamento começa em 1")
    sql = ("UPDATE config SET valor = %s, atualizado_em = now() WHERE chave = %s")
    if cur is not None:
        cur.execute(sql, (str(int(numero)), CHAVE_NUMERO))
        return
    if banco.executar(sql, (str(int(numero)), CHAVE_NUMERO)) == 0:
        raise SemNumeracao(f"a chave {CHAVE_NUMERO} não está no config")


def centavos(valor) -> int:
    """Reais (texto, float ou Decimal) -> centavos inteiros, meio pra cima."""
    return int((Decimal(str(valor)) * 100).quantize(Decimal("1"), ROUND_HALF_UP))


def reais(valor_centavos: int) -> str:
    """Centavos -> "1.234,56", do jeito que se lê em português."""
    inteiro, resto = divmod(abs(int(valor_centavos)), 100)
    sinal = "-" if valor_centavos < 0 else ""
    return f"{sinal}{inteiro:,}".replace(",", ".") + f",{resto:02d}"


def _quantidade_texto(quantidade, unidade: str) -> str:
    """"77,7 km" e "1 un" -- sem casa decimal à toa, e com vírgula."""
    q = Decimal(str(quantidade)).normalize()
    texto = format(q, "f")
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    return f"{texto.replace('.', ',')} {unidade}"


def calcular(itens: list[dict]) -> tuple[list[dict], int]:
    """Normaliza as linhas e soma. Devolve (itens, total em centavos).

    🚨 O VALOR DA LINHA É CALCULADO AQUI, não aceito da tela: preço x
    quantidade é conta, e conta que chega pronta do navegador é conta que
    alguém pode ter editado.
    """
    if not itens:
        raise ValueError("orçamento sem nenhuma linha não é orçamento")
    normalizados, total = [], 0
    for ordem, item in enumerate(itens, start=1):
        servico = (item.get("servico") or "").strip()
        if not servico:
            raise ValueError(f"a linha {ordem} está sem serviço")
        unidade = (item.get("unidade") or "un").strip()
        if unidade not in UNIDADES:
            raise ValueError(f"unidade inválida na linha {ordem}: {unidade!r}")
        preco = centavos(item.get("preco_unit") if "preco_unit" in item
                         else Decimal(item["preco_unit_centavos"]) / 100)
        quantidade = Decimal(str(item.get("quantidade", 1)))
        if quantidade <= 0:
            raise ValueError(f"quantidade tem de ser positiva na linha {ordem}")
        valor = int((Decimal(preco) * quantidade).quantize(Decimal("1"), ROUND_HALF_UP))
        total += valor
        normalizados.append({
            "ordem": ordem, "servico": servico, "unidade": unidade,
            "preco_unit_centavos": preco, "quantidade": quantidade,
            "valor_centavos": valor,
        })
    return normalizados, total


# ---------------------------------------------------------------------------
# O PDF
# ---------------------------------------------------------------------------
def montar_pdf(*, numero: int, tecnico: str, ordens: list[int],
               itens: list[dict], total_centavos: int, data=None) -> bytes:
    """O documento, no layout do modelo que ele mandou.

    `fpdf2` de propósito: é a única biblioteca de PDF sem dependência de
    sistema -- nada de `wkhtmltopdf` nem de navegador headless num servidor
    que também atende WhatsApp.
    """
    from fpdf import FPDF  # tardio: só quem emite orçamento paga o import

    data = data or datetime.now()
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    if LOGO.exists():
        # Centralizado, como no modelo. 52 mm mantém a proporção 732x252.
        pdf.image(str(LOGO), x=(210 - 52) / 2, y=12, w=52)
        pdf.ln(26)
    else:
        # 🚨 Sem logo o documento SAI MESMO ASSIM. Orçamento preso por causa
        # de uma imagem seria o pior dos dois mundos.
        log.warning("logo não encontrado em %s -- PDF sai sem ele", LOGO)
        pdf.ln(6)

    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 7, f"Orçamento nº {numero}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 11)
    pdf.cell(0, 7, f"Data: {data:%d/%m/%Y}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    pdf.set_font("helvetica", "B", 18)
    pdf.cell(0, 12, "ORÇAMENTO DE SERVIÇO TÉCNICO", align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    largura = 190

    def faixa(titulo: str, conteudo: str):
        pdf.set_font("helvetica", "B", 10)
        pdf.set_fill_color(235, 235, 235)
        pdf.cell(largura, 8, titulo, border=1, align="C", fill=True,
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("helvetica", "", 10)
        pdf.cell(largura, 10, conteudo, border=1, align="C",
                 new_x="LMARGIN", new_y="NEXT")

    faixa("Técnico responsável:", tecnico or "-")
    faixa("Ordem(ns) de serviço(s):",
          ", ".join(str(o) for o in ordens) if ordens else "-")
    pdf.ln(8)

    colunas = (60, 35, 45, 50)
    pdf.set_font("helvetica", "B", 10)
    pdf.set_fill_color(245, 245, 245)
    for rotulo, largura_col, alinhamento in zip(
            ("SERVIÇO", "PREÇO UNIT.", "QTDE.", "VALOR"), colunas,
            ("L", "R", "R", "R")):
        pdf.cell(largura_col, 9, rotulo, border=1, align=alinhamento, fill=True)
    pdf.ln()

    pdf.set_font("helvetica", "", 10)
    for item in itens:
        pdf.cell(colunas[0], 9, item["servico"], border=1)
        pdf.cell(colunas[1], 9, reais(item["preco_unit_centavos"]), border=1, align="R")
        # ⚠️ AQUI MORA O CONSERTO: "77,7 km", e não "77.7 un".
        pdf.cell(colunas[2], 9,
                 _quantidade_texto(item["quantidade"], item["unidade"]),
                 border=1, align="R")
        pdf.cell(colunas[3], 9, reais(item["valor_centavos"]), border=1, align="R")
        pdf.ln()

    pdf.set_font("helvetica", "B", 10)
    pdf.cell(largura, 9, f"Total do orçamento: R${reais(total_centavos)}",
             border=1, align="R", fill=True, new_x="LMARGIN", new_y="NEXT")

    saida = pdf.output()
    return bytes(saida)


def nome_do_arquivo(numero: int) -> str:
    return f"Orcamento_{numero}.pdf"


# ---------------------------------------------------------------------------
# Emissão
# ---------------------------------------------------------------------------
def emitir(*, conversa_id: int, tecnico_contato_id: int, tecnico_nome: str,
           ordens: list[int], itens: list[dict], criado_por: int,
           enviar_na_conversa=None) -> dict:
    """Gera o PDF, gasta o número e grava — nesta ordem.

    `enviar_na_conversa(dados, mime, nome, legenda)` é injetado por quem chama
    (o `main.py` embrulha `conversas.responder_com_arquivo`). Fica como
    parâmetro para o teste poder emitir sem mandar nada a ninguém: **teste não
    fala com o WhatsApp**.

    🚨 A ORDEM É O DESENHO. O PDF é montado ANTES de o número ser gasto, e o
    número é gasto na MESMA transação em que o orçamento é gravado. Assim:
    modal fechado no meio não consome número, e número consumido sempre tem
    documento do lado.
    """
    linhas, total = calcular(itens)

    with banco.cursor() as cur:
        # `FOR UPDATE` na linha do config: dois operadores emitindo no mesmo
        # segundo não podem receber o mesmo número.
        cur.execute("SELECT valor FROM config WHERE chave = %s FOR UPDATE",
                    (CHAVE_NUMERO,))
        linha = cur.fetchone()
        if not linha:
            raise SemNumeracao(
                f"a chave {CHAVE_NUMERO} não está no config -- ver migração 069")
        numero = int(linha["valor"])

        pdf = montar_pdf(numero=numero, tecnico=tecnico_nome, ordens=ordens,
                         itens=linhas, total_centavos=total)

        cur.execute(
            "INSERT INTO orcamento (numero, tecnico_contato_id, conversa_id, "
            "    total_centavos, criado_por, ordens_os) "
            "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
            (numero, tecnico_contato_id, conversa_id, total, criado_por,
             [int(o) for o in ordens]))
        orcamento_id = cur.fetchone()["id"]
        for item in linhas:
            cur.execute(
                "INSERT INTO orcamento_item (orcamento_id, ordem, servico, "
                "    preco_unit_centavos, quantidade, unidade, valor_centavos) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (orcamento_id, item["ordem"], item["servico"],
                 item["preco_unit_centavos"], item["quantidade"],
                 item["unidade"], item["valor_centavos"]))
        cur.execute("UPDATE config SET valor = %s, atualizado_em = now() "
                    " WHERE chave = %s", (str(numero + 1), CHAVE_NUMERO))

    resultado = {"id": orcamento_id, "numero": numero,
                 "total_centavos": total, "itens": linhas,
                 "arquivo": nome_do_arquivo(numero), "enviado": None}

    if enviar_na_conversa is not None:
        # 🚨 O ENVIO É DEPOIS DO COMMIT, e a falha dele NÃO desfaz o
        # orçamento: o documento existe, está numerado, e o atendente pode
        # reenviar. Desfazer aqui abriria buraco na sequência.
        #
        # 🚨 E A FALHA NÃO PODE VIRAR ERRO DA EMISSÃO. Em 21/10, no primeiro
        # uso real dele, um erro meu na chamada do envio estourou DEPOIS do
        # commit: o orçamento nº 1 existia, o número já tinha sido gasto, e a
        # tela só disse "erro ao gerar PDF". Quem emite tem de receber o
        # documento que existe, e o aviso de que o envio não foi.
        resultado["enviado"] = _enviar(pdf, numero, orcamento_id,
                                       enviar_na_conversa)
        if resultado["enviado"].get("midia_id"):
            resultado["midia_id"] = resultado["enviado"]["midia_id"]
    return resultado


def _enviar(pdf: bytes, numero: int, orcamento_id: int, enviar_na_conversa) -> dict:
    """Manda o PDF e amarra a mídia ao orçamento. Nunca estoura."""
    try:
        envio = enviar_na_conversa(pdf, "application/pdf",
                                   nome_do_arquivo(numero),
                                   f"Orçamento nº {numero}")
    except Exception as e:  # noqa: BLE001 -- aqui engolir é o comportamento certo
        log.exception("orçamento %s emitido, e o envio falhou", numero)
        return {"ok": False, "motivo": f"O documento foi gerado, mas o envio "
                                       f"falhou: {type(e).__name__}: {e}"}
    if envio and envio.get("ok") and envio.get("midia_id"):
        banco.executar("UPDATE orcamento SET midia_id = %s WHERE id = %s",
                       (envio["midia_id"], orcamento_id))
    return envio or {"ok": False, "motivo": "o envio não respondeu nada"}


def reenviar(orcamento_id: int, enviar_na_conversa) -> dict:
    """Remonta o PDF de um orçamento já emitido e manda de novo.

    🚨 NÃO GASTA NÚMERO NOVO. É o conserto para o caso em que o documento
    existe e o envio falhou -- emitir outro deixaria dois números para o mesmo
    serviço, que é exatamente o buraco que a numeração tenta evitar.
    """
    guardado = por_id(orcamento_id)
    if not guardado:
        raise ValueError("orçamento não encontrado")
    pdf = montar_pdf(
        numero=guardado["numero"],
        tecnico=guardado.get("tecnico_nome") or "",
        # As OS vêm da própria linha: é o que faz o reenvio ser o MESMO papel.
        ordens=list(guardado.get("ordens_os") or []),
        itens=guardado["itens"],
        total_centavos=guardado["total_centavos"],
        data=guardado.get("criado_em"),
    )
    envio = _enviar(pdf, guardado["numero"], orcamento_id, enviar_na_conversa)
    return {"id": orcamento_id, "numero": guardado["numero"], "enviado": envio}


def por_id(orcamento_id: int) -> dict | None:
    linha = banco.um(
        "SELECT o.*, c.nome AS tecnico_nome FROM orcamento o "
        "  LEFT JOIN contato c ON c.id = o.tecnico_contato_id "
        " WHERE o.id = %s", (orcamento_id,))
    if not linha:
        return None
    linha["itens"] = banco.varios(
        "SELECT ordem, servico, preco_unit_centavos, quantidade, unidade, "
        "       valor_centavos FROM orcamento_item "
        " WHERE orcamento_id = %s ORDER BY ordem", (orcamento_id,))
    return linha


def da_conversa(conversa_id: int) -> list[dict]:
    """Os orçamentos já emitidos nesta conversa — o modal mostra para não
    emitir dois iguais sem querer."""
    return banco.varios(
        "SELECT id, numero, total_centavos, midia_id, criado_em FROM orcamento "
        " WHERE conversa_id = %s ORDER BY numero DESC", (conversa_id,))
