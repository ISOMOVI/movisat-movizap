# -*- coding: utf-8 -*-
"""Cria o segredo da ponte MoviZap -> FPSL nos dois .env, sem passar por shell.

🚨 O SEGREDO NUNCA APARECE: nem em argv, nem em variável de ambiente, nem na
saída. O script gera, grava nos dois arquivos e imprime só a conferência --
mesmo desenho do `scripts/aplicar_migracao.py`, que existe para a senha do
banco não passar por `PGPASSWORD=`.

Idempotente: se a chave já existe nos dois lados com o mesmo valor, não mexe.
"""
import secrets
from pathlib import Path

CHAVE = "PONTE_FPSL_SEGREDO"
ENVS = [
    Path("/home/claude/movizap_painel/.env"),
    Path("/home/claude/fpsl_weso/.env"),
]


def ler(env: Path) -> str | None:
    if not env.exists():
        return None
    for linha in env.read_text(encoding="utf-8").splitlines():
        if linha.strip().startswith(f"{CHAVE}="):
            return linha.partition("=")[2].strip()
    return None


atuais = {env: ler(env) for env in ENVS}
faltando = [env for env, v in atuais.items() if not v]
distintos = {v for v in atuais.values() if v}

if not faltando and len(distintos) == 1:
    print(f"{CHAVE} ja existe nos dois .env e bate -- nada a fazer")
    raise SystemExit(0)
if len(distintos) > 1:
    raise SystemExit(
        f"{CHAVE} existe nos dois .env com valores DIFERENTES. "
        "Nao escolho qual vale: decida e apague o errado a mao."
    )

segredo = distintos.pop() if distintos else secrets.token_urlsafe(32)

for env in faltando:
    texto = env.read_text(encoding="utf-8")
    if not texto.endswith("\n"):
        texto += "\n"
    texto += (
        "\n# 21/10: segredo da ponte MoviZap -> FPSL (leitura de OS).\n"
        "# Rota de servico nao tem cookie de sessao: toda rota do painel do\n"
        "# FPSL exige `Depends(requer_aba(...))`, e chamada servidor-a-servidor\n"
        "# nao passa por ali. Este segredo e o que autentica a ponte.\n"
        f"{CHAVE}={segredo}\n"
    )
    env.write_text(texto, encoding="utf-8")
    print(f"gravado em {env}")

iguais = len({ler(env) for env in ENVS}) == 1
print(f"os dois .env batem: {iguais}")
print(f"tamanho do segredo: {len(ler(ENVS[0]))} caracteres")
