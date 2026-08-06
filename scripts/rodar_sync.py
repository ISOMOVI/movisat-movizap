"""Roda o sync do Harmonit pela linha de comando. É o que o cron chama.

🚨 A confirmação NUNCA é o retorno: depois de gravar, este script RELÊ o banco
e mostra o estado. Foi assim que se descobriu, em julho, que 1.457 chips
responderam 200 OK sem gravar nada.

Uso:
  ./venv/bin/python scripts/rodar_sync.py --apenas 998063   # 1 caso
  ./venv/bin/python scripts/rodar_sync.py --limite 200      # amostra
  ./venv/bin/python scripts/rodar_sync.py --origem cron     # base inteira
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from movizap import banco, sync  # noqa: E402
from movizap.config import silenciar_clientes_http  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
silenciar_clientes_http()  # 🚨 antes de qualquer requisição sair

p = argparse.ArgumentParser()
p.add_argument("--apenas", help="harmonit_id de um cliente só")
p.add_argument("--limite", type=int, help="para depois de N clientes")
p.add_argument("--origem", default="manual", choices=["manual", "cron"])
args = p.parse_args()

banco.abrir()
try:
    resultado = sync.executar(
        origem=args.origem, limite=args.limite, apenas_id=args.apenas)

    print("\n=== o que o sync DISSE ===")
    for chave, valor in resultado.items():
        print(f"  {chave:14} {valor}")

    # ── 🚨 A PROVA: reler o estado ────────────────────────────────────────
    print("\n=== o que o BANCO diz (releitura) ===")
    totais = banco.um("""
        SELECT (SELECT count(*) FROM cliente)                          AS clientes,
               (SELECT count(*) FROM cliente WHERE ativo)              AS clientes_ativos,
               (SELECT count(*) FROM cliente WHERE origem='movizap')   AS clientes_nossos,
               (SELECT count(*) FROM contato)                          AS contatos,
               (SELECT count(*) FROM contato_telefone)                 AS telefones,
               (SELECT count(*) FROM contato_telefone
                 WHERE tem_whatsapp IS NULL)                           AS tel_nao_verificados
    """)
    for chave, valor in totais.items():
        print(f"  {chave:22} {valor}")

    if args.apenas:
        print(f"\n=== o cliente {args.apenas}, relido linha por linha ===")
        cli = banco.um(
            "SELECT id, nome, nome_fantasia, documento, tipo_pessoa, email, "
            "origem, harmonit_id, ativo FROM cliente WHERE harmonit_id=%s",
            (args.apenas,))
        if not cli:
            print("  🚨 NAO ESTA NO BANCO -- o sync disse que fez e nao fez")
            raise SystemExit(1)
        for chave, valor in cli.items():
            print(f"  {chave:16} {valor!r}")

        for tel in banco.varios(
            "SELECT t.e164, t.bruto, t.origem_campo, t.principal, t.tem_whatsapp "
            "  FROM contato_telefone t JOIN contato c ON c.id = t.contato_id "
            " WHERE c.cliente_id = %s ORDER BY t.origem_campo", (cli["id"],)
        ):
            print(f"  telefone       {tel['e164']:16} campo={tel['origem_campo']:9}"
                  f" principal={tel['principal']!s:5}"
                  f" tem_whatsapp={tel['tem_whatsapp']}"
                  f" bruto={tel['bruto']!r}")

    print("\n=== ultimas execucoes registradas ===")
    for e in sync.execucoes(5):
        print(f"  #{e['id']} {e['iniciado_em']:%d/%m %H:%M:%S} {e['origem']:6}"
              f" lidos={e['lidos']:5} criados={e['criados']:5}"
              f" atualizados={e['atualizados']:5} inativados={e['inativados']:4}"
              f" vazios={e['vazios']:5} erros={e['erros']:4}"
              f"{'  ERRO: ' + e['mensagem_erro'] if e['mensagem_erro'] else ''}")
finally:
    banco.fechar()
