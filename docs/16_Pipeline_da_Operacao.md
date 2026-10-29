# Pipeline da Operação — o painel, a OS e o chamado

> **Escrito em 29/10/2026**, a pedido dele: *"proponha o plano e documente ele
> certinho com o que avançamos e com o que falta para continuar depois"*.
>
> 🚨 **Este arquivo é o plano DESTA frente.** O diário do dia continua em
> `06_Conteudo_das_Telas.md` (três entradas de 29/10), o modelo de dados em
> `02_Modelo_Dados.md` (migrações 079, 080 e 081) e o registro de telas em
> `03_Registro_Telas.md`. O `Proximos_Passos.md` aponta para cá e **não
> duplica** a lista.
>
> **Mockup:** `https://claude.ai/artifact/GXx2aBj4Tei8t51KR4HZSC` — dois
> quadros: o painel com as 11 OS reais desde 24/10, e o card fechado e aberto.

---

## 0. O que esta frente é, em três frases

O **chamado** entra por formulário (link público ou, depois, botão na conversa
do MoviZap). Ele **abre uma OS de análise no Harmonit**, uma por placa. O
**painel da Operação** é o pipeline dessas OS — 17 colunas, que são as 17
situações do ERP —, e cada card é o resumo de consulta rápida da OS, com o que
falta na etapa em que ela está.

🔵 **O motivo, nas palavras dele (22/10):** *"hoje ainda não usamos a situação
da OS, por isso o painel e consulta para atualizar a situação no painel"*.

---

## 1. O que avançou em 29/10 — e está no ar

### 1.1 O formulário de Suporte no formato novo (`forms.movisat.com.br/f/suporte`)

🚨 **"Igual os outros" não existia:** o formato novo estava **desenhado e não
implementado** (o arquivo de design de 23/10 diz *"nada aqui foi
implementado"*). O que havia no ar nos 15 era a página de 22/10 — rolo único,
sem logo, sem máscara, sem o `+`. Este é o primeiro, e com ele entrou o motor
que os outros 14 vão reusar.

| Peça | Estado |
|---|---|
| 4 etapas, trilho rolável, Voltar/Avançar | ✅ no ar |
| logo oficial (arquivo dele) + base `#021529` + catavento como código de etapa | ✅ |
| repetidor `+` nos campos múltiplos, `×` desabilitado na última linha | ✅ |
| máscaras com dígito verificador real (CPF, CNPJ), placa nos dois padrões, telefone, e-mail, CEP | ✅ |
| **CNPJ alfanumérico** (12 alfanuméricas + 2 dígitos, DV por ASCII−48) | ✅ |
| "Escolha…" esmaecido no campo, fora da lista | ✅ |
| botão **Buscar** no CNPJ, preenchendo a Empresa | ✅ |
| modal **"Sem empresa vinculada"** (Continuar / Cancelar) antes de enviar | ✅ |
| **frota ativa** do cliente marcável + *"Meu veículo não está na lista"* | ✅ |
| **regra da placa**: chamado só para placa ativa na WESO | ✅ |
| 6 ajustes dele (nome numa caixa, fantasma do telefone, 4 opções novas, sai o Assunto, campo mais alto, fonte da placa) | ✅ |

**Interruptor:** `formulario.formato` nasce `classico` nos 15 e **só o SUPORTE
está em `novo`**. Ligar o próximo é uma linha em `FORMATO_NOVO`, no
`scripts/carregar_formularios.py`, e rodar a carga — sem migração e sem deploy.

### 1.2 As 17 situações da OS, no Harmonit e no painel

**O catálogo do ERP foi ajustado** (`fpsl_weso/ajustar_situacoes_os.py`): **11
renomeadas, 6 criadas, nenhuma excluída, nenhuma sobrando.** Ids e ordem (a
ordem é o fluxo, e é dele) na entrada de 29/10 do `06_Conteudo_das_Telas.md` e
na tupla `SITUACOES` do `movizap/paineis.py` — **um lugar só**.

**O painel** passou a ter exatamente essas 17 colunas, saíram "Sem OS" e "Sem
situação", e saíram os três textos que ele mandou sumir. O que não tem coluna é
**contado** (`fora_do_quadro`), nunca escondido.

### 1.3 O que foi medido e passou a ser fato

| Medição | Número |
|---|---|
| `dataPrevisao` **é** a data de criação da OS | **12 de 12** OS conferidas contra a linha do tempo, mesmo minuto |
| a linha do tempo da OS **não registra situação**, só `status` | 2 a 3 eventos por OS (17043, 17045, 17046) |
| OS não excluídas com data ≥ 24/10 | **11** (6 não finalizadas) |
| placas com dono conhecido (Harmonit) | **9.114** |
| placas ativas (WESO = tem rastreador) | **1.998** |
| casamento, normalizando os dois lados | **1.918**; dos 80 restantes, **50 não são placa** (chassi/série na coluna `placa`) e **30** são placa que o Harmonit não tem → **98,5 %** entre as que são placa |
| conversas por cliente | média **2,2**, máximo **16** — mais de uma é o normal |
| contatos já casados com técnico do Harmonit | **187** |
| `ANÁLISE OPERACIONAL` no catálogo de problemas | **já existe: 12760** |

**Suítes no fim do dia:** **1885 Python** · **559 JS** · **46** na ponte do
FPSL.

---

## 2. As decisões dele desta volta (e as duas que mudaram de lado)

| # | Decisão | Palavras dele |
|---|---|---|
| D1 | Chamado **só para placa ativa na WESO** | *"essa é a regra"* |
| D2 | CNPJ **alfanumérico**, e todos os formatos de colagem | *"podem colar somente numero ou . e - e / tbm"* |
| D3 | **Uma OS por placa** (muda a de 23/10, que era 1 por envio) | confirmado na pergunta |
| D4 | OS **automática no envio** (muda a de 23/10, que era por botão) | *"todo chamado de suporte abrirá uma OS"* |
| D5 | As **17 situações**, nesta ordem | *"as situações já estão na Ordem"* |
| D6 | **677** = "Enviar por correio/transportadora"; "Entrega de materiais prontos" nasce nova | confirmado na pergunta |
| D7 | **15694** renomeada para "Atendimento finalizado" | confirmado na pergunta |
| D8 | Cards = **OS abertas**, de qualquer origem (painel, FPSL, formulário, à mão) | *"seja pelo painel, seja pelo FPSL, seja pelo formulario, seja a mão"* |
| D9 | **Data inicial 24/10**, e **só o owner** muda | *"a data inicial é somente do Owner"* · *"não vamos retroagir mais do que o dia que pedi"* |
| D10 | O fluxo em texto dentro da `solucaoTecnica` **vai ser apagado** — este pipeline o substitui | *"vamos apagar mais para frente"* |
| D11 | **Espelho da OS no card**, para alterar daqui também | *"pode ser"* |
| D12 | O R$ 0,01 do `ABERTURA DE OS` é **por OS**, simbólico | *"cada placa com OS de 0,01"* |

⚠️ **E um erro meu de método, registrado porque é o que não deve repetir:** eu
havia escrito em três arquivos que a lista da frota *"sugere, nunca
restringe"*. **Ninguém me disse isso** — eu inferi de uma medição minha (95 %,
e grosseira) e tratei a inferência como decisão. Resposta dele: *"a regra sempre
foi essa, voce quem decidiu algo sem perguntar e acabou fazendo trabalho atoa"*.
**Medição não vira regra sozinha.**

