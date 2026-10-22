"""Patch: a documentação do painel da Operação e o plano dos outros três."""
import sys
from pathlib import Path

RAIZ = Path("/home/claude/movizap_painel")


def emendar(caminho, ancora, novo, marca):
    t = caminho.read_text(encoding="utf-8")
    if marca in t:
        print(f"{caminho.name}: {marca!r} ja estava")
        return
    if t.count(ancora) != 1:
        sys.exit(f"{caminho.name}: ancora de {marca!r} aparece {t.count(ancora)}x")
    caminho.write_text(t.replace(ancora, novo, 1), encoding="utf-8")
    print(f"{caminho.name}: {marca!r} emendado")


# ---------------------------------------------------------------- docs/03
D03 = RAIZ / "docs" / "03_Registro_Telas.md"
emendar(D03,
        "| `FRM_1.1` | Solicitações | `/solicitacoes` | `equipe` | 1 |",
        "| `FRM_1.1` | Solicitações | `/solicitacoes` | `equipe` | 1 |\n"
        "| `PNL_1.1` | Operação | `/paineis/operacao` | `owner` | 1 |",
        "| `PNL_1.1` | Operação |")
emendar(D03,
        "| `FRM_1.1` Solicitações | `bi-ui-checks` | menu |",
        "| `FRM_1.1` Solicitações | `bi-ui-checks` | menu |\n"
        "| `PNL_1.1` Operação | `bi-kanban` | menu (grupo Painéis) |",
        "| `PNL_1.1` Operação | `bi-kanban` |")

# ---------------------------------------------------------------- docs/02
D02 = RAIZ / "docs" / "02_Modelo_Dados.md"
MODELO = """
## Migração 075 — a que painel cada formulário pertence

🔵 O mapa é dele (plano, §2.1): **Operação** (Suporte · Demonstração · Teste
gratuito · Credenciamento), **Pós venda** (NPS · CES), **Contratual** (Ficha
cadastral · Aditivo · Substituição · Rescisão), **Financeiro** (Financeiras ·
Pagamento de técnicos · Administrativas · Fornecedores) e **sem painel**
(Contato).

`formulario.painel` — `varchar(20)`, **anulável**, com CHECK em
`operacao | pos_venda | contratual | financeiro`.
🚨 **É coluna, não lista no código**, pelo mesmo motivo que a definição do
formulário é dado: mover "Administrativas" de Financeiro para Contratual não
pode exigir deploy.
🚨 **O mapa vive em UM lugar** — a tabela `NOSSOS` do
`scripts/carregar_formularios.py` — e é **reescrito a cada carga**
(`painel = EXCLUDED.painel`). ⚠️ `ativo` **não** entra nessa lista: recarregar
não publica formulário nenhum.
⚠️ **Nulo é um valor legítimo**, e tem nome: *"SEM PAINEL — Contato"*.

## Migração 076 — a situação da OS, guardada na solicitação

Para o painel da Operação (opção A) ter colunas, a solicitação precisa saber
em que situação está a OS dela.

`formulario_solicitacao.situacao_id` · `situacao_em` · `situacao_erro`.
🚨 **É CACHE, e o nome diz:** a verdade da situação é do Harmonit; aqui fica a
última lida, **com a hora**. Sem a hora, a tela afirmaria a situação sem prazo.
🚨 **Três estados distinguíveis, não dois:** `os_id` nulo (não virou OS) ·
`os_id` com `situacao_id` nulo (tem OS e **nunca foi lida**) ·
`situacao_id = 0` (lida, e o Harmonit respondeu zero — **127 das 574 OS** estão
assim, medido em 22/10). Os três caem na mesma coluna da tela e continuam
separados no banco.
⚠️ `situacao_erro` segue a régua do `agendamento.endereco_os_erro` (073): nulo
com `situacao_em` nulo = não tentou; nulo com data = deu certo.
⚠️ **Ninguém escreve nestas colunas ainda** — a leitura e a escrita de
`situacaoId` são da volta seguinte, e dependem de decisão dele.
"""
t = D02.read_text(encoding="utf-8")
if "Migração 075" in t:
    print("docs/02: ja tinha a 075")
else:
    D02.write_text(t.rstrip("\n") + "\n" + MODELO, encoding="utf-8")
    print("docs/02: migracoes 075 e 076")

