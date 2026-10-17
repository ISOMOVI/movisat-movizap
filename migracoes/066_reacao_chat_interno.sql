-- ============================================================================
-- MoviZap — migração 066: reagir a mensagem no Chat interno
--
-- 🔵 Demanda dele, 16/10: "verifique recursos de reagir a mensagens internas,
-- como do externo" → "pode fazer tudo". A Caixa de entrada reage desde 034/036
-- (`mensagem_reacao`); o Chat interno não tinha tabela, rota nem botão.
--
-- Mesmo contrato da Caixa: UMA reação por pessoa por mensagem -- trocar o
-- emoji substitui, reagir com nada tira. Aqui não há `evolution` nem eco de
-- webhook, então quem reagiu é o próprio `atendente_id`, e não a chave
-- textual `quem` que a Caixa precisa para casar o eco do WhatsApp.
--
-- ⚠️ CASCATA NAS DUAS CHAVES, igual à `chat_mencao` (037): a limpeza dos
-- testes apaga sala e depois atendente, e uma reação sem cascata seguraria os
-- dois por chave estrangeira.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS chat_reacao (
    mensagem_id   BIGINT NOT NULL REFERENCES chat_mensagem(id) ON DELETE CASCADE,
    atendente_id  BIGINT NOT NULL REFERENCES atendente(id)     ON DELETE CASCADE,
    emoji         TEXT   NOT NULL,
    em            TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (mensagem_id, atendente_id)
);

COMMENT ON TABLE chat_reacao IS
    'Reação a uma mensagem do Chat interno. Uma por pessoa por mensagem '
    '(a chave primária é a trava): trocar o emoji substitui, tirar apaga a '
    'linha. A lista de emojis aceitos é a da Caixa, conferida no chat.py.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('066', now(), 'chat interno: reagir a mensagem com emoji');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA (a prova é RELER O ESTADO):
--
--   \d chat_reacao
--   SELECT count(*) FROM chat_reacao;                          -- 0
--   SELECT versao FROM schema_migracao WHERE versao = '066';   -- 066
--
-- DESFAZER, se precisar:
--   DROP TABLE chat_reacao;
--   DELETE FROM schema_migracao WHERE versao = '066';
-- ----------------------------------------------------------------------------
