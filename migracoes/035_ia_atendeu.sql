-- ============================================================================
-- MoviZap — migração 035: a marca de até onde a IA já atendeu
--
-- O passo 8 (o motor) precisa de UMA coisa que o schema ainda não tinha: uma
-- trava de "esta mensagem já foi respondida pela IA" que sobreviva a duas
-- execuções simultâneas.
--
-- 🚨 A TRAVA É DO BANCO, NÃO DA DISCIPLINA -- a mesma lição de
-- `boas_vindas_em` (migração 032). `processar_pendentes` roda no laço de 5 s
-- E na rota `/api/conversas/processar`: são duas threads. Um `if` no Python
-- perde a corrida, e o cliente recebe DUAS respostas da IA para a mesma
-- pergunta. Repetir é pior do que faltar.
--
-- ⚠️ GUARDA O ID DA MENSAGEM, NÃO UM `timestamp` NEM UM `bool`.
--   - `bool` só serve uma vez e a IA responderia a primeira mensagem da
--     conversa e mais nenhuma;
--   - `timestamp` compara com `criada_em`, que é a hora DO PROVEDOR e chega
--     fora de ordem por desenho (`webhook.py`) -- comparar hora com hora faria
--     mensagem atrasada parecer já respondida.
--   O id é monotônico e é nosso. `ia_atendeu_ate < <id da última entrada>` é
--   a pergunta exata: "existe entrada que a IA ainda não viu?".
--
-- O `UPDATE ... WHERE ia_atendeu_ate IS DISTINCT FROM %s` é o que só passa
-- uma vez, mesmo com as duas threads entrando juntas.
-- ============================================================================

ALTER TABLE conversa ADD COLUMN IF NOT EXISTS ia_atendeu_ate bigint;

COMMENT ON COLUMN conversa.ia_atendeu_ate IS
    'Id da última mensagem de ENTRADA que a IA já atendeu. NULL = nenhuma. É '
    'a trava contra responder duas vezes: o UPDATE condicionado a esta coluna '
    'só passa uma vez, mesmo com duas execuções simultâneas.';

-- A varredura pergunta "quais conversas têm entrada não atendida pela IA?".
-- Sem índice isso é varredura na tabela inteira a cada 5 segundos.
-- Parcial: só conversa de atendimento em curso interessa.
CREATE INDEX IF NOT EXISTS ix_conversa_ia_pendente
    ON conversa (canal_id, ultima_atividade_em)
 WHERE estado IN ('nova', 'bot') AND atendente_id IS NULL AND tipo = 'direta';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('035', now(), 'ia_atendeu_ate: a trava de nao responder duas vezes');
