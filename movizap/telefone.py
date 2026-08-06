"""Normalização de telefone — a chave de tudo no MoviZap.

Telefone é o que liga a mensagem que acabou de chegar ao cliente que já existe
no cadastro. Se a normalização erra, o cliente escreve e o sistema responde que
ele não é cliente. O erro é invisível: nada quebra, nada estoura, nada aparece
no log -- simplesmente não encontra.

REGRA DA CASA (metodologia §2, "Telefone é chave, e telefone brasileiro é sujo"):
  - grava-se SEMPRE o bruto e o normalizado. O bruto nunca se perde;
  - busca NUNCA por igualdade do que chegou -- sempre pelo normalizado;
  - `tem_whatsapp` é campo verificado pelo Evolution, não suposição.
    NULL é "não verificado" e é DIFERENTE de False.

🚨 O NONO DÍGITO, e como este módulo resolve.

`+5518998116168` e `+551898116168` são a mesma pessoa. A saída canônica daqui
SEMPRE inclui o nono dígito quando o número é celular, então as duas grafias
convergem para a mesma string. É isso que faz o índice `ix_telefone_e164`
bastar: não precisa de coluna colapsada, não precisa de migração, e a busca
continua sendo uma igualdade simples.

Isso quer dizer que o `e164` de um celular que chegou com 8 dígitos é um
PALPITE. Um palpite correto -- a migração brasileira de 2016 apenas prefixou o
9 aos celulares -- mas ainda assim um palpite. **É exatamente por isso que a
coluna `bruto` existe**, e por isso ela nunca deve ser sobrescrita.

⚠️ Ao PERGUNTAR para fora (Harmonit, WESO), use `variantes()`. Lá não existe
garantia nenhuma de qual das duas grafias foi gravada.
"""

import re
from dataclasses import dataclass

_SO_DIGITOS = re.compile(r"\D+")

DDI_BR = "55"

# DDDs que existem de verdade. A lista importa: sem ela, "00" e "99999999999"
# viram telefone válido e vão parar no cadastro parecendo gente.
DDDS_VALIDOS = frozenset({
    "11", "12", "13", "14", "15", "16", "17", "18", "19",
    "21", "22", "24", "27", "28",
    "31", "32", "33", "34", "35", "37", "38",
    "41", "42", "43", "44", "45", "46", "47", "48", "49",
    "51", "53", "54", "55",
    "61", "62", "63", "64", "65", "66", "67", "68", "69",
    "71", "73", "74", "75", "77", "79",
    "81", "82", "83", "84", "85", "86", "87", "88", "89",
    "91", "92", "93", "94", "95", "96", "97", "98", "99",
})

# Celular brasileiro começa em 6-9; fixo, em 2-5. É o que separa "acrescenta o
# nono dígito" de "não encosta".
_INICIO_MOVEL = frozenset("6789")
_INICIO_FIXO = frozenset("2345")

MOVEL = "movel"
FIXO = "fixo"
INTERNACIONAL = "internacional"
INVALIDO = "invalido"


@dataclass(frozen=True)
class Analise:
    """O resultado, com o motivo junto.

    O motivo não é enfeite: o sync precisa separar `ok` / `vazio` / `erro`, e
    sem a razão da recusa o painel vira "76% de falha" num sistema saudável.
    """

    e164: str | None
    tipo: str
    motivo: str = ""
    nono_digito_acrescentado: bool = False

    def __bool__(self) -> bool:
        return self.e164 is not None


def _tira_prefixo_nacional(digitos: str) -> str:
    """Remove o 0 de discagem e o código de operadora (`0 15 18 99811...`)."""
    if not digitos.startswith("0"):
        return digitos
    if len(digitos) in (13, 14):  # 0 + operadora(2) + DDD(2) + assinante(8|9)
        return digitos[3:]
    if len(digitos) in (11, 12):  # 0 + DDD(2) + assinante(8|9)
        return digitos[1:]
    return digitos.lstrip("0")


