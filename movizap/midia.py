"""Mídia da conversa: foto, áudio, vídeo e documento que o cliente manda.

🚨 A MÍDIA JÁ CHEGA NO WEBHOOK. Medido em 10/08 nos eventos guardados: o
Evolution manda o binário em `data.message.base64`, nos 57 casos sem exceção.
Não há download da Meta, não há URL que expira, não há chave de descriptografia
para administrar. O que faltava era mover o dado do log de eventos para um
lugar onde a tela consiga mostrá-lo.

ONDE MORA, E POR QUE FORA DO PROJETO
------------------------------------
Decisão do usuário em 10/08: *"pode ficar salvas na VPS, mas fora do backup do
projeto"*. Por isso a raiz é `/home/claude/movizap_midia/`, e não uma pasta
dentro de `movizap_painel/`.

🚨 O `backup_projetos.sh` empacota o DIRETÓRIO `movizap_painel`. Mídia guardada
lá dentro entraria no pacote diário e o faria crescer sem teto -- 24,2 MB já
existem hoje, de 5 dias de conversa. Ficando fora, o backup segue do tamanho
do código, que é o que ele existe para proteger.

⚠️ A consequência tem que estar dita, não subentendida: **mídia não tem
backup**. Se o disco da VPS se perder, o texto da conversa volta e as fotos
não. É o que a decisão escolheu, e é aceitável porque o binário original
também continua no `webhook_evento.payload`, que está no banco.

COMO O ARQUIVO É NOMEADO
------------------------
`AAAA-MM/<sha256>.<ext>`. O hash é o nome de propósito:

  - a mesma foto reenviada não ocupa espaço duas vezes;
  - nome de arquivo do cliente nunca vira caminho no disco -- `../../etc` é um
    nome de arquivo válido no WhatsApp, e o nome original fica só na coluna
    `nome_original`, para aparecer na hora de baixar;
  - a pasta por mês evita diretório com dezenas de milhares de entradas.
"""
import base64
import binascii
import hashlib
import logging
import mimetypes
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("movizap.midia")

RAIZ = Path("/home/claude/movizap_midia")

# O que `data.message` pode trazer, e o tipo que o CHECK da tabela aceita.
TIPOS = {
    "imageMessage": "imagem",
    "audioMessage": "audio",
    "videoMessage": "video",
    "documentMessage": "documento",
    "documentWithCaptionMessage": "documento",
    "stickerMessage": "figurinha",
}

# 🚨 Teto por arquivo. O WhatsApp já limita, mas o limite é DELE, não nosso:
# sem teto próprio um payload gigante viraria disco cheio e o painel inteiro
# cai junto. 32 MB dá folga sobre o maior arquivo que o WhatsApp entrega.
TETO_BYTES = 32 * 1024 * 1024

EXTENSAO_PADRAO = {
    "imagem": ".jpg",
    "audio": ".ogg",
    "video": ".mp4",
    "documento": ".bin",
    "figurinha": ".webp",
}


def _extensao(mime: str, tipo: str) -> str:
    if mime:
        achada = mimetypes.guess_extension(mime.split(";")[0].strip())
        if achada:
            return achada
    return EXTENSAO_PADRAO.get(tipo, ".bin")


def extrair(mensagem: dict) -> dict | None:
    """O que dá para guardar desta mensagem, ou None se não há mídia.

    Não escreve nada: separar o que é leitura do payload do que é escrita em
    disco é o que permite testar a interpretação sem sujar o sistema de
    arquivos.
    """
    if not isinstance(mensagem, dict):
        return None

    bruto = mensagem.get("base64")
    if not isinstance(bruto, str) or not bruto:
        return None

    chave = next((k for k in TIPOS if k in mensagem), None)
    if chave is None:
        return None

    corpo = mensagem.get(chave)
    corpo = corpo if isinstance(corpo, dict) else {}

    try:
        dados = base64.b64decode(bruto, validate=True)
    except (binascii.Error, ValueError) as e:
        # ⚠️ Base64 quebrado não pode derrubar a gravação da mensagem: o texto
        # e a conversa valem mesmo sem o anexo.
        log.warning("base64 inválido em mensagem de %s: %s", chave, e)
        return None

    if not dados or len(dados) > TETO_BYTES:
        log.warning("mídia de %d bytes fora do teto (%d)", len(dados), TETO_BYTES)
        return None

    return {
        "tipo": TIPOS[chave],
        "dados": dados,
        "mime": (corpo.get("mimetype") or "").split(";")[0].strip(),
        "nome_original": corpo.get("fileName") or None,
    }


