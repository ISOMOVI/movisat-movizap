"""Acesso ao banco `movizap`.

Um pool, aberto no arranque e fechado no encerramento. Sem ORM: as consultas
são SQL, porque o modelo de dados é o documento e ver a consulta é ver o
modelo.

🚨 Toda consulta é parametrizada (`%s`). Nunca há concatenação de valor em
string de SQL — nem "só neste caso", nem "o valor é interno".
"""
import logging
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import settings

log = logging.getLogger("movizap.banco")

_pool: ConnectionPool | None = None


def abrir() -> None:
    """Chamado no arranque. Falha aqui derruba o serviço, e isso é certo:
    painel sem banco não tem o que mostrar."""
    global _pool
    if _pool is not None:
        return
    _pool = ConnectionPool(
        conninfo=settings.dsn(),
        min_size=1,
        max_size=8,
        open=True,
        timeout=10,
        kwargs={"row_factory": dict_row},
    )
    log.info("pool do banco aberto (%s@%s/%s)",
             settings.db_usuario, settings.db_host, settings.db_nome)


def fechar() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def cursor():
    """Uso: `with banco.cursor() as cur: cur.execute(...)`.

    Commit no fim se nada estourar; rollback se estourar. Não existe
    "esqueci de commitar".
    """
    if _pool is None:
        raise RuntimeError("banco não foi aberto -- ver ciclo_de_vida em main.py")
    with _pool.connection() as conn:
        with conn.cursor() as cur:
            yield cur


def um(sql: str, params: tuple = ()) -> dict | None:
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def varios(sql: str, params: tuple = ()) -> list[dict]:
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def executar(sql: str, params: tuple = ()) -> int:
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.rowcount


def saude() -> dict:
    """Para /api/saude. Não levanta exceção: o painel precisa conseguir
    dizer 'o banco caiu' em vez de cair junto."""
    try:
        with cursor() as cur:
            cur.execute("SELECT version() AS v, current_database() AS d")
            r = cur.fetchone()
            cur.execute("SELECT MAX(versao) AS m FROM schema_migracao")
            m = cur.fetchone()
        return {
            "ok": True,
            "banco": r["d"],
            "migracao": m["m"],
            "postgres": r["v"].split(" ")[1],
        }
    except (psycopg.Error, RuntimeError) as e:
        log.error("banco indisponível: %s", e.__class__.__name__)
        return {"ok": False, "erro": e.__class__.__name__}
