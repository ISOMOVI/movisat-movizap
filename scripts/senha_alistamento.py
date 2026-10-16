"""A senha de alistamento de um ramal — a ferramenta dele (15/10/2026).

🔵 *"validar o atendente do MicroSip com uma senha que será gerada sempre via
algoritmo e é mutável para rodar"* e *"se trocarem de PC é só executar
novamente e me pedir a senha de uso"*.

Uso:
  ./venv/bin/python scripts/senha_alistamento.py --ramal 3404
      A senha da janela atual daquele ramal. É só ditar.

  ./venv/bin/python scripts/senha_alistamento.py --ramal 124 --nome "Claudia"
      Para quem ainda não tem ramal: amarra o ramal à pessoa e devolve a senha.
      (Um ramal é de uma pessoa só; se já for de outra, ele recusa e diz de quem.)

A senha vale no máximo 10 minutos (20 no pior caso de relógio torto) e **só
pode ser usada uma vez**. Se passar do tempo, rode de novo: a senha muda.

🚨 ESTA SENHA SÓ ALISTA. Ela não serve para o batimento nem para o envio —
depois de alistado, o PC trabalha com a chave e o certificado dele. E nada
secreto fica neste comando: a senha é derivada na hora, e não se guarda em
lugar nenhum.

Substitui o `Preparar operador` e o `Assinar pedido` do kit: a chave e o
certificado passam a nascer no próprio alistamento, no PC da pessoa.
"""
import argparse
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from movizap import banco, ligacoes_alistar  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--ramal", required=True, help="o ramal que apareceu no 'Testar' do PC")
p.add_argument("--nome", help="só na primeira vez: a quem este ramal pertence")
a = p.parse_args()

banco.abrir()
r = ligacoes_alistar.preparar(a.ramal, a.nome)

print(f"Ramal {r['ramal']} — {r['atendente']}")
print()
print(f"    SENHA:  {r['senha']}")
print()
# 🔵 15/10: a senha passou a valer 1 dia, então "min" sozinho não serve mais.
horas, resto = divmod(max(0, r["segundos"]), 3600)
minutos, segundos = divmod(resto, 60)
quanto = (f"{horas} h {minutos:02d} min" if horas
          else f"{minutos} min {segundos:02d} s")
print(f"Vale por {quanto}. Depois disso, rode de novo.")
print("Serve UMA VEZ: a primeira utilizacao a queima.")
if r["pc_atual"]:
    quando = r["pc_atual_em"]
    visto = (quando.astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M")
             if quando else "nunca falou")
    print(f"⚠️  Este ramal já está no PC {r['pc_atual']} (último contato: {visto}).")
    print("    Alistar em outro PC REVOGA esse, e ele para de enviar.")
print()
print("No PC da pessoa: dois cliques em 'MoviZap-Instalar-Ligacoes.exe' e digitar a senha.")
