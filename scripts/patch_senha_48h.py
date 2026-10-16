"""A senha de alistamento passa de 1 dia para 48 h (15/10, pedido dele).

🔵 *"essas senhas pode deixa-las com 48hrs a partir da geracao"*.

Continua valendo tudo o que ja estava escrito em `JANELAS_ACEITAS`: quem muda e
a ACEITACAO, nunca a janela de geracao (`JANELA_S = 600`), porque e o
`UNIQUE (ramal, janela)` que faz a senha servir uma vez -- e janela grande
viraria "um alistamento por ramal a cada 48 h".

⚠️ E o custo cresce junto: uma senha ditada e nao usada passa a servir por dois
dias. Ela continua de uso unico e continua so alistando.

Uso: ./venv/bin/python scripts/patch_senha_48h.py [--conferir]
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SO_CONFERIR = "--conferir" in sys.argv

PASSOS = [
    ("movizap/ligacoes_alistar.py", "a aceitação vai de 24 h para 48 h",
     "JANELAS_ACEITAS = 144        # 144 × 10 min = 24 h",
     "JANELAS_ACEITAS = 288        # 288 × 10 min = 48 h (pedido dele, 15/10)"),

    ("movizap/ligacoes_alistar.py", "o docstring diz 48 h",
     """⏱️ **A senha vale 1 DIA** (pedido dele em 15/10). Ela TROCA a cada 10 minutos,""",
     """⏱️ **A senha vale 48 HORAS** (pedido dele em 15/10). Ela TROCA a cada 10 minutos,"""),

    ("tests/teste_ligacoes_alistar.py", "o teste do prazo acompanha",
     """    def test_e_e_aceita_por_um_dia(self):
        assert (ligacoes_alistar.JANELAS_ACEITAS
                * ligacoes_alistar.JANELA_S) == 24 * 3600""",
     """    def test_e_e_aceita_por_48_horas(self):
        assert (ligacoes_alistar.JANELAS_ACEITAS
                * ligacoes_alistar.JANELA_S) == 48 * 3600"""),

    ("tests/teste_ligacoes_alistar.py", "o prazo informado acompanha",
     """    assert r["segundos"] > 20 * 3600""",
     """    assert r["segundos"] > 44 * 3600"""),

    ("tests/teste_ligacoes_alistar.py", "senha de 47 h ainda serve",
     """    def test_senha_de_mais_de_um_dia_nao_serve(self):""",
     """    def test_senha_de_47_horas_ainda_serve(self):
        \"\"\"É o caso dele: deixar as senhas prontas hoje e os operadores
        rodarem o instalador depois de amanhã.\"\"\"
        pessoa("99134")
        import time as _t
        janela = ligacoes_alistar.janela_de(_t.time() - 47 * 3600)
        senha = ligacoes_alistar.senha_da_janela("99134", janela)
        assert ligacoes_alistar.alistar("99134", senha, pedido("99134"),
                                        pc="PC-47H")["ok"]

    def test_senha_de_mais_de_48_horas_nao_serve(self):"""),

    ("tests/teste_ligacoes_alistar.py", "e a de 49 h não",
     """        janela_antiga = ligacoes_alistar.janela_de(_t.time() - 25 * 3600)""",
     """        janela_antiga = ligacoes_alistar.janela_de(_t.time() - 49 * 3600)"""),

    ("tests/teste_ligacoes_alistar.py", "o ramal do teste antigo muda de nome",
     """        pessoa("99131")
        import time as _t""",
     """        pessoa("99131")
        import time as _t  # noqa: F811"""),
]


def aplicar():
    por_arquivo: dict[str, str] = {}
    for rel, nome, velho, novo in PASSOS:
        caminho = RAIZ / rel
        if rel not in por_arquivo:
            por_arquivo[rel] = caminho.read_text(encoding="utf-8")
        texto = por_arquivo[rel]
        if novo in texto:
            print(f"  ja aplicado: {nome}")
            continue
        n = texto.count(velho)
        if n != 1:
            raise SystemExit(f"ANCORA {n}x em {rel} '{nome}': {velho[:60]!r}")
        por_arquivo[rel] = texto.replace(velho, novo, 1)
        print(f"  {'conferido' if SO_CONFERIR else 'aplicado'}: {nome}")
    for rel, texto in por_arquivo.items():
        compile(texto, str(RAIZ / rel), "exec")
    if not SO_CONFERIR:
        for rel, texto in por_arquivo.items():
            (RAIZ / rel).write_text(texto, encoding="utf-8")


aplicar()
