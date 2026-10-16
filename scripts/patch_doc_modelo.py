"""docs/02: as duas tabelas da migração 063 (Blocos 1 e 3, 15/10).

`tests/teste_modelo_documentado.py` cobra: o documento é o espelho do banco.

Idempotente. Uso: ./venv/bin/python scripts/patch_doc_modelo.py [--conferir]
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SO_CONFERIR = "--conferir" in sys.argv

DE = "| `ligacao_gravacao` | as gravações de cada ligação: `ligacao_id`, `nome_original`, `arquivo_sha256` (único), `arquivo_bytes`, `caminho`, `inicio`, `recebida_em` |\n"

PARA = DE + (
    "| `alistamento_queimado` | **migração 063 (15/10)**: a janela de senha de alistamento já GASTA — `ramal`, `janela` (epoch/600), `usado_em`, `pc`, `ip`, `agente_id`, com `UNIQUE (ramal, janela)`. 🚨 A senha NUNCA é guardada: ela é derivada por HMAC de `MOVIZAP_LIGACOES_SENHA_SEGREDO` sobre (ramal, janela de 10 min), e é este `UNIQUE` que a faz servir **uma vez só** |\n"
    "| `ligacao_exportacao` | **migração 063 (15/10)**: o rastro de cada CSV exportado da aba Ligações — `atendente_id`, `quando`, `filtros` (jsonb) e `linhas`. Não guarda o conteúdo exportado, só quem levou o quê e quando: exportar ligação é número de telefone e áudio de conversa saindo do sistema |\n"
)

EXTRA_DE = """- **Uma ligação pode ter várias gravações:** quando a gravação recomeça, o
  MicroSIP abre outro arquivo (medido em 10/08 13:27 e 18/09 17:34). Por isso
  a gravação tem tabela própria, e não colunas em `ligacao`.
"""
EXTRA_PARA = EXTRA_DE + """- **Índices da 063 (15/10), nascidos junto das consultas que os usam:**
  `ligacao (inicio DESC)` para o grid, `(atendente_id, inicio DESC)` e
  `(ramal, inicio DESC)` para os filtros, e a FK `(agente_id)`. O de
  `(telefone_e164, inicio DESC)` vem da 059 e é o que serve o modal da ficha.
  Índice sem consulta é palpite -- por isso não nasceram antes.
"""

alvo = RAIZ / "docs/02_Modelo_Dados.md"
texto = alvo.read_text(encoding="utf-8")
mudou = False

if "`alistamento_queimado`" in texto:
    print("já estava: as duas tabelas")
else:
    if texto.count(DE) != 1:
        raise SystemExit(f"ÂNCORA da tabela: {texto.count(DE)}×")
    texto = texto.replace(DE, PARA)
    mudou = True
    print(f"{'conferido' if SO_CONFERIR else 'aplicado'}: as duas tabelas")

if "Índices da 063" in texto:
    print("já estava: nota dos índices")
else:
    if texto.count(EXTRA_DE) != 1:
        raise SystemExit(f"ÂNCORA da nota: {texto.count(EXTRA_DE)}×")
    texto = texto.replace(EXTRA_DE, EXTRA_PARA)
    mudou = True
    print(f"{'conferido' if SO_CONFERIR else 'aplicado'}: nota dos índices")

if mudou and not SO_CONFERIR:
    alvo.write_text(texto, encoding="utf-8")
    print(f"gravado: {alvo}")
