"""Bloco 6: a rota devolve 404 para conversa inexistente, como a rota irma de
ligacoes. Conversa que nao existe e erro de quem chamou, nao lista vazia."""
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "movizap" / "main.py"
t = p.read_text(encoding="utf-8")

VELHO = "    return conversas.contatos_da_empresa(conversa_id)"
NOVO = '''    r = conversas.contatos_da_empresa(conversa_id)
    if r["motivo"] == "conversa_inexistente":
        # 404, e não corpo vazio: é o mesmo trato da rota irmã de ligações --
        # conversa que não existe é erro de quem chamou, não lista vazia.
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")
    return r'''

if NOVO in t:
    print("ja aplicado")
else:
    assert t.count(VELHO) == 1, f"ancora {t.count(VELHO)}x"
    t = t.replace(VELHO, NOVO, 1)
    compile(t, str(p), "exec")
    p.write_text(t, encoding="utf-8")
    print("aplicado")
