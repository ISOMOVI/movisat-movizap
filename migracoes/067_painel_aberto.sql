-- ============================================================================
-- MoviZap — migração 067: o painel diz que está aberto
--
-- 🔵 Demanda dele, 19/10: *"o status dos atendentes devem permanecer online
-- ou ausente quando logados dentro da jornada"*. Veio de ver o Thiago como
-- offline estando logado.
--
-- 🚨 O SISTEMA NÃO SABIA QUEM ESTAVA LOGADO. O único relógio era
-- `ultima_acao_em`, e "ação" é ESCREVER (mensagem, nota, chat, editar, apagar,
-- reagir). Quem passava a manhã lendo conversa não tocava o relógio e caía
-- para `ausente` em 30 min e `offline` em 60 -- logado, olhando a tela.
--
-- Esta coluna é o sinal que faltava: o painel pede a lista da Caixa a cada 8 s
-- enquanto a aba está aberta, e a rota carimba aqui (no máximo uma escrita por
-- minuto por pessoa). ⚠️ O que ela prova é "o painel está aberto", não "a
-- pessoa está na frente dele" -- e é por isso que `ausente` continua existindo
-- dentro da jornada: a inatividade de 30 min segue valendo.
-- ============================================================================

BEGIN;

ALTER TABLE atendente ADD COLUMN IF NOT EXISTS painel_visto_em TIMESTAMPTZ;

COMMENT ON COLUMN atendente.painel_visto_em IS
    'Quando o painel desta pessoa falou com o servidor pela última vez (a '
    'lista da Caixa, a cada 8 s). Prova que a aba está ABERTA, não que alguém '
    'a esteja olhando. A régua de presença usa isto para não pôr em offline '
    'quem está logado dentro da jornada.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('067', now(), 'presenca: painel aberto nao cai em offline dentro da jornada');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA (a prova é RELER O ESTADO):
--
--   \d atendente
--   SELECT count(*) FROM atendente WHERE painel_visto_em IS NOT NULL;  -- 0 antes de abrir o painel
--   SELECT versao FROM schema_migracao WHERE versao = '067';           -- 067
--
-- DESFAZER, se precisar:
--   ALTER TABLE atendente DROP COLUMN painel_visto_em;
--   DELETE FROM schema_migracao WHERE versao = '067';
-- ----------------------------------------------------------------------------
