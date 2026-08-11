-- ============================================================================
-- MoviZap — migração 022: a transferência sabe dizer "o dono saiu"
--
-- Consequência direta da regra de 11/08: quando o dono sai da conversa, a
-- posse passa para quem ficou. Isso é uma troca de dono, e toda troca de dono
-- é registrada em `transferencia` -- mas o CHECK só conhecia
-- `manual | inatividade | ia_triagem | sem_time`.
--
-- 🚨 GRAVAR ISTO COMO 'manual' SERIA MENTIR NO DADO. O relatório diria que
-- alguém transferiu a conversa à mão, quando quem passou a posse foi o
-- sistema, sozinho, porque o dono saiu. É a mesma lição que a migração 009 já
-- ensinou ao separar `motivo_ignorado` de `erro`: descartar de propósito não é
-- falhar, e passar posse por regra não é transferir à mão.
--
-- ⚠️ CHECK é contrato (docs/02). Ampliar o vocabulário é decisão, e está aqui
-- para quem ler o histórico saber quando o valor passou a existir.
-- ============================================================================

ALTER TABLE transferencia DROP CONSTRAINT IF EXISTS transferencia_motivo_check;
ALTER TABLE transferencia ADD CONSTRAINT transferencia_motivo_check
    CHECK (motivo IN ('manual', 'inatividade', 'ia_triagem', 'sem_time',
                      'saida_do_dono'));

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('022', now(), 'transferencia aceita motivo saida_do_dono');
