"""Procura o segredo do webhook nos logs SEM colocá-lo em linha de comando.

🚨 ESTE SCRIPT EXISTE POR CAUSA DE UM ERRO MEU, em 12/08. Auditando se o
segredo aparecia em algum log, rodei:

    s=$(grep "^MOVIZAP_WEBHOOK_SEGREDO=" .env | cut -d= -f2)
    grep -rl -- "$s" /var/log/

O `$s` vira **argv** do `grep` — e o `auditd` registra `EXECVE` com argv
inteiro. Resultado: o comando que procurava o segredo nos logs **escreveu o
segredo num log**, o `/var/log/audit/audit.log`. Auditar assim contamina o que
se está auditando.

⚠️ Aqui o valor é lido do `.env` DENTRO do processo e nunca sai dele: não vai
para argv, não é impresso, e o que aparece na tela é só a contagem.
"""
import gzip
import sys
from pathlib import Path

ENV = Path("/home/claude/movizap_painel/.env")
RAIZ = Path("/var/log")
CHAVES = ("MOVIZAP_WEBHOOK_SEGREDO", "MOVIZAP_WEBHOOK_SEGREDO_ANTERIOR")


def segredos() -> dict[str, str]:
    achados = {}
    for linha in ENV.read_text(encoding="utf-8").splitlines():
        for chave in CHAVES:
            if linha.strip().startswith(f"{chave}="):
                valor = linha.split("=", 1)[1].strip()
                if valor:
                    achados[chave] = valor
    return achados


def procurar(alvos: dict[str, str]) -> dict[str, list[str]]:
    onde = {chave: [] for chave in alvos}
    for caminho in RAIZ.rglob("*"):
        if not caminho.is_file():
            continue
        try:
            abrir = gzip.open if caminho.suffix == ".gz" else open
            with abrir(caminho, "rb") as f:
                conteudo = f.read()
        except Exception:
            continue
        for chave, valor in alvos.items():
            if valor.encode() in conteudo:
                onde[chave].append(str(caminho))
    return onde


def main() -> None:
    alvos = segredos()
    if not alvos:
        raise SystemExit("nenhum segredo configurado no .env")
    print(f"conferindo {len(alvos)} segredo(s) em vigor contra {RAIZ}\n")
    onde = procurar(alvos)
    limpo = True
    for chave, arquivos in onde.items():
        if arquivos:
            limpo = False
            print(f"🚨 {chave} aparece em {len(arquivos)} arquivo(s):")
            for a in arquivos:
                print(f"     {a}")
        else:
            print(f"✅ {chave}: nenhum arquivo em {RAIZ}")
    print()
    print("LIMPO" if limpo else "EXPOSTO — rotacionar")
    sys.exit(0 if limpo else 1)


if __name__ == "__main__":
    main()
