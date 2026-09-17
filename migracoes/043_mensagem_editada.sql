-- ============================================================================
-- MoviZap — migração 043: a mensagem que o cliente editou
--
-- 🟡 Sugestão minha (17/09), provada contra tráfego real antes de escrever.
--
-- 🚨 A EDIÇÃO JÁ CHEGAVA E ERA JOGADA FORA. Medido em 17/09 nos 54.544 eventos
-- crus recebidos desde 18/08: `editedMessage` apareceu **5 vezes**, e as 5
-- casam com uma mensagem nossa pelo `keyId` -- 5 de 5. Elas entram por
-- `messages.update`, o mesmo evento do tique de entrega, e o
-- `_atualizar_entrega` só olhava `data.status`: o texto novo era descartado
-- em silêncio. O atendente segue lendo a versão velha, para sempre.
--
-- O que se perdeu, em casos reais desta base: alguém corrigiu "Bom dia" para
-- "Boa tarde", e outra pessoa acrescentou "para ativar ign virtual" a um
-- comando SMS de rastreador. Quem atendia nunca viu a correção.
--
-- 🚨 O ORIGINAL FICA, e é o motivo de existir uma coluna em vez de só
-- sobrescrever `conteudo`. Conversa é prova de combinado -- a mesma razão por
-- que "excluir conversa" esconde para mim e não destrói para o outro (27/08).
-- O atendente AGIU sobre o texto que leu; se o cliente edita depois, o que
-- ele leu não pode sumir do registro.
--
-- ⚠️ SÓ A PRIMEIRA VERSÃO É GUARDADA. Na segunda edição o `conteudo_original`
-- NÃO se sobrescreve (o código usa `COALESCE(conteudo_original, conteudo)`):
-- guardar a penúltima versão responderia a pergunta errada. O que importa é
-- "o que estava escrito quando isto virou atendimento", não o histórico
-- completo de digitação de quem escreveu.
--
-- ⚠️ NULL NOS DOIS = NUNCA EDITADA, que é o caso de 99,99% das 26.559
-- mensagens de hoje. Coluna anulável, sem default, sem backfill: nada muda
-- para quem já está lá.
-- ============================================================================

BEGIN;

ALTER TABLE mensagem
    ADD COLUMN IF NOT EXISTS editada_em        TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS conteudo_original TEXT;

COMMENT ON COLUMN mensagem.editada_em IS
    'Quando a ULTIMA edicao chegou. NULL = nunca editada.';

COMMENT ON COLUMN mensagem.conteudo_original IS
    'O texto como chegou da PRIMEIRA vez, antes de qualquer edicao. Nao se '
    'sobrescreve em edicoes seguintes. NULL = nunca editada.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('043', now(), 'mensagem editada: guarda o texto original e quando mudou');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA (a prova é RELER O ESTADO):
--
--   \d mensagem
--   SELECT count(*) FROM mensagem WHERE editada_em IS NOT NULL;  -- 0 antes
--   SELECT versao FROM schema_migracao WHERE versao = '043';     -- 043
--
-- DESFAZER, se precisar:
--   ALTER TABLE mensagem DROP COLUMN editada_em, DROP COLUMN conteudo_original;
--   DELETE FROM schema_migracao WHERE versao = '043';
-- ----------------------------------------------------------------------------
