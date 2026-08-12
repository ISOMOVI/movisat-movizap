"""Cliente do Evolution API — o único módulo que fala com o WhatsApp.

Evolution 2.3.7, em `http://localhost:8081` dentro do host.

🚨 A chave sai do `.env` e NUNCA é impressa. O `silenciar_clientes_http()`
do config já cala httpx/httpcore em DEBUG — foi assim que a chave da WESO
apareceu num log em julho.

✅ 07/08: O ENVIO ENTROU, por decisão do usuário, e entrou como estava
previsto — aqui, e só para responder conversa que existe.

🚨 NÃO EXISTE ENVIO PARA DESTINATÁRIO ARBITRÁRIO, e isso é a trava que impede
o painel de virar ferramenta de disparo. `enviar_texto` recebe o número, mas
quem o chama é `conversas.responder`, que o lê da CONVERSA — nunca de algo
digitado. Disparo em massa continua sendo Fase 2, com decisão própria.
"""
import logging

import httpx

from .config import settings

log = logging.getLogger("movizap.evolution")

TIMEOUT = httpx.Timeout(20.0, connect=5.0)

# Aplicadas no pareamento, decididas no escopo da Fase 1.
SETTINGS_PADRAO = {
    # 🚨 CONTINUA `True` COMO PADRÃO DE PAREAMENTO, e é decisão: instância nova
    # não deve começar recebendo todo grupo de que o número participa. Quem
    # atende grupo é a `atendimento`, e lá o valor foi desligado
    # explicitamente em 12/08 (ver `scripts/ligar_grupo.py`). A `informativos`
    # é disparo e nunca deve receber grupo.
    "groupsIgnore": True,
    "syncFullHistory": False,  # o histórico que importa vem da ficha, não do balão
    "readMessages": False,     # não marcar lido por nós: quem lê é o atendente
    "alwaysOnline": False,
    "readStatus": False,
    "rejectCall": False,
}


class ErroEvolution(Exception):
    """Falha ao falar com o Evolution. Carrega o status para a rota decidir."""

    def __init__(self, mensagem: str, status: int = 0):
        super().__init__(mensagem)
        self.status = status


def _cliente() -> httpx.Client:
    if not settings.evolution_api_key:
        raise ErroEvolution("EVOLUTION_API_KEY ausente no .env")
    return httpx.Client(
        base_url=settings.evolution_base_url,
        headers={"apikey": settings.evolution_api_key},
        timeout=TIMEOUT,
    )


def _pedir(metodo: str, caminho: str, corpo: dict | None = None) -> dict:
    try:
        with _cliente() as c:
            r = c.request(metodo, caminho, json=corpo)
    except httpx.RequestError as e:
        # 🚨 Nunca colocar `e` inteiro na mensagem: a URL do httpx pode
        # carregar credencial em query em outros provedores, e o hábito é o
        # que protege.
        raise ErroEvolution(
            f"Evolution não respondeu ({e.__class__.__name__}).", 0) from None

    if r.status_code >= 400:
        detalhe = ""
        try:
            corpo_erro = r.json()
            detalhe = str(corpo_erro.get("message") or corpo_erro.get("error") or "")[:200]
        except ValueError:
            detalhe = r.text[:200]
        log.warning("evolution %s %s -> %s", metodo, caminho, r.status_code)
        raise ErroEvolution(detalhe or f"Evolution respondeu {r.status_code}.",
                            r.status_code)

    try:
        return r.json()
    except ValueError:
        return {}


