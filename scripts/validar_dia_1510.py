"""Validacao do que entrou em 15/10 — medido, nao lembrado.

Confere, em ordem: migracoes aplicadas, estado da base, residuo de teste,
agentes vivos, o que o bundle PUBLICADO carrega, e o cron.
"""
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "/home/claude/movizap_painel")
from movizap import banco  # noqa: E402

RAIZ = Path("/home/claude/movizap_painel")
DIST = RAIZ / "frontend/dist/assets"
ok_geral = True


def diga(ok, texto):
    global ok_geral
    if not ok:
        ok_geral = False
    print(f"  {'OK   ' if ok else 'FALHA'} {texto}")


banco.abrir()
try:
    print("== migracoes de hoje ==")
    versoes = {r["versao"] for r in banco.varios(
        "SELECT versao FROM schema_migracao WHERE versao IN ('063','064','065')")}
    for v in ("063", "064", "065"):
        diga(v in versoes, f"migracao {v} aplicada")

    print("== o contrato do banco ==")
    checks = {r["conname"] for r in banco.varios(
        """SELECT conname FROM pg_constraint
            WHERE conrelid = 'mensagem'::regclass""")}
    diga("ck_evento_conhecido" in checks, "ck_evento_conhecido (lista fechada de eventos)")
    diga("ck_evento_e_nota_interna" in checks, "ck_evento_e_nota_interna (evento nunca sai)")
    diga(bool(banco.um("SELECT to_regclass('nota_leitura') AS t")["t"]),
         "tabela nota_leitura")

    print("== a base, depois de tudo ==")
    b = banco.um("""SELECT (SELECT count(*) FROM ligacao) AS ligacoes,
                           (SELECT count(*) FROM ligacao_gravacao) AS gravacoes,
                           (SELECT count(*) FROM ligacao WHERE pc LIKE 'importado:%%')
                             AS importadas,
                           (SELECT count(*) FROM mensagem WHERE evento IS NOT NULL)
                             AS eventos,
                           (SELECT count(*) FROM nota_leitura) AS vistos,
                           (SELECT count(*) FROM conversa) AS conversas""")
    print(f"       {dict(b)}")
    # ⚠️ O NUMERO NAO E FIXO, e nao deve ser: a base CRESCE a cada operador
    # alistado. Em 15/10 de manha eram 28/19 (so o Iago); a tarde viraram
    # 144/19, porque a Claudia subiu 116 ligacoes SEM gravacao -- coerente com
    # o aviso de que a gravacao automatica dela esta desligada. O que se checa
    # e a coerencia, nao um numero decorado.
    diga(b["ligacoes"] >= 28, f"ligacoes nao diminuiram ({b['ligacoes']})")
    diga(b["gravacoes"] >= 19, f"gravacoes nao diminuiram ({b['gravacoes']})")
    diga(b["importadas"] == 0, "nenhuma ligacao importada (o import de teste gravou zero)")

    print("== residuo de teste na base ==")
    residuo = banco.um(
        """SELECT (SELECT count(*) FROM atendente WHERE login LIKE 'zz_teste%%') AS atendentes,
                  (SELECT count(*) FROM cliente WHERE nome LIKE 'Zz Teste%%') AS clientes,
                  (SELECT count(*) FROM ligacao WHERE ramal LIKE '99%%') AS ligacoes,
                  (SELECT count(*) FROM agente_ligacao WHERE ramal LIKE '99%%') AS agentes,
                  (SELECT count(*) FROM conversa
                    WHERE telefone_e164 LIKE '+55189777%%') AS conversas""")
    print(f"       {dict(residuo)}")
    diga(all(v == 0 for v in residuo.values()), "zero residuo de teste")

    print("== agentes vivos ==")
    for r in banco.varios(
            """SELECT g.ramal, a.nome, g.id, g.ultimo_pc, g.ultimo_aviso
                 FROM agente_ligacao g JOIN atendente a ON a.id = g.atendente_id
                WHERE g.revogado_em IS NULL ORDER BY g.ramal"""):
        aviso = f"  !! {r['ultimo_aviso']}" if r["ultimo_aviso"] else ""
        print(f"       ramal {r['ramal']} {r['nome']} (agente {r['id']}, PC {r['ultimo_pc']}){aviso}")
    vivos = banco.um("SELECT count(*) AS n FROM agente_ligacao WHERE revogado_em IS NULL")["n"]
    diga(vivos == 2, f"2 agentes vivos (Iago e Claudia) — achei {vivos}")
finally:
    banco.fechar()

print("== o que o bundle PUBLICADO carrega ==")
js = "".join(f.read_text(encoding="utf-8", errors="ignore")
             for f in DIST.glob("*.js") if "map" not in f.name)
css = "".join(f.read_text(encoding="utf-8", errors="ignore") for f in DIST.glob("*.css"))
tudo = js + css
for nome, marca in [
        ("Bloco 5 — modal de 7 dias", "/ligacoes?dias=7"),
        ("Bloco 6 — outros contatos", "contatos-da-empresa"),
        ("Bloco 7 — rascunho", "movizap.rascunho."),
        ("Bloco 8 — sessao do dia", "sessão do dia"),
        ("Ficha A — cartao da empresa", "gaveta__cartao"),
        ("Ficha A — barra de acoes", "gaveta__acoes"),
        # 🚨 NAO procurar por `ICONE_EVENTO`: e um `const` de modulo, e o
        # minificador o renomeia -- falso negativo garantido. Classe de CSS e
        # string literal sobrevivem ao build.
        ("Bloco 11 — linha do evento", "evento__hora"),
        ("Bloco 11 — icone de assumiu", "bi-hand-index-thumb"),
        ("Bloco 12 — visto por", "balao__visto"),
        ("Bloco 12 — a rota", "/notas/vistas"),
]:
    diga(marca in tudo, nome)
diga("gaveta__fones" not in tudo, "a linha de telefone repetida NAO esta mais la")

print("== cron do vigia ==")
cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
linhas = [l for l in cron.splitlines()
          if "agentes_mudos" in l and not l.strip().startswith("#")]
for l in linhas:
    print(f"       {re.sub(r'  +', ' ', l)[:110]}")
diga(len(linhas) == 2, "duas linhas (08:10 e 18:10)")
diga(sum("--resumo" in l for l in linhas) == 1, "so a das 18:10 tem --resumo")

print("\n" + ("TUDO CONFERIDO" if ok_geral else "HA FALHA ACIMA"))
