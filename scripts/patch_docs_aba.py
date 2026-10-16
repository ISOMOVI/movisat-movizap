"""Bloco 4: a aba Ligações nos docs obrigatórios (03 e 06) e na lista do teste.

`tests/teste_telas_documentadas.py` exige o código em `docs/03` E em `docs/06`;
`tests/teste_ajuda_das_telas.py` exige a tela na lista COM_AJUDA.

Idempotente, com âncora conferida.
Uso: ./venv/bin/python scripts/patch_docs_aba.py [--conferir]
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SO_CONFERIR = "--conferir" in sys.argv

D03_TABELA_DE = "| `REL_1.1` | Relatórios | `/relatorios` | `owner` | 3 |\n"
D03_TABELA_PARA = ("| `LIG_1.1` | Ligações | `/ligacoes` | `ligacoes` | 1 |\n"
                   "| `REL_1.1` | Relatórios | `/relatorios` | `owner` | 3 |\n")

D03_ICONE_DE = "| `ATD_6.1` Chat interno | `bi-chat-left-dots` | menu |\n"
D03_ICONE_PARA = ("| `ATD_6.1` Chat interno | `bi-chat-left-dots` | menu |\n"
                  "| `LIG_1.1` Ligações | `bi-telephone` | menu |\n")

D06_SECAO = """
## 15/10 — Ligações do MicroSIP: a aba (LIG_1.1)

🔵 *"considere que vamos precisar de uma aba nova no Movizap para 'Ligações' -
a idéia é um grid simples que tenha as ligações do historico do MicroSip,
consultadas por cliente - ja da base Movizap, ou por Atendente, ou por data ou
por numero, etc, exportar e importar e um botão para baixar a ligação se quiser
ou reproduzir por lá"*.

### A aba Ligações

Grid com uma linha por ligação: quando, sentido (feita, recebida, perdida),
número, cliente, atendente (com o ramal), duração e a gravação. Filtros de
período, atendente, sentido, número e "só com gravação"; paginação de 50.

- **Ouvir e baixar na própria linha.** O áudio vem por `pedirBlob` (o token
  vive no cabeçalho, e `<audio src>` não o manda); arrastar funciona porque o
  blob está inteiro na memória. Um player por vez, e o blob é liberado ao
  trocar ou sair da tela.
- **Exportar CSV** do que está filtrado, com rastro: quem exportou, quando,
  com que filtros e quantas linhas (`ligacao_exportacao`).
- **Faixa de cobertura no topo**, e é ela que impede a tela de mentir por
  omissão: diz quantos atendentes têm agente, com o último contato de cada um,
  e **nomeia quem está de fora**. Sem isso, quem não tem agente instalado
  pareceria não ter ligado. A mesma frase aparece no estado vazio.
- **Cliente em várias empresas** vira "nome +N", nunca uma empresa escolhida
  no lugar das outras. Sem cadastro aparece como "sem cadastro", que é
  diferente de vazio.
- ⚠️ **Não há busca de empresa por nome:** isso é `CAD_1.1`, permissão que
  esta aba não tem. Quando se chega aqui pela ficha de uma conversa, o
  `cliente_id` vem na URL e aparece como chip removível.
- 🚨 **Permissão `ligacoes`, que nenhum perfil lista:** a aba nasce **só do
  owner** (decisão dele, 15/10). Conceder é acrescentar a permissão a um
  perfil, numa linha.
- O **import** que ele pediu junto é o Bloco 9 do plano (retroativo de PC que
  ainda não tinha agente) e não entrou nesta rodada.
"""

ANCORA_06 = "## 28/09 — Plano 4: nota editável, Chat interno com a cara da Caixa, anexos em lote"

AJUDA_DE = '''    "Clientes.vue", "Contatos.vue", "Fila.vue", "Historico.vue",
'''
AJUDA_PARA = '''    "Clientes.vue", "Contatos.vue", "Fila.vue", "Historico.vue",
    "Ligacoes.vue",
'''

PASSOS = [
    ("docs/03: linha da tabela", "docs/03_Registro_Telas.md", D03_TABELA_DE,
     D03_TABELA_PARA, "| `LIG_1.1` | Ligações |"),
    ("docs/03: ícone", "docs/03_Registro_Telas.md", D03_ICONE_DE, D03_ICONE_PARA,
     "| `LIG_1.1` Ligações | `bi-telephone` |"),
    ("teste_ajuda_das_telas: COM_AJUDA", "tests/teste_ajuda_das_telas.py", AJUDA_DE,
     AJUDA_PARA, '"Ligacoes.vue"'),
]

for nome, arquivo, ancora, novo, marca in PASSOS:
    alvo = RAIZ / arquivo
    texto = alvo.read_text(encoding="utf-8")
    if marca in texto:
        print(f"já estava: {nome}")
        continue
    if ancora not in texto:
        raise SystemExit(f"ÂNCORA NÃO ACHADA ({nome}): {ancora[:60]!r}")
    if texto.count(ancora) != 1:
        raise SystemExit(f"ÂNCORA AMBÍGUA ({nome}): {texto.count(ancora)}×")
    if not SO_CONFERIR:
        alvo.write_text(texto.replace(ancora, novo), encoding="utf-8")
    print(f"{'conferido' if SO_CONFERIR else 'aplicado'}: {nome}")

alvo = RAIZ / "docs/06_Conteudo_das_Telas.md"
texto = alvo.read_text(encoding="utf-8")
if "## 15/10 — Ligações do MicroSIP: a aba (LIG_1.1)" in texto:
    print("já estava: docs/06")
elif ANCORA_06 not in texto:
    raise SystemExit("ÂNCORA NÃO ACHADA: docs/06")
else:
    novo = texto.replace(ANCORA_06, D06_SECAO.lstrip("\n") + "\n" + ANCORA_06)
    if not SO_CONFERIR:
        alvo.write_text(novo, encoding="utf-8")
    print(f"{'conferido' if SO_CONFERIR else 'aplicado'}: docs/06")
