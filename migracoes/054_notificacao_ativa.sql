-- ============================================================================
-- MoviZap — migração 054: notificação ligada ou desligada, por pessoa
--
-- 🔵 Decisão dele em 24/09: *"a opção da notificação estar ativada por usuario
-- ou não, só aparece ao Owner"* -- e, desligada, *"some tudo"* (som e aba
-- piscando; o contador das abas fica, porque é informativo).
--
-- ⚠️ COLUNA, NÃO `preferencia_atendente`. Aquela tabela é o GOSTO de cada
-- pessoa (tom, volume, Enter). Isto é decisão do owner SOBRE a pessoa -- quem
-- a vê e a muda é outro, e por isso não mora junto do que é dela.
--
-- Nasce LIGADA para todos: o pedido é notificar; desligar é a exceção.
-- ============================================================================

ALTER TABLE atendente ADD COLUMN notificacao_ativa boolean NOT NULL DEFAULT true;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('054', now(), 'notificacao ativa por atendente (decisao do owner)');
