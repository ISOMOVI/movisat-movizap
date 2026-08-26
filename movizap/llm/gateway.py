"""O caminho único até o modelo. Nenhum outro módulo do MoviZap sabe da chave.

🚨 ISTO É GENÉRICO DE PROPÓSITO. Aqui não há nada de atendimento, de contato
nem de conversa: o catálogo de ferramentas e a execução delas entram por
parâmetro, e vivem em `movizap/ia.py`. É o que permite exercitar o laço
inteiro num teste sem banco e sem rede.

O laço de ferramentas é herdado do MoviChat, com as três lições que custaram
caro lá:

  🚨 **A ÚLTIMA RODADA VAI SEM `tools`.** Não é economia: com o catálogo
  ainda oferecido no fim, o modelo tenta emitir sintaxe de chamada mesmo
  sem poder, e os tokens especiais vazam como TEXTO PURO na resposta que o
  cliente lê. Defeito real, medido em 15/07.

  🚨 **A CONDUTA DIANTE DA FALHA É NOSSA, NÃO DO MODELO.** Quando a
  ferramenta falha, o resultado que volta para ele carrega junto COMO
  responder. Sem isso o modelo improvisa e conta ao cliente que "houve um
  erro no sistema" -- que é o item 5 do "o que ela nunca faz".

  🚨 **TETO DE RODADAS.** Refinar uma busca é legítimo; refinar para sempre
  é conta de token sem fundo.
"""
import json
import logging

from ..config import settings
from .params import Params
from .provedores import PROVEDORES, Provedor, SemChave

log = logging.getLogger("movizap.llm")

# Uma rodada para chamar a ferramenta, uma para eventualmente refinar, uma
# para responder. Passou disso, a pergunta não era para a IA.
MAX_RODADAS = 3


