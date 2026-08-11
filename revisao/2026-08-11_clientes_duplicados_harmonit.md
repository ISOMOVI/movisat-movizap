# Clientes duplicados — resolver NO HARMONIT

> 🚨 GERADO por script. **Nada foi alterado.** Cada linha tem
> `harmonit_id` próprio: são registros diferentes no Harmonit, e o
> sync faz upsert por esse id a cada 12h. Consertar no MoviZap é
> desfeito às 05:45 — a correção é lá.

- documentos repetidos: **7**
- linhas a mais: **10**
- conversas em risco de ir para o cadastro errado: **1**

## Recomendação

Manter quem tem mais histórico (conversa > telefone > contato > mais antigo). ⚠️ marca empate: decida você.

| Documento | harmonit_id | Nome | Contatos | Tel | Conversas | |
|---|---|---|---|---|---|---|
| `22860204000135` | `247895` | BASEPEX ENCOMENDAS URGENTES LTDA | 1 | 1 | 0 | ⚠️ empate |
| `22860204000135` | `249962` | BASEPEX ENCOMENDAS URGENTES LTDA | 1 | 1 | 0 | unificar |
| `22860204000135` | `255341` | BASEPEX ENCOMENDAS URGENTES LTDA | 1 | 1 | 0 | unificar |
| | | | | | | |
| `23076958000161` | `30801` | HORSE LOCADORA DE VEICULOS E EQUIPAMENTOS LTDA | 1 | 0 | 0 | ⚠️ empate |
| `23076958000161` | `90922` | HORSE LOCADORA DE VEICULOS E EQUIPAMENTOS LTDA. | 1 | 0 | 0 | unificar |
| `23076958000161` | `90923` | HORSE LOCADORA DE VEICULOS E EQUIPAMENTOS LTDA. | 1 | 0 | 0 | unificar |
| | | | | | | |
| `34942225841` | `266473` | Rodrigo Vannuci | 1 | 1 | 0 | ⚠️ empate |
| `34942225841` | `888925` | RODRIGO JOSÉ VANNUCCI | 1 | 1 | 0 | unificar |
| `34942225841` | `30899` | EQUIPE COMERCIAL | 1 | 0 | 0 | unificar |
| | | | | | | |
| `01212782000195` | `77059` | HR TRANSPORTES | 2 | 2 | 0 | **MANTER** |
| `01212782000195` | `190945` | HELIO RONCHIN IBATE | 1 | 0 | 0 | unificar |
| | | | | | | |
| `05394225000193` | `30835` | DANIELLA PORTASIO BORGES | 1 | 1 | 0 | ⚠️ empate |
| `05394225000193` | `265962` | DANIELLA PORTASIO BORGES | 1 | 1 | 0 | unificar |
| | | | | | | |
| `08897417000291` | `30697` | FW DISTRIBUIDORA LTDA | 2 | 5 | 1 | **MANTER** |
| `08897417000291` | `302344` | F W DISTRIBUIDORA LTDA. | 1 | 0 | 0 | unificar |
| | | | | | | |
| `76166766858` | `30705` | THIAGO TÉCNICO | 1 | 1 | 0 | **MANTER** |
| `76166766858` | `30665` | RELISON POSSIDONIO | 1 | 0 | 0 | unificar |
| | | | | | | |

## 🚨 Dois casos que não são duplicata — são CPF errado

- `76166766858` está em **RELISON POSSIDONIO** e **THIAGO TÉCNICO**: nomes diferentes com o mesmo CPF. Um dos dois está com o documento de outra pessoa.
- `01212782000195` está em **HR TRANSPORTES** e **HELIO RONCHIN IBATE** — pode ser a pessoa física e a empresa dela com o mesmo número, o que também é erro de cadastro.

- `34942225841` está em **EQUIPE COMERCIAL**, **Rodrigo Vannuci** e **RODRIGO JOSÉ VANNUCCI** — o mesmo CPF em três cadastros, um deles com nome de setor.
