-- ============================================================================
-- MoviZap — migração 048: mensagem do chat pode ser só o anexo
--
-- 🚨 A 047 ESQUECEU ESTA METADE, e quem achou foi o teste. Eu li a coluna
-- (`texto` é `NOT NULL`), escrevi no comentário da 047 que "o que se grava é
-- string vazia" -- e NÃO LI AS RESTRIÇÕES DA TABELA. Havia um
-- `CHECK (length(btrim(texto)) > 0)` desde a 026, proibindo exatamente isso.
-- A primeira rodada do `teste_anexo_chat` estourou em `CheckViolation`.
--
-- É o `M15`: ausência só se afirma LENDO A DEFINIÇÃO, nunca deduzindo de uma
-- coluna vizinha. `NOT NULL` e "não pode ser vazio" são duas regras
-- diferentes, e eu tratei uma como prova da outra.
--
-- 🚨 O `CHECK` ORIGINAL ESTAVA CERTO PARA O MUNDO DELE. Mensagem sem nada não
-- é mensagem, e ele nasceu junto com o chat, quando anexo não existia. O que
-- mudou foi o mundo: agora o ANEXO pode ser o conteúdo. Quem manda um print
-- raramente escreve legenda, e obrigar texto faria a tela inventar um -- e
-- texto inventado aparece no histórico e na busca.
--
-- ⚠️ A REGRA NÃO AFROUXOU, MUDOU DE FORMA: continua proibida a mensagem
-- vazia. O que passa a valer é "ou tem texto, ou tem anexo" -- nunca nenhum
-- dos dois.
-- ============================================================================

BEGIN;

ALTER TABLE chat_mensagem DROP CONSTRAINT chat_mensagem_texto_check;

ALTER TABLE chat_mensagem ADD CONSTRAINT chat_mensagem_tem_conteudo
    CHECK (length(btrim(texto)) > 0 OR midia_id IS NOT NULL);

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('048', now(), 'chat interno: mensagem pode ser so o anexo, sem legenda');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA (a prova é RELER O ESTADO):
--
--   SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
--    WHERE conrelid = 'chat_mensagem'::regclass;    -- chat_mensagem_tem_conteudo
--   SELECT count(*) FROM chat_mensagem WHERE btrim(texto) = '' AND midia_id IS NULL;  -- 0
--   SELECT versao FROM schema_migracao WHERE versao = '048';                          -- 048
--
-- DESFAZER (só se não houver mensagem que seja só anexo):
--   ALTER TABLE chat_mensagem DROP CONSTRAINT chat_mensagem_tem_conteudo;
--   ALTER TABLE chat_mensagem ADD CONSTRAINT chat_mensagem_texto_check
--       CHECK (length(btrim(texto)) > 0);
--   DELETE FROM schema_migracao WHERE versao = '048';
-- ----------------------------------------------------------------------------
