# 08 — Identidade: de quem é o número que acabou de escrever

**Auditado em 2026-08-06, contra a base real de 1.050 clientes.** Este
documento existe porque a resposta óbvia está errada em 4 de cada 5 casos.

---

## A pergunta

Chega uma mensagem de `+5519 2101-3000`. Quem é?

Se o número estivesse em um contato só, não haveria documento. Mas **44 números
da base estão em mais de um cliente** — um deles em **oito**.

```
Objetivo:     mensagem que chega é ligada à pessoa certa, ou a ninguém
Hoje:         medido, não implementado -- ver "O que foi decidido"
Por quê:      ligar à pessoa errada é pior que não ligar: o atendente vê a
              ficha de outra empresa e age sobre ela
Reavaliar se: o cadastro do ERP substituir o do Harmonit como fonte
```

---

## O que a auditoria mediu

`scripts/auditar_duplicados.py` e `scripts/auditar_natureza.py`, contra a API
real.

| | |
|---|---|
| Números em mais de um cliente | **44** |
| Clientes envolvidos | **110** |
| Vínculos telefone↔cliente em disputa | **81** de 1.248 (6,5 %) |
| Distribuição | 28 números em 2 clientes · 7 em 3 · 5 em 4 · 1 em 5 · 1 em 7 · 2 em 8 |

### 🚨 O achado que muda tudo: são **três** naturezas, não uma

| Natureza | Vínculos | Exemplo real |
|---|---|---|
| **(a) Mesmo cliente cadastrado várias vezes** | **17** | `FAXT TELECOMUNICACOES LTDA.` e `FAXT TELECOMUNICACOES LTDA` · `DANIELLA PORTASIO BORGES` duas vezes |
| **(b) Empresas genuinamente diferentes** | **30** | `+551932273720` → DANIEL MATIAS, ANTONIO CARLOS e EDUARDO GONÇALVES · `ALPHA CLICHERIA` e `SMART CLICHERIA` |
| **(c) Misto — grupo econômico + terceiro junto** | **34** | `+552121361900` → **três** `FAZENDA DA TOCA` **mais** `MANTIQUEIRA ALIMENTOS` |

**Só em (a) o número é de quem parece ser.** Em (b) é um terceiro — revendedor,
contador, familiar, instalador. Em (c) há um grupo econômico legítimo e um
estranho no meio.

---

## Por que "o mais antigo fica com o número" não basta

A regra pedida pelo usuário em 06/08 foi: *o número fica só no cliente mais
antigo cadastrado; os repetidos não entram.*

Ela é **correta para (a)** — 17 vínculos — e **arbitrária para (b) e (c)** — 64
vínculos. Aplicada sozinha, ela acerta **21 %** dos casos e chuta os outros 79 %.

E o chute não é inofensivo. Em `+553837215181`, oito empresas de energia solar
diferentes dividem o número de um instalador. A regra elegeria a `GM ENERGIA`
porque é a única com data — e as outras sete perderiam o telefone **sem que
ninguém soubesse**, enquanto a GM ganharia a identidade de todas.

### 🚨 E a data de cadastro não é confiável

| | |
|---|---|
| Clientes **sem data utilizável** | **303 de 1.050 (28,9 %)** |
| Campo ausente ou vazio | 291 |
| Sentinela `0001-01-01T00:00:00` | 12 |

🚨 **`0001-01-01` é o vazio do .NET, não uma data.** Ele parseia sem erro e
vira o ano 1 — então, sem tratamento, **o registro sem data ganharia toda
disputa de "quem é o mais antigo"**. A regra ficaria exatamente invertida, e
nada acusaria: o resultado é plausível, só está errado.

Range real, depois de tirar o sentinela: **12/08/1967 a 22/07/2026**.

⚠️ Ordenar por data dá resultado **diferente** de ordenar por `harmonit_id` em
**665 de 747** posições. Então o id não substitui a data — mas a data falta em
29 % dos casos. Nenhum dos dois critérios resolve sozinho.

---

## Os `[NÃO USAR]` são um problema separado, e pequeno

**3 clientes** têm marca no nome (`[NÃO USAR]`, `(INATIVADO)`) — dois inativos,
um ativo. Os três têm telefone.

⚠️ **Descartá-los resolve zero dos 44 números compartilhados.** Eu tinha
sugerido que ajudaria; a auditoria mostrou que não. São dois problemas
independentes que por acaso aparecem juntos no `+551932780637`.

---

## O que foi decidido — confirmado pelo usuário em 06/08

```
Objetivo:     o número identifica quem ele realmente identifica
Hoje:         (a) resolve sozinho; o duvidoso NAO SOBE -- fica em arquivo
Por quê:      a regra automática acerta 21% e chuta 79%. "Não sobe ainda,
              pode sujar a base nova" -- decisão do usuário em 06/08
Reavaliar se: o usuário validar os 96 vínculos caso a caso
```

**"Não cadastre os duvidosos ainda."** O vínculo duvidoso não entra em
`contato_telefone` e é listado em `revisao/`, para validação caso a caso.

| | |
|---|---|
| Números compartilhados | **44** |
| Resolvidos sozinho (mesmo cliente) | **12** |
| **Esperando validação** | **32** |
| Vínculos que ficaram de fora | **96** |

⚠️ **Os números da lista são maiores que os da auditoria** (96 contra 81). A
auditoria contou o excedente por número — quantos vínculos passariam do
primeiro. A lista conta **todos** os vínculos de um número duvidoso, porque
quando o caso vai para revisão **ninguém** recebe o número, nem o mais antigo.
São medidas de coisas diferentes, e a da lista é a que vale.

A lista é **gerada** por `scripts/listar_revisao.py` e não se edita à mão. O
sync relê o Harmonit inteiro a cada 12 h: corrigir lá muda a lista sozinho.

| Caso | O que o sync faz |
|---|---|
| **(a) mesmo cliente** | número fica com o **mais antigo**: `cadastrado_em`, desempate por `harmonit_id`. Os demais não recebem |
| **(b) empresas diferentes** | **ninguém recebe** o número. Vai para a lista de revisão |
| **(c) misto** | **ninguém recebe.** Vai para a lista de revisão |
| **`[NÃO USAR]` / `(INATIVADO)`** | marcado `revisar`, com motivo. Não é apagado |

**Nada é apagado.** O que não entra em `contato_telefone` continua no Harmonit
e volta assim que a regra mudar — o sync relê tudo a cada 12 h.

### Como (a) é distinguido de (b)

Comparação do **núcleo** do nome: tira `LTDA`, `ME`, `EPP`, `EIRELI`, `S/A`,
`COMÉRCIO`, `INDÚSTRIA`, `MATRIZ`, `FILIAL` e conectivos, e compara o que
sobra. Igual, contido, ou 72 % de semelhança ⇒ mesmo cliente.

⚠️ **É heurística, e heurística erra.** Por isso ela só decide o caso fácil —
quando *todos* os nomes do grupo se parecem. Qualquer mistura cai em revisão.
O custo de errar para mais é uma linha a revisar; para menos, é ficha errada
no atendimento.

---

## Consequência para o atendimento

Quando chegar mensagem de um número em revisão, o sistema **não terá contato
para exibir** — e isso é o comportamento certo. A tela dirá que o número está
em revisão e mostrará os candidatos, em vez de escolher um.

A saída definitiva não é uma regra melhor: é **a IA perguntar** *"você está
falando em nome de qual empresa?"* e gravar a resposta. Isso resolve (b) e (c)
com a única fonte que sabe a verdade — a pessoa do outro lado. Entra quando a
`CFG_2.1` existir.
