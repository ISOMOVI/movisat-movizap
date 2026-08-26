"""`movizap.llm` — o motor da IA, o passo 8.

🚨 ESTE PACOTE É O ÚNICO LUGAR DO MOVIZAP QUE SABE QUE EXISTE UMA CHAVE DE
MODELO. Nenhum outro módulo lê `settings.deepseek_api_key`.
`docs/04_Contrato_IA.md`: *"chave lida do `.env` por um único gateway"*.

Uso:
    from .llm import obter, Params
    resposta = obter().conversar(mensagens, ferramentas, executar)
"""
from .gateway import MAX_RODADAS, Gateway, obter, reiniciar
from .params import Params
from .provedores import PROVEDORES, SemChave

__all__ = ["Gateway", "Params", "PROVEDORES", "SemChave", "MAX_RODADAS",
           "obter", "reiniciar"]
