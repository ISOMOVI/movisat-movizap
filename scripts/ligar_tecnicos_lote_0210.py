"""Liga conversas soltas ao tecnico importado em 02/10 com o mesmo numero.

Uso: ligar_tecnicos.py CONVERSA:CONTATO [CONVERSA:CONTATO ...]
Passa pela mesma funcao da tela (conversas.vincular com contato_id) e
so age se a conversa continua sem contato e o numero responde por
EXATAMENTE aquele contato. Confirma relendo o banco, nunca pelo retorno.
"""
import sys
sys.path.insert(0, "/home/claude/movizap_painel")
from movizap import banco, cadastro, conversas  # noqa: E402

banco.abrir()
ok = pulou = 0
for par in sys.argv[1:]:
    conversa_id, contato_id = (int(x) for x in par.split(":"))
    conv = banco.um("SELECT id, contato_id, telefone_e164, tipo FROM conversa WHERE id = %s",
                    (conversa_id,))
    if not conv or conv["contato_id"] is not None or conv["tipo"] == "grupo":
        print(f"PULOU {conversa_id}: estado mudou ({conv})"); pulou += 1; continue
    cands = [c["id"] for c in cadastro.por_telefone(conv["telefone_e164"])]
    if cands != [contato_id]:
        print(f"PULOU {conversa_id}: candidatos {cands} != [{contato_id}]"); pulou += 1; continue
    r = conversas.vincular(conversa_id, contato_id=contato_id)
    depois = banco.um("SELECT contato_id FROM conversa WHERE id = %s", (conversa_id,))
    rel = banco.um("SELECT nome, relacao FROM contato WHERE id = %s", (contato_id,))
    if depois["contato_id"] == contato_id:
        print(f"LIGOU {conversa_id} {conv['telefone_e164']} -> {contato_id} {rel['nome']} ({rel['relacao']})"); ok += 1
    else:
        print(f"FALHOU {conversa_id}: retorno={r} banco={depois}"); pulou += 1
print(f"total: {ok} ligadas, {pulou} puladas/falhas")
