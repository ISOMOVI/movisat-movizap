"""Foto de perfil do WhatsApp, por telefone — 🟢 pedido da Erika (15/09).

🚨 O ARQUIVO FICA EM DISCO, A URL NÃO SERVE. Medido em 15/09 no payload real:
a URL do WhatsApp traz `oe=` (hora de expirar). Guardar o link daria uma foto
que funciona hoje e vira quadrado quebrado depois, sem nada no log dizendo por
quê. É a mesma decisão que já vale para a mídia das mensagens.

🚨 POR TELEFONE, NÃO POR CONTATO. 61% das conversas não têm cadastro nenhum
(medido em 28/08): pendurar no `contato` deixaria a maioria sem foto.

⚠️ NUNCA NO CAMINHO DA MENSAGEM. Buscar foto é chamada de rede ao Evolution;
fazê-la ao gravar mensagem colocaria a rede no meio da fila do webhook, que é
o lugar onde este projeto mais paga caro por lentidão. Ela roda quando a TELA
pede, e no máximo uma vez por dia por número.
"""
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from . import banco, evolution

log = logging.getLogger("movizap.foto")

RAIZ = Path("/home/claude/movizap_midia/perfil")

# Uma consulta por número por dia. Quem troca de foto não troca de hora em
# hora, e cada consulta é uma ida à rede.
VALIDADE = timedelta(days=1)

# Foto de perfil é pequena (dezenas de KB). Teto baixo de propósito: se vier
# coisa grande, é outra coisa, e não é para entrar no disco.
TETO_BYTES = 2 * 1024 * 1024


def _caminho(e164: str) -> Path:
    """Nome pelo hash do telefone: o número não vira nome de arquivo no disco.

    ⚠️ O caminho nunca é montado com o que veio do cliente -- é sempre o hash,
    que é hexadecimal por construção.
    """
    digest = hashlib.sha256(e164.encode()).hexdigest()[:32]
    return RAIZ / f"{digest}.jpg"


def _linha(e164: str) -> dict | None:
    return banco.um("SELECT * FROM foto_perfil WHERE e164 = %s", (e164,))


def _esta_fresca(linha: dict) -> bool:
    return (datetime.now(timezone.utc) - linha["buscada_em"]) < VALIDADE


def arquivo_de(e164: str) -> Path | None:
    """O arquivo já guardado, se existir. Não vai à rede."""
    linha = _linha(e164)
    if not linha or not linha["arquivo"]:
        return None
    caminho = Path(linha["arquivo"])
    return caminho if caminho.is_file() else None


def garantir(e164: str, instancia: str) -> Path | None:
    """Devolve o arquivo da foto, buscando no Evolution se estiver velha.

    ⚠️ Falha de rede NÃO apaga a foto que já existe: devolve a antiga. Uma
    foto de ontem é melhor que um espaço vazio porque o Evolution piscou.
    """
    linha = _linha(e164)
    if linha and _esta_fresca(linha):
        if linha["sem_foto"]:
            return None
        caminho = Path(linha["arquivo"]) if linha["arquivo"] else None
        if caminho and caminho.is_file():
            return caminho

    try:
        url = evolution.url_da_foto(instancia, e164)
    except evolution.ErroEvolution as e:
        log.warning("foto de %s: Evolution recusou (%s)", e164, e)
        return arquivo_de(e164)          # o que já houver serve

    if not url:
        banco.executar(
            """INSERT INTO foto_perfil (e164, arquivo, sem_foto, buscada_em)
               VALUES (%s, NULL, true, now())
               ON CONFLICT (e164) DO UPDATE
                  SET sem_foto = true, buscada_em = now()""", (e164,))
        return None

    try:
        with httpx.Client(timeout=15, follow_redirects=True) as c:
            r = c.get(url)
            r.raise_for_status()
            dados = r.content
    except httpx.HTTPError as e:
        log.warning("foto de %s: não baixou (%s)", e164, e.__class__.__name__)
        return arquivo_de(e164)

    if len(dados) > TETO_BYTES:
        log.warning("foto de %s: %d bytes, acima do teto -- descartada",
                    e164, len(dados))
        return arquivo_de(e164)

    RAIZ.mkdir(parents=True, exist_ok=True)
    caminho = _caminho(e164)
    caminho.write_bytes(dados)
    banco.executar(
        """INSERT INTO foto_perfil (e164, arquivo, sem_foto, buscada_em)
           VALUES (%s, %s, false, now())
           ON CONFLICT (e164) DO UPDATE
              SET arquivo = EXCLUDED.arquivo, sem_foto = false,
                  buscada_em = now()""",
        (e164, str(caminho)))
    log.info("foto de perfil guardada: %s (%d bytes)", e164, len(dados))
    return caminho
