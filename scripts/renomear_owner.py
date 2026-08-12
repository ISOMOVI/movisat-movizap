"""Renomeia o login do owner de `Admin` para `owner` — .env e banco JUNTOS.

🚨 OS DOIS OU NENHUM. O login do `.env` e o `atendente.login` do dono precisam
ser o MESMO texto: é essa igualdade que faz `buscar_usuario` fundir a
identidade da tabela (id, nome, e-mail) com a senha do `.env`. Mexer em um só
deixa o dono em um destes dois estados, ambos ruins:

  · só o banco  -> entrar como "Admin" cai na porta de emergência, SEM id, e
                   tudo que ele escrever sai com autor NULL, em silêncio;
  · só o .env   -> entrar como "owner" acha a linha, que tem `senha_hash`
                   NULL, e a senha é recusada -- ninguém entra.

⚠️ VALIDA ANTES DE GRAVAR (metodologia §"validar antes de gravar"): monta o
texto novo em memória, confere que a linha existe e é única, e só então
escreve. O backup vai para FORA do repositório -- `.env.bak` dentro dele já
causou incidente antes.

Uso:  ./venv/bin/python scripts/renomear_owner.py --conferir
      ./venv/bin/python scripts/renomear_owner.py --aplicar
"""
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, "/home/claude/movizap_painel")

from movizap import banco  # noqa: E402

ENV = Path("/home/claude/movizap_painel/.env")
BACKUP_DIR = Path("/home/claude/backups")     # fora do repositório, de propósito
CHAVE = "MOVIZAP_ADMIN_LOGIN"
DE, PARA = "Admin", "owner"


def ler_env() -> list[str]:
    return ENV.read_text(encoding="utf-8").splitlines(keepends=True)


def valor_atual(linhas: list[str]) -> str | None:
    for linha in linhas:
        if linha.strip().startswith(f"{CHAVE}="):
            return linha.split("=", 1)[1].strip()
    return None


def montar(linhas: list[str]) -> list[str]:
    """O .env novo, em memória. Não grava nada."""
    novas, trocadas = [], 0
    for linha in linhas:
        if linha.strip().startswith(f"{CHAVE}="):
            fim = "\n" if linha.endswith("\n") else ""
            novas.append(f"{CHAVE}={PARA}{fim}")
            trocadas += 1
        else:
            novas.append(linha)
    if trocadas != 1:
        raise SystemExit(f"ABORTADO: esperava 1 linha {CHAVE}=, achei {trocadas}.")
    return novas


def conferir() -> dict:
    linhas = ler_env()
    atual = valor_atual(linhas)

    banco.abrir()
    dono = banco.um(
        "SELECT id, login, nome, email, perfil, owner, "
        "       (senha_hash IS NOT NULL) AS tem_senha "
        "  FROM atendente WHERE owner")
    colide = banco.um("SELECT id FROM atendente WHERE lower(login) = lower(%s)",
                      (PARA,))
    banco.fechar()

    print(f".env   {CHAVE} = {atual!r}")
    print(f"banco  owner    = {dono}")
    print(f"colisão com {PARA!r} na tabela: {colide}")

    problemas = []
    if atual is None:
        problemas.append(f"{CHAVE} não existe no .env")
    if dono is None:
        problemas.append("nenhuma linha com owner = true")
    elif dono["login"] != DE and atual != PARA:
        problemas.append(f"o login do owner é {dono['login']!r}, esperava {DE!r}")
    # A colisão só é problema se for OUTRA linha: rodar de novo depois de
    # aplicado tem de ser inofensivo.
    if colide and dono and colide["id"] != dono["id"]:
        problemas.append(f"já existe outro atendente com login {PARA!r}")
    return {"atual": atual, "dono": dono, "problemas": problemas}


def aplicar() -> None:
    estado = conferir()
    if estado["problemas"]:
        raise SystemExit("ABORTADO:\n  - " + "\n  - ".join(estado["problemas"]))

    linhas = ler_env()
    novas = montar(linhas)          # valida em memória; estoura antes de gravar

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    destino = BACKUP_DIR / f"env_movizap_{carimbo}.bak"
    shutil.copy2(ENV, destino)
    destino.chmod(0o600)
    print(f"backup: {destino}")

    ENV.write_text("".join(novas), encoding="utf-8")
    ENV.chmod(0o600)
    print(f".env: {CHAVE} = {PARA}")

    banco.abrir()
    linha = banco.um(
        "UPDATE atendente SET login = %s, atualizado_em = now() "
        " WHERE owner RETURNING id, login", (PARA,))
    banco.fechar()
    print(f"banco: atendente {linha['id']} agora é login {linha['login']!r}")

    print()
    print("FALTA REINICIAR: systemctl --user restart movizap")
    print("A sessão aberta no navegador CAI -- o token carrega o login antigo.")


if __name__ == "__main__":
    if "--aplicar" in sys.argv:
        aplicar()
    else:
        estado = conferir()
        print()
        print("PROBLEMAS:", estado["problemas"] or "nenhum — pode --aplicar")
