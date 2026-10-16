"""Bloco 4: registra o prefixo de módulo LIG na trava do teste.

O `test_todo_codigo_segue_o_formato` existe para impedir código inventado
passar despercebido: prefixo novo se declara ALI, de propósito. Esta é a
declaração.

Idempotente. Uso: ./venv/bin/python scripts/patch_prefixo_lig.py [--conferir]
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SO_CONFERIR = "--conferir" in sys.argv

DE = '''            # INI entrou em 10/08 com a tela inicial: é a porta de entrada,
            # não atendimento nem cadastro. Prefixo novo se registra AQUI --
            # é este teste que impede código inventado passar despercebido.
            assert modulo in {"INI", "EML", "ATD", "CAD", "CFG", "REL"}, t["codigo"]
'''
PARA = '''            # INI entrou em 10/08 com a tela inicial: é a porta de entrada,
            # não atendimento nem cadastro. Prefixo novo se registra AQUI --
            # é este teste que impede código inventado passar despercebido.
            #
            # LIG entrou em 15/10: ligação do MicroSIP não é conversa de
            # WhatsApp nem cadastro, e a aba é de auditoria -- pendurá-la em
            # ATD faria o log misturar "falou com cliente" e "ligou".
            assert modulo in {"INI", "EML", "ATD", "CAD", "CFG", "LIG", "REL"}, t["codigo"]
'''

alvo = RAIZ / "tests/teste_telas.py"
texto = alvo.read_text(encoding="utf-8")
if '"LIG"' in texto:
    print("já estava: prefixo LIG")
elif DE not in texto:
    raise SystemExit("ÂNCORA NÃO ACHADA: a trava de prefixo")
else:
    if not SO_CONFERIR:
        alvo.write_text(texto.replace(DE, PARA), encoding="utf-8")
    print(f"{'conferido' if SO_CONFERIR else 'aplicado'}: prefixo LIG")
