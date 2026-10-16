"""Separa o cron do vigia em duas linhas: 08:10 sem resumo, 18:10 com (15/10).

🔵 *"se quer resumo diario do vigia quando esta tudo em dia"* -> aprovado.

⚠️ UMA VEZ POR DIA. A linha unica rodava as 08:10 e as 18:10; se o resumo
fosse nela, ele viraria DUAS mensagens diarias para sempre. O resumo sai so na
passada da tarde, quando os dois horarios dos PCs ja passaram.

Idempotente: mostra o antes e o depois, e nao mexe em mais nenhuma linha do
crontab.
Uso: ./venv/bin/python scripts/cron_vigia_resumo.py [--conferir]
"""
import subprocess
import sys

SO_CONFERIR = "--conferir" in sys.argv
BASE = ("cd /home/claude/movizap_painel && PYTHONPATH=. venv/bin/python "
        "scripts/agentes_mudos.py --avisar-whatsapp")
LOG = ">> /home/claude/logs/movizap_ligacoes_vigia.log 2>&1"
VELHA = f"10 8,18 * * * {BASE} {LOG}"
NOVAS = [
    f"# 08:10: so alerta. Nada errado = silencio, que e o que faz o alerta ser alerta.",
    f"10 8 * * * {BASE} {LOG}",
    f"# 18:10: alerta e, nao havendo nada errado, o RESUMO do dia (pedido dele,",
    f"# 15/10). Uma vez por dia, nunca duas.",
    f"10 18 * * * {BASE} --resumo {LOG}",
]

atual = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
linhas = atual.splitlines()

if any("--resumo" in l for l in linhas):
    print("ja aplicado: o cron das 18:10 ja tem --resumo")
    sys.exit(0)

if VELHA not in linhas:
    print("LINHA ANTIGA NAO ENCONTRADA. O crontab de hoje:")
    for l in linhas:
        if "agentes_mudos" in l:
            print(f"  {l}")
    sys.exit(1)

i = linhas.index(VELHA)
novo = linhas[:i] + NOVAS + linhas[i + 1:]

print("--- antes ---")
print(f"  {VELHA}")
print("--- depois ---")
for l in NOVAS:
    print(f"  {l}")

if SO_CONFERIR:
    print("(nada instalado)")
    sys.exit(0)

texto = "\n".join(novo) + "\n"
r = subprocess.run(["crontab", "-"], input=texto, capture_output=True, text=True)
if r.returncode:
    print("FALHOU:", r.stderr)
    sys.exit(1)
print("instalado. conferindo:")
for l in subprocess.run(["crontab", "-l"], capture_output=True,
                        text=True).stdout.splitlines():
    if "agentes_mudos" in l:
        print(f"  {l}")
