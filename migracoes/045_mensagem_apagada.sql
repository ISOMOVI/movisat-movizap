-- ============================================================================
-- MoviZap — migração 045: a mensagem que o cliente apagou
--
-- 🚨 PROVADO CONTRA O MUNDO REAL EM 17/09, e só depois de três medições que
-- diziam o contrário. O evento `messages.delete` NUNCA tinha chegado em
-- 54.544 eventos (18/08 a 17/09) por dois motivos somados:
--   1. `MESSAGES_DELETE` não estava assinado no webhook do Evolution;
--   2. mesmo assinado, o que NÓS apagamos não é ecoado de volta -- exercitado
--      duas vezes, o REVOKE acontece (ele confirmou no celular) e nada volta.
-- O que destravou foi o teste dele: mandar do próprio celular para o número
-- do painel e apagar para todos. Aí chegou, 6 segundos depois.
--
-- 🚨 O ID DO ALVO VEM EM `data.id`, e este é o TERCEIRO lugar. O upsert usa
-- `data.key.id`, o update usa `data.keyId` e o delete usa `data.id`. Três
-- formatos para a mesma coisa, no mesmo provedor -- quem escrever o handler
-- olhando só o que já conhecia erra o alvo e não apaga nada.
--
-- 🚨 O TEXTO NÃO É DESTRUÍDO, e a razão é a mesma da 043: o atendente AGIU
-- sobre o que leu. Se o cliente apaga depois, o registro de que aquilo foi
-- dito não pode sumir -- é a mesma decisão de "esconder conversa é para mim,
-- não para o outro" (27/08). O que muda é a EXIBIÇÃO: o balão passa a dizer
-- que foi apagada e o texto fica atrás de um clique.
--
-- ⚠️ DECISÃO DELE, SE QUISER MUDAR: o padrão aqui é "marca e esconde atrás de
-- um clique". As outras saídas são esconder de vez (o atendente nunca mais lê)
-- ou não esconder nada (o balão continua igual, só com um aviso). Escolhi a do
-- meio porque não perde informação e respeita a intenção de quem apagou.
--
-- ⚠️ NULL = NUNCA APAGADA, que é o caso das 26.559 de hoje. Coluna anulável,
-- sem default, sem backfill.
-- ============================================================================

BEGIN;

ALTER TABLE mensagem ADD COLUMN IF NOT EXISTS apagada_em TIMESTAMPTZ;

COMMENT ON COLUMN mensagem.apagada_em IS
    'Quando o WhatsApp avisou que a mensagem foi apagada para todos. '
    'NULL = nunca apagada. O `conteudo` NAO e destruido: o atendente agiu '
    'sobre o que leu, e a exibicao e que muda.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('045', now(), 'mensagem apagada pelo cliente: marca sem destruir o texto');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA (a prova é RELER O ESTADO):
--
--   \d mensagem
--   SELECT count(*) FROM mensagem WHERE apagada_em IS NOT NULL;   -- 0 antes
--   SELECT versao FROM schema_migracao WHERE versao = '045';      -- 045
--
-- DESFAZER:
--   ALTER TABLE mensagem DROP COLUMN apagada_em;
--   DELETE FROM schema_migracao WHERE versao = '045';
-- ----------------------------------------------------------------------------
