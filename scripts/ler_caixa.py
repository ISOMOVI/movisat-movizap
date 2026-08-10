"""Primeira leitura da caixa. Valida com poucas antes do lote."""
import sys

sys.path.insert(0, "/home/claude/movizap_painel")
from movizap import banco, gmail  # noqa: E402

quantas = int(sys.argv[1]) if len(sys.argv) > 1 else 3

banco.abrir()
try:
    print(f"=== lendo {quantas} mensagens, para conferir o formato ===")
    r = gmail.ler(limite=quantas)
    print("resultado:", r)

    print("\n=== RELENDO O ESTADO ===")
    print("marcadores:", banco.um("SELECT count(*) n FROM email_marcador")["n"])
    print("mensagens :", banco.um("SELECT count(*) n FROM email_mensagem")["n"])

    for m in banco.varios(
        "SELECT remetente, left(coalesce(assunto,'-'),44) a, enviado_em::date d,"
        " cliente_id, tem_anexo, length(coalesce(texto,'')) tam"
        " FROM email_mensagem ORDER BY enviado_em DESC LIMIT 6"
    ):
        dono = f"cliente {m['cliente_id']}" if m["cliente_id"] else "nao identificado"
        anexo = " ANEXO" if m["tem_anexo"] else ""
        print(f"  {str(m['d']):11} {str(m['remetente'])[:30]:30} {m['a']:44} "
              f"{m['tam']:5}ch  {dono}{anexo}")

    print("\n=== marcadores ===")
    for x in banco.varios(
        "SELECT nome, natureza FROM email_marcador ORDER BY natureza, nome LIMIT 14"
    ):
        print(f"  {x['natureza']:8} {x['nome']}")

    print("\n=== quantos casaram com o cadastro ===")
    c = banco.um(
        "SELECT count(*) t, count(cliente_id) com FROM email_mensagem")
    print(f"  {c['com']} de {c['t']}")
finally:
    banco.fechar()
