# Lógica de fluxo do atendimento — extraída do MoviBot

**Origem:** `movibot/flows/{welcome,financeiro,suporte_tecnico,contratual}.yaml`,
extraídos em 2026-08-13 antes de o MoviBot ser eliminado. O MoviBot era um bot
de menu numerado; **o MoviZap não vai repetir o menu**, mas a lógica de triagem
abaixo é conhecimento de negócio e não pode se perder com o diretório.

Destino: virar seção "COMO TRIAR" de uma versão de prompt na `CFG_2.1`.

---

## 1. Identificação

```
telefone -> cliente?
  achou      -> saúda pelo nome fantasia e triа
  não achou  -> pede CNPJ/CPF + nome -> tenta de novo
                 achou     -> segue normal
                 não achou -> só resta transferir
```

⚠️ **Não perguntar "posso te identificar pelo número?"** — foi removido em
22/07: o fluxo já prevê os dois desfechos, então a pergunta só gastava um turno.

🚨 **Não existe nome do contato.** O `contatoPrincipal` do Harmonit nunca
devolve `nome` — só `celular`, `contatoPrincipalId`, `email`, `telefone`,
`telefone2`. Usar `nome_fantasia` do cliente. Um `{nome_contato}` vazio saía
como *"Eu falo com  mesmo?"* para 100% dos clientes.

## 2. Os quatro caminhos

| Assunto | Fecha em |
|---|---|
| Contratual | equipe Contratual |
| Financeiro | equipe Financeiro |
| Suporte Técnico | Operacional, Agendamento ou Pós Venda, conforme o caso |
| "Falar com meu especialista" | Pós Venda |

## 3. Financeiro

- **Consultar situação** → busca boletos. Sem boleto em aberto, a resposta é
  "está tudo em dia", não um erro.
- **2ª via de boleto** → escolher a parcela pelo vencimento e valor.
  🚧 **Parado de propósito desde 22/07**: o envio do PDF usava
  `evolution.send_document` e a inbox de atendimento virou Meta Cloud. Religar
  quando o anexo migrar.
- **Comprovante de pagamento** → coleta o arquivo e transfere.
- **Negociar débitos**, **Notas fiscais**, **Renegociação** → transferem.

Etiquetas usadas no Chatwoot: `comprovante`, `negociacao`, `notas-fiscais`,
`renegociacao`. Servem para a equipe filtrar a fila.

## 4. Suporte técnico

**Rastreador sem comunicação** e **equipamento com defeito** seguem a mesma
cadeia:

```
houve manutenção recente no veículo?  ->  o veículo deu ou recebeu carga?
  ->  qual a placa?  ->  peça áudio/foto/vídeo  ->  equipe Operacional
```

🚨 **AS DUAS PERGUNTAS NÃO RAMIFICAM.** "Sim" e "Não" vão para o mesmo lugar
nas duas. Elas existem para **coletar contexto para o técnico**, não para
decidir caminho. No prompt isso vira: *pergunte para levar a resposta junto,
não para escolher o que fazer.* Manutenção recente e carga são as duas causas
mais comuns de rastreador mudo — é diagnóstico, não formulário.

- **Agendamento** → pede a placa → equipe Agendamento.
- **Plataforma com problemas** → navegador ou celular? → pede print → Pós Venda.
- **Outros assuntos** → mesmas cadeias, mas o destino é **sempre Pós Venda**;
  inclui "acesso a dados ou backup", que não existe nos outros caminhos.

Sempre que transferir por problema técnico: **pedir áudio, foto ou vídeo**.

## 5. Contratual

Quatro pedidos, cada um com formulário próprio: adicionar/remover veículo,
trocar equipamento, venda de veículo, transferir para outro CNPJ. Manda o link
do formulário e transfere para a equipe Contratual.

---

## 🚨 O que NÃO copiar sem decidir antes

**Metade dos destinos não tem ninguém.** Medido no Chatwoot em 06/08: com
membro estão Comercial (Claudia), Financeiro (Karla), Suporte (Erika) e Geral
(Administrador). **Contratual, Pós Venda e agendamento não têm nenhum membro**,
e **"Operacional" não aparece na lista de times** — o fluxo do MoviBot escalava
para um nome que pode nem existir.

Ou seja: reproduzir esse roteamento como está manda cliente para fila vazia, em
silêncio. Antes de a IA usar isso, é preciso decidir para onde vai cada caso —
e essa decisão é do usuário, não minha.

**Sem menu numerado.** O MoviBot obrigava o cliente a escolher número. A regra
do prompt do MoviZap é o contrário: *o cliente escreve do jeito dele e você
entende*. O que se aproveita daqui é **para onde cada assunto vai e o que
perguntar antes de transferir** — não a forma.
