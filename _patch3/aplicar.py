"""Aplicador de trocas ancoradas em texto, para o FPSL (16/10/2026).

Cada troca vive em DOIS arquivos de texto puro (`*_antes.txt` e `*_depois.txt`),
listados no `manifesto.txt`. Assim nÃ£o hÃ¡ aspas escapadas dentro de aspas
escapadas -- a armadilha que fez a primeira tentativa deste patch morrer no
shell.

Uso, de dentro de /home/claude/movizap_painel:
    venv/bin/python _patch/aplicar.py

Regras:
  Â· a Ã¢ncora tem de aparecer EXATAMENTE uma vez, senÃ£o o script para sem tocar
    em nada;
  Â· se o resultado jÃ¡ estiver no arquivo, a troca Ã© pulada (rodar duas vezes
    nÃ£o duplica);
  Â· backup `.bak_2026-10-16_log` por arquivo, sÃ³ na primeira vez.
"""
import pathlib
import shutil
import sys

AQUI = pathlib.Path(__file__).resolve().parent
RAIZ = pathlib.Path("/home/claude/movizap_painel")
SELO = ".bak_2026-10-16_log"

feitos, pulados = [], []

for linha in (AQUI / "manifesto.txt").read_text(encoding="utf-8").splitlines():
    linha = linha.strip()
    if not linha or linha.startswith("#"):
        continue
    rel, antes_arq, depois_arq, apelido = [x.strip() for x in linha.split("|")]
    alvo = RAIZ / rel
    if not alvo.exists():
        print(f"PARO: {rel} nÃ£o existe")
        sys.exit(1)
    antes = (AQUI / antes_arq).read_text(encoding="utf-8")
    depois = (AQUI / depois_arq).read_text(encoding="utf-8")
    texto = alvo.read_text(encoding="utf-8")

    # Marca de "jÃ¡ aplicado": a primeira linha nÃ£o-vazia do resultado que nÃ£o
    # exista na Ã¢ncora. Ã‰ o que torna o script repetÃ­vel.
    marca = next((l for l in depois.splitlines()
                  if l.strip() and l not in antes), None)
    if marca and marca in texto:
        pulados.append(apelido)
        continue
    if texto.count(antes) != 1:
        print(f"PARO: Ã¢ncora de '{apelido}' aparece {texto.count(antes)}x em {rel}")
        sys.exit(1)
    bak = alvo.with_name(alvo.name + SELO)
    if not bak.exists():
        shutil.copy2(alvo, bak)
    alvo.write_text(texto.replace(antes, depois), encoding="utf-8")
    feitos.append(apelido)

print("APLICADOS:")
for f in feitos:
    print("  +", f)
if pulados:
    print("jÃ¡ estavam aplicados:")
    for p in pulados:
        print("  =", p)
if not feitos:
    print("  (nenhuma troca nova)")