def guardar(cur, conversa_id: int, achado: dict) -> int | None:
    """Grava o arquivo e devolve o id da linha em `midia`.

    Idempotente pelo hash: a mesma mídia reprocessada não duplica arquivo nem
    linha. Isso importa porque o reprocesso do que já chegou vai rodar mais de
    uma vez enquanto a tela é construída.
    """
    dados = achado["dados"]
    digest = hashlib.sha256(dados).hexdigest()

    cur.execute("SELECT id FROM midia WHERE hash = %s AND conversa_id = %s",
                (digest, conversa_id))
    ja = cur.fetchone()
    if ja:
        return ja["id"]

    pasta = RAIZ / datetime.now(timezone.utc).strftime("%Y-%m")
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"{digest}{_extensao(achado['mime'], achado['tipo'])}"

    if not caminho.exists():
        # Escreve em temporário e renomeia: arquivo pela metade nunca fica
        # visível com o nome definitivo, nem se o processo morrer no meio.
        temporario = caminho.with_suffix(caminho.suffix + ".parcial")
        temporario.write_bytes(dados)
        temporario.rename(caminho)

    cur.execute(
        """INSERT INTO midia (conversa_id, mime, tamanho, caminho,
                              nome_original, hash, baixada_em)
           VALUES (%s, %s, %s, %s, %s, %s, now())
           RETURNING id""",
        (conversa_id, achado["mime"] or None, len(dados), str(caminho),
         achado["nome_original"], digest))
    return cur.fetchone()["id"]


def arquivo(midia_id: int) -> dict | None:
    """A linha da mídia, já conferindo que o arquivo continua no disco.

    🚨 Devolver o caminho sem olhar o disco daria 500 na cara do atendente se
    alguém tivesse limpado a pasta. Aqui a ausência é um caso tratado.
    """
    from . import banco

    linha = banco.um(
        "SELECT id, conversa_id, mime, tamanho, caminho, nome_original "
        "FROM midia WHERE id = %s", (midia_id,))
    if not linha:
        return None
    if not Path(linha["caminho"]).is_file():
        log.warning("mídia %s some do disco: %s", midia_id, linha["caminho"])
        return None
    return linha


# Como chamar o arquivo quando o WhatsApp não manda nome. Foto e áudio nunca
# vêm com `fileName` -- só documento vem.
ROTULO = {"image": "foto", "audio": "audio", "video": "video"}


def nome_para_baixar(linha: dict) -> str:
    """O nome que o navegador vai sugerir ao salvar.

    ⚠️ O nome vem do cliente. Só o nome-base entra, sem diretório: `fileName`
    pode conter barra, e não é papel do navegador nos proteger disso.

    ⚠️ Sem `fileName` o nome do arquivo em disco é o SHA256 -- 64 caracteres de
    hexadecimal, que é ótimo como chave e péssimo na pasta de downloads de
    quem atende. Nesse caso o nome é montado: `foto-12.jpg`.
    """
    original = (linha.get("nome_original") or "").strip()
    if original:
        seguro = Path(original.replace("\\", "/")).name
        if seguro not in ("", ".", ".."):
            return seguro

    caminho = Path(linha["caminho"])
    familia = (linha.get("mime") or "").split("/")[0]
    return f"{ROTULO.get(familia, 'arquivo')}-{linha['id']}{caminho.suffix}"
