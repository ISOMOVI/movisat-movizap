-- ============================================================================
-- MoviZap — migração 056: sai `atendente.max_conversas`
--
-- 🔵 Decisão dele em 25/09: *"não deve haver máximo de conversas para a pessoa
-- ou para receber conversas."* Medido no mesmo dia: 0 de 11 atendentes com
-- valor, e nenhuma consulta a lia -- era um campo que prometia um teto que
-- não existia.
--
-- 🚨 APLICAR SÓ COM O BACKEND NOVO NO AR (M16). O antigo ainda seleciona a
-- coluna em `listar_atendentes`, `atendente` e `/api/eu/perfil`.
-- ============================================================================

BEGIN;

ALTER TABLE atendente DROP COLUMN max_conversas;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('056', now(), 'sai max_conversas (sem teto de conversas)');

COMMIT;
