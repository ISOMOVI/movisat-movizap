# 12 — O Bitrix entra no cadastro: 862 números, 39% → 61% de alcance

> Trabalho de **2026-08-11**. Fecha o assunto Bitrix: o `COMPANY` não virá, e
> o que dava para aproveitar foi aproveitado. O que sobrou não é limitação
> técnica, é o tamanho real da interseção entre as duas bases.

---

## O que mudou

```
contato           945 → 1.750     +805, todos origem = 'bitrix'
contato_telefone 1.055 → 1.933     +878, todos origem_campo = 'bitrix'
cliente           944 →   944     INTOCADO

clientes alcançáveis por WhatsApp:  370 → 577   (39,2% → 61,1%)
```

**862 números com WhatsApp verificado** entraram, distribuídos em **325
clientes**. Nenhum é suposição: o Evolution respondeu `exists` para cada um,
ou a pessoa já tinha conversado com a gente.

---

## 🚨 A decisão que inverteu o `docs/11`

O `docs/11` fixou, em 10/08, que **nome de empresa NUNCA vincula**. Era uma
regra escrita sem medição — e a medição de 11/08 a contradiz.

**O teste:** dos contatos do Bitrix onde existiam ao mesmo tempo o nome da
empresa **e** uma chave dura (telefone ou e-mail já no cadastro), verificou-se
se as duas apontavam o mesmo cliente.

```
265 contatos com nome E chave dura
254 concordam      → 95,8%
 11 discordam
```

**95,8%** — praticamente a mesma confiança do telefone e do e-mail exatos
(96,7%). E as 11 discordâncias não são aleatórias: `503 ENGENHARIA` ↔ `ETRO
CONSTRUÇÃO` aparece dos dois lados e compartilha domínio de e-mail. São
empresas que dividem estrutura, não erro de algoritmo.

⚠️ **A ressalva honesta:** só foi possível validar onde havia segunda chave.
Nome sozinho — que alcança 206 dos 423 clientes — não tem nada que o confirme.

**A decisão foi do usuário, em 11/08:** *"já que sabemos de qual empresa os
números são e os que têm WhatsApp, é só salvar no cadastro deles a empresa"*.
Nome de empresa, contra cliente **ativo**, com núcleo normalizado, passou a
vincular.

---

## A régua, como ficou

| Chave | Força | O que o sistema faz |
|---|---|---|
| CNPJ / CPF igual | prova | vincula sozinho |
| Telefone E164 em 1 cadastro | forte | vincula sozinho |
| E-mail corporativo exato em 1 cadastro | forte | vincula sozinho |
| **Nome de empresa × cliente ATIVO** | **95,8% medido** | **vincula** *(decisão de 11/08)* |
| Telefone em N cadastros | é grupo | mostra as N |
| **Domínio de e-mail** | 🚨 **0/6 no teste** | **não vincula** |

### Por que o domínio de e-mail reprovou

Parecia a via mais promissora e foi a única que a medição derrubou por
completo. Dos 22 domínios que apontam mais de um cliente, **16 são empresas
realmente distintas** — e o motivo é estrutural do setor:

- `tnevelog.com.br` → **12 clientes**, cada um com CNPJ próprio: transportadora
  com agregados, e todo agregado usa o e-mail da transportadora;
- `solarenergia.ind.br` → 13 empresas distintas;
- `movisat.com.br` → 12 clientes — o nosso próprio domínio no cadastro de
  terceiros.

Não há critério mais rígido que a salve: domínios únicos sustentados por dois
ou mais e-mails do cadastro são **zero**. Não existe amostra para validar.

---

## Onde o documento estava, e o que ele não tinha

| O que se procurava | O que o `CONTACT` tem |
|---|---|
| CNPJ das empresas | **811 valores, 669 válidos, 147 CNPJs distintos** — e `"Hello"` repetido 142 vezes |
| Ligação formal contato→empresa | 3.598 (25,3%) têm o **ID**; 6.024 (42,4%) têm só o **nome** |
| Telefone | 6.767 comerciais · 2.035 celulares |
| E-mail | 9.803 de trabalho |
| Colunas | **242, das quais 120 estão 100% vazias** |

**O documento é a chave que não existe aqui**: dos 14.214 contatos, só 507 têm
documento válido, e apenas **38 casam com cliente ativo**. O CNPJ mora na
empresa, e a empresa não foi exportada.

---

## A interseção real das duas bases