---

## 3. O PLANO — 6 blocos, na ordem de dependência

> Régua de pronto, igual para os seis: (a) as **duas suítes** passam; (b) o
> estado é **relido** e conferido, nunca o retorno da escrita; (c) **ele validou
> no navegador**. 🚨 `M9`: placar verde não vê tela quebrada.

### Bloco A — Criar a OS do chamado

```
Objetivo:     o chamado de Suporte vira OS de análise no Harmonit, automático
Hoje:         nada cria OS. `grep SalvarOrdemServico` no MoviZap = zero
Por quê:      é o que faz o card existir; sem OS o painel é uma tela vazia
Reavaliar se: ele voltar a querer criação por botão
```

- rota nova na ponte do FPSL: **criar OS** (`SalvarOrdemServico` com `id: 0`),
  pelo caminho provado do `os_ponte._corpo_de_escrita`;
- **uma OS por placa** informada; sem placa, uma OS só;
- campos: `tipoId` **1783** (MoviZap) / **1782** (link público) ·
  `problemaId` **12760** ANÁLISE OPERACIONAL · `situacaoId` **38** ·
  `prioridadeId` **382** Normal · `produtoServicoId` **670990** ABERTURA DE OS
  (**R$ 0,01 por OS**) · `descricaoDetalhada` = a observação do formulário ·
  **sem técnico**;
- `formulario_solicitacao` passa a guardar **N** OS, não uma: tabela de ligação
  (solicitação ↔ placa ↔ `os_id`);
- 🚨 **a falha tem de ser visível:** chamado gravado e OS não criada é o pior
  caso — o cliente recebe "recebemos" e ninguém abre OS. O envio **grava
  primeiro** e a OS entra em seguida; falhando, a solicitação fica marcada e
  aparece na linha de aviso do painel.

