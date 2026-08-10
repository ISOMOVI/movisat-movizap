"""Tira as empresas inativas da base. Decisao do usuario em 10/08.

*"inativas ok, prossiga"* -- empresa inativa nao precisa fazer parte desta
base. O MoviZap e painel de ATENDIMENTO: quem nao e mais cliente nao escreve,
e se escrever entra como nao identificado, que e o caso normal.

🚨 MEDE ANTES DE APAGAR, E PARA SE ENCOSTAR EM CONVERSA. Se alguma conversa
estiver ligada a contato de empresa inativa, apagar deixaria a conversa orfa
-- e conversa e o dado que nao se recupera do Harmonit. Nesse caso o script
NAO apaga nada e mostra quais sao.

Uso:  limpar_inativas.py            -> so mede
      limpar_inativas.py --apagar   -> apaga, se estiver seguro
"""
import sys

sys.path.insert(0, "/home/claude/movizap_painel")
sys.path.insert(0, "/home/claude/movizap_painel/scripts")
from expurgar_base64 import conectar  # noqa: E402

apagar = "--apagar" in sys.argv
con = conectar()
cur = con.cursor()

print("=" * 68)
print("MEDINDO")
print("=" * 68)
cur.execute("SELECT count(*) FILTER (WHERE ativo) a, count(*) FILTER (WHERE NOT ativo) i,"
            " count(*) t FROM cliente")
r = cur.fetchone()
print(f"  clientes: {r['t']} total · {r['a']} ativos · {r['i']} INATIVOS")

cur.execute("""SELECT count(DISTINCT c.id) n FROM contato c
                 JOIN cliente cl ON cl.id = c.cliente_id WHERE NOT cl.ativo""")
contatos = cur.fetchone()["n"]
cur.execute("""SELECT count(*) n FROM contato_telefone ct
                 JOIN contato c ON c.id = ct.contato_id
                 JOIN cliente cl ON cl.id = c.cliente_id WHERE NOT cl.ativo""")
telefones = cur.fetchone()["n"]
print(f"  contatos dessas empresas:  {contatos}")
print(f"  telefones dessas empresas: {telefones}")

# 🚨 A pergunta que decide
cur.execute("""SELECT cv.id, cv.telefone_e164, cv.nome_whatsapp, cl.nome AS empresa
                 FROM conversa cv
                 JOIN contato c ON c.id = cv.contato_id
                 JOIN cliente cl ON cl.id = c.cliente_id
                WHERE NOT cl.ativo""")
presas = cur.fetchall()
print(f"\n  CONVERSAS ligadas a empresa inativa: {len(presas)}")
for p in presas:
    print(f"    conversa {p['id']} · {p['telefone_e164']} · {p['empresa']}")

# telefones que EXISTEM SO na empresa inativa (some o alcance)
cur.execute("""
    SELECT count(DISTINCT ct.e164) n FROM contato_telefone ct
      JOIN contato c ON c.id = ct.contato_id
      JOIN cliente cl ON cl.id = c.cliente_id
     WHERE NOT cl.ativo
       AND NOT EXISTS (SELECT 1 FROM contato_telefone ct2
                         JOIN contato c2 ON c2.id = ct2.contato_id
                         JOIN cliente cl2 ON cl2.id = c2.cliente_id
                        WHERE cl2.ativo AND ct2.e164 = ct.e164)""")
print(f"  telefones que existem SO em empresa inativa: {cur.fetchone()['n']}")

if not apagar:
    print("\n(so medicao -- rode com --apagar)")
    con.close()
    sys.exit(0)

if presas:
    print("\n🚨 NAO APAGUEI NADA. Ha conversa ligada a empresa inativa; "
          "apagar deixaria a conversa orfa. Decida caso a caso primeiro.")
    con.close()
    sys.exit(1)

print("\n" + "=" * 68)
print("APAGANDO")
print("=" * 68)
cur.execute("""DELETE FROM contato_telefone ct USING contato c, cliente cl
                WHERE ct.contato_id = c.id AND c.cliente_id = cl.id AND NOT cl.ativo""")
print(f"  telefones apagados: {cur.rowcount}")
cur.execute("""DELETE FROM contato c USING cliente cl
                WHERE c.cliente_id = cl.id AND NOT cl.ativo""")
print(f"  contatos apagados:  {cur.rowcount}")
cur.execute("DELETE FROM cliente WHERE NOT ativo")
print(f"  clientes apagados:  {cur.rowcount}")
con.commit()

print("\n=== RELENDO O ESTADO ===")
cur.execute("SELECT count(*) FILTER (WHERE ativo) a, count(*) t FROM cliente")
r = cur.fetchone()
print(f"  clientes: {r['t']} (ativos {r['a']})  {'OK' if r['t'] == r['a'] else 'FALHOU'}")
cur.execute("SELECT count(*) n FROM contato")
print(f"  contatos:  {cur.fetchone()['n']}")
cur.execute("SELECT count(*) n FROM contato_telefone")
print(f"  telefones: {cur.fetchone()['n']}")
cur.execute("""SELECT count(*) n FROM conversa cv LEFT JOIN contato c ON c.id = cv.contato_id
                WHERE cv.contato_id IS NOT NULL AND c.id IS NULL""")
print(f"  conversas orfas (tem que ser 0): {cur.fetchone()['n']}")
con.close()
