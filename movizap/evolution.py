"""Cliente do Evolution API — o único módulo que fala com o WhatsApp.

Evolution 2.3.7, em `http://localhost:8081` dentro do host.

🚨 A chave sai do `.env` e NUNCA é impressa. O `silenciar_clientes_http()`
do config já cala httpx/httpcore em DEBUG — foi assim que a chave da WESO
apareceu num log em julho.

O que este módulo NÃO faz de propósito: enviar mensagem. Fase 1 é receber.
Quando o envio entrar, entra aqui, com ritmo e teto — nunca em rajada.
"""
import logging

import httpx

from .config import settings

log = logging.getLogger("movizap.evolution")

TIMEOUT = httpx.Timeout(20.0, connect=5.0)

# Aplicadas no pareamento, decididas no escopo da Fase 1.
SETTINGS_PADRAO = {
    "groupsIgnore": True,      # grupo é Fase 3, e a IA nunca responde em grupo
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