⚠️ **O que a decisão D4 traz:** o formulário é **público**. A isca, o tempo
mínimo de abertura, o teto de 5 envios/hora por IP e a conta de somar passam a
ser as únicas camadas entre a internet e a criação de OS **no ERP**.

### Bloco B — O painel monta os cards das OS que já existem

```
Objetivo:     as OS abertas desde 24/10 aparecem na coluna da situação delas
Hoje:         o painel só lê `formulario_solicitacao`, e há 1 (de CES)
Por quê:      decisão D8: o card é a OS, de qualquer origem
Reavaliar se: a data matriz dele mudar (é parâmetro, não código)
```

- rota nova na ponte: **OS por situação desde uma data**, lendo o cache
  `os_historico` que a rotina de varredura já mantém;
- a data vive em `/config › Geral`, **24/10/2026** inicial, **editável só pelo
  owner** (D9) — e a tela **diz desde quando** está montando;
- o card junta: OS (ERP) + cliente (nosso `cliente.harmonit_id`) + a
  solicitação, quando houver;
- **"aberta"** = não excluída e não finalizada. ⚠️ Medido: isso **não** esvazia
  as colunas finais (as 11 OS em "Atendimento finalizado" estão com status
  *Iniciada* — situação e status são eixos independentes), mas **zera o
  Financeiro** (as financeiras nascem `Finalizado`). Por isso o filtro "só
  abertas" é interruptor na tela, ligado por padrão.

### Bloco C — O tempo por etapa

```
Objetivo:     saber quanto tempo cada OS ficou em cada etapa
Hoje:         não existe em lugar nenhum
Por quê:      pedido dele, e é o que faz o painel responder "o que está parado"
Reavaliar se: o Harmonit passar a registrar situação na linha do tempo
```

🚨 **O Harmonit não guarda isso.** A linha do tempo registra só o `status`
(*Nova*, *Agendado*, *Fechamento Parcial*) — conferido em três OS. Então:

- tabela nossa de **passagem de etapa**: OS, de qual situação, para qual, quem,
  quando;
- o card mostra **dois tempos**: nesta etapa e total da OS;
- ⚠️ **para as 11 OS que já existem, a contagem começa no dia em que o card
  nascer** — e o card **diz isso**, em vez de inventar um número (D-resposta 2
  dele: *"pode colocar como data de criação do card"*);
