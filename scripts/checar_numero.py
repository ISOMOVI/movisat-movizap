"""Pergunta ao Evolution se um numero tem WhatsApp. Somente consulta."""
import sys

sys.path.insert(0, "/home/claude/movizap_painel")
from movizap import banco, evolution, telefone  # noqa: E402

BRUTO = sys.argv[1] if len(sys.argv) > 1 else "5519974140416"

banco.abrir()
try:
    analise = telefone.analisar(BRUTO)
    e164 = analise.e164 if analise else None
    print(f"digitado : {BRUTO}")
    print(f"normalizado: {e164}")

    canal = banco.um(
        "SELECT instancia FROM canal WHERE tipo = 'atendimento' LIMIT 1")
    print(f"instancia : {canal['instancia']}")

    # 🚨 O Evolution responde 200 mesmo para numero que nao existe -- quem diz
    # e o campo `exists`, nunca o codigo de retorno.
    r = evolution._pedir(
        "POST", f"/chat/whatsappNumbers/{canal['instancia']}",
        {"numbers": [e164.lstrip("+")]})
    print(f"\nresposta crua: {r}")

    itens = r if isinstance(r, list) else (r or {}).get("data") or []
    if not itens:
        print("\nO Evolution nao devolveu nada para este numero.")
    for i in itens:
        existe = i.get("exists")
        print(f"\n  TEM WHATSAPP? {'SIM' if existe else 'NAO'}")
        print(f"  jid devolvido: {i.get('jid')}")
        if i.get("number") and e164 and i["number"] not in e164:
            print(f"  ⚠️ o numero devolvido difere do consultado: {i['number']}")

    print("\n=== o que a nossa base ja sabia ===")
    print(banco.varios(
        "SELECT ct.e164, ct.tem_whatsapp, ct.verificado_em, c.nome"
        "  FROM contato_telefone ct JOIN contato c ON c.id = ct.contato_id"
        " WHERE ct.e164 = %s", (e164,)) or "  este numero nao esta no cadastro")

    print("\n=== ja conversou pelo painel? ===")
    print(banco.varios(
        "SELECT id, nome_whatsapp, estado, criada_em FROM conversa"
        " WHERE telefone_e164 = %s", (e164,)) or "  nenhuma conversa")
finally:
    banco.fechar()