def enviar_texto(instancia: str, numero_e164: str, texto: str) -> dict:
    """Manda uma mensagem de texto e devolve a chave que o WhatsApp deu a ela.

    🚨 O `key.id` DA RESPOSTA É O QUE EVITA A MENSAGEM DUPLICADA. O Evolution
    devolve pelo webhook a nossa própria mensagem, com `fromMe: true` e o mesmo
    id. Se ela não for gravada AGORA com esse id, o eco chega depois e vira uma
    segunda mensagem igual na tela do atendente. Com o id gravado, o
    `ux_mensagem_id_externo` transforma o eco em conflito ignorado.

    ⚠️ O número vai sem o `+`: o Evolution quer só dígitos.
    """
    numero = destino_para_evolution(numero_e164)
    if not numero:
        raise ErroEvolution("Sem número para enviar.", 0)
    if not (texto or "").strip():
        raise ErroEvolution("Mensagem vazia.", 0)

    resposta = _pedir("POST", f"/message/sendText/{instancia}",
                      {"number": numero, "text": texto})

    chave = (resposta or {}).get("key") or {}
    log.info("enviado por %s (id=%s)", instancia, chave.get("id"))
    return {
        "id_externo": chave.get("id"),
        "status": (resposta or {}).get("status"),
        "bruto": resposta,
    }


def nome_do_grupo(instancia: str, jid: str) -> str | None:
    """O nome (subject) de um grupo, perguntado ao Evolution.

    🚨 `pushName` NÃO É O NOME DO GRUPO. Num evento de grupo ele é o perfil de
    QUEM MANDOU -- e para mensagem nossa (`fromMe`) é o nome do nosso próprio
    perfil de negócio. Em 12/08 eu gravei "Movisat Rastreamento e Gestão de
    Frotas" como nome de um grupo que se chama "Suporte Movisat -> Weso".
    Descoberto lendo o estado depois de ligar, não pelo teste: o payload não
    tem o nome do grupo em lugar nenhum.

    ⚠️ Falha em silêncio de propósito: nome de grupo é enfeite comparado a
    receber a mensagem. Sem o nome, a tela mostra o JID e a conversa funciona.
    """
    # ⚠️ A INSTÂNCIA VAI NO CAMINHO, o JID vai na query. Sem a instância o
    # Evolution devolve 404 — testado em 12/08 contra o servidor real, porque
    # a documentação do 2.3.7 mostra a forma curta.
    try:
        dados = _pedir("GET", f"/group/findGroupInfos/{instancia}?groupJid={jid}")
    except ErroEvolution as e:
        log.info("nome do grupo %s não veio: %s", jid, e)
        return None
    if isinstance(dados, list):
        dados = dados[0] if dados else {}
    nome = (dados or {}).get("subject")
    return nome or None


def destino_para_evolution(destino: str) -> str:
    """O que vai no campo `number` do Evolution.

    🚨 GRUPO VAI COM O JID INTEIRO; TELEFONE VAI SÓ COM DÍGITOS. Tirar o que
    não é dígito de um `1203...@g.us` deixaria só o número do grupo, sem o
    `@g.us` — e o Evolution trataria como telefone, mandando a resposta do
    grupo para um número que não existe. Falha silenciosa: a API aceita e a
    mensagem some.
    """
    destino = (destino or "").strip()
    if destino.endswith("@g.us"):
        return destino
    return "".join(c for c in destino if c.isdigit())


FAMILIA_PARA_EVOLUTION = {
    "image": "image",
    "video": "video",
    "audio": "audio",
}


def tipo_de_midia(mime: str) -> str:
    """O `mediatype` que o Evolution espera, a partir do MIME do arquivo.

    ⚠️ Vocabulário FECHADO do lado deles: `image`, `video`, `audio` ou
    `document`. Mandar `mediatype` que não existe não dá erro claro -- dá
    mensagem que não chega.
    """
    familia = (mime or "").split("/")[0].strip().lower()
    return FAMILIA_PARA_EVOLUTION.get(familia, "document")


