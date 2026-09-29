-- ============================================================================
-- MoviZap — migração 061: editar/apagar a própria mensagem no Chat interno
--
-- 🔵 Demanda dele, 25/09 (Plano 4, item B): "Chat interno: editar (15 min) e
-- apagar (48 h) a própria mensagem, como na Caixa".
--
-- Mesmo padrão das migrações 043/045 (Caixa de entrada), aplicado agora a
-- `chat_mensagem`. Como é mensagem interna (nunca vai ao WhatsApp), não há
-- chamada de API externa envolvida -- é o mesmo contrato, sem o `evolution`.
--
-- ⚠️ NULL nos três = nunca editada/apagada, caso de toda mensagem de hoje.
-- Colunas anuláveis, sem default, sem backfill.
-- ============================================================================

BEGIN;

ALTER TABLE chat_mensagem
    ADD COLUMN IF NOT EXISTS editada_em        TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS conteudo_original TEXT,
    ADD COLUMN IF NOT EXISTS apagada_em        TIMESTAMPTZ;

COMMENT ON COLUMN chat_mensagem.editada_em IS
    'Quando a mensagem foi editada por quem escreveu. NULL = nunca editada.';

COMMENT ON COLUMN chat_mensagem.conteudo_original IS
    'O texto como foi escrito da PRIMEIRA vez, antes de qualquer edicao. '
    'Nao se sobrescreve em edicoes seguintes. NULL = nunca editada.';

COMMENT ON COLUMN chat_mensagem.apagada_em IS
    'Quando quem escreveu apagou a mensagem. NULL = nunca apagada. O '
    '`texto` NAO e destruido -- mesma regra da Caixa (045).';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('061', now(), 'chat interno: editar (15min) e apagar (48h) a propria mensagem');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA (a prova é RELER O ESTADO):
--
--   \d chat_mensagem
--   SELECT count(*) FROM chat_mensagem WHERE editada_em IS NOT NULL;  -- 0 antes
--   SELECT versao FROM schema_migracao WHERE versao = '061';          -- 061
--
-- DESFAZER, se precisar:
--   ALTER TABLE chat_mensagem DROP COLUMN editada_em, DROP COLUMN conteudo_original,
--       DROP COLUMN apagada_em;
--   DELETE FROM schema_migracao WHERE versao = '061';
-- ----------------------------------------------------------------------------
