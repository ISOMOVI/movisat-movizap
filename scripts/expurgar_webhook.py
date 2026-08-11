"""Expurgo do `webhook_evento`: apaga o cru com mais de 90 dias.

Decisão do usuário em 2026-08-11. O evento cru existe para reprocessar quando
o processamento tem bug -- passado o prazo, ele só ocupa espaço: a conversa,
a mensagem e a mídia já estão em tabela própria.

🚨 SÓ APAGA O QUE JÁ FOI PROCESSADO OU IGNORADO DE PROPÓSITO. Evento com
`erro` preenchido FICA, por mais velho que seja: ele é a única pista do que
falhou, e é justamente o que alguém vai querer ler.

⚠️ `VACUUM` não é detalhe. Sem ele o espaço não volta para o disco -- as
linhas somem da consulta e o arquivo continua do mesmo tamanho.

Uso:  expurgar_webhook.py               simulação
      expurgar_webhook.py --aplicar
      expurgar_webhook.py --dias 180 --aplicar
"""
import argparse
import sys

sys.path.insert(0, "/home/claude/movizap_painel")
import psycopg  # noqa: E402

from movizap import banco  # noqa: E402
from movizap.config import settings  # noqa: E402

ALVO = """
  recebido_em < now() - make_interval(days => %s)
  AND erro IS NULL
  AND (processado IS TRUE OR motivo_ignorado IS NOT NULL)
"""


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dias", type=int, default=90)
    p.add_argument("--aplicar", action="store_true")
    a = p.parse_args()

    banco.abrir()
    try:
        total = banco.um("SELECT count(*) n FROM webhook_evento")["n"]
        tam = banco.um("SELECT pg_size_pretty(pg_total_relation_size("
                       "'webhook_evento')) t")["t"]
        alvo = banco.um(f"SELECT count(*) n FROM webhook_evento WHERE {ALVO}",
                        (a.dias,))["n"]
        guardados = banco.um(
            "SELECT count(*) n FROM webhook_evento WHERE erro IS NOT NULL")["n"]
        print(f"webhook_evento : {total} linhas · {tam}")
        print(f"corte          : {a.dias} dias")
        print(f"a apagar       : {alvo}")
        print(f"preservados por terem erro: {guardados}")

        if not a.aplicar:
            print("\n(simulação — nada apagado. Use --aplicar.)")
            return 0
        if not alvo:
            print("\nnada a apagar.")
            return 0

        with banco.cursor() as cur:
            cur.execute(f"DELETE FROM webhook_evento WHERE {ALVO}", (a.dias,))
            print(f"\napagadas: {cur.rowcount}")

        # ⚠️ VACUUM não roda dentro de transação, e `banco.cursor()` sempre
        # abre uma. Conexão própria em autocommit, com o mesmo DSN do projeto
        # -- a senha continua vindo do .env, nunca de argumento ou ambiente.
        with psycopg.connect(settings.dsn(), autocommit=True) as con:
            con.execute("VACUUM (ANALYZE) webhook_evento")

        print("\nRELENDO:")
        print("   linhas:", banco.um("SELECT count(*) n FROM webhook_evento")["n"])
        print("   tamanho:", banco.um("SELECT pg_size_pretty("
                                      "pg_total_relation_size('webhook_evento')) t")["t"])
    finally:
        banco.fechar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
