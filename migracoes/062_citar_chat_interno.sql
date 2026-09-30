-- ============================================================================
-- MoviZap — migração 062: responder citando no Chat interno
--
-- 🔵 Demanda dele, 29/09: "no chat interno também" (clicar na citação vai até
-- a original) — pedido feito supondo que citar já existia lá. Não existia:
-- o Chat interno nunca teve "responder citando" (nem botão, nem coluna).
-- Confirmado por ele que entra no plano: construir citar, igual foi feito
-- com anexo em 22/09 ("igual no aberto"), e junto o clique-vai-à-origem.
--
-- Mesmo padrão da citação da Caixa de entrada (`mensagem.citada_id`), mas SEM
-- `evolution` nem `stanzaId`: aqui é conversa só nossa, então citar é um FK
-- direto para outra linha de `chat_mensagem` -- confirmado no código
-- (`chat.py::_conferir_citada`) que a mensagem citada precisa ser da MESMA
-- sala.
--
-- ⚠️ NULL = mensagem não é resposta a nada, caso de toda mensagem de hoje.
-- Coluna anulável, sem default, sem backfill.
-- ============================================================================

BEGIN;

ALTER TABLE chat_mensagem
    ADD COLUMN IF NOT EXISTS citada_id INTEGER REFERENCES chat_mensagem(id);

COMMENT ON COLUMN chat_mensagem.citada_id IS
    'A mensagem desta MESMA SALA que esta responde citando. NULL = não '
    'cita nada. Sem ON DELETE: mensagem citada não se apaga de verdade '
    '(mesma regra de apagada_em, 061), então a referência nunca fica orfã '
    'por exclusão real.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('062', now(), 'chat interno: responder citando outra mensagem da sala');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA (a prova é RELER O ESTADO):
--
--   \d chat_mensagem
--   SELECT count(*) FROM chat_mensagem WHERE citada_id IS NOT NULL;  -- 0 antes
--   SELECT versao FROM schema_migracao WHERE versao = '062';         -- 062
--
-- DESFAZER, se precisar:
--   ALTER TABLE chat_mensagem DROP COLUMN citada_id;
--   DELETE FROM schema_migracao WHERE versao = '062';
-- ----------------------------------------------------------------------------
