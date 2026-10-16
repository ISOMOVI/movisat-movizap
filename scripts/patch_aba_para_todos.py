"""A aba Ligações passa a ser de quem atende (decisão dele, 15/10).

🔵 *"pode exibir a aba para todos"*.

Como: a tela troca a permissão PRÓPRIA (`ligacoes`, que nenhum perfil listava)
pela permissão **`atendimento`**. Assim ela entra para `atendimento` e `admin`
sem tocar em `PERFIS` -- e sem furar o
`test_admin_ve_exatamente_o_que_ele_decidiu`, que guarda a frase dele de 24/09
como conjunto FECHADO e cuja própria docstring diz: *"tela nova de atendimento
entra sozinha (é a permissão)"*.

⚠️ Quem fica de fora: o perfil `cadastro` (que só vê CAD_1.1 e CAD_1.2). Se ele
quiser lá também, é acrescentar `ligacoes` ao perfil -- mas aí volta a ser
permissão própria.

🚨 Consequência que tem de estar escrita: **todo atendente passa a poder ouvir
e baixar a gravação de qualquer ligação, e exportar o CSV.** O rastro de quem
exporta (`ligacao_exportacao`) deixa de ser detalhe e passa a ser a única
resposta para "quem levou o quê".

Idempotente. Uso: ./venv/bin/python scripts/patch_aba_para_todos.py [--conferir]
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SO_CONFERIR = "--conferir" in sys.argv

TELAS_DE = '''        # 🚨 PERMISSÃO PRÓPRIA, e NENHUM perfil em PERFIS a lista: a aba nasce
        # **só do owner**, que é a decisão dele de 15/10. Conceder depois é
        # acrescentar "ligacoes" a um perfil -- uma linha.
        #
        # ⚠️ Módulo novo (LIG): `MenuLateral.NOME_DO_MODULO` precisa conhecê-lo,
        # senão o menu mostra o prefixo cru.
        "codigo": "LIG_1.1",
        "titulo": "Ligações",
        "rota": "/ligacoes",
        "icone": "bi-telephone",
        "descricao": "Ligações do MicroSIP: por cliente, atendente, data ou número.",
        "permissao": "ligacoes",
'''
TELAS_PARA = '''        # 🚨 NASCEU SÓ DO OWNER E DUROU UM DIA. Em 15/10, poucas horas depois:
        # *"pode exibir a aba para todos"*. Virou permissão `atendimento` em
        # vez de permissão própria concedida a cada perfil, porque é isso que
        # o `test_admin_ve_exatamente_o_que_ele_decidiu` prevê ("tela nova de
        # atendimento entra sozinha -- é a permissão"): o conjunto fechado do
        # admin, que guarda a frase dele de 24/09, continua intacto.
        #
        # ⚠️ Fica de fora o perfil `cadastro` (só CAD_1.1/CAD_1.2). Se for para
        # lá também, volta a ser permissão própria, concedida perfil a perfil.
        #
        # 🚨 Todo atendente passa a poder OUVIR, BAIXAR e EXPORTAR. O rastro de
        # `ligacao_exportacao` deixa de ser detalhe: é a única resposta para
        # "quem levou o quê".
        #
        # ⚠️ Módulo novo (LIG): `MenuLateral.NOME_DO_MODULO` precisa conhecê-lo,
        # senão o menu mostra o prefixo cru.
        "codigo": "LIG_1.1",
        "titulo": "Ligações",
        "rota": "/ligacoes",
        "icone": "bi-telephone",
        "descricao": "Ligações do MicroSIP: por cliente, atendente, data ou número.",
        "permissao": "atendimento",
'''

D03_DE = "| `LIG_1.1` | Ligações | `/ligacoes` | `ligacoes` | 1 |\n"
D03_PARA = "| `LIG_1.1` | Ligações | `/ligacoes` | `atendimento` | 1 |\n"

D03_PERFIL_DE = "| `atendimento` | `atendimento` | `INI_1.1` `ATD_1.*` `ATD_5.1` `ATD_6.1` `EML_1.1` `CFG_0.1` › `CFG_10.1` `CFG_11.1` `CFG_12.1` |\n"
D03_PERFIL_PARA = "| `atendimento` | `atendimento` | `INI_1.1` `ATD_1.*` `ATD_5.1` `ATD_6.1` `LIG_1.1` `EML_1.1` `CFG_0.1` › `CFG_10.1` `CFG_11.1` `CFG_12.1` |\n"

D06_DE = """- 🚨 **Permissão `ligacoes`, que nenhum perfil lista:** a aba nasce **só do
  owner** (decisão dele, 15/10). Conceder é acrescentar a permissão a um
  perfil, numa linha.
"""
D06_PARA = """- 🚨 **Nasceu só do owner e durou um dia.** Horas depois, em 15/10: *"pode
  exibir a aba para todos"*. Passou à permissão **`atendimento`** — todo
  atendente (e o admin) vê a aba, ouve, baixa e exporta. Fica de fora só o
  perfil `cadastro`. É por isso que o rastro de `ligacao_exportacao` deixou de
  ser detalhe: com a aba aberta a todos, ele é a única resposta para "quem
  levou o quê".
