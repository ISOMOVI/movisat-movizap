"""Parâmetros canônicos do modelo — o meio-termo entre os provedores.

Herdado do `services/llm/params.py` do MoviChat, com os valores que lá foram
medidos, não escolhidos:

  🚨 `max_tokens = 900` NÃO É EXAGERO. Era 512 e cortava resposta no meio,
  achado no teste de regressão de 15/07 do MoviChat. Teto alto não gasta
  token à toa: o modelo para sozinho quando termina.

  ⚠️ `temperature` baixa porque atendimento pede resposta factual. Criativa
  aqui é a que inventa prazo -- o item 1 do "o que ela nunca faz"
  (`docs/04_Contrato_IA.md`).
"""
from dataclasses import dataclass, field


@dataclass
class Params:
    temperature: float = 0.3
    max_tokens: int = 900
    top_p: float = 0.9
    # Parâmetros que só um dos provedores entende. O adaptador filtra.
    extras: dict = field(default_factory=dict)
