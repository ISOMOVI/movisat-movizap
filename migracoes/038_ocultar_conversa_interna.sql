-- ============================================================================
-- MoviZap — migração 038: esconder uma conversa do chat interno
--
-- Pedido dele em 27/08: *"Canal interno -> botão de excluir conversa"*.
--
-- ----------------------------------------------------------------------------
-- 🚨 ESCONDE PARA MIM, NÃO APAGA PARA O OUTRO
--
-- É o que "excluir conversa" faz no WhatsApp, que é a referência que ele
-- escolheu para esta tela. E é a única versão segura: apagar a sala levaria
-- junto o histórico da OUTRA pessoa, que não pediu nada e não tem como
-- desfazer. Uma conversa interna é prova de combinado -- quem disse o quê
-- sobre um atendimento.
--
-- ⚠️ E VOLTA SOZINHA quando chega mensagem nova, também como no WhatsApp:
-- esconder não pode virar um jeito de deixar de receber recado da equipe.
-- Por isso o campo guarda ATÉ QUE MENSAGEM foi escondida, e não um booleano:
-- com um booleano, ou a conversa some para sempre, ou é preciso um segundo
-- lugar para saber quando ela volta.
--
-- ⚠️ NÃO SE PERDE NADA. Nenhuma linha de `chat_mensagem` é tocada; a conversa
-- reaparece inteira, do começo, no dia em que voltar.
-- ============================================================================

ALTER TABLE chat_membro
    ADD COLUMN IF NOT EXISTS oculta_ate_id BIGINT;

COMMENT ON COLUMN chat_membro.oculta_ate_id IS
    'A conversa some da lista DESTA pessoa enquanto nao houver mensagem com id maior. NULL = visivel. Nao apaga nada, e nao afeta os outros membros.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('038', now(), 'chat interno: esconder conversa para mim, sem apagar para o outro');
