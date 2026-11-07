-- ============================================================================
-- 096 — O PAINEL DO FINANCEIRO, com as dez colunas que ele escreveu
-- ============================================================================
-- 🔵 06/11, pedido dele: *"do 1"* (as colunas do Financeiro, a pendência que
-- ficou de 05/11) seguido da lista, e *"conclua e exiba o financeiro no paniel
-- para owner"*. As dez, na ordem dele:
--
--   Nova solicitação · Contratos assinados · Contrato vinculado no financeiro ·
--   Aguardando prazo · Aguardando Datascope · Em tratativa ·
--   Aguardando terceiros · INADIMPLENTES · Atendimento feito · Não atendido
--
-- 🚨 NENHUMA DESTAS COLUNAS EXISTE NO HARMONIT, como nas do Pós-venda: mover
-- card aqui escreve **só aqui**. É o mesmo motor (`pipeline.py`), e a trava que
-- prova que esta tela não fala com o ERP já existe no `teste_abas.py`.
--
-- 🚨 UMA ABA, E NÃO QUATRO. O `painel_aba` do Pós-venda tem duas linhas porque
-- ele escreveu duas listas de colunas. Aqui ele escreveu **uma** lista, sob o
-- título "Colunas", para o Financeiro. ⚠️ O que havia antes sobre "abas do
-- financeiro" era o **exemplo de permissão** (*"a Erika, apenas a aba 3"*),
-- que ele mesmo marcou como *"Apenas exemplo"*, e a lista do §2.1 do
-- `MoviZap_Formularios_PLANO.md` (`Financeiro · Pagamento técnicos ·
-- Administrativo · Fornecedores`), que é de **FORMULÁRIOS**, não de etapas.
-- Inventar quatro abas e repartir dez colunas entre elas seria escopo meu.
-- Aba nova é uma linha aqui e uma no `telas.py`, no dia em que ele disser.
--
-- 🚨 "INADIMPLENTES" ENTRA COM O NOME, E SEM A AUTOMAÇÃO. Ele escreveu
-- *"INADIMPLENTES (Automação move para pipeline Cobrança)"* -- o parêntese é
-- COMPORTAMENTO FUTURO, não parte do nome da coluna. E não dá para construí-lo
-- hoje: o painel "Cobrança" **não existe**, nem como tela nem no vocabulário
-- (`painel_aba_painel_conhecido` aceita só `operacao`, `pos_venda`,
-- `contratual` e `financeiro`). Automação que move card para pipeline que não
-- existe não é automação, é perda de card. Fica como decisão dele, escrita nos
-- Próximos Passos.
--
-- 🚨 DUAS COLUNAS FINAIS, e não uma. No Pós-venda só a última era `final`
-- porque só havia um fim. Aqui **"Atendimento feito" e "Não atendido" são os
-- dois fins** -- marcar só a última diria que chegar em "Atendimento feito" não
-- é terminar, e isso é falso. ⚠️ `final` continua sendo só o fato escrito no
-- banco: nada na tela depende dele ainda.
--
-- 🔴 O PAINEL NASCE VAZIO, E ISSO É ESTADO, NÃO DEFEITO: a ORIGEM dos cards
-- segue em aberto por decisão dele de 06/11 (*"3 por enquanto matem assim"*).
-- Nenhum formulário alimenta o Financeiro hoje. A tela **diz** isso -- "Nenhum
-- card nesta aba ainda." -- em vez de parecer quebrada.
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. A ABA
-- ---------------------------------------------------------------------------
-- ⚠️ `NOT EXISTS` em vez de `ON CONFLICT`: mantém a migração repetível sem
-- depender de qual chave única a tabela tem hoje.
INSERT INTO painel_aba (painel, codigo_tela, titulo, ordem, ativo)
     SELECT 'financeiro', 'PNL_1.4', 'Financeiro', 1, true
      WHERE NOT EXISTS (SELECT 1 FROM painel_aba WHERE codigo_tela = 'PNL_1.4');

-- ---------------------------------------------------------------------------
-- 2. AS DEZ COLUNAS, NA ORDEM DELE
-- ---------------------------------------------------------------------------
-- 🚨 A ORDEM É O FLUXO, e é a coisa mais fácil de perder: um `sorted()`
-- bem-intencionado destruiria o caminho sem quebrar nada visível. O
-- `teste_painel_financeiro.py` compara a lista inteira, posição por posição.
INSERT INTO pipeline_etapa (aba_id, titulo, ordem, ativo, final)
     SELECT a.id, t.titulo, t.ordem, true, t.final
       FROM painel_aba a
       CROSS JOIN (VALUES ('Nova solicitação',                  1, false),
                          ('Contratos assinados',               2, false),
                          ('Contrato vinculado no financeiro',  3, false),
                          ('Aguardando prazo',                  4, false),
                          ('Aguardando Datascope',              5, false),
                          ('Em tratativa',                      6, false),
                          ('Aguardando terceiros',              7, false),
                          ('INADIMPLENTES',                     8, false),
                          ('Atendimento feito',                 9, true),
                          ('Não atendido',                     10, true))
                  AS t(titulo, ordem, final)
      WHERE a.codigo_tela = 'PNL_1.4'
        AND NOT EXISTS (SELECT 1 FROM pipeline_etapa e
                         WHERE e.aba_id = a.id AND e.titulo = t.titulo);

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('096', now(),
        'o painel do Financeiro (PNL_1.4) com as 10 colunas dele');

COMMIT;

-- ============================================================================
-- CONFERÊNCIA (rodar depois, e o esperado está escrito)
-- ============================================================================
--   SELECT painel, codigo_tela, titulo FROM painel_aba ORDER BY painel, ordem;
--     -- esperado: financeiro/PNL_1.4 · operacao/PNL_1.1 ·
--     --           pos_venda/PNL_1.2 · pos_venda/PNL_1.3
--   SELECT e.ordem, e.titulo, e.final FROM pipeline_etapa e
--     JOIN painel_aba a ON a.id = e.aba_id
--    WHERE a.codigo_tela = 'PNL_1.4' ORDER BY e.ordem;
--     -- esperado: as 10 na ordem dele, com `final` só nas duas últimas
--   SELECT count(*) FROM pipeline_card c JOIN pipeline_etapa e ON e.id = c.etapa_id
--     JOIN painel_aba a ON a.id = e.aba_id WHERE a.codigo_tela = 'PNL_1.4';
--     -- esperado: 0 -- a ORIGEM dos cards é decisão dele
-- ============================================================================
