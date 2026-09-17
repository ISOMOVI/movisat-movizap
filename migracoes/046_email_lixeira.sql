-- ============================================================================
-- MoviZap — migração 046: a mensagem que sumiu do Gmail
--
-- 🔵 Pedido dele (17/09): "não temos lixeira também no movizap? não deveria
-- se espelhado o uso?" -- e resolve de quebra outra lacuna que a mesma
-- pergunta descobriu: "arquivada" já existe desde a 014 e NUNCA teve tela
-- própria -- uma vez arquivada, a mensagem só desaparecia, sem lugar para
-- ver de novo.
--
-- 🚨 MEDIDO EM 17/09, CONTRA O GMAIL AO VIVO: das 575 mensagens que o painel
-- mostra, 190 (33%) já estão na lixeira do Gmail e 72 (13%) foram apagadas
-- de vez. 46% da caixa está desatualizada, e o painel não tinha como saber
-- -- `ler()` só baixa mensagem NUNCA vista antes; uma vez importada, nunca é
-- reconferida.
--
-- 🚨 NUNCA PERDEMOS O CONTEÚDO, e é a diferença para o caso do WhatsApp: o
-- texto, HTML e anexos já foram baixados na importação. "Sumida do Gmail"
-- não apaga nada nosso -- só registra que lá não existe mais.
--
-- ⚠️ DOIS CAMPOS, NÃO UM ENUM. Na_lixeira e sumida são fatos que aconteceram
-- em momentos diferentes e podem ser revertidos independente um do outro
-- (o Gmail deixa restaurar da lixeira; não deixa "desapagar" de vez). Um
-- enum ('ativa'/'lixeira'/'removida') perderia a data de cada transição.
-- ============================================================================

BEGIN;

ALTER TABLE email_mensagem
    ADD COLUMN IF NOT EXISTS na_lixeira_desde   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS sumida_do_gmail_em TIMESTAMPTZ;

COMMENT ON COLUMN email_mensagem.na_lixeira_desde IS
    'Quando a varredura viu esta mensagem na lixeira do Gmail. NULL = não '
    'está lá. Volta a NULL se a pessoa restaurar (no Gmail ou no painel).';

COMMENT ON COLUMN email_mensagem.sumida_do_gmail_em IS
    'Quando a varredura deixou de achar esta mensagem em QUALQUER lugar do '
    'Gmail (nem lixeira). NULL = ainda existe lá, de algum jeito. O nosso '
    'texto/HTML/anexos continuam intactos -- só o lado do Gmail sumiu.';

-- A caixa principal já filtra por `arquivada`; agora também não mostra o
-- que está na lixeira ou sumiu, sem precisar tocar nas consultas que já
-- existem -- os índices parciais bastam para as abas novas.
CREATE INDEX IF NOT EXISTS ix_email_lixeira
    ON email_mensagem (conta_id, na_lixeira_desde DESC)
    WHERE na_lixeira_desde IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_email_arquivadas
    ON email_mensagem (conta_id, enviado_em DESC)
    WHERE arquivada AND na_lixeira_desde IS NULL;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('046', now(), 'email: deteccao de lixeira e exclusao no Gmail');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA (a prova é RELER O ESTADO):
--
--   \d email_mensagem
--   SELECT count(*) FROM email_mensagem WHERE na_lixeira_desde IS NOT NULL;   -- 0
--   SELECT count(*) FROM email_mensagem WHERE sumida_do_gmail_em IS NOT NULL; -- 0
--   SELECT versao FROM schema_migracao WHERE versao = '046';                 -- 046
--
-- DESFAZER:
--   ALTER TABLE email_mensagem DROP COLUMN na_lixeira_desde, DROP COLUMN sumida_do_gmail_em;
--   DROP INDEX IF EXISTS ix_email_lixeira, ix_email_arquivadas;
--   DELETE FROM schema_migracao WHERE versao = '046';
-- ----------------------------------------------------------------------------
