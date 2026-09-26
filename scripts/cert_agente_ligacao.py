"""Certificado de cliente do agente de ligações de um PC (Plano 5.1, 25/09).

Uso:
  ./venv/bin/python scripts/cert_agente_ligacao.py --criar-ca
      Cria a CA (uma vez só). Mostra onde ficou o certificado PÚBLICO, que é o
      que vai para o nginx (`/etc/nginx/movizap_ligacoes_ca.crt`).

  ./venv/bin/python scripts/cert_agente_ligacao.py --ramal 3404 --pedido pedido.req --saida pc.cer
      Assina o pedido que o `instalar.ps1` gerou no PC e amarra o certificado
      ao agente VIVO daquele ramal (gere a chave antes). O `.cer` volta ao PC
      (`instalar.ps1 -Concluir`). Certificado novo substitui o anterior.

Nada secreto sai daqui: o pedido e o certificado são públicos; a chave
privada do PC nunca saiu do PC, e a da CA nunca sai de `movizap_ligacoes_ca`.
"""
import argparse
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from movizap import banco, ligacoes_ca  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--criar-ca", action="store_true")
p.add_argument("--ramal")
p.add_argument("--pedido", type=Path)
p.add_argument("--saida", type=Path)
a = p.parse_args()

if a.criar_ca:
    print(f"CA criada. Certificado público: {ligacoes_ca.criar_ca()}")
    sys.exit(0)

if not (a.ramal and a.pedido and a.saida):
    p.error("use --criar-ca, ou --ramal + --pedido + --saida")

banco.abrir()
r = ligacoes_ca.assinar(a.ramal, a.pedido.read_bytes())
a.saida.write_text(r["pem"], encoding="ascii")
quando = r["validade"].astimezone(ZoneInfo("America/Sao_Paulo"))
print(f"Ramal {a.ramal}: certificado emitido (agente {r['agente_id']}), "
      f"vale até {quando:%d/%m/%Y}, impressão {r['cert_sha256'][:16]}…")
print(f"Arquivo para o PC: {a.saida}")
