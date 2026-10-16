"""Bloco 11: as tres acoes de CADASTRO registram o evento na ROTA (15/10).

🚨 POR QUE AQUI E NAO NA FUNCAO. `vincular`, `desvincular` e `definir_tipo` nao
recebem quem agiu -- elas tratam de cadastro, nao de posse da conversa. Mudar
as tres assinaturas mexeria em todo mundo que as chama (inclusive o sync e a
automacao, que nao tem atendente nenhum para informar). A rota, ao contrario,
tem o `usuario` na mao. Log sem autor nao serve para log de acoes, entao o
evento sai de onde o autor existe.

⚠️ Aqui o evento fica FORA da transacao da acao -- que ja terminou quando a
rota responde --, e e por isso que nao precisa de `cur`.

Idempotente. Uso: ./venv/bin/python scripts/patch_bloco11_rotas.py [--conferir]
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ALVO = RAIZ / "movizap" / "main.py"
SO_CONFERIR = "--conferir" in sys.argv

PASSOS = [
    ("vincular: o evento na conversa",
     """        " [FICHA NOVA]" if resultado.get("criou_contato") else "",
    )
    return resultado""",
     """        " [FICHA NOVA]" if resultado.get("criou_contato") else "",
    )
    # 🔵 15/10, Bloco 11: além do journal em arquivo, o log DENTRO da conversa
    # -- é lá que quem atende vai perguntar "quem ligou este número a esta
    # empresa?", e não num log do servidor que ele não abre.
    conversas.registrar_evento(
        conversa_id, "vinculou",
        "vinculou o número a " + (resultado.get("cliente_nome")
                                  or resultado.get("contato_nome") or "um cadastro"),
        _atendente_do_usuario(usuario))
    return resultado"""),

    ("desvincular: o evento na conversa",
     """        resultado.get("contato_nome") or "—", resultado.get("contato_id"),
        resultado.get("cliente_nome") or "—",
    )
    return resultado""",
     """        resultado.get("contato_nome") or "—", resultado.get("contato_id"),
        resultado.get("cliente_nome") or "—",
    )
    conversas.registrar_evento(
        conversa_id, "desvinculou",
        "desfez o vínculo com " + (resultado.get("cliente_nome")
                                   or resultado.get("contato_nome") or "o cadastro"),
        _atendente_do_usuario(usuario))
    return resultado"""),
]

TIPO_ANCORA = """    r = conversas.definir_tipo(conversa_id, dados.relacao)
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("motivo"))"""
TIPO_NOVO = """    r = conversas.definir_tipo(conversa_id, dados.relacao)
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("motivo"))
    # 🔵 15/10, Bloco 11. O tipo decide se a automação e a IA atendem esta
    # pessoa (CFG_5.1): mudá-lo sem rastro deixava a conversa sem explicação
    # para "por que a automação parou de responder aqui?".
    conversas.registrar_evento(
        conversa_id, "mudou_tipo", f"mudou o tipo para {dados.relacao}",
        _atendente_do_usuario(usuario))"""


def aplicar():
    texto = ALVO.read_text(encoding="utf-8")
    feitos, pulados = [], []
    for nome, velho, novo in PASSOS + [("definir_tipo: o evento na conversa",
                                        TIPO_ANCORA, TIPO_NOVO)]:
        if novo in texto:
            pulados.append(nome)
            continue
        n = texto.count(velho)
        if n != 1:
            raise SystemExit(f"ANCORA {n}x em '{nome}': {velho[:70]!r}")
        texto = texto.replace(velho, novo, 1)
        feitos.append(nome)
    compile(texto, str(ALVO), "exec")
    if not SO_CONFERIR and feitos:
        ALVO.write_text(texto, encoding="utf-8")
    for n in feitos:
        print(f"  {'conferido' if SO_CONFERIR else 'aplicado'}: {n}")
    for n in pulados:
        print(f"  ja aplicado: {n}")


aplicar()
