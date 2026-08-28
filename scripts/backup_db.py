#!/usr/bin/env python3
"""Backup do banco `movizap`.

🚨 EXISTE PORQUE NÃO EXISTIA. Auditoria de 28/08: o cron salvava o banco do
hub-fotos (03:00) e o do MoviChat (03:30), e o `backup_projetos.sh` (02:00)
empacotava o DIRETÓRIO `movizap_painel` -- código, docs e migrações. O banco do
MoviZap não tinha uma linha de backup em lugar nenhum: 192 MB, 37 tabelas, o
histórico de atendimento inteiro. Código se reconstrói do git; isto não.

🚨 A SENHA NÃO PASSA POR `argv` NEM FICA DE ENFEITE NO AMBIENTE. É a regra que
o `aplicar_migracao.py` já escreveu neste projeto, e que os dois scripts
antigos violam (`PGPASSWORD=<valor> pg_dump ...`, com o valor em `argv`, que o
`auditd` grava). Aqui a senha sai do `.env` dentro do processo e vai para um
`.pgpass` temporário com modo 0600, apagado no `finally` -- inclusive quando o
`pg_dump` falha.

⚠️ VERIFICA O QUE GRAVOU. Backup que não abre é pior que backup nenhum, porque
dá confiança. O arquivo só vira definitivo depois de o gzip passar no teste e
de as tabelas esperadas aparecerem dentro dele -- mesma disciplina do
`backup_projetos.sh`, que só promove o `.parcial` se o `tar -tzf` abrir.

Uso:  ./venv/bin/python scripts/backup_db.py [--reter DIAS]
"""
import argparse
import gzip
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path("/home/claude/movizap_painel")
ENV = RAIZ / ".env"
DESTINO = Path("/home/claude/backups/db")

# As tabelas que PRECISAM estar no dump para ele valer. Não é a lista inteira
# de propósito: são as que carregam o que não se reconstrói de outra fonte.
ESSENCIAIS = ("conversa", "mensagem", "contato", "contato_telefone",
              "cliente", "atendente", "conversa_participante")


def config() -> dict:
    cfg = {}
    for linha in ENV.read_text(encoding="utf-8").splitlines():
        if "=" in linha and not linha.strip().startswith("#"):
            chave, _, valor = linha.partition("=")
            cfg[chave.strip()] = valor.strip()
    return cfg


def dump(cfg: dict, alvo: Path) -> None:
    """Roda o pg_dump com a senha num PGPASSFILE 0600, nunca em argv."""
    pasta = Path(tempfile.mkdtemp(prefix="movizap_bkp_"))
    senha = pasta / "pgpass"
    try:
        senha.write_text(
            "{host}:{porta}:{db}:{usuario}:{senha}\n".format(
                host=cfg["MOVIZAP_DB_HOST"], porta=cfg["MOVIZAP_DB_PORTA"],
                db=cfg["MOVIZAP_DB_NOME"], usuario=cfg["MOVIZAP_DB_USUARIO"],
                senha=cfg["MOVIZAP_DB_SENHA"]),
            encoding="utf-8")
        senha.chmod(0o600)

        ambiente = dict(os.environ, PGPASSFILE=str(senha))
        # 🚨 O `pg_dump` VAI PARA UM CANO, e a compressão é feita aqui.
        # Passar o `gzip.GzipFile` como `stdout=` não funciona e falha CALADO:
        # o subprocess usa o `fileno()`, que é o do arquivo de baixo, então o
        # SQL cru entra dentro do `.gz` e o arquivo fica com nome de comprimido
        # e conteúdo de texto. Foi o que aconteceu na primeira execução, em
        # 28/08 -- e quem pegou foi a conferência, não o código de retorno:
        # o `pg_dump` devolveu 0, satisfeito.
        proc = subprocess.Popen(
            ["pg_dump", "-h", cfg["MOVIZAP_DB_HOST"],
             "-p", cfg["MOVIZAP_DB_PORTA"], "-U", cfg["MOVIZAP_DB_USUARIO"],
             "--no-password", cfg["MOVIZAP_DB_NOME"]],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=ambiente)
        with gzip.open(alvo, "wb") as saida:
            for pedaco in iter(lambda: proc.stdout.read(1 << 20), b""):
                saida.write(pedaco)
        proc.stdout.close()
        erro = proc.stderr.read()
        if proc.wait() != 0:
            # ⚠️ O stderr do pg_dump não cita a senha, mas cita host e usuário.
            # Vai para a saída porque quem lê o log precisa saber o que falhou.
            raise SystemExit(f"pg_dump falhou: {erro.decode()[:400]}")
    finally:
        senha.unlink(missing_ok=True)
        pasta.rmdir()


def conferir(alvo: Path) -> dict:
    """Abre o arquivo e prova que ele tem o que precisa ter."""
    achadas, linhas = set(), 0
    with gzip.open(alvo, "rt", encoding="utf-8", errors="replace") as f:
        for linha in f:
            linhas += 1
            if linha.startswith("COPY public."):
                achadas.add(linha.split("COPY public.", 1)[1].split(" ", 1)[0])
    faltando = [t for t in ESSENCIAIS if t not in achadas]
    return {"linhas": linhas, "tabelas": len(achadas), "faltando": faltando}


def expurgar(dias: int) -> int:
    corte = datetime.now() - timedelta(days=dias)
    saiu = 0
    for velho in DESTINO.glob("movizap_*.sql.gz"):
        if datetime.fromtimestamp(velho.stat().st_mtime) < corte:
            velho.unlink()
            saiu += 1
    return saiu


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--reter", type=int, default=14,
                   help="dias de retenção (padrão 14)")
    args = p.parse_args()

    DESTINO.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d_%H%M")
    parcial = DESTINO / f"movizap_{carimbo}.sql.gz.parcial"
    final = DESTINO / f"movizap_{carimbo}.sql.gz"

    dump(config(), parcial)
    prova = conferir(parcial)
    if prova["faltando"]:
        parcial.unlink(missing_ok=True)
        print(f"BACKUP RECUSADO -- faltam tabelas: {prova['faltando']}")
        return 1

    parcial.rename(final)
    mb = final.stat().st_size / 1024 / 1024
    print(f"ok {final.name}  {mb:.1f} MB  "
          f"{prova['tabelas']} tabelas  {prova['linhas']} linhas")
    if args.reter:
        saiu = expurgar(args.reter)
        if saiu:
            print(f"expurgo: {saiu} backup(s) acima de {args.reter} dias")
    return 0


if __name__ == "__main__":
    sys.exit(main())
