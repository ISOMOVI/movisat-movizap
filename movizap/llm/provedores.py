"""Os adaptadores de modelo — DeepSeek e Groq, pelo REST compatível com OpenAI.

🚨 HERDADO DO MOVICHAT, MAS FALANDO POR `httpx` SÍNCRONO, NÃO PELO SDK
`openai`. O que se herda são as DECISÕES (o modelo, o `thinking` desligado, o
teto de tempo, o retry, o fallback), não a biblioteca:

  - o caminho que chama a IA no MoviZap é síncrono de ponta a ponta
    (`conversas.processar_pendentes` é `def`, e roda em `asyncio.to_thread`
    justamente porque `async def` ali NÃO EXECUTA NADA);
  - a API da DeepSeek é REST compatível com OpenAI -- é UM POST;
  - `httpx` já é dependência de todo módulo que fala para fora daqui
    (`harmonit`, `evolution`, `gmail`).

Trazer o SDK arrastaria uma cadeia de dependência e um mundo `async` para
dentro de um laço que é `def`. Ver `docs/04_Contrato_IA.md`.

🚨 A CHAVE NUNCA É IMPRESSA, e o `silenciar_clientes_http()` do `config` é o
que impede o `httpx` de despejar o header `Authorization` em DEBUG. Foi assim
que a chave da WESO vazou para um log em julho/2026.
"""
import logging

import httpx

from ..config import settings
from .params import Params

log = logging.getLogger("movizap.llm")

# 🚨 O SDK da OpenAI vem com read=600s e 2 retries -- até meia hora de trabalho
# atrás de um nginx que corta antes. O teto fica ABAIXO do da borda, com 1
# retry: uma rodada de ferramenta cabe folgada (medido no MoviChat: 2 a 6 s).
TEMPO_LIMITE_S = 45.0
TENTATIVAS = 2  # a original + 1


class SemChave(RuntimeError):
    """O provedor não tem chave no `.env`. Não é falha de rede."""


class Provedor:
    """Um modelo, atrás de um POST. Só o que os dois provedores têm em comum."""

    nome = ""
    modelo = ""
    base_url = ""
    # O que este provedor NÃO aceita e devolveria 4xx se fosse junto.
    nao_aceita: frozenset = frozenset()

    @property
    def chave(self) -> str:
        raise NotImplementedError

    @property
    def configurado(self) -> bool:
        return bool(self.chave)

    def corpo_extra(self) -> dict:
        return {}

    def completar(self, mensagens: list[dict], params: Params,
                  ferramentas: list | None = None,
                  escolha: str | None = None) -> dict:
        """Uma rodada. Devolve o dicionário `message` do modelo + os tokens.

        ⚠️ Devolve a mensagem CRUA de propósito: quem chama precisa ver
        `tool_calls`, e achatar para texto aqui tornaria o laço de ferramentas
        impossível de escrever sem duplicar o parser.
        """
        if not self.configurado:
            raise SemChave(f"provedor {self.nome} sem chave no .env")

        corpo = {
            "model": self.modelo,
            "messages": mensagens,
            "max_tokens": params.max_tokens,
            "temperature": params.temperature,
            "top_p": params.top_p,
            "stream": False,
        }
        corpo.update(self.corpo_extra())
        for k, v in (params.extras or {}).items():
            if k not in self.nao_aceita:
                corpo[k] = v
        if ferramentas:
            corpo["tools"] = ferramentas
            corpo["tool_choice"] = escolha or "auto"

        ultimo: Exception | None = None
        for tentativa in range(TENTATIVAS):
            try:
                with httpx.Client(timeout=TEMPO_LIMITE_S) as c:
                    r = c.post(
                        f"{self.base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self.chave}",
                                 "Content-Type": "application/json"},
                        json=corpo)
                r.raise_for_status()
                dados = r.json()
                break
            except Exception as e:                            # noqa: BLE001
                ultimo = e
                # ⚠️ O `repr` da exceção, NUNCA a resposta crua nem o corpo: a
                # requisição carrega a chave no header e o corpo carrega a
                # conversa do cliente.
                log.warning("%s falhou (tentativa %s/%s): %s", self.nome,
                            tentativa + 1, TENTATIVAS, e.__class__.__name__)
        else:
            raise RuntimeError(f"{self.nome} não respondeu") from ultimo

        escolhas = dados.get("choices") or []
        if not escolhas:
            raise ValueError(f"{self.nome} devolveu choices vazio")
        uso = dados.get("usage") or {}
        return {
            "mensagem": escolhas[0].get("message") or {},
            "tokens": int(uso.get("total_tokens") or 0),
            "cache_hit": uso.get("prompt_cache_hit_tokens"),
            "provedor": self.nome,
        }


class DeepSeek(Provedor):
    # 🚨 "deepseek-chat" e "deepseek-reasoner" FORAM DESATIVADOS pela DeepSeek
    # em 2026-07-24. O MoviChat migrou para "deepseek-v4-flash" com o modo de
    # pensar desligado, que reproduz o comportamento do antigo. NÃO VOLTAR
    # para o nome antigo por parecer "mais estável": ele não existe mais.
    nome = "deepseek"
    modelo = "deepseek-v4-flash"
    base_url = "https://api.deepseek.com"

    @property
    def chave(self) -> str:
        return settings.deepseek_api_key

    def corpo_extra(self) -> dict:
        return {"thinking": {"type": "disabled"}}


class Groq(Provedor):
    nome = "groq"
    modelo = "openai/gpt-oss-20b"
    base_url = "https://api.groq.com/openai/v1"
    nao_aceita = frozenset({"presence_penalty", "frequency_penalty", "logit_bias"})

    @property
    def chave(self) -> str:
        return settings.groq_api_key


PROVEDORES: dict[str, type[Provedor]] = {"deepseek": DeepSeek, "groq": Groq}
