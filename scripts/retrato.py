# -*- coding: utf-8 -*-
"""Retratos de estrutura do MoviZap, para a garantia de entrega de 27/11.

🔵 Ele: *"se tiver backup da estrutura, pode comparar depois, revalidar e
garantir entrega -- e pode validar antes ainda"*.

🚨 A SENHA NUNCA ENTRA EM `argv` NEM EM VARIAVEL DE AMBIENTE SOLTA. Reusa o
padrao do `scripts/backup_db.py`: um `PGPASSFILE` 0600 em pasta temporaria,
`--no-password` no comando, e o arquivo apagado no `finally`. Em 05/08 a
migracao 001 foi aplicada com `export PGPASSWORD=$(...)` -- variavel de
ambiente e legivel em /proc pelo proprio usuario, e e esse caminho que o
padrao da casa fecha.

Uso:
  retrato.py esquema <banco> <saida.sql>
  retrato.py restaurar <dump.sql.gz|dump.sql> <banco>
  retrato.py aplicar <arquivo.sql> <banco>
  retrato.py sql <banco> "<consulta>"
"""
import gzip
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ENV = Path("/home/claude/movizap_painel/.env")


def config() -> dict:
    cfg = {}
    for linha in ENV.read_text(encoding="utf-8").splitlines():
        if "=" in linha and not linha.strip().startswith("#"):
            chave, _, valor = linha.partition("=")
            cfg[chave.strip()] = valor.strip()
    return cfg


class Senha:
    """O PGPASSFILE 0600, criado e destruido em volta do comando.

    ⚠️ O curinga no nome do banco (`*`) e deliberado: o mesmo arquivo serve
    `movizap`, `movizap_ontem_2711` e `movizap_copia_2711`, que vivem no mesmo
    servidor com o mesmo usuario. Sem ele seria um passfile por banco.
    """

    def __init__(self, cfg):
        self.cfg = cfg
        self.pasta = None
        self.arquivo = None

    def __enter__(self):
        self.pasta = Path(tempfile.mkdtemp(prefix="movizap_retrato_"))
        self.arquivo = self.pasta / "pgpass"
        self.arquivo.write_text(
            "{h}:{p}:*:{u}:{s}\n".format(
                h=self.cfg["MOVIZAP_DB_HOST"], p=self.cfg["MOVIZAP_DB_PORTA"],
                u=self.cfg["MOVIZAP_DB_USUARIO"],
                s=self.cfg["MOVIZAP_DB_SENHA"]),
            encoding="utf-8")
        self.arquivo.chmod(0o600)
        return dict(os.environ, PGPASSFILE=str(self.arquivo))

    def __exit__(self, *_):
        if self.arquivo:
            self.arquivo.unlink(missing_ok=True)
        if self.pasta:
            self.pasta.rmdir()
        return False


def _base(cfg):
    return ["-h", cfg["MOVIZAP_DB_HOST"], "-p", cfg["MOVIZAP_DB_PORTA"],
            "-U", cfg["MOVIZAP_DB_USUARIO"], "--no-password"]


def esquema(banco: str, saida: str) -> None:
    """Só a ESTRUTURA, e com a ordem estabilizada para o diff servir.

    🚨 `--schema-only` sozinho ja sai em ordem deterministica para o mesmo
    `pg_dump`, mas `--no-owner` e `--no-privileges` tiram linhas de dono e de
    GRANT que mudam entre uma copia restaurada e a producao -- e que sujariam o
    diff com dezenas de linhas que nao sao a minha mudanca.
    """
    cfg = config()
    with Senha(cfg) as ambiente:
        with open(saida, "wb") as f:
            r = subprocess.run(
                ["pg_dump", *_base(cfg), "--schema-only", "--no-owner",
                 "--no-privileges", banco],
                stdout=f, stderr=subprocess.PIPE, env=ambiente)
    if r.returncode != 0:
        raise SystemExit("pg_dump falhou: " + r.stderr.decode()[:400])
    linhas = sum(1 for _ in open(saida, encoding="utf-8", errors="replace"))
    print(f"{saida}: {linhas} linhas")


def restaurar(origem: str, banco: str) -> None:
    """Joga o dump dentro do banco, por cano -- sem descomprimir em disco."""
    cfg = config()
    abrir = gzip.open if origem.endswith(".gz") else open
    with Senha(cfg) as ambiente:
        proc = subprocess.Popen(
            ["psql", *_base(cfg), "-q", "-v", "ON_ERROR_STOP=0", "-d", banco],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, env=ambiente)
        with abrir(origem, "rb") as f:
            for pedaco in iter(lambda: f.read(1 << 20), b""):
                proc.stdin.write(pedaco)
        proc.stdin.close()
        erro = proc.stderr.read().decode(errors="replace")
        proc.wait()
    # ⚠️ `ON_ERROR_STOP=0` de proposito: o dump traz `CREATE EXTENSION` e
    # linhas de dono que a copia pode recusar, e parar nelas deixaria a
    # estrutura pela metade. O que importa e o que chegou -- conferido depois
    # pelo retrato, nao pelo codigo de retorno.
    graves = [l for l in erro.splitlines()
              if "ERROR" in l and "already exists" not in l]
    print(f"restaurado em {banco}; {len(graves)} erro(s) nao-trivial(is)")
    for l in graves[:15]:
        print("  ", l[:160])


def aplicar(arquivo: str, banco: str) -> None:
    """Aplica um .sql num banco de ENSAIO, parando no primeiro erro.

    🚨 `ON_ERROR_STOP=1`, ao contrario do `restaurar`: aqui o arquivo e uma
    MIGRACAO, e migracao que falha no meio deixa o banco em estado que nao e
    nem o antigo nem o novo. O `restaurar` pode tolerar erro trivial porque o
    que vale la e o retrato conferido depois; aqui o que vale e ter aplicado
    inteiro ou nada.

    ⚠️ NAO substitui o `scripts/aplicar_migracao.py` para producao -- aquele
    recusa versao ja registrada em `schema_migracao`, e e essa guarda que
    impede reaplicar. Este serve a COPIA, onde reaplicar e o esperado.
    """
    cfg = config()
    with Senha(cfg) as ambiente:
        r = subprocess.run(
            ["psql", *_base(cfg), "-q", "-v", "ON_ERROR_STOP=1",
             "-d", banco, "-f", arquivo],
            capture_output=True, env=ambiente)
    saida = r.stdout.decode(errors="replace").strip()
    erro = r.stderr.decode(errors="replace").strip()
    if saida:
        print(saida[:2000])
    if r.returncode != 0:
        raise SystemExit("FALHOU em " + banco + ": " + erro[:2000])
    if erro:
        print("avisos:", erro[:600])
    print(f"aplicado em {banco}")


def sql(banco: str, consulta: str) -> None:
    cfg = config()
    with Senha(cfg) as ambiente:
        r = subprocess.run(["psql", *_base(cfg), "-d", banco, "-A", "-F", "|",
                            "-c", consulta],
                           capture_output=True, env=ambiente)
    sys.stdout.write(r.stdout.decode(errors="replace"))
    if r.returncode != 0:
        sys.stderr.write(r.stderr.decode(errors="replace")[:400])


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    acao = sys.argv[1]
    if acao == "esquema":
        esquema(sys.argv[2], sys.argv[3])
    elif acao == "restaurar":
        restaurar(sys.argv[2], sys.argv[3])
    elif acao == "aplicar":
        aplicar(sys.argv[2], sys.argv[3])
    elif acao == "sql":
        sql(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit(__doc__)
