"""docs/ligacoes.md: a camada de consulta (Bloco 3, 15/10/2026).

Idempotente, com âncora conferida.
Uso: ./venv/bin/python scripts/patch_docs_consulta.py [--conferir]
"""
import sys
from pathlib import Path

ALVO = Path(__file__).resolve().parent.parent / "docs/ligacoes.md"
SO_CONFERIR = "--conferir" in sys.argv

ANTIGA = """## Consulta rápida (hoje)

- Por contato: `ligacao (telefone_e164, inicio DESC)`, o índice da 059.
- Os índices por operador e por dia e a visão `ligacao_resumo` **nascem com a
  Fase 2**, junto da tela que os usa (índice sem consulta é palpite).
"""

NOVA = """## A camada de consulta (Bloco 3, 15/10/2026)

🔵 *"um grid simples que tenha as ligações do historico do MicroSip,
consultadas por cliente - ja da base Movizap, ou por Atendente, ou por data ou
por numero, etc"* e, na conversa, *"o modal só trará ultimos 7 dias"*.

Até 15/10 o módulo só escrevia: nenhuma rota de leitura, nenhuma tela, nenhum
player. Agora:

| Onde | O quê |
|---|---|
| `movizap/ligacoes_consulta.py` | `consultar` (o grid, com filtros e paginação), `para_csv`, `do_telefone` (o modal da ficha), `gravacao`, `agentes` (a cobertura) |
| `movizap/relatorio_csv.py` | o primeiro CSV do projeto: `;`, BOM e CRLF, com fórmula neutralizada |
| `GET /api/conversas/{id}/ligacoes?dias=7` | **`ATD_1.2`** — o que o modal do botão Ligações usa |

**Módulo separado de propósito:** `ligacoes.py` é o caminho de escrita do
agente, no ar desde 25/09, e não se mexe nele para acrescentar leitura — mesma
divisão de `ligacoes_ca.py` e `ligacoes_alistar.py`.

**Índices** (migração 063): `(inicio DESC)`, `(atendente_id, inicio DESC)`,
`(ramal, inicio DESC)` e a FK `(agente_id)`. O de `(telefone_e164, inicio DESC)`
já vinha da 059 e é o que serve o modal. Nasceram **junto** das consultas que
os usam — índice sem consulta é palpite. ⚠️ A visão `ligacao_resumo` que eu
havia previsto **não foi feita**: as subconsultas de gravações e de clientes
resolvem, e uma visão a mais seria lugar a mais para a verdade divergir.

### Três coisas que a consulta tem de acertar, e que viraram teste

1. **Uma ligação pode ter DUAS gravações** (o MicroSIP reinicia o arquivo no
   meio da chamada e o agente manda os dois pedaços). Com `JOIN` isso viraria
   duas linhas no grid; por isso as gravações vêm por **subconsulta
   agregada**, como lista.
2. **Um número pode cair em VÁRIAS empresas** — é o "empresas do mesmo
   responsável" que a ficha já mostra. `clientes` é lista, e uma ligação de
   duas gravações em duas empresas continua **uma** linha.
3. **A maioria das ligações não tem cadastro nenhum** (`08000028000`,
   `1925172200`, o ramal interno `3407` estão no histórico real). Lista vazia
   significa "sem cadastro", e a tela tem de distinguir isso de "não
   consultei".

Mais duas, que também viraram teste: os **totais são do filtro inteiro**, não
da página (rodapé que conta a página mente a cada virada), e a busca por
**pedaço** de número funciona (`"9811"`), comparando só dígitos dos dois lados.

**`cobertura` vai junto no modal** (quantos ramais têm agente, de quantos
atendentes ativos): sem isso a tela afirma "nenhuma ligação" onde a verdade é
"aquele PC não tem agente".

### Provado em 15/10

| O quê | Resultado |
|---|---|
| `tests/teste_ligacoes_consulta.py` | **22 verdes** (17 da consulta + 5 da rota, com `TestClient`) |
| Contra a base real | 28 ligações, 19 gravações, `{feita: 19, recebida: 4, perdida: 5}` — igual à simulação do agente no mesmo dia |
| Cobertura | 1 ramal com agente, 9 atendentes ativos |
| Rota da ficha, no ar | 401 sem token; 200 com token, 7 dias por padrão; grupo (sem número) responde vazio em vez de explodir; conversa inexistente dá 404 |
| Resíduo de teste | zero (atendente, cliente, contato, conversa e grupo de teste apagados) |
"""

texto = ALVO.read_text(encoding="utf-8")
if "## A camada de consulta (Bloco 3" in texto:
    print("já estava: seção da consulta")
elif ANTIGA not in texto:
    raise SystemExit("ÂNCORA NÃO ACHADA: seção 'Consulta rápida (hoje)'")
else:
    texto = texto.replace(ANTIGA, NOVA)
    print(f"{'conferido' if SO_CONFERIR else 'aplicado'}: seção da consulta")
    if not SO_CONFERIR:
        ALVO.write_text(texto, encoding="utf-8")
        print(f"gravado: {ALVO} ({len(texto.splitlines())} linhas)")