class Gateway:
    """Um provedor principal, um reserva. `estrategia` decide se o reserva entra."""

    def __init__(self, principal: str | None = None, estrategia: str | None = None):
        nome = (principal or settings.llm_provider or "deepseek").lower()
        if nome not in PROVEDORES:
            log.warning("provedor %r desconhecido, usando deepseek", nome)
            nome = "deepseek"
        self.principal: Provedor = PROVEDORES[nome]()
        reserva = next((p for p in ("deepseek", "groq") if p != nome), nome)
        self.reserva: Provedor = PROVEDORES[reserva]()
        self.estrategia = (estrategia or settings.llm_strategy or "single").lower()

    # ── o que a tela precisa saber, sem saber a chave ─────────────────────
    @property
    def disponivel(self) -> bool:
        if self.principal.configurado:
            return True
        return self.estrategia == "fallback" and self.reserva.configurado

    def estado(self) -> dict:
        from ..config import mascarar
        return {
            "disponivel": self.disponivel,
            "provedor": self.principal.nome,
            "modelo": self.principal.modelo,
            "estrategia": self.estrategia,
            # 🚨 `mascarar`, nunca o valor. A tela mostra `sk-...a3f9`.
            "chave": mascarar(self.principal.chave),
        }

    # ── uma completagem simples, sem ferramenta ───────────────────────────
    def _tentar(self, mensagens, params, ferramentas, escolha) -> dict:
        candidatos = [self.principal]
        if self.estrategia == "fallback":
            candidatos.append(self.reserva)
        ultimo: Exception | None = None
        for p in candidatos:
            if not p.configurado:
                log.info("provedor %s sem chave, pulando", p.nome)
                continue
            try:
                return p.completar(mensagens, params, ferramentas, escolha)
            except Exception as e:                            # noqa: BLE001
                ultimo = e
                log.warning("provedor %s falhou: %s", p.nome, e.__class__.__name__)
        if ultimo is None:
            raise SemChave("nenhum provedor de IA tem chave no .env")
        raise RuntimeError("todos os provedores de IA falharam") from ultimo

    # ── o laço com ferramentas ────────────────────────────────────────────
    def conversar(self, mensagens: list[dict], ferramentas: list,
                  executar, params: Params | None = None) -> dict:
        """`executar(nome, argumentos) -> dict` é quem sabe o que a ferramenta faz.

        Devolve `{texto, tokens, provedor, ferramentas_usadas, encerrou}`.

        ⚠️ `executar` pode devolver `{"__final__": "texto"}`: é a ferramenta
        que JÁ É a resposta (transferir, encerrar). Sem esse atalho o modelo
        receberia o resultado e escreveria mais uma frase por cima -- e
        "vou transferir você" é justamente o que o handoff proíbe.
        """
        params = params or Params()
        mensagens = list(mensagens)
        tokens = 0
        usadas: list[str] = []

        for rodada in range(MAX_RODADAS):
            ultima = rodada == MAX_RODADAS - 1
            r = self._tentar(mensagens, params,
                             None if ultima else ferramentas,
                             None if ultima else "auto")
            tokens += r["tokens"]
            if r.get("cache_hit") is not None:
                log.info("rodada %s: cache_hit=%s tokens=%s",
                         rodada, r["cache_hit"], r["tokens"])
            msg = r["mensagem"] or {}
            chamadas = msg.get("tool_calls") or []

            if not chamadas:
                return {"texto": (msg.get("content") or "").strip(),
                        "tokens": tokens, "provedor": r["provedor"],
                        "ferramentas_usadas": usadas, "encerrou": False}

            # Uma por rodada. Mais de uma chamada simultânea é o modelo
            # adivinhando; a segunda vem na rodada seguinte, já sabendo o
            # resultado da primeira.
            chamada = chamadas[0]
            funcao = (chamada.get("function") or {})
            nome = funcao.get("name") or ""
            try:
                argumentos = json.loads(funcao.get("arguments") or "{}")
            except json.JSONDecodeError:
                argumentos = {}
            if not isinstance(argumentos, dict):
                argumentos = {}

            log.info("rodada %s: ferramenta %r args=%s", rodada, nome,
                     sorted(argumentos))
            usadas.append(nome)

            try:
                resultado = executar(nome, argumentos)
            except Exception as e:                            # noqa: BLE001
                log.exception("ferramenta %r estourou", nome)
                resultado = {"erro": e.__class__.__name__}

            if isinstance(resultado, dict) and "__final__" in resultado:
                return {"texto": (resultado["__final__"] or "").strip(),
                        "tokens": tokens, "provedor": r["provedor"],
                        "ferramentas_usadas": usadas,
                        "encerrou": bool(resultado.get("encerrou"))}

            if resultado is None or (isinstance(resultado, dict) and "erro" in resultado):
                # 🚨 A instrução vai JUNTO com a falha. Sem ela o modelo conta
                # ao cliente que o sistema deu erro -- expor o mecanismo é o
                # item 5 do contrato.
                resultado = {
                    "indisponivel": True,
                    "como_responder": (
                        "Não foi possível levantar esse dado. NÃO mencione erro, "
                        "sistema, falha, consulta nem detalhe técnico. Transfira "
                        "para um atendente humano usando a ferramenta transferir."),
                }

            mensagens.append({
                "role": "assistant",
                "content": msg.get("content"),
                "tool_calls": [{
                    "id": chamada.get("id"),
                    "type": "function",
                    "function": {"name": nome,
                                 "arguments": funcao.get("arguments") or "{}"},
                }],
            })
            mensagens.append({
                "role": "tool",
                "tool_call_id": chamada.get("id"),
                "content": json.dumps(resultado, ensure_ascii=False, default=str),
            })

        # Rede de segurança: a última rodada vai sem ferramenta, então não
        # deveria chegar aqui. Se a API mudar, chega -- e é melhor devolver
        # vazio (que o chamador trata como "transfere") do que texto inventado.
        log.warning("laço de ferramentas terminou sem resposta (%s)", usadas)
        return {"texto": "", "tokens": tokens, "provedor": self.principal.nome,
                "ferramentas_usadas": usadas, "encerrou": False}


_gateway: Gateway | None = None


def obter() -> Gateway:
    global _gateway
    if _gateway is None:
        _gateway = Gateway()
    return _gateway


def reiniciar() -> None:
    """Usado pelo teste e por quem trocar a chave sem derrubar o serviço."""
    global _gateway
    _gateway = None
