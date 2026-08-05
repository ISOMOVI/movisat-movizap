-- ============================================================================
-- MoviZap — migração 003: o canal de atendimento
--
-- A instância `atendimento` já existe no Evolution desde 04/08, em estado
-- `close`, criada de propósito SEM parear: o pareamento é pelo painel, na
-- CFG_1.1. Esta migração dá a ela uma linha no banco, para haver onde
-- pendurar o histórico de conexão.
--
-- ⚠️ O canal INFORMATIVOS não entra: é Fase 2, e código de canal que existe
-- sem tela é convite a alguém mandar mensagem por ele antes da hora.
-- ============================================================================

BEGIN;

INSERT INTO canal (nome, tipo, gateway, instancia, modo, ativo)
VALUES ('Atendimento', 'atendimento', 'evolution', 'atendimento', 'baileys', true)
ON CONFLICT DO NOTHING;

-- Estado inicial explícito. Sem esta linha o histórico começaria na primeira
-- consulta da tela, e "desde quando está assim?" responderia a hora errada.
INSERT INTO canal_evento (canal_id, estado, motivo)
SELECT id, 'desconectado', 'cadastrado pela migração 003'
FROM canal WHERE instancia = 'atendimento'
  AND NOT EXISTS (SELECT 1 FROM canal_evento ce WHERE ce.canal_id = canal.id);

INSERT INTO schema_migracao (versao, descricao)
  VALUES ('003', 'Canal de atendimento (CFG_1.1)');

COMMIT;
