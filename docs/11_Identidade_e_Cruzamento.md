# 11 — Identidade, vínculo e cruzamento de dados

> Desenho aprovado pelo usuário em **2026-08-10**. É a peça que decide se o
> painel vira cadastro confiável ou uma pilha de palpites — e vale para o
> WhatsApp, para o e-mail e para o ERP que vem depois.

---

## O problema

Quatro sistemas afirmam quem é quem, e **nenhum é autoridade sobre tudo**:

| Fonte | Sabe de verdade | Não sabe |
|---|---|---|
| **Harmonit** | quem paga — 944 ativos, com CNPJ | contato atualizado: 574 sem WhatsApp alcançável |
| **Bitrix** | quem foi abordado — 14.214 pessoas, 3.884 empresas | quem é cliente hoje (7.113 são prospect) |
| **WhatsApp** | o número, e o nome que a pessoa escolheu | de qual empresa ela fala |
| **Gmail** | o endereço, e o nome no cabeçalho | se o endereço é dela ou do escritório |

---

## A espinha: separar **fato observado** de **identidade afirmada**

### Camada 1 — Observação (nunca é verdade, nunca se apaga)

O que cada sistema **diz**, com origem e data. O Bitrix inteiro vive aqui
(`bitrix_contato`, `bitrix_chave`), incluindo prospect e ex-cliente.

🚨 **Nada nesta camada identifica ninguém.** Ela responde *"o que se sabe sobre
este número?"* — nunca *"de quem é este número?"*.

### Camada 2 — Vínculo (o cadastro)

`contato_telefone` e `contato.email`. **Só entra o que tem prova, ou o que uma
pessoa confirmou na tela** — e cada linha carrega de onde veio
(`origem_campo`, `email_origem`).

### Camada 3 — Exibição

Uma regra só, em todas as telas:

```
1º  nome do cadastro       ← se há vínculo. É o nome oficial
2º  nome que a pessoa usa  ← pushName do WhatsApp / remetente do e-mail
3º  o identificador        ← número ou endereço
```

---

## 🚨 A régua de confiança

Cada chave vale uma coisa diferente. **Esta tabela é a regra da casa:**

| Chave | Força | O que o sistema faz |
|---|---|---|
| **CNPJ / CPF igual** | prova | **vincula sozinho** |
| Telefone E164 em **1** cadastro | forte | **vincula sozinho** |
| Telefone em **N** cadastros | é pessoa de grupo | **mostra as N empresas, não escolhe** |
| E-mail corporativo em 1 cadastro | forte | vincula sozinho |
| E-mail `gmail`/`hotmail` | fraco | **sugere, não vincula** |
| **Nome de empresa normalizado** | indício | 🚨 **NUNCA vincula** — vai para revisão |

⚠️ **A última linha é a disciplina que mais importa.** Foi por nome que se
encontraram as 305 empresas do Bitrix que parecem clientes nossos — e é por
isso que elas **não foram importadas**. "Transportes Silva" existe dez vezes no
Brasil.

---

## Os selos na tela

| Selo | Significa |
|---|---|
| 🟢 Cliente | vinculado com prova |
| 🔵 Cliente (confirmado por você) | vínculo manual feito no atendimento |
| 🟡 **Aparece no Bitrix** | há observação, **não** há vínculo |
| ⚪ Desconhecido | nada em lugar nenhum |

🚨 **O selo amarelo é o mais importante.** Deixa o atendente ver *"esta pessoa
já foi abordada como prospect em março"* **sem o sistema afirmar que ela é
cliente**. Informação sem mentira.

⚠️ Ele aparece **só quando não há vínculo**: com cliente identificado seria
ruído, e poderia contradizer o cadastro na cara de quem atende.

---

## O plano do Bitrix, em quatro passos

| # | Passo | Estado |
|---|---|---|
| **1** | Importar em tabelas próprias, fora do cadastro | ✅ **10/08** — 14.214 contatos, 23.854 chaves |
| **2** | Exportar **COMPANY** do Bitrix | ⬜ **é o próximo, e é do usuário** |
| **3** | Promover ao cadastro **só o que casar por documento** | ⬜ depende do 2 |
| **4** | O que casar por nome/e-mail → **lista de revisão** | ⬜ depende do 2 |

### O que o passo 1 já entregou

```
61 de 72 conversas sem vínculo agora têm informação  (85%)
36 de 70 e-mails sem cliente também
cadastro intocado: 944 clientes · 945 contatos · 1.055 telefones
```

O `+55 15 98107-1358` — que em 10/08 apareceu como número desconhecido
notificando OS — passou a mostrar **Fabrício Augusto Camargo, E-METAL
ESQUADRIAS, Cliente**. O caso fechou sozinho.

### Por que o passo 2 destrava tudo

O Bitrix separa **contato** de **empresa**, e **o CNPJ mora na empresa** — por
isso só 5% dos contatos têm documento, e o cruzamento por documento deu 4%.
Pelo eixo certo (empresa), são **305 empresas** e **160 clientes** que ganhariam
telefone.

Sem o `COMPANY`, a escolha é ruim dos dois lados: não importar (perder 160
clientes) ou importar por nome (sujar o cadastro).

---

## ⚠️ O que a medição revelou, e não pode ser esquecido

1. **1.810 contatos sem tipo e 309 ex-clientes.** Importar sem filtrar traria
   ex-cliente de volta para uma base de onde 106 inativas acabaram de sair.
2. **8.401 telefones existem só no Bitrix**, a maioria prospect. No cadastro,
   fariam o alcance "subir" no papel e o painel ofereceria conversa com quem
   nunca foi cliente.
3. **42% têm nome de empresa, mas só 25% têm o ID da empresa ligado.** O
   vínculo formal no Bitrix está incompleto: alguém digitou o nome e não fez a
   ligação.
4. **Vincular remetente automático suja o cadastro.** Provado ao vincular
   `data-studio-noreply@google.com` — funcionou como projetado, e é o argumento
   a favor do marcador no Gmail separando o que é atendimento.

---

## Por que isto não vira mais um silo

O ERP vai substituir o Harmonit e o Bitrix já está saindo. Enfiar o Bitrix
dentro do cadastro criaria uma **terceira verdade** — e em seis meses alguém
pergunta qual vale.

A camada de observação faz o oposto: guarda **o que cada sistema disse, com
data**, e deixa o cadastro limpo. Quando o ERP nascer, herda o cadastro provado
e a memória de onde cada coisa veio.
