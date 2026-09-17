"""Reaplica as edicoes que chegaram ANTES de o painel saber trata-las.

O tratamento de `editedMessage` entrou em 17/09 (migracao 043). Os eventos
anteriores ja estao em `webhook_evento` marcados como processados -- o texto
novo foi lido e descartado na epoca. Este script os encontra e aplica, para a
conversa passar a mostrar o que a pessoa realmente escreveu.

🚨 SECO POR PADRAO. Sem `--aplicar`, roda tudo e da ROLLBACK -- serve para ver
o que aconteceria sem arriscar nada. A prova, no fim, e RELER o estado.

🚨 CONEXAO PROPRIA, NAO `banco.cursor()`. O cursor do projeto commita sozinho
ao sair do `with` ("nao existe esqueci de commitar"), o que e certo para o
painel e impede o ensaio seco aqui. Por isso esta conexao e aberta a mao, com
`autocommit = False`.

⚠️ NAO PERDE NADA: o texto anterior vai para `conteudo_original`, que e
justamente o que o atendente leu na epoca.

⚠️ IDEMPOTENTE: mensagem que ja tem `editada_em` e pulada, entao rodar duas
vezes nao reescreve nada.

Uso:
    ./venv/bin/python scripts/reaplicar_edicoes.py            # seco
    ./venv/bin/python scripts/reaplicar_edicoes.py --aplicar  # grava
"""
import sys
from pathlib import Path

sys.path.insert(0, "/home/claude/movizap_painel")
import psycopg  # noqa: E402
from movizap.conversas import _aplicar_edicao  # noqa: E402

APLICAR = "--aplicar" in sys.argv

cfg = {}
for linha in Path("/home/claude/movizap_painel/.env").read_text(
        encoding="utf-8").splitlines():
    if "=" in linha and not linha.strip().startswith("#"):
        chave, _, valor = linha.partition("=")
        cfg[chave.strip()] = valor.strip()

conn = psycopg.connect(
    host=cfg.get("MOVIZAP_DB_HOST", "localhost"),
    port=cfg.get("MOVIZAP_DB_PORTA", "5432"),
    dbname=cfg.get("MOVIZAP_DB_NOME", "movizap"),
    user=cfg.get("MOVIZAP_DB_USUARIO"),
    password=cfg.get("MOVIZAP_DB_SENHA"),
)
conn.autocommit = False
cur = conn.cursor()

cur.execute("""
    SELECT id, payload, recebido_em::date
      FROM webhook_evento
     WHERE payload::text LIKE '%%editedMessage%%'
     ORDER BY recebido_em
""")
eventos = cur.fetchall()
print(f"{len(eventos)} eventos de edicao na base\n")

aplicados = pulados = 0
for ev_id, payload, dia in eventos:
    alvo = (payload.get("data") or {}).get("keyId")
    cur.execute(
        "SELECT id, conteudo, editada_em FROM mensagem WHERE id_externo = %s",
        (alvo,))
    antes = cur.fetchone()

    if not antes:
        print(f"[{ev_id}] {dia}  alvo {alvo} nao esta na base -- pulado")
        pulados += 1
        continue
    if antes[2] is not None:
        print(f"[{ev_id}] {dia}  mensagem {antes[0]} ja marcada como editada -- pulado")
        pulados += 1
        continue

    nota = _aplicar_edicao(cur, payload)
    cur.execute("SELECT conteudo FROM mensagem WHERE id_externo = %s", (alvo,))
    depois = cur.fetchone()
    print(f"[{ev_id}] {dia}  mensagem {antes[0]}: {nota}")
    print(f"    antes: {antes[1][:80]!r}")
    print(f"    agora: {depois[0][:80]!r}")
    aplicados += 1

if APLICAR:
    conn.commit()
    print(f"\n{aplicados} aplicados, {pulados} pulados -- GRAVADO.")
    print("\n=== RELENDO O ESTADO (a prova) ===")
    cur.execute("""SELECT id, left(conteudo, 70), left(conteudo_original, 70),
                          editada_em
                     FROM mensagem WHERE editada_em IS NOT NULL ORDER BY id""")
    for m_id, agora, antes_txt, quando in cur.fetchall():
        print(f"  mensagem {m_id}  editada_em={quando}")
        print(f"    original: {antes_txt!r}")
        print(f"    agora   : {agora!r}")
else:
    conn.rollback()
    print(f"\n{aplicados} seriam aplicados, {pulados} pulados.")
    print("SECO -- ROLLBACK feito, nada foi gravado. Use --aplicar para valer.")
