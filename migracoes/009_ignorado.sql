-- ============================================================================
-- MoviZap — migração 009: separar "ignorado de propósito" de "falhou"
--
-- 🚨 O DEFEITO
--
-- `webhook.registrar` gravava o motivo do DESCARTE no campo `erro`:
--     erro = 'canal informativo: não vira conversa'
--     erro = 'grupo: fora da Fase 1'
--
-- E `conversas.resumo()` conta `erro IS NOT NULL` como falha. Resultado: o
-- painel acusava 16 erros num sistema em que nada falhou.
--
-- É exatamente a lição que a metodologia §3 já registrava, com outro nome:
-- "Resposta vazia não é falha. Separar `ok` / `vazio` / `erro` -- sem isso o
-- painel acusa 76% de falha num sistema saudável." O mesmo erro, cometido de
-- novo, num lugar diferente.
--
-- Alarme falso não é incômodo: é o que faz alguém parar de olhar o painel.
-- Quando o erro de verdade chegar, ele vai estar no meio dos 16 falsos.
--
-- ----------------------------------------------------------------------------
-- A CORREÇÃO
--
-- Dois estados diferentes, dois campos diferentes:
--     motivo_ignorado -> foi descartado DE PROPÓSITO, e por quê
--     erro            -> falhou, e precisa de gente
--
-- As duas colunas são exclusivas por CHECK: um evento não pode ser as duas
-- coisas ao mesmo tempo.
-- ============================================================================

BEGIN;

ALTER TABLE webhook_evento
    ADD COLUMN IF NOT EXISTS motivo_ignorado text;

-- Move o que estava no lugar errado. São 16 linhas, todas de canal
-- informativo, todas já processadas com sucesso.
UPDATE webhook_evento
   SET motivo_ignorado = erro,
       erro = NULL
 WHERE erro IS NOT NULL
   AND processado
   AND (erro LIKE 'canal informativo:%' OR erro LIKE 'grupo:%');

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'webhook_evento_ignorado_ou_erro') THEN
        ALTER TABLE webhook_evento
            ADD CONSTRAINT webhook_evento_ignorado_ou_erro
            CHECK (motivo_ignorado IS NULL OR erro IS NULL);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_webhook_erro
    ON webhook_evento (id) WHERE erro IS NOT NULL;

COMMENT ON COLUMN webhook_evento.motivo_ignorado IS
    'Descartado de propósito (canal informativo, grupo). NÃO é falha: não '
    'entra no contador de erro e não pede ação de ninguém.';

COMMENT ON COLUMN webhook_evento.erro IS
    'Falha de verdade: o evento não pôde ser interpretado e continua '
    'pendente para reprocessar. Se isto tem valor, alguém precisa olhar.';

INSERT INTO schema_migracao (versao, descricao)
VALUES ('009', 'Separa motivo_ignorado de erro no webhook_evento');

COMMIT;
