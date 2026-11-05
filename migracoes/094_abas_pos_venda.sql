-- ============================================================================
-- 094 — AS DUAS ABAS DO PÓS-VENDA, com as colunas que ele escreveu
-- ============================================================================
-- 🔵 05/11, pedido dele: *"a aba 'Operação' do Movizap é a mesma lógica para os
-- demais: Pós-venda - Abas - Permissão por abas / Aba 1: Treinamentos /
-- Solicitação: Agenda* / Treinamento 1: / Treinamento 2: / Entregue: /
-- Aba 2: Pós-venda"*, e depois as colunas da segunda: *"Solicitação: Testes:
-- Realizar Pós-venda: Pós-venda Realizado:"*.
--
-- 🚨 NENHUMA DESTAS COLUNAS EXISTE NO HARMONIT, e é a linha inteira: mover
-- numa das 17 da Operação escreve `situacaoId` no ERP; mover numa destas
-- escreve **só aqui**. É o mesmo motor da coluna `Chamados` (`pipeline.py`).
--
-- 🚨 UMA ENTRADA DE TELA POR ABA, e não uma para o painel: a permissão é por
-- aba — decisão dele (*"será por abas. então terá mais de uma pipeline, mas
-- todas dentro de 'Pós-Venda'"* · *"a Karla terá permissão para ver o
-- 'Financeiro' e todas as abas. A Erika, apenas a aba 3 do financeiro"*). E
-- `permissao` é campo da entrada do `telas.py`, então cada aba precisa da sua.
--
-- ⚠️ AS DUAS NASCEM SÓ DO OWNER — ele: *"todas hoje nascem somente para o
-- owner"*. Conceder é gesto dele, na `CFG`.
--
-- 🔴 OS CARDS NASCEM VAZIOS, E ISSO É ESTADO, NÃO DEFEITO: a ORIGEM deles ficou
-- em aberto por decisão dele (*"deixe em aberto, depois veremos"*). Hoje
-- `pos_venda` só recebe NPS e CES, e nenhum formulário alimenta Treinamentos.
-- Quando ele disser de onde vêm, é configuração — não código.
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. AS DUAS ABAS
-- ---------------------------------------------------------------------------
-- ⚠️ `NOT EXISTS` em vez de `ON CONFLICT`: não há UNIQUE em `codigo_tela` (de
-- propósito — a tabela não é o catálogo de telas, o `telas.py` é), então o
-- conflito não teria em que chave bater. Isto mantém a migração repetível.
INSERT INTO painel_aba (painel, codigo_tela, titulo, ordem, ativo)
     SELECT 'pos_venda', 'PNL_1.2', 'Treinamentos', 1, true
      WHERE NOT EXISTS (SELECT 1 FROM painel_aba WHERE codigo_tela = 'PNL_1.2');

INSERT INTO painel_aba (painel, codigo_tela, titulo, ordem, ativo)
     SELECT 'pos_venda', 'PNL_1.3', 'Pós-venda', 2, true
      WHERE NOT EXISTS (SELECT 1 FROM painel_aba WHERE codigo_tela = 'PNL_1.3');

-- ---------------------------------------------------------------------------
-- 2. AS COLUNAS DA ABA 1 — Treinamentos
-- ---------------------------------------------------------------------------
-- 🔵 *"Solicitação: Agenda* / Treinamento 1: / Treinamento 2: / Entregue:"*
--
-- ⚠️ O `Agenda*` da primeira coluna é LIGAÇÃO, não nome: ele respondeu *"Liga
-- na Agenda do MoviZap"*. As tabelas `agendamento` e `agendamento_os` já
-- existem (migrações 072/073), e o elo é frente própria — o título da coluna
-- é só "Solicitação".
--
-- 🚨 `final = true` SÓ NA ÚLTIMA: é o que diz que chegar ali é terminar. Ele
-- não pediu comportamento para isso ainda, e por enquanto é só o fato escrito
-- no banco — nada na tela depende dele.
INSERT INTO pipeline_etapa (aba_id, titulo, ordem, ativo, final)
     SELECT a.id, t.titulo, t.ordem, true, t.final
       FROM painel_aba a
       CROSS JOIN (VALUES ('Solicitação', 1, false),
                          ('Treinamento 1', 2, false),
                          ('Treinamento 2', 3, false),
                          ('Entregue', 4, true))
                  AS t(titulo, ordem, final)
      WHERE a.codigo_tela = 'PNL_1.2'
        AND NOT EXISTS (SELECT 1 FROM pipeline_etapa e
                         WHERE e.aba_id = a.id AND e.titulo = t.titulo);

-- ---------------------------------------------------------------------------
-- 3. AS COLUNAS DA ABA 2 — Pós-venda
-- ---------------------------------------------------------------------------
-- 🔵 *"Aba 2: Pós-venda / Solicitação: Testes: Realizar Pós-venda: Pós-venda
-- Realizado:"*
--
-- ⚠️ A COLUNA "Solicitação" APARECE NAS DUAS ABAS, e é assim mesmo: `titulo`
-- não é único no sistema, é único DENTRO da aba. Duas pipelines que começam
-- pelo mesmo nome são duas pipelines, e não uma compartilhada.
INSERT INTO pipeline_etapa (aba_id, titulo, ordem, ativo, final)
     SELECT a.id, t.titulo, t.ordem, true, t.final
       FROM painel_aba a
       CROSS JOIN (VALUES ('Solicitação', 1, false),
                          ('Testes', 2, false),
                          ('Realizar Pós-venda', 3, false),
                          ('Pós-venda Realizado', 4, true))
                  AS t(titulo, ordem, final)
      WHERE a.codigo_tela = 'PNL_1.3'
        AND NOT EXISTS (SELECT 1 FROM pipeline_etapa e
                         WHERE e.aba_id = a.id AND e.titulo = t.titulo);

-- ---------------------------------------------------------------------------
-- 4. O REGISTRO DA PRÓPRIA VERSÃO
-- ---------------------------------------------------------------------------
INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('094', now(),
        'as duas abas do Pos-venda (PNL_1.2 Treinamentos, PNL_1.3 Pos-venda)');

COMMIT;

-- ============================================================================
-- CONFERÊNCIA (rodar depois, e o esperado está escrito)
-- ============================================================================
--   SELECT codigo_tela, titulo FROM painel_aba ORDER BY painel, ordem;
--     -- esperado: PNL_1.1 Operação · PNL_1.2 Treinamentos · PNL_1.3 Pós-venda
--   SELECT a.codigo_tela, e.ordem, e.titulo, e.final
--     FROM pipeline_etapa e JOIN painel_aba a ON a.id = e.aba_id
--    ORDER BY a.ordem, e.ordem;
--     -- esperado: 1 etapa na PNL_1.1 e 4 em cada uma das outras duas
--   SELECT count(*) FROM pipeline_card WHERE aba_id IN
--     (SELECT id FROM painel_aba WHERE codigo_tela IN ('PNL_1.2','PNL_1.3'));
--     -- esperado: 0 -- a ORIGEM dos cards é decisão dele
-- ============================================================================