# ---------------------------------------------------------------- docs/06
D06 = RAIZ / "docs" / "06_Conteudo_das_Telas.md"
SECAO = """
## 22/10 — 🔵 PNL_1.1: o painel da Operação (opção A), e o plano dos outros três

🔵 **Escolha dele**, depois de ver três mockups lado a lado: *"vamos de A
somente para a Operação por enquanto, mas bem documentado para as demais
futuramente"*. Os mockups ficam em
`https://claude.ai/artifact/3mM5bs3gv1hYsyTaShsd6s`.

**No ar:** `PNL_1.1 Operação`, rota `/paineis/operacao`, grupo **Painéis**,
permissão **owner**. É o primeiro habitante do grupo que nasceu declarado e
vazio em 19/10 — e o subgrupo "Operacional" **saiu** (fecha a pendência 6 do
plano: ele nunca teve tela, e o painel chama-se "Operação").

**As 13 colunas, nesta ordem:** `Sem OS` → `Sem situação` → as **11 situações**
da OS do Harmonit (38 · 251 · 677 · 890 · 1316 · 15694 · 15695 · 15696 ·
15746 · 15747 · 15797).

🚨 **"Sem OS" é a primeira porque é de onde a OS nasce.** Hoje **todas** as
solicitações estariam nela — nenhuma virou OS ainda —, e esse é o estado
correto, não uma tela quebrada.

🚨 **"Sem situação" existe por um número medido:** das **574 OS** no cache do
FPSL em 22/10, **127 têm `situacao_id = 0` e 37 têm `NULL`** — 164 que não
estão em nenhuma das 11. Sem essa coluna elas desapareceriam da tela (`M12`).
E os **três** casos (nulo, zero, número fora da lista) caem nela com o número
cru à vista: é a régua do grid do FPSL, *"estado desconhecido mostra o valor
cru"*.

🚨 **Mover o card ainda NÃO existe, e a tela diz isso em vez de oferecer o
gesto.** A rota que escreve `situacaoId` no Harmonit é da volta seguinte e
depende de ele confirmar o mapa formulário → `problemaId`. Precedente: o
`ModalAgendar`, que explica em vez de sumir.

⚠️ **Coluna vazia nasce colapsada**, com o contador à vista — como a coluna
"Pago" do kanban do FPSL. As duas primeiras **nunca** colapsam.

⚠️ **A cor nunca é o único portador:** o estado da solicitação vem escrito na
etiqueta e a situação vem escrita no card.

O card leva para a **FRM_1.1** (`/solicitacoes?solicitacao=<id>`): a ficha dos
34 campos do credenciamento é de lá, e o painel não a repete.

### 🔵 Os outros três painéis — desenhados, medidos, e NÃO implementados

🚨 **Nenhum deles é este com outro filtro** — é por isso que só o da Operação
nasceu. Quando um entrar, entra com módulo e rota próprios, não com um `if`
dentro do `paineis.py`.

**PÓS VENDA** — NPS (9 campos) · CES (5).
🚨 **Não é fila, é MEDIÇÃO**, e isso saiu do formulário, não de gosto: a nota é
uma lista de **1 a 10**, e as regras do NPS já separam quem respondeu —
**8, 9 ou 10 pede INDICAÇÃO** (nome do indicado, telefone, e-mail, empresa) e
**7 ou menos pede O QUE OCORREU**, campo obrigatório. NPS e CES **não geram
OS**: coluna por situação ali não mede nada. A tela quer três medidas (NPS do
mês, CES, respostas), a distribuição das notas, e **duas filas de ação**:
indicações a contatar e reclamações a tratar.
🔴 Falta dele: **o corte do promotor, 8 ou 9** (o formulário do Bitrix trata 8
como promotor; no NPS de mercado 8 é neutro) · se nota baixa avisa alguém na
hora pelo chat interno.

**CONTRATUAL** — Ficha cadastral (36) · Aditivo (18) · Substituição (17) ·
Rescisão (17).
O que trava **não é a situação, é o documento**: três faixas — falta documento
→ a conferir → pronto. A ficha cadastral pede **3 anexos** e **10 dos seus 36
campos** só nascem depois de uma escolha; a rescisão, 8 de 17. O campo
`product` (Aditivo e Substituição) é **texto** nesta etapa.
🔴 Falta dele: **endereço** — puxar do Harmonit, pedir no formulário com
ViaCEP, ou os dois? (o cadastro do MoviZap **não tem endereço em forma
nenhuma**) · o que conta como "pronto" · se a conferência vira OS.

**FINANCEIRO** — Financeiras (10) · Pagamento de técnicos (16) ·
Administrativas (11) · Fornecedores (16).
Fila simples com três medidas, e o único com **elo externo**: *Pagamento de
parceiros técnicos* fala do mesmo assunto que o **Fechamento de Contas dos
Técnicos** do FPSL (`FIN_2.1`, 170 técnicos reais).
⚠️ Risco nomeado: virar **uma segunda contabilidade** ao lado dele. Enquanto o
elo for um link, não há duas verdades.
🔴 Falta dele: ligar ou não ao fechamento do FPSL · se o painel mostra
**valor** — e, se sim, **acrescentar o campo**, porque **nenhum dos quatro
tem** hoje.

⚠️ **O que falta para QUALQUER um deles mostrar OS:** duas rotas que a ponte do
FPSL ainda não tem — **criar OS** (`SalvarOrdemServico` com `id: 0`) e
**escrever `situacaoId`** —, as duas pelo caminho provado do
`os_ponte.py:_corpo_de_escrita` (relê, remonta inteira, grava, relê e compara
os 39 campos). Elas dependem do mapa formulário → `problemaId`, que é decisão
dele.
"""
t = D06.read_text(encoding="utf-8")
if "PNL_1.1" in t:
    print("docs/06: ja tinha a PNL_1.1")
else:
    D06.write_text(t.rstrip("\n") + "\n" + SECAO, encoding="utf-8")
    print("docs/06: secao do painel + plano dos outros tres")