- o que a linha do tempo **dá** e entra no card: **quem abriu e quando** (a
  17045 foi a Erika, 28/10 08:56:19) e **quem agendou** (*"Técnico Franck foi
  agendado"*, pela Aline).

### Bloco D — Mover o card (escrever a situação)

```
Objetivo:     arrastar o card muda a situação da OS no Harmonit
Hoje:         `pode_mover` é falso e não há gesto de arrastar
Por quê:      é o motivo que ele deu para o painel existir
Reavaliar se: nunca
```

✅ **A escrita está provada** (29/10, OS 16991): `SalvarOrdemServico` troca
`situacaoId` e a releitura dos 40 campos/listas acusa **só** o `situacaoId`.
- lê a OS, remonta as 25 chaves, troca a situação, grava, **relê e compara**;
- deu diferença fora da situação → o card **volta** para a coluna de origem e a
  tela diz o que foi tocado;
- carimba a passagem (Bloco C).

⚠️ **Ordem livre ou com regra?** O Harmonit aceita pular de qualquer situação
para qualquer outra — fui de "Serviço Realizado" para "Agendamento" e ele
aceitou. Se existe caminho proibido, a regra é dele. 🔵 Ele já disse: *"depois
vou montar as regras entre eles"*.

### Bloco E — O card aberto: os resumos, a prioridade, a observação e a conversa

```
Objetivo:     o card é consulta rápida e, aberto, é onde se age
Hoje:         o card leva para a FRM_1.1 e nada mais
Por quê:      pedidos dele de 29/10
Reavaliar se: ele achar que o modal fica melhor como tela
```

- **quatro resumos**, cada um num painel lateral: **Descrição da OS** ·
  **Solução técnica** · **Dados do chamado** (as respostas do formulário) ·
  **Agendamento** — este nasce desabilitado e **acende em "Serviço Agendado"**,
  dizendo por quê, e é o elo com a `ATD_7.1` (o compromisso já existe lá com
  `agendamentoId`);
- **prioridade** escrita no card fechado (nasce *Normal*; mudar é exceção, e
  exceção precisa ser visível sem abrir) e editável no aberto. ⚠️ Mudar
  prioridade **escreve a OS inteira**;
- **observação do painel**, com autor e hora, **no MoviZap**. Não vai para a
  `solucaoTecnica` — aquele campo é da operação, e o fluxo que está lá vai ser
  apagado (D10);
- **falar com o cliente**: 🚨 **mais de uma conversa é o normal** (média 2,2,
  máximo 16; a TGS tem 6). Com mais de uma, abre a lista com a última mensagem
  de cada;
- **falar com o técnico**: aparece quando o agendamento tem técnico — 187
  contatos já estão casados com o cadastro de técnico.

### Bloco F — O espelho da OS

```
Objetivo:     alterar a OS daqui, sem abrir o Harmonit
Hoje:         só a situação (Bloco D) e o endereço (21/10) são escritos
Por quê:      decisão D11 -- não existe link por OS no Harmonit
Reavaliar se: o Harmonit ganhar deep link por OS
```

🚨 **Não existe link por OS.** Medido: `https://hc.harmonit.com.br/Manager/OrdemServico`
responde 200 e **redireciona para `/Account/Login`**; é ASP.NET MVC e a OS abre
por postback/ajax — a URL não muda, como ele mesmo notou. Então o espelho é o
caminho.

**O que o espelho edita** (o `SalvarOrdemServico` é a OS inteira, e a doc deles
lista exatamente as 25 chaves que a ponte já remonta): situação · prioridade ·
previsão · descrição · solução técnica · endereço (7) · tipo · problema ·
produto/serviço · cliente · vendedor · local do serviço · as 3 retenções.

**O que tem rota própria** e não entra nesse save (medido: eles **sobrevivem** a
um save da OS): **materiais** · **técnicos/agendamento** · **checklist** ·
**oficina**.

🚨 **A trava de concorrência:** quem grava por último ganha, e o corpo é a OS
inteira. Então **reler imediatamente antes de gravar** e comparar com o retrato
que a modal carregou; mudou algo no meio → **recusa** e mostra o que mudou.
⚠️ Ele considerou o risco pequeno (*"cada 1 atua em uma área especifica do
fluxo"*) **e pediu a trava mesmo assim** (*"mas pode ter sim"*).

**Em duas fases, por decisão de superfície:** fase 1 = espelho de **leitura** +
escrever **situação, prioridade e observação**; fase 2 = descrição, solução
técnica, previsão e endereço editáveis.

---

## 4. 🔴 O que falta DELE

| # | Pergunta | Por que trava |
|---|---|---|
| 1 | **Validar no navegador**: `forms.movisat.com.br/f/suporte` e `/paineis/operacao` | `M9` — em 21/10 ele tirou sete apontamentos com 1572 testes verdes |
| 2 | As **2 OS com situação `0`**: a **17050** (DCBM, aberta hoje) vai para "Novo Solicitação 1ª" e a **17042** (DOCA, finalizada) para "Atendimento finalizado"? E a regra geral: `0` + *Nova* → primeira etapa; `0` + *Finalizado* → finalizado | sem isso, 2 das 11 ficam fora de coluna |
| 3 | Os **tipos 76 e 57**, que não existem no catálogo de 5 tipos (5 das 11 OS). Mostrar o número cru, ou **reescrever** para `2` Contrato? | reescrever é mexer em OS existente no ERP |
| 4 | O que a aba **Network** do navegador mostra ao abrir uma OS — se for `GET` com id, existe link; se for `POST`, não existe | decide se o Bloco F é o único caminho |
| 5 | **Ordem das etapas**: livre ou com caminho proibido? | ele já disse que monta as regras depois |
| 6 | Ligar o formato novo nos **outros 14 formulários** | é uma linha por formulário |
| 7 | O **texto dos termos de aceite** (teste gratuito, ficha cadastral, fornecedores) | aberto desde 22/10 |
| 8 | Os **50 registros da WESO com chassi no campo `placa`** — limpar a base ou abrir exceção na regra da placa? | hoje a regra recusaria o chamado desses clientes |
| 9 | Apagar a solicitação de teste **39** (é do **CES**, não do Suporte) | sobra de teste |

---

## 5. Onde está cada peça

| Peça | Arquivo |
|---|---|
| migrações | `migracoes/079_formato_novo_do_formulario.sql` · `080_ajustes_do_campo.sql` · `081_regra_da_placa.sql` |
| o mapa (formato, etapas, máscaras, ajustes) | `scripts/carregar_formularios.py` — `FORMATO_NOVO`, `ETAPAS`, `VALIDACOES`, `AJUSTES` |
| definição, validação, busca de cliente, regra da placa | `movizap/formularios.py` |
| rotas públicas | `movizap/main.py` — `_etapas_publicas`, `/cliente`, `/placa` |
| as 17 colunas | `movizap/paineis.py` — `SITUACOES` |
| máscara e conferência | `frontend/src/util/validacao_campo.js` |
| o renderizador dos campos | `frontend/src/componentes/CamposDoFormulario.vue` |
| a página pública | `frontend/publico/FormularioPublico.vue` · `identidade.css` · `movisat_logo.png` |
| o painel | `frontend/src/telas/PainelOperacao.vue` |
| ponte: placas, conferência de placa | `movizap/fpsl_ponte.py` + `fpsl_weso/fpsl_weso/routers/os_ponte.py` |
| o catálogo de situações | `fpsl_weso/ajustar_situacoes_os.py` |
| medições de hoje | `fpsl_weso/medir_situacao_os.py` · `medir_catalogo_situacao.py` |
| travas | `tests/teste_formato_novo.py` (31) · `tests/teste_paineis.py` (20) · `frontend/src/formulario_novo.teste.js` (38) · `painel_2210.teste.js` (16) |

---

# 6. 29/10, SEGUNDA VOLTA — BLOCOS A e B NO AR

> Pedido dele: *"depois de subir o painel, verifique: 1 sem OS (a escrita no
> Harmonit falhou) — abra em Solicitações"*, e antes disso *"continuar com os
> ajustes do painel operação + form + situação das OS"*.

## 6.1 O que entrou

| Bloco | Estado | Prova |
|---|---|---|
| **A — criar a OS do chamado** | ✅ **no ar** | OS **17056** criada e removida no ERP |
| **B — o painel monta as OS** | ✅ **no ar** | **10 cards reais** no quadro, com nome de cliente e de tipo |
| C — tempo por etapa | ❌ não começou | — |
| D — mover o card | ❌ não começou | `pode_mover` segue falso |
| E — card aberto | ❌ não começou | — |
| F — espelho da OS | ❌ não começou | — |

**Migração 082** (`solicitacao_os`) · **1 rota nova no MoviZap**
(`PUT /api/paineis/operacao/desde`) · **2 na ponte** (`POST /api/os/criar`,
`GET /api/os/por-situacao`) · módulo novo `movizap/chamado_os.py`.

## 6.2 O Bloco A, e o que a escrita real ensinou

🚨 **`SalvarOrdemServico` com `id: 0` DEVOLVE o número.** Era a única coisa que
nenhum teste podia responder — a doc do Harmonit documenta o retorno da rota
**básica**, não o da completa. Medido com uma OS de verdade (autorizada por ele:
*"criar uma e apagar"*): a resposta traz `numeroOrdem` **17056** e
`ordemServicoId` **927648**, e a releitura devolveu os **8 campos idênticos ao
pedido** — `tipo` 1782 · `problema` 12760 · `situacaoId` **38** · `prioridade`
382 · `parceiro` 68546 · `produtoId` 670990 · `status` 2 *Nova* ·
`dataPrevisao` no minuto do envio. A OS foi removida
(`RemoverOrdemServico`) e a leitura dela passou a recusar.

⚠️ **O número 17056 foi consumido e não volta** — remover a OS não devolve o
número à sequência. É o custo da prova, e foi uma vez.

**Os cinco ids de catálogo foram LIDOS do ERP antes de qualquer escrita**, não
copiados de memória: `1782` Demanda Interna · `1783` Solicitação de Cliente ·
`12760` ANÁLISE OPERACIONAL · `38` Novo Solicitação 1ª · `382` Normal. Id de
catálogo errado não dá erro de escrita — dá OS torta e muda no ERP.

⚠️ **`status = 2`, não o `1` do exemplo da doc.** Medido: `2` é "Nova" em 302
OS do cache, e a 17050 (aberta por eles em 29/10) nasceu com `2`.

### 🚨 O caso que o código trata e a doc deles não menciona

`criada` tem **três** valores, e o terceiro é o que importa: `True` nasceu ·
`False` não nasceu · **`None` = não se sabe** (o Harmonit aceitou a escrita e
não disse o número). No caso `None` a linha é marcada e **a retentativa não
acontece** — tentar de novo abriria a **segunda** OS.

⚠️ **Timeout da ponte cai em `None`, e foi um erro que quase ficou no código:**
*"não respondeu no tempo"* **não** quer dizer *"não gravou"* — a escrita pode
ter chegado ao Harmonit e a resposta ter se perdido na volta. O `_postar` da
ponte agora marca `incerto` no timeout, e só nele.

### A ordem é chamado primeiro, OS depois

O pior caso da frente é o cliente ler *"recebemos sua solicitação"* e ninguém
abrir OS. Então o envio **grava**, as linhas de `solicitacao_os` nascem com
`os_id` nulo, e cada falha fica **escrita na linha** e contada no painel. Criar
a OS antes perderia o chamado inteiro quando o ERP estivesse fora do ar — que é
justamente quando o cliente mais precisa ser ouvido.

🔴 **A pendência que isto deixou, e é dele:** o `SalvarOrdemServico` **exige
`clienteId`**, o formulário é público e o modal *"Sem empresa vinculada"* deixa
enviar sem empresa. Hoje o chamado de quem não é cliente fica gravado,
**marcado**, e aparece na linha de aviso do painel — em vez de virar OS de um
cliente inventado. Se ele quiser um "cliente avulso" no ERP para esses casos, é
uma linha.

## 6.3 O Bloco B, e dois números do plano que estavam errados

🚨 **"Só abertas" NÃO zera o Financeiro.** O plano da manhã dizia que zerava.
Medido: o Financeiro (15746) vai de **6 para 2** cards, não para 0 — há OS
financeira que não está `Finalizado`. O interruptor continua valendo (ele muda
o quadro), mas a razão escrita estava mais forte que o dado.

✅ **Os 9 clientes das OS estão TODOS no nosso cadastro** — nenhum card sem
nome. Era um risco nomeado e não se materializou.

**O quadro agora é a união de duas fontes**, deduplicada pelo `numero_ordem`:
as OS do ERP desde a data matriz (via ponte) **mais** as nossas solicitações que
já têm OS. Isso é o que faz a tela sobreviver à ponte caída.

⚠️ **Ponte caída não esvazia o painel**, e a tela DIZ: sem o FPSL o quadro cai
de 10 para 2 cards, e um quadro pequeno sem explicação faria o operador concluir
que não há trabalho — justo na hora em que há.

**A data matriz** vive em `config.painel_operacao_desde`, nasce
**2026-10-24** (D9) e **só o owner muda** (`PUT /api/paineis/operacao/desde`
recusa com 403). ⚠️ A permissão da tela não bastava: `PNL_1.1` abre o painel
para a operação inteira, e mover a data muda o que **todos** veem.

## 6.4 🚨 Uma pendência DELE morreu por medição

A pergunta nº 3 (*"os tipos 76 e 57 não existem no catálogo de 5 tipos —
mostrar o número cru ou **reescrever** para `2` Contrato?"*) **era uma pergunta
errada, e a minha.** São **duas rotas diferentes**:

| rota | devolve |
|---|---|
| `ObterListaTipoOrdemServico` | **5** — os selecionáveis em tela |
| `ObterTiposOrdemServico` | **28** — o catálogo inteiro |

Os tipos existem todos: **`76` Instalação rastreador · `57` Retirada · `77`
Upgrade** (este terceiro nem estava na pergunta, e aparece em 2 OS). **Nada a
reescrever no ERP** — a opção arriscada saiu de pauta.

🚨 **E isso era a causa de um defeito que vinha desde 21/10:** a rotina
`sync_tipos_os` lia a rota curta, então o dicionário tinha 5 nomes e a mensagem
do agendamento **omitia o tipo em uma de cada três OS**. Corrigido na origem, e
medido:

| | antes | depois |
|---|---|---|
| nomes no dicionário | 5 | **28** |
| OS com nome de tipo | 385 de 574 | **574 de 574** |
| ids "desconhecidos" | 9 | **nenhum** |

⚠️ **Isso muda o que o cliente lê:** a mensagem do agendamento passa a trazer o
tipo nas OS que antes o omitiam. A regra *"nulo omite o segmento"* não mudou —
nulo é que ficou raro.

⚠️ **E o comentário que eu havia escrito no código estava errado:** dizia que os
nove ids eram *"tipos que o Harmonit removeu ou renomeou"*. Eu inferi
"removido" de uma ausência que era só da rota curta. **Ausência numa lista não
prova ausência no cadastro** — é o mesmo erro de método que ele apontou de
manhã.

## 6.5 🚨 O defeito que ELE achou na tela, minutos depois de ela subir

> *"1 sem OS (a escrita no Harmonit falhou) — abra em Solicitações."*

**Nada havia falhado.** A solicitação é a **544**, um Suporte enviado hoje
**13:06** — duas horas e meia **antes** de o Bloco A existir. `solicitacao_os`
tinha zero linha para ela: **ninguém tentou escrever**.

`M9` outra vez: **1.908 verificações verdes** e nenhuma viu a frase errada,
porque nenhuma delas olha a tela com o dado de hoje dentro.

E `M12` na forma mais exata: **o texto era verdadeiro quando foi escrito.** Em
22/10 a OS nascia por botão e "sem OS" só podia ser espera; em 29/10 a D4 tornou
a abertura automática e eu reescrevi a frase para *"a escrita falhou"*,
assumindo que todo chamado dali em diante teria tentativa. **Os de antes não
têm, e para eles a frase nova mente.**

A correção é a distinção que a `solicitacao_os` já carregava e o painel não
lia — e são **três** casos, não dois:

| na linha | significa | a tela diz |
|---|---|---|
| nenhuma linha | **nunca se tentou** (chamado anterior ao Bloco A, ou formulário que não abre OS) | *"N chamados sem OS, de antes de a abertura ser automática"* |
| linha com `erro` | tentou e **falhou** | *"N OS não abriram em M chamados (última tentativa …)"* |
| a sobra das duas contas | linha preparada e nunca tentada | *"N sem OS e sem motivo registrado"* |

🚨 **A terceira frase existe de propósito:** sem ela, uma linha preparada e
nunca tentada desapareceria **entre** as duas outras — o mesmo defeito, mais
fundo. Tem trava própria.

⚠️ **E um teste estava GUARDANDO o defeito:** ele exigia a palavra `"Harmonit"`
na frase, isto é, exigia que a tela acusasse o ERP por toda solicitação sem OS.
Trocado, com o motivo escrito no próprio teste.

## 6.6 Um erro meu em produção, de 13 segundos

🚨 **Derrubei o MoviZap das 15:46:10 às 15:46:23.** Acrescentei o parâmetro
`so_abertas = Query(...)` na rota do painel e **`Query` não estava importado no
`main.py`** — o uvicorn entrou em loop de reinício. Pego pela minha própria
verificação do serviço (`systemctl is-active` devolveu `activating`), consertado
em cerca de um minuto, serviço estável desde 15:46:23.

⚠️ **O `py_compile` que eu rodo antes de gravar NÃO pega isto**: nome não
importado é erro de execução, não de sintaxe. A régua que faltou foi conferir o
`import` antes de usar o nome — e é barata: um `grep` na linha do `from
fastapi import`.

## 6.7 As travas

| arquivo | quantas |
|---|---|
| `fpsl_weso/tests/teste_criar_os_ponte.py` | **35** (25 do Bloco A + 10 do B) |
| `movizap_painel/tests/teste_chamado_os.py` | **27** |
| `movizap_painel/tests/teste_paineis.py` | **29** |
| `frontend/src/painel_2210.teste.js` | **29** |

⚠️ **E um defeito da minha própria suíte, achado na primeira rodada:** o fixture
criava o formulário de teste **sem `validacoes` e sem `ajustes`**, então nenhum
campo tinha `validacao` nem `fonte` — e **12 das 23 travas pulavam**, com o
placar parecendo saudável (*"29 passaram"*). Teste que pula é teste que não
existe. O fixture agora lê as duas tabelas **do próprio
`scripts/carregar_formularios.py`**, porque copiá-las criaria a terceira
verdade.

## 6.8 🔴 O que falta dele

| # | o que | por que trava |
|---|---|---|
| 1 | **Validar no navegador**: `/paineis/operacao` com os 10 cards, o interruptor "só as abertas" e o "desde 24/10/2026" | `M9` — ele já achou um defeito hoje que 1.908 testes não viram |
| 2 | As **OS com situação `0`** — hoje **1** no quadro aberto e **2** no total. A proposta segue: `0` + *Nova* → primeira etapa · `0` + *Finalizado* → finalizado | sem isso elas ficam contadas em `fora_do_quadro`, sem coluna |
| 3 | ~~Os tipos 76 e 57~~ | ✅ **morreu em 29/10**: existem no catálogo de 28 (ver §6.4) |
| 4 | O que a aba **Network** mostra ao abrir uma OS no Harmonit | decide se o Bloco F é o único caminho |
| 5 | **Ordem das etapas**: livre ou com caminho proibido? | é o Bloco D, o próximo |
| 6 | Ligar o formato novo nos **outros 14 formulários** | uma linha por formulário |
| 7 | O **texto dos termos de aceite** | aberto desde 22/10 |
| 8 | Os **50 registros da WESO com chassi no campo `placa`** | hoje a regra recusaria o chamado desses clientes |
| 9 | Apagar a solicitação **39** (CES) **e a 544** (Suporte, teste dele de hoje: nome *"Teste"*, telefone dele, CNPJ da Velasco) | sobras de teste. ⚠️ A 544 é a que faz a linha de aviso aparecer no painel |
| 10 | 🆕 **Um "cliente avulso" no ERP?** — para o chamado de quem não está no cadastro virar OS em vez de ficar marcado | ver §6.2 |

## 6.10 Os efeitos do mockup, na tela de verdade

> 🔵 Pedido dele: *"depois não esqueça de subir tbm com os efeitos, pois o
> mockup ficou muito bom"* — o mockup é
> `claude.ai/artifact/GXx2aBj4Tei8t51KR4HZSC`.

🚨 **O QUE NÃO VEIO DO MOCKUP: OS HEXES.** O mockup escreve `#D8E0E9`,
`#4A5A6B`, `#021529`, `#F1F5F9` à mão — e **cada um desses é um token desta
casa** (`--borda`, `--texto-fraco`, `--acento`, `--superficie-2`). Trazer os
hexes criaria uma segunda paleta dentro do painel e quebraria a tela no dia em
que o tema mudar. Veio a **estrutura** e vieram os **efeitos**, sobre os
tokens.

| do mockup | na tela |
|---|---|
| borda de cima da coluna na cor da etapa | ✅ 6 cores do catavento, ciclando pelas 17 colunas |
| borda esquerda do card na mesma cor | ✅ |
| contador **cheio** com card, **vazado** sem | ✅ `--texto` de fundo × contorno apagado |
| a **OS na frente** do card, não o formulário | ✅ |
| "há 2 dias" / "hoje" no canto | ✅ |
| cliente em negrito, tipo em cinza, pílulas de 999px | ✅ |
| sombra e levantada na passagem | ✅ `--sombra-1` + `translateY(-1px)` |
| coluna vazia mais apagada | ✅ `--superficie-2` |

🚨 **A COR É CÓDIGO DE ETAPA E NUNCA O ÚNICO PORTADOR** — regra desta casa, e
tem trava própria: o **nome da etapa** fica escrito na coluna e o **número da
situação** no card. Quem não distingue as cores perde a decoração, nunca a
informação.

⚠️ **`prefers-reduced-motion` desliga o movimento e MANTÉM a sombra:** quem
pediu menos movimento no sistema continua vendo que o card responde ao
ponteiro.

### Três coisas que o mockup não tinha e a tela de verdade precisava

1. **Cliente fora do nosso cadastro é DITO**, em itálico, com o `harmonit_id` —
   o mockup sempre tem nome. Hoje os 9 clientes das OS estão todos no cadastro,
   então esta linha não aparece; basta uma OS de cliente novo.
2. **"Finalizada" é aviso, não decoração.** Ela só aparece com o interruptor
   desligado, e sem a marca ficaria indistinguível de uma OS viva na mesma
   coluna — são **14 cards** com ele desligado contra **10** ligado.
3. **"Lido do Harmonit às HH:MM"** no pé do card. A varredura roda a cada
   5 min, e a tela não pode deixar supor que o dado é de agora.

### 🔴 O que do mockup NÃO entrou, e por quê

| peça do mockup | por que não |
|---|---|
| **os dois tempos** ("nesta etapa 1d 4h", "total 1d 4h"), e o laranja do limite | é o **Bloco C**, e o tempo por etapa **não existe no Harmonit** — a linha do tempo registra só o `status`. O card mostra o tempo desde a abertura, e **não** o chama de "nesta etapa": seria a tela afirmando o que ninguém mediu |
| **o card aberto** (modal com os 4 resumos, prioridade, observação, "falar com") | é o **Bloco E** |
| **"Avançar etapa"** no rodapé do modal | é o **Bloco D** — `pode_mover` segue falso, e não há gesto de arrastar |
| o campo de data **editável** no cabeçalho | a data matriz é do **owner** (a rota recusa com 403), então na tela ela é texto. 🚨 Botão que o servidor recusa é pior que botão nenhum |

## 6.9 Onde está cada peça nova

| peça | arquivo |
|---|---|
| migração | `migracoes/082_a_os_do_chamado.sql` |
| as regras do chamado (ids, mapa, descrição, cliente) | `movizap/chamado_os.py` |
| o quadro, a data matriz e a junção | `movizap/paineis.py` |
| o cliente da ponte | `movizap/fpsl_ponte.py` — `criar_os`, `os_por_situacao` |
| as rotas do painel | `movizap/main.py` — `ver_painel`, `definir_desde_do_painel` |
| a escrita e a leitura no ERP | `fpsl_weso/fpsl_weso/routers/os_ponte.py` — `criar_os`, `os_por_situacao` |
| o conserto do catálogo de tipos | `fpsl_weso/fpsl_weso/services/sync_tipos_os.py` |
| a tela | `frontend/src/telas/PainelOperacao.vue` |
| a prova no ERP (cria e apaga) | `fpsl_weso/provar_criacao_os.py` |
