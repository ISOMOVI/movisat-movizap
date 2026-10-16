"""Bloco 2: a variável do número que recebe o aviso do vigia das ligações.

Idempotente, com âncora conferida. Não reinicia serviço.
Uso: ./venv/bin/python scripts/patch_config_aviso.py [--conferir]
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SO_CONFERIR = "--conferir" in sys.argv

ANCORA = '    ligacoes_senha_segredo: str = _ler("MOVIZAP_LIGACOES_SENHA_SEGREDO")\n'
NOVO = '''
    # 🔵 15/10: *"Rotina da VPS verifica se os envios estão sendo feito
    # corretamente"*. Quem recebe o aviso do vigia (`scripts/agentes_mudos.py
    # --avisar-whatsapp`, no cron das 08:10 e 18:10). Vazio = não envia, só
    # imprime -- é o que mantém o gancho da sessão funcionando sem mandar
    # mensagem para ninguém.
    ligacoes_aviso_numero: str = _ler("MOVIZAP_LIGACOES_AVISO_NUMERO")
'''

alvo = RAIZ / "movizap/config.py"
texto = alvo.read_text(encoding="utf-8")
if "ligacoes_aviso_numero" in texto:
    print("já estava: ligacoes_aviso_numero")
elif ANCORA not in texto:
    raise SystemExit(f"ÂNCORA NÃO ACHADA: {ANCORA!r}")
elif texto.count(ANCORA) != 1:
    raise SystemExit(f"ÂNCORA AMBÍGUA: {texto.count(ANCORA)}×")
else:
    texto = texto.replace(ANCORA, ANCORA + NOVO)
    if not SO_CONFERIR:
        alvo.write_text(texto, encoding="utf-8")
    print(f"{'conferido' if SO_CONFERIR else 'aplicado'}: ligacoes_aviso_numero")
