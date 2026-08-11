# A cadeia do Bitrix — o que produziu os 862 números do cadastro

> Rodada uma vez, em **2026-08-11**. Está aqui porque o resultado dela está no
> cadastro: sem estes scripts não há como auditar de onde veio cada linha
> `origem = 'bitrix'`, nem refazer o extrato se algo estiver errado.

🚨 **Os scripts são de UMA passada, não de rotina.** O Bitrix está saindo e não
haverá nova exportação — o `COMPANY` nunca virá (decisão do usuário em 11/08).
Nenhum deles está no cron, e nenhum deve entrar.

## A ordem importa

Cada etapa escreve por cima do arquivo da anterior. Rodar fora de ordem produz
um arquivo diferente e silenciosamente errado.

| # | Script | O que faz | Entra → Sai |
|---|---|---|---|
| 01 | `01_extrair_clientes_ativos.py` | filtra do arquivo de 35 MB só os contatos de empresas que são cliente **ativo** | `.xls` → `BITRIX_CLIENTES_ATIVOS.csv` (1.450 linhas) |
| 02 | `02_gerar_chaves.py` | vira uma linha por chave (telefone/e-mail) | → `BITRIX_CHAVES.csv` (2.402) |
| 03 | `03_limpar_internos.py` | tira e-mails `@movisat.com.br` e o que aponta a própria Movisat | −49 |
| 04 | `04_tratar_formatos.py` | `+55` que faltava · `@whatsapp.wazzup` vira telefone · marca fixo/gratuito/nono dígito | −36 |
| 05 | `05_corrigir_subtipo.py` | recalcula o subtipo a partir da chave corrigida | 8 rótulos |
| 06 | `06_confirmar_pelo_painel.py` | preenche WhatsApp com o que o MoviZap já sabia | 196 sem gastar chamada |
| 07 | `07_consolidar_matriz.py` | contatos do mesmo grupo vão para a matriz | 15 clientes |
| 08 | `08_verificar_evolution.py` | pergunta ao Evolution quem existe no WhatsApp | 963 números |
| 09 | `09_salvar_no_cadastro.py` | grava os que têm WhatsApp, na empresa deles | **+805 contatos, +878 telefones** |

## O que ficou no cadastro, e como desfazer

```
contato           945 → 1.750   origem = 'bitrix'
contato_telefone 1.055 → 1.933   origem_campo = 'bitrix'
cliente           944 →   944   INTOCADO
```

Desfazer é uma linha, e é por isso que a marca de origem existe:

```sql
DELETE FROM contato WHERE origem = 'bitrix';   -- leva os telefones junto
```

## As armadilhas que estes scripts já pagaram

🚨 **Número repetido no mesmo lote derruba o lote inteiro** no Evolution, com
HTTP 400 `numbers contains duplicate item` — e o sintoma engana, parece limite
de chamadas. O `08` agrupa por número distinto antes de perguntar.

🚨 **Falha de rede não vira "não tem WhatsApp".** Fica em branco para a próxima
rodada. Gravar `false` por timeout silenciaria o cliente para sempre.

🚨 **Celular sem o `+55` tem 11 dígitos, igual a um CPF.** Sem conferir o
dígito verificador, `(18) 99811-6168` viraria o "documento" 18998116168 — e
documento é a única chave que vincula sozinha.

🚨 **`+19981227491` é DDD 19, não Estados Unidos.** O `+` colado sem o 55 fez
o parser ler código de país. Oito números brasileiros.

🚨 **`5514998323471@whatsapp.wazzup` não é e-mail, é telefone.** Vinte e cinco
números com WhatsApp comprovado estavam disfarçados de endereço inválido.

🚨 **Documento `00000000000000` não agrupa nada.** Ele aparece em mais de um
cliente e chegou a fundir `AGILIS GROUP` com `CEASA CAMPINAS` numa primeira
tentativa — duas empresas sem relação alguma.

⚠️ **Padrão de `LIKE` vai como parâmetro**, nunca dentro do SQL: `'%IAGO%'`
faz o psycopg ler `%I` como placeholder e estourar antes de consultar.