def enviar_midia(instancia: str, numero_e164: str, base64_dados: str,
                 mime: str, nome_arquivo: str, legenda: str = "") -> dict:
    """Manda um arquivo e devolve a chave que o WhatsApp deu à mensagem.

    🚨 MESMA REGRA DO TEXTO: o `key.id` da resposta é o que evita a mensagem
    duplicada. O Evolution ecoa a nossa própria mensagem pelo webhook com
    `fromMe: true` e o mesmo id; sem gravar o id agora, o eco vira um segundo
    balão igual na tela.

    ⚠️ O número vai sem o `+`: o Evolution quer só dígitos.

    ⚠️ `fileName` importa para documento -- é o nome que o cliente vê e usa
    para abrir. Sem ele o WhatsApp mostra um nome genérico e o PDF chega
    parecendo lixo.
    """
    numero = destino_para_evolution(numero_e164)
    if not numero:
        raise ErroEvolution("Sem número para enviar.", 0)
    if not base64_dados:
        raise ErroEvolution("Arquivo vazio.", 0)

    corpo = {
        "number": numero,
        "mediatype": tipo_de_midia(mime),
        "mimetype": mime,
        "media": base64_dados,
        "fileName": nome_arquivo or "arquivo",
    }
    if legenda:
        corpo["caption"] = legenda

    resposta = _pedir("POST", f"/message/sendMedia/{instancia}", corpo)
    chave = (resposta or {}).get("key") or {}
    log.info("arquivo enviado por %s (id=%s, tipo=%s, %s)",
             instancia, chave.get("id"), corpo["mediatype"], nome_arquivo)
    return {
        "id_externo": chave.get("id"),
        "status": (resposta or {}).get("status"),
        "bruto": resposta,
    }


# --------------------------------------------------------------- consulta

def instancias() -> list[dict]:
    """Todas as instâncias que o Evolution conhece."""
    dados = _pedir("GET", "/instance/fetchInstances")
    if isinstance(dados, list):
        return [i.get("instance", i) if isinstance(i, dict) else {} for i in dados]
    return []


def estado(instancia: str) -> str:
    """`open` (conectado) · `connecting` · `close`.

    🚨 Instância que não existe faz o Evolution responder 404. Isso NÃO é
    "desconectado": é configuração errada, e tratar como desconectado
    esconderia o problema atrás de um botão de reconectar que nunca funciona.
    """
    dados = _pedir("GET", f"/instance/connectionState/{instancia}")
    return ((dados.get("instance") or {}).get("state")
            or dados.get("state") or "desconhecido")


def numero(instancia: str) -> str | None:
    """O número pareado, quando há. `None` enquanto não parear."""
    for i in instancias():
        if (i.get("instanceName") or i.get("name")) == instancia:
            bruto = i.get("owner") or i.get("number") or ""
            return bruto.split("@")[0] or None
    return None


# --------------------------------------------------------------- pareamento

def conectar(instancia: str) -> dict:
    """Pede o QR. Devolve `{base64, code, pairingCode}` conforme a versão.

    ⚠️ O QR do Baileys expira em ~60 s. Quem chama de novo recebe um QR novo
    — é assim que a tela renova sem pedir F5.
    """
    dados = _pedir("GET", f"/instance/connect/{instancia}")
    return {
        "base64": dados.get("base64") or dados.get("qrcode", {}).get("base64"),
        "codigo": dados.get("code") or dados.get("qrcode", {}).get("code"),
        "pareamento": dados.get("pairingCode"),
    }


def desconectar(instancia: str) -> None:
    """Desfaz o pareamento. O número precisa ler o QR de novo para voltar."""
    _pedir("DELETE", f"/instance/logout/{instancia}")


def reiniciar(instancia: str) -> None:
    _pedir("PUT", f"/instance/restart/{instancia}")


def aplicar_settings(instancia: str, valores: dict | None = None) -> dict:
    """Aplica as settings da Fase 1.

    🚨 Roda no pareamento, não no arranque: settings aplicadas antes de a
    instância conectar não pegam, e o silêncio faz parecer que pegaram.
    """
    corpo = dict(SETTINGS_PADRAO)
    if valores:
        corpo.update({k: v for k, v in valores.items() if k in SETTINGS_PADRAO})
    _pedir("POST", f"/settings/set/{instancia}", corpo)
    return corpo


def settings_atuais(instancia: str) -> dict:
    dados = _pedir("GET", f"/settings/find/{instancia}")
    return {k: dados.get(k) for k in SETTINGS_PADRAO} if dados else {}
