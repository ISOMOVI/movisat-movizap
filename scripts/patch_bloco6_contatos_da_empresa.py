"""Bloco 6: "Outros contatos" da empresa — consulta sob ATD_1.2 (15/10).

Idempotente, com ancora conferida. Nao reinicia servico e nao faz build.
Uso: ./venv/bin/python scripts/patch_bloco6_contatos_da_empresa.py [--conferir]
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SO_CONFERIR = "--conferir" in sys.argv

# ------------------------------------------------------------- conversas.py
CONV_ANCORA = "def _empresa_da_conversa(conversa: dict) -> dict | None:"
CONV_NOVO = '''def contatos_da_empresa(conversa_id: int) -> dict:
    """Os outros contatos da empresa desta conversa (Bloco 6, 15/10).

    🔵 15/10: na ficha, poder ver os outros contatos da empresa vinculada e
    pular para a conversa de um deles.

    🚨 ROTA IRMÃ, NÃO `/api/clientes/{id}`. A consulta sai sob `ATD_1.2`
    porque é da CONVERSA; `/api/clientes/{id}` é `CAD_1.1`, que o perfil
    `atendimento` não tem desde 10/08 -- a gaveta tomaria 403. É o mesmo
    motivo de `buscar_empresa_para_vincular` existir.

    🚨 CADA TELEFONE É UMA LINHA, não cada contato: contato com dois números
    dá duas linhas, e contato SEM número nenhum aparece mesmo assim, com
    `e164` nulo. Esconder quem não tem número faria a lista afirmar "a empresa
    tem 3 contatos" onde ela tem 5 -- omissão também é tela que mente.

    ⚠️ `tem_whatsapp` tem TRÊS valores, e eles não se confundem: `true` é
    conferido e tem, `false` é conferido e NÃO tem, `None` é nunca conferido.
    O valor vai cru; quem decide o que mostrar é a tela.

    ⚠️ `motivo` existe para a tela não precisar adivinhar por que a lista veio
    vazia: número sem cadastro é diferente de empresa sem outro contato.
    """
    conversa = banco.um(
        "SELECT contato_id, telefone_e164 FROM conversa WHERE id = %s",
        (conversa_id,))
    if not conversa:
        return {"cliente": None, "contatos": [], "motivo": "conversa_inexistente"}
    if not conversa["contato_id"]:
        return {"cliente": None, "contatos": [], "motivo": "sem_cadastro"}

    pessoa = cadastro.contato(conversa["contato_id"])
    if not pessoa or not pessoa.get("cliente_id"):
        return {"cliente": None, "contatos": [], "motivo": "contato_sem_empresa"}

    empresa = cadastro.cliente(pessoa["cliente_id"])
    if not empresa:
        return {"cliente": None, "contatos": [], "motivo": "contato_sem_empresa"}

    atual = conversa["contato_id"]
    linhas = []
    for c in empresa.get("contatos") or []:
        base = {"contato_id": c["id"], "nome": c["nome"],
                "papeis": c.get("papeis") or [],
                "este_contato": c["id"] == atual}
        telefones = c.get("telefones") or []
        if not telefones:
            linhas.append({**base, "telefone_id": None, "e164": None,
                           "bruto": None, "principal": False,
                           "tem_whatsapp": None, "esta_conversa": False})
            continue
        for t in telefones:
            linhas.append({**base, "telefone_id": t["id"], "e164": t["e164"],
                           "bruto": t.get("bruto"),
                           "principal": bool(t.get("principal")),
                           "tem_whatsapp": t.get("tem_whatsapp"),
                           "esta_conversa": bool(conversa["telefone_e164"]
                                                 and t["e164"] == conversa["telefone_e164"])})

    # O contato DESTA conversa primeiro, depois por nome: quem abre o modal
    # está perguntando "quem mais existe além de quem eu estou atendendo".
    linhas.sort(key=lambda l: (not l["este_contato"], (l["nome"] or "").lower(),
                               not l["principal"], l["e164"] or ""))

    return {"cliente": {"id": empresa["id"], "nome": empresa["nome"],
                        "nome_fantasia": empresa.get("nome_fantasia"),
                        "ativo": empresa.get("ativo")},
            "contatos": linhas, "motivo": None}


'''

# ----------------------------------------------------------------- main.py
MAIN_ANCORA = '''@app.get("/api/conversas/{conversa_id}/ligacoes")'''
MAIN_NOVO = '''@app.get("/api/conversas/{conversa_id}/contatos-da-empresa")
def contatos_da_empresa_da_conversa(
        conversa_id: int,
        usuario: dict = Depends(auth.requer_tela("ATD_1.2"))):
    """Os outros contatos da empresa vinculada a esta conversa (Bloco 6, 15/10).

    🚨 `ATD_1.2` de propósito, como a rota de empresas e a de ligações: é
    consulta da conversa. A rota de cadastro (`/api/clientes/{id}`) é
    `CAD_1.1` e daria 403 justamente para quem atende.

    ⚠️ Lista vazia vem com `motivo` -- "sem_cadastro" não é a mesma coisa que
    "empresa sem outro contato", e a tela precisa dizer qual é o caso.
    """
    return conversas.contatos_da_empresa(conversa_id)


'''


def aplicar(caminho: Path, ancora: str, novo: str, marca: str) -> str:
    texto = caminho.read_text(encoding="utf-8")
    if marca in texto:
        return f"ja aplicado: {caminho.name}"
    if ancora not in texto:
        raise SystemExit(f"ANCORA NAO ENCONTRADA em {caminho.name}: {ancora[:60]!r}")
    if texto.count(ancora) != 1:
        raise SystemExit(f"ancora ambigua em {caminho.name} ({texto.count(ancora)}x)")
    candidato = texto.replace(ancora, novo + ancora, 1)
    # Validar ANTES de gravar, nunca depois (abertura, item 8).
    compile(candidato, str(caminho), "exec")
    if not SO_CONFERIR:
        caminho.write_text(candidato, encoding="utf-8")
    return f"{'conferido' if SO_CONFERIR else 'aplicado'}: {caminho.name}"


print(aplicar(RAIZ / "movizap" / "conversas.py", CONV_ANCORA, CONV_NOVO,
              "def contatos_da_empresa("))
print(aplicar(RAIZ / "movizap" / "main.py", MAIN_ANCORA, MAIN_NOVO,
              "contatos-da-empresa"))
