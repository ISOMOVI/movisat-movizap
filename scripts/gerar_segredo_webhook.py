"""Gera o segredo do webhook e grava no .env, sem imprimir o valor.

🚨 O endpoint do webhook fica PUBLICO -- o Evolution roda em container e nao
alcanca o 127.0.0.1 do host, entao a chamada entra pelo nginx. O que o protege
e este segredo no caminho da URL. Por isso ele nasce com 43 caracteres e nunca
e impresso: quem precisa dele e o Evolution, e a configuracao dele e feita por
script que le do mesmo .env.

Idempotente: se ja existir, nao troca -- trocar quebraria o webhook ja
configurado no Evolution.
"""
import os
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ENV = Path("/home/claude/movizap_painel/.env")
CHAVE = "MOVIZAP_WEBHOOK_SEGREDO"

texto = ENV.read_text(encoding="utf-8")
if f"{CHAVE}=" in texto:
    print(f"{CHAVE} ja existe -- nao vou trocar, isso quebraria o webhook "
          f"ja configurado no Evolution")
    raise SystemExit(0)

segredo = secrets.token_urlsafe(32)
with open(ENV, "a", encoding="utf-8") as f:
    f.write(f"\n# ---- webhook (passo 4, 2026-08-06) ----\n")
    f.write(f"{CHAVE}={segredo}\n")
os.chmod(ENV, 0o600)

print(f"{CHAVE}: gerado, {len(segredo)} caracteres")
print(f".env com modo {oct(ENV.stat().st_mode)[-3:]}")
print("nenhum valor foi impresso")