"""

VUE_DE = """   ⚠️ O filtro por CLIENTE não é um campo de busca de empresa: buscar empresa
   por nome é `CAD_1.1`, permissão que esta aba não tem (e a aba nasce só do
   owner). Quando se chega aqui a partir da ficha de uma conversa, o
   `cliente_id` vem na URL e aparece como chip removível. Por número, a busca
   aceita pedaço ("9811").
"""
VUE_PARA = """   ⚠️ O filtro por CLIENTE não é um campo de busca de empresa: buscar empresa
   por nome é `CAD_1.1`, permissão que esta aba não tem. Quando se chega aqui a
   partir da ficha de uma conversa, o `cliente_id` vem na URL e aparece como
   chip removível. Por número, a busca aceita pedaço ("9811").

   🚨 A aba nasceu só do owner e, horas depois, ele disse *"pode exibir a aba
   para todos"*: hoje é permissão `atendimento`. Ou seja, qualquer atendente
   ouve e baixa gravação de qualquer ligação — e exporta. Quem exportou fica
   registrado.
"""

TESTE_DE = '''    def test_o_grid_responde_ao_owner_e_nega_o_atendimento(self):
        r = self.owner.get(f"/api/ligacoes?ramal={RAMAL}")
        assert r.status_code == 200, r.text
        assert r.json()["total"] == 4
        # 403, não 404: a aba existe, a pessoa é que não tem.
        assert self.atendente.get("/api/ligacoes").status_code == 403
'''
TESTE_PARA = '''    def test_o_grid_responde_a_quem_atende_e_nega_o_resto(self):
        """🔵 15/10, horas depois de a aba nascer: *"pode exibir a aba para
        todos"*. Virou permissão `atendimento` — então quem atende entra, e o
        perfil `cadastro` (que só vê clientes e contatos) continua fora."""
        for cliente in (self.owner, self.atendente):
            r = cliente.get(f"/api/ligacoes?ramal={RAMAL}")
            assert r.status_code == 200, r.text
            assert r.json()["total"] == 4
        # 403, não 404: a aba existe, a pessoa é que não tem.
        assert self.cadastro.get("/api/ligacoes").status_code == 403
'''

TESTE_CENA_DE = '''        for login, perfil in ((LOGIN + "owner", "owner"), (LOGIN + "atd", "atendimento")):
'''
TESTE_CENA_PARA = '''        for login, perfil in ((LOGIN + "owner", "owner"), (LOGIN + "atd", "atendimento"),
                              (LOGIN + "cad", "cadastro")):
'''

TESTE_CLIENTE_DE = '''        self.atendente = TestClient(main.app)
        self.atendente.headers.update(
            {"Authorization": f"Bearer {auth.criar_token(LOGIN + 'atd')}"})
'''
TESTE_CLIENTE_PARA = '''        self.atendente = TestClient(main.app)
        self.atendente.headers.update(
            {"Authorization": f"Bearer {auth.criar_token(LOGIN + 'atd')}"})
        self.cadastro = TestClient(main.app)
        self.cadastro.headers.update(
            {"Authorization": f"Bearer {auth.criar_token(LOGIN + 'cad')}"})
'''

PASSOS = [
    ("telas.py: permissão atendimento", "movizap/telas.py", TELAS_DE, TELAS_PARA,
     '"permissao": "atendimento",\n    },\n    {\n        "codigo": "REL_1.1"'),
    ("docs/03: tabela", "docs/03_Registro_Telas.md", D03_DE, D03_PARA,
     "| `LIG_1.1` | Ligações | `/ligacoes` | `atendimento` |"),
    ("docs/03: linha do perfil atendimento", "docs/03_Registro_Telas.md",
     D03_PERFIL_DE, D03_PERFIL_PARA, "`ATD_6.1` `LIG_1.1`"),
    ("docs/06: a permissão", "docs/06_Conteudo_das_Telas.md", D06_DE, D06_PARA,
     "Nasceu só do owner e durou um dia"),
    ("Ligacoes.vue: o cabeçalho", "frontend/src/telas/Ligacoes.vue", VUE_DE, VUE_PARA,
     "pode exibir a aba\n   para todos"),
    ("teste: a cena ganha o perfil cadastro", "tests/teste_ligacoes_consulta.py",
     TESTE_CENA_DE, TESTE_CENA_PARA, 'LOGIN + "cad", "cadastro"'),
    ("teste: o cliente do perfil cadastro", "tests/teste_ligacoes_consulta.py",
     TESTE_CLIENTE_DE, TESTE_CLIENTE_PARA, "self.cadastro = TestClient"),
    ("teste: quem entra e quem não", "tests/teste_ligacoes_consulta.py",
     TESTE_DE, TESTE_PARA, "test_o_grid_responde_a_quem_atende_e_nega_o_resto"),
]

for nome, arquivo, ancora, novo, marca in PASSOS:
    alvo = RAIZ / arquivo
    texto = alvo.read_text(encoding="utf-8")
    if marca in texto:
        print(f"já estava: {nome}")
        continue
    if ancora not in texto:
        raise SystemExit(f"ÂNCORA NÃO ACHADA ({nome}): {ancora[:70]!r}")
    if texto.count(ancora) != 1:
        raise SystemExit(f"ÂNCORA AMBÍGUA ({nome}): {texto.count(ancora)}×")
    if not SO_CONFERIR:
        alvo.write_text(texto.replace(ancora, novo), encoding="utf-8")
    print(f"{'conferido' if SO_CONFERIR else 'aplicado'}: {nome}")