```
944  clientes ativos
423  encontrados pelo NOME da empresa      (44,8%)
324  encontrados por telefone/e-mail        (34,3%)
217  pelos dois
─────
530  união                                  (56,1%)
414  não estão no Bitrix por caminho nenhum
```

**56,1% é o teto**, não uma etapa. Sem o `COMPANY`, os 44% restantes não têm
por onde ser alcançados — e isso não é falha de método, é o tamanho da
sobreposição entre um CRM comercial e uma base de clientes pagantes.

---

## O que o WhatsApp respondeu

```
1.174 telefones no extrato
  970 TÊM WhatsApp   (82,6%)
  204 não têm

  818 verificados no dia      36 já tinham conversa no painel
   91 verificados antes       25 vieram do integrador Wazzup
```

⚠️ **196 foram resolvidos sem gastar uma chamada** — o próprio painel já sabia,
e 46 deles eram números que o Evolution **já havia negado**. Perguntar o que se
sabe é desperdício, e a fonte mais confiável das três é a conversa que chegou.

---

## As armadilhas que este trabalho pagou

🚨 **Celular sem `+55` tem 11 dígitos, exatamente como um CPF.** Sem conferir o
dígito verificador, `(18) 99811-6168` viraria o documento `18998116168` — e
documento é a única chave que vincula sozinha. Um telefone na coluna errada
casaria empresas sem relação nenhuma.

🚨 **`+19981227491` é DDD 19, não Estados Unidos.** O `+` colado sem o 55 fez o
parser ler código de país; oito números brasileiros viraram estrangeiros.

🚨 **`5514998323471@whatsapp.wazzup` não é e-mail — é telefone.** Descartá-lo
como "domínio inválido" jogaria fora 25 números com WhatsApp comprovado.

🚨 **Documento `00000000000000` não agrupa nada.** Numa primeira tentativa ele
fundiu `AGILIS GROUP` com `CEASA CAMPINAS`, porque os dois "têm o mesmo CNPJ".

🚨 **Os pesos do CPF vão de 10 a 2 e não ciclam** — diferente do CNPJ. Usar a
ciclagem do CNPJ reprova CPF válido.

⚠️ **O `Tipo de Contato` do Bitrix não serve de filtro:** dos 1.450 contatos
que pertencem a cliente ativo, **631 estão marcados como "Prospect"** e só 576
como "Cliente". Quem decide quem é cliente é o Harmonit, e ele já decidiu.

---

## O que ficou de fora, e por quê

| O quê | Motivo |
|---|---|
| **1.036 e-mails** do extrato | mesma lógica dos telefones; não foram pedidos |
| Banco, Agência, Conta, PIX, RG (826 registros) | não temos uso, e é passivo de LGPD numa base que vira ERP |
| Fonte, UTM, Comentário | é marketing: o "Comentário" é o assunto da campanha de e-mail |
| Endereço | 13 registros com CEP em 14 mil contatos |
| Qualificação comercial (dor, objetivo, controles) | menos de 1% preenchido cada |

---

## O que o trabalho revelou sobre a nossa própria base

- **~49 "clientes ativos" não são clientes**: `vivo`, `AMBEV`, `SUNTECH`,
  `ITAU EMPRESAS`, `CEASA CAMPINAS`, e também `FERNANDO apagar`, `a`,
  `RETIRADA MOVISAT`, `19974140416` (um telefone no campo nome) e
  `27.772.156/0002-28` (um CNPJ no campo nome). Os IDs 141–193 são uma faixa
  contígua de fornecedores. **É do Harmonit — não se mexe.**
- **7 documentos duplicados** entre clientes ativos (10 linhas a mais).
- **A caixa de e-mail é 68% interna**: 144 de 212 mensagens vêm de
  `@movisat.com.br`. É o argumento mais forte para o marcador no Gmail.
- **`webhook_evento` cresce 1.077 linhas/dia** → 393 mil/ano, 15 MB em 5 dias.

---

## Onde as coisas estão

| O quê | Onde |
|---|---|
| A cadeia que produziu tudo | `scripts/bitrix/01…09` + `README.md` |
| O extrato final | `/home/claude/movizap_bitrix/BITRIX_CHAVES.csv` |
| O extrato completo (100 colunas) | `/home/claude/movizap_bitrix/BITRIX_CLIENTES_ATIVOS.csv` |
| O arquivo original de 35 MB | `/home/claude/movizap_bitrix/contatos_*.xls` — **fora do backup** |
| Auditoria de lixo do banco | `scripts/auditar_lixo.py` |

**Desfazer tudo:** `DELETE FROM contato WHERE origem = 'bitrix';`
