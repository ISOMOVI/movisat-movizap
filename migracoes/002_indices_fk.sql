-- ============================================================================
-- MoviZap — migração 002: índices em chave estrangeira
--
-- Achado pela auditoria de 2026-08-05: 16 FKs sem índice. Postgres NÃO cria
-- índice em FK automaticamente (só em PK e UNIQUE), e é engano comum supor
-- que sim.
--
-- 🚨 NÃO estou indexando as 16. Índice não é grátis: pesa em todo INSERT e
-- UPDATE, e a mensagem é a tabela que mais cresce. Entram só as que têm
-- padrão de leitura real.
--
-- O outro motivo clássico para indexar FK -- DELETE no pai varrer a filha
-- inteira -- NÃO se aplica aqui: o princípio do modelo é "nada se apaga,
-- inativa-se". Não se apaga atendente, time nem classificação.
-- ============================================================================

BEGIN;

-- "minhas conversas": a consulta que todo atendente faz o dia inteiro
CREATE INDEX ix_conversa_atendente ON conversa (atendente_id)
    WHERE atendente_id IS NOT NULL;

-- abrir uma conversa carrega as mídias dela
CREATE INDEX ix_midia_conversa ON midia (conversa_id);

-- "quem é do time X": tela de times e roteamento da transferência
CREATE INDEX ix_atendente_time_time ON atendente_time (time_id);
CREATE INDEX ix_atendente_time_perm_time ON atendente_time_permissao (time_id);

-- relatório: quantas conversas foram parar em cada time
CREATE INDEX ix_transferencia_time ON transferencia (para_time_id)
    WHERE para_time_id IS NOT NULL;

-- Deliberadamente SEM índice, e o porquê:
--   mensagem.citada_id, mensagem.midia_id, mensagem.atendente_id
--     -> mensagem é a tabela que mais cresce; três índices a mais em toda
--        inserção de webhook, para junções que quase não acontecem
--   conversa.classificacao_id, conversa.prompt_versao_id
--     -> baixa cardinalidade; o planejador prefere varrer
--   prompt_versao.autor_id, sync_execucao.atendente_id
--     -> tabelas pequenas, consultadas por data
--   transferencia.de_atendente_id / para_atendente_id
--     -> relatório por PESSOA ainda não existe; entra quando existir
--   time.time_transbordo_id
--     -> sete linhas

INSERT INTO schema_migracao (versao, descricao)
  VALUES ('002', 'Índices em FK com padrão de leitura real (auditoria 05/08)');

COMMIT;
