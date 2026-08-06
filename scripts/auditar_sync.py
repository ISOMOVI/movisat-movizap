"""Auditoria do passo 1 -- procura DEFEITO, nao confirmacao.

Cada bloco tenta provar que alguma coisa esta errada. Bloco que nao acha nada
imprime "ok"; bloco que acha imprime o caso concreto.
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from movizap import banco, harmonit, telefone  # noqa: E402
from movizap.config import silenciar_clientes_http  # noqa: E402

silenciar_clientes_http()
banco.abrir()

achados = []


def achado(titulo, detalhe):
    achados.append(titulo)
    print(f"  🔴 {titulo}\n     {detalhe}")


print("=== 1) contatoPrincipalId se repete entre clientes? ===")
print("    Se repetir, o contato fica trocando de cliente a cada sync.")
vistos = {}
repetidos = []
for _p, lista in harmonit.paginar_clientes():
    for cli in lista:
        cp = cli.get("contatoPrincipal") or {}
        cpid = cp.get("contatoPrincipalId")
        if not cpid:
            continue
        if cpid in vistos and vistos[cpid] != cli.get("id"):
            repetidos.append((cpid, vistos[cpid], cli.get("id")))
        vistos[cpid] = cli.get("id")
if repetidos:
    achado(f"contatoPrincipalId repetido em {len(repetidos)} casos",
           f"exemplos: {repetidos[:5]}")
else:
    print(f"  ok -- {len(vistos)} ids, nenhum repetido entre clientes diferentes")

print("\n=== 2) algum contato ficou pendurado no cliente errado? ===")
erradas = banco.varios("""
    SELECT c.id, c.harmonit_id AS contato_hid, c.cliente_id,
           cl.harmonit_id AS cliente_hid
      FROM contato c JOIN cliente cl ON cl.id = c.cliente_id
     WHERE c.harmonit_id LIKE 'cli:%%'
       AND c.harmonit_id <> 'cli:' || cl.harmonit_id
     LIMIT 5
""")
if erradas:
    achado(f"{len(erradas)} contatos com chave cli: apontando para outro cliente",
           str(erradas))
else:
    print("  ok -- toda chave cli:{id} bate com o cliente dono")

print("\n=== 3) `inativados` mede fluxo, nao estoque ===")
print("    ESTOQUE = quantos estao inativos. FLUXO = quantos VIRARAM inativos.")
print("    O contador tem que ser o fluxo: e a unica pergunta que ele responde")
print("    ('o que mudou desde ontem?').")
execs = banco.varios("""
    SELECT id, lidos, inativados FROM sync_execucao
     WHERE lidos > 1000 ORDER BY id DESC LIMIT 3
""")
estoque = banco.um("SELECT count(*) AS n FROM cliente WHERE NOT ativo")["n"]
print(f"  estoque de inativos no banco: {estoque}")
for e in reversed(execs):
    print(f"  execucao #{e['id']}: inativados={e['inativados']}")

# 🚨 O sintoma do bug original: TODA execucao completa devolvia exatamente o
# estoque. Se voltar a acontecer em duas seguidas, o contador regrediu.
completas = [e["inativados"] for e in execs]
if len(completas) >= 2 and all(v == estoque for v in completas[:2]) and estoque:
    achado("`inativados` voltou a medir estoque",
           f"as duas ultimas execucoes deram {estoque}, o total de inativos")
elif execs and execs[0]["inativados"] == 0:
    print("  ok -- a ultima execucao completa nao inativou ninguem, e nada")
    print("       mudou no Harmonit desde a anterior. E o esperado.")
else:
    print("  ok -- o contador varia entre execucoes")

print("\n=== 4) o estoque continua consistente? ===")
ativos = banco.um("SELECT count(*) AS n FROM cliente WHERE ativo")["n"]
print(f"  ativos {ativos} + inativos {estoque} = {ativos + estoque}")
total = banco.um("SELECT count(*) AS n FROM cliente")["n"]
if ativos + estoque != total:
    achado("a soma nao fecha", f"total={total}")
else:
    print(f"  ok -- fecha com o total de {total}")

print("\n=== 5) telefone gravado que o normalizador nao reconhece de volta ===")
print("    Ida e volta: se o e164 gravado nao normaliza para ele mesmo, ha")
print("    inconsistencia entre gravar e buscar.")
ruins = []
for t in banco.varios("SELECT id, e164, bruto FROM contato_telefone"):
    if telefone.normalizar(t["e164"]) != t["e164"]:
        ruins.append(t)
if ruins:
    achado(f"{len(ruins)} telefones nao sobrevivem a ida e volta", str(ruins[:5]))
else:
    print("  ok -- todos os e164 gravados normalizam para si mesmos")

print("\n=== 6) telefone duplicado entre contatos diferentes ===")
print("    Nao e erro, mas decide a quem a mensagem que chega vai ser ligada.")
dups = banco.varios("""
    SELECT e164, count(DISTINCT contato_id) AS contatos
      FROM contato_telefone GROUP BY e164 HAVING count(DISTINCT contato_id) > 1
     ORDER BY 2 DESC LIMIT 10
""")
if dups:
    print(f"  ⚠️ {len(dups)} numeros aparecem em mais de um contato:")
    for d in dups:
        print(f"     {d['e164']} em {d['contatos']} contatos")
else:
    print("  ok -- nenhum numero compartilhado")

print("\n=== 7) cliente sem contato, ou contato sem telefone ===")
sem_contato = banco.um(
    "SELECT count(*) AS n FROM cliente cl WHERE NOT EXISTS "
    "(SELECT 1 FROM contato c WHERE c.cliente_id = cl.id)")["n"]
sem_tel = banco.um(
    "SELECT count(*) AS n FROM contato c WHERE NOT EXISTS "
    "(SELECT 1 FROM contato_telefone t WHERE t.contato_id = c.id)")["n"]
print(f"  clientes sem contato: {sem_contato}")
print(f"  contatos sem telefone: {sem_tel} de 1050"
      f" ({100*sem_tel/1050:.1f}%) -- esperado ~15,8%")
if sem_contato:
    achado(f"{sem_contato} clientes ficaram sem contato", "o sync deveria criar 1")

print("\n=== 8) distribuicao de tipo por telefone ===")
tipos = Counter(telefone.analisar(t["e164"]).tipo
                for t in banco.varios("SELECT e164 FROM contato_telefone"))
print(f"  {dict(tipos)}")

print("\n=== 9) o `principal` esta em algum lugar util? ===")
sem_principal = banco.um("""
    SELECT count(*) AS n FROM contato c
     WHERE EXISTS (SELECT 1 FROM contato_telefone t WHERE t.contato_id=c.id)
       AND NOT EXISTS (SELECT 1 FROM contato_telefone t
                        WHERE t.contato_id=c.id AND t.principal)
""")["n"]
print(f"  contatos COM telefone mas NENHUM principal: {sem_principal}")
if sem_principal:
    print("     ⚠️ sao os que tem fixo mas nao celular. Quando o atendimento")
    print("        precisar de 'o numero do cliente', esses nao tem resposta.")

banco.fechar()
print(f"\n{'='*60}\nACHADOS QUE EXIGEM CORRECAO: {len(achados)}")
for a in achados:
    print(f"  - {a}")
