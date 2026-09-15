-- ============================================================================
-- MoviZap — migração 042: até onde cada pessoa leu cada conversa
--
-- 🟢 Pedido da Erika (15/09): *"aparecer a bolinha de quantidade de novas
-- mensagens como no bitrix e whatsapp"*.
--
-- 🚨 ELE NÃO EXISTIA PARA O WHATSAPP. O chat INTERNO tem `chat_membro.lido_ate`
-- desde sempre, e é dele que sai o selo do menu; a conversa de cliente não
-- tinha nada equivalente -- nenhuma coluna, em nenhuma tabela, dizia o que
-- alguém já tinha lido. Esta migração copia o modelo que já funciona ao lado,
-- em vez de inventar um segundo jeito de responder a mesma pergunta.
--
-- 🚨 POR PESSOA, e é o ponto. A mesma conversa está lida para quem acabou de
-- atender e não lida para quem vai pegar o plantão. Uma marca única na
-- `conversa` diria que está lida para todos assim que UM abrisse.
--
-- ⚠️ SEM LINHA = NUNCA ABRIU. A contagem trata ausência como "tudo não lido",
-- que é o certo: a conversa que ninguém desta equipe abriu ainda tem tudo por
-- ler.
--
-- ⚠️ ON DELETE CASCADE nos dois lados: isto é marcador de leitura, não
-- histórico. Se a conversa some, não faz falta a ninguém saber até onde
-- alguém a tinha lido.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS conversa_leitura (
    conversa_id   BIGINT NOT NULL REFERENCES conversa(id)  ON DELETE CASCADE,
    atendente_id  BIGINT NOT NULL REFERENCES atendente(id) ON DELETE CASCADE,
    lido_ate      BIGINT NOT NULL DEFAULT 0,
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (conversa_id, atendente_id)
);

COMMENT ON TABLE conversa_leitura IS
    'Ate qual mensagem cada pessoa leu cada conversa. Espelha o '
    'chat_membro.lido_ate do chat interno. Sem linha = nunca abriu.';

COMMENT ON COLUMN conversa_leitura.lido_ate IS
    'Maior mensagem.id ja visto por esta pessoa nesta conversa.';

-- A contagem pergunta "o que este atendente ainda nao leu", em toda carga da
-- caixa de entrada: o indice segue a pergunta, nao a tabela.
CREATE INDEX IF NOT EXISTS ix_conversa_leitura_atendente
    ON conversa_leitura (atendente_id);

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('042', now(), 'leitura por pessoa nas conversas do WhatsApp');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA (a prova é RELER O ESTADO):
--
--   \d conversa_leitura
--   SELECT count(*) FROM conversa_leitura;                     -- 0
--   SELECT versao FROM schema_migracao WHERE versao = '042';   -- 042
-- ----------------------------------------------------------------------------