def analisar(bruto) -> Analise:
    """Do que veio para o E.164 canônico, dizendo por que quando não dá."""
    if bruto is None:
        return Analise(None, INVALIDO, "vazio")

    texto = str(bruto).strip()
    if not texto:
        return Analise(None, INVALIDO, "vazio")

    # JID do Evolution: `5518998116168@s.whatsapp.net`, às vezes com sufixo de
    # dispositivo `:12`. Chega assim em TODO webhook -- tratar aqui é o que
    # evita repetir `.split("@")` espalhado pelo código.
    texto = texto.split("@", 1)[0].split(":", 1)[0]

    tinha_mais = texto.lstrip().startswith("+")
    digitos = _SO_DIGITOS.sub("", texto)
    if not digitos:
        return Analise(None, INVALIDO, "sem dígito")

    digitos = _tira_prefixo_nacional(digitos)

    # Estrangeiro só quando o "+" disse que era: sem ele, "441234567890" é
    # ambíguo e chutar país é pior que recusar.
    if tinha_mais and not digitos.startswith(DDI_BR):
        if 8 <= len(digitos) <= 15:
            return Analise("+" + digitos, INTERNACIONAL)
        return Analise(None, INVALIDO, f"internacional com {len(digitos)} dígitos")

    # +55 só sai se o que sobra tiver cara de número brasileiro. Isso protege o
    # DDD 55 (Santa Maria/RS): "5599876543" tem 10 dígitos e não é tocado.
    if digitos.startswith(DDI_BR) and len(digitos) in (12, 13):
        digitos = digitos[2:]

    if len(digitos) not in (10, 11):
        return Analise(
            None, INVALIDO, f"{len(digitos)} dígitos -- esperado 10 ou 11 com DDD"
        )

    ddd, assinante = digitos[:2], digitos[2:]
    if ddd not in DDDS_VALIDOS:
        return Analise(None, INVALIDO, f"DDD {ddd} não existe")

    if len(assinante) == 9:
        if assinante[0] != "9":
            return Analise(
                None, INVALIDO, f"9 dígitos começando em {assinante[0]}, não em 9"
            )
        return Analise(f"+{DDI_BR}{ddd}{assinante}", MOVEL)

    if assinante[0] in _INICIO_MOVEL:
        # Celular na grafia antiga: acrescenta o nono dígito para convergir com
        # quem já chegou com ele. O bruto guarda o que veio.
        return Analise(
            f"+{DDI_BR}{ddd}9{assinante}", MOVEL, nono_digito_acrescentado=True
        )

    if assinante[0] in _INICIO_FIXO:
        return Analise(f"+{DDI_BR}{ddd}{assinante}", FIXO)

    return Analise(None, INVALIDO, f"assinante começa em {assinante[0]}")


def normalizar(bruto) -> str | None:
    """O E.164 canônico, ou None. Atalho de `analisar` para quem não quer o motivo."""
    return analisar(bruto).e164


def de_partes(ddi=None, ddd=None, numero=None) -> Analise:
    """Para a forma que o Harmonit devolve: ddi, ddd e phone em campos separados.

    ⚠️ O Harmonit às vezes manda o DDD grudado no número e o campo `ddd` vazio.
    Por isso o número é medido antes de concatenar.
    """
    d_numero = _SO_DIGITOS.sub("", str(numero or ""))
    if not d_numero:
        return Analise(None, INVALIDO, "vazio")

    d_ddd = _SO_DIGITOS.sub("", str(ddd or ""))
    d_ddi = _SO_DIGITOS.sub("", str(ddi or "")) or DDI_BR

    if not d_ddd and len(d_numero) in (10, 11):
        return analisar("+" + d_ddi + d_numero)
    return analisar("+" + d_ddi + d_ddd + d_numero)


def e_movel(e164: str | None) -> bool:
    return analisar(e164).tipo == MOVEL


def variantes(e164: str | None) -> set[str]:
    """As duas grafias do mesmo celular, para consultar base de TERCEIRO.

    Dentro do MoviZap isso não é necessário: aqui tudo converge para a forma
    com o nono dígito. Mas Harmonit e WESO não dão essa garantia -- lá o mesmo
    celular pode estar gravado das duas formas, inclusive no mesmo dia. Ao
    perguntar para fora, pergunta-se pelas duas.

    Para fixo e internacional devolve só a própria forma: não há segunda.
    """
    analise = analisar(e164)
    if not analise:
        return set()
    if analise.tipo != MOVEL:
        return {analise.e164}

    completo = analise.e164
    corpo = completo[len("+" + DDI_BR):]  # DDD + assinante
    ddd, assinante = corpo[:2], corpo[2:]
    return {completo, f"+{DDI_BR}{ddd}{assinante[1:]}"}
