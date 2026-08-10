-- ============================================================================
-- MoviZap — migração 016: os índices que faltavam nas chaves estrangeiras
--
-- Auditoria de gargalos em 10/08 achou **15 FK sem índice**. 🚨 O Postgres NÃO
-- cria índice de chave estrangeira sozinho -- é a mesma lição da migração 002,
-- cometida de novo nas tabelas que nasceram depois dela.
--
-- ⚠️ Hoje nada disso dói: são 58 conversas e 1.069 mensagens. Índice de FK é
-- exatamente o problema que só aparece com volume -- e aí aparece na forma de
-- "o painel ficou lento" sem ninguém saber por quê. Custa nada agora.
--
-- ----------------------------------------------------------------------------
-- O QUE ENTRA, E POR QUE CADA UM
--
-- `mensagem` é a tabela que mais cresce -- 1.069 linhas em 3 dias. As duas FK
-- dela foram criadas HOJE e já nasceram sem índice:
--   midia_id      -> a conversa monta o balão buscando a mídia de cada msg;
--   atendente_id  -> "quem respondeu isto" e o futuro relatório por pessoa.
--
-- `conversa.time_id` é a fila: a tela de fila filtra por time em toda carga.
-- `conversa.classificacao_id` é o histórico filtrado por motivo.
-- `transferencia.*` é o rastro de quem passou para quem.
-- `email_mensagem.contato_id` nasceu hoje, na 014.
--
-- ----------------------------------------------------------------------------
-- O QUE **NÃO** ENTRA, DE PROPÓSITO
--
-- 🚨 `disparo.*`, `disparo_destino.*`, `prompt_versao.autor_id`,
-- `sync_execucao.atendente_id`, `time.time_transbordo_id`,
-- `conversa.prompt_versao_id` e `atendente_jornada` ficam SEM índice.
--
-- Todas essas tabelas têm ZERO linhas e pertencem a coisas que ainda não
-- existem (disparo, IA, jornada). Índice em tabela vazia é escrita mais cara
-- sem leitura nenhuma para pagar -- e criar por simetria é como se enche um
-- banco de estrutura que ninguém pediu. Entram quando a funcionalidade entrar.
-- ============================================================================

CREATE INDEX IF NOT EXISTS ix_mensagem_midia
    ON mensagem (midia_id) WHERE midia_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_mensagem_atendente
    ON mensagem (atendente_id) WHERE atendente_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_conversa_time
    ON conversa (time_id) WHERE time_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_conversa_classificacao
    ON conversa (classificacao_id) WHERE classificacao_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_transferencia_de
    ON transferencia (de_atendente_id) WHERE de_atendente_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_transferencia_para
    ON transferencia (para_atendente_id) WHERE para_atendente_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_email_contato
    ON email_mensagem (contato_id) WHERE contato_id IS NOT NULL;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('016', now(), 'Índices nas FK que a auditoria de gargalos achou');
