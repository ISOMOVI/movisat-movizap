"""O alerta do Claude Code: agentes de ligação sem contato há mais de 24 h.

🔵 *"se ficar mais 1 dia sem comunicar com VPS, tenhamos um alerta pelo meu
shell, inicialmente"* -- o gancho `SessionStart` do Claude Code roda isto por
ssh ao abrir a sessão.

🚨 EM SILÊNCIO QUANDO ESTÁ TUDO EM DIA: nenhuma linha impressa. O gancho
coloca na sessão o que sair daqui, e aviso que aparece todo dia vira aviso
que ninguém lê.
"""
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging  # noqa: E402
logging.disable(logging.CRITICAL)  # o log do pool não pode sujar a saída

from movizap import banco, ligacoes  # noqa: E402

try:
    banco.abrir()
    mudos = ligacoes.agentes_mudos()
    avisos = ligacoes.agentes_com_aviso()
    vencendo = ligacoes.certs_vencendo()
except Exception as e:  # noqa: BLE001
    print(f"ALERTA MoviZap Ligações: não consegui consultar os agentes ({e.__class__.__name__}).")
    sys.exit(0)

br = ZoneInfo("America/Sao_Paulo")

# PC que fala, mas trouxe erro ou aviso (gravação desligada, arquivo pulado...).
for m in avisos:
    texto = " | ".join(x for x in (m["ultimo_erro"], m["ultimo_aviso"]) if x)
    print(f"AVISO MoviZap Ligações: ramal {m['ramal']} ({m['operador']}), "
          f"PC {m['ultimo_pc'] or '?'}: {texto}")

# Certificado do PC vencendo: vencido, o nginx recusa e o PC fica mudo.
for m in vencendo:
    print(f"AVISO MoviZap Ligações: o certificado do ramal {m['ramal']} ({m['operador']}) "
          f"vence em {m['cert_validade'].astimezone(br):%d/%m/%Y}: emitir outro.")

if not mudos:
    sys.exit(0)

print(f"ALERTA MoviZap Ligações: {len(mudos)} PC(s) sem falar com a VPS há mais de "
      f"{ligacoes.HORAS_MUDO} h (as gravações deles não estão tendo backup):")
for m in mudos:
    if m["ultimo_contato_em"]:
        desde = m["ultimo_contato_em"].astimezone(br)
        horas = (datetime.now(br) - desde).total_seconds() / 3600
        quando = f"último contato {desde:%d/%m %H:%M} ({horas:.0f} h atrás)"
    else:
        quando = f"NUNCA falou (chave criada em {m['criado_em'].astimezone(br):%d/%m %H:%M})"
    extra = f" | último erro: {m['ultimo_erro']}" if m["ultimo_erro"] else ""
    print(f"  - ramal {m['ramal']} ({m['operador']}), PC {m['ultimo_pc'] or '?'}: {quando}{extra}")
