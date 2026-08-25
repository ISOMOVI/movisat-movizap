-- ============================================================================
-- MoviZap — migração 034: reação e encaminhamento
--
-- Pedidos do usuário: reagir com emoji e responder citando (12/08, aprovados e
-- nunca começados) e encaminhar (25/08, quando a regra de "não é caixa de
-- disparo" caiu).
--
-- 🚨 AS ROTAS DO EVOLUTION ESTÃO MEDIDAS, NÃO SUPOSTAS. Probadas em 25/08 na
-- instância real (2.3.7) com corpo vazio: `sendReaction` e
-- `sendWhatsAppAudio` respondem 400 (existem e recusaram o corpo), nunca 404.
-- Antes disso eu havia afirmado o suporte de memória, que é o `M5`.
--
-- ----------------------------------------------------------------------------
-- `reacao`: O NOSSO EMOJI NAQUELA MENSAGEM
--
-- Uma coluna, não tabela: no WhatsApp cada participante tem UMA reação por
-- mensagem -- reagir de novo troca, não soma. Do nosso lado só existe um
-- participante (o painel), então é uma coluna.
--
-- ⚠️ REAÇÃO DO CLIENTE NÃO ENTRA AINDA. Ela chega como `reactionMessage` no
-- webhook e hoje cai no ramo de "tipo ainda não tratado" -- vira uma mensagem
-- com texto entre colchetes. Tratá-la é outro trabalho, e esta migração NÃO
-- finge que ele existe: a coluna guarda o que NÓS mandamos.
--
-- ----------------------------------------------------------------------------
-- `encaminhada_de`: DE ONDE ELA VEIO
--
-- 🚨 O WHATSAPP MARCA O QUE FOI ENCAMINHADO, e o histórico daqui precisa
-- marcar também. Sem isto, seis meses depois ninguém sabe se aquela frase foi
-- escrita para o cliente ou repassada de outra conversa -- e a diferença
-- importa quando alguém reclama do que foi dito.
--
-- FK para `mensagem`, com ON DELETE SET NULL: mensagem apagada não pode
-- derrubar a que a repassou.
-- ============================================================================

ALTER TABLE mensagem ADD COLUMN IF NOT EXISTS reacao text;

COMMENT ON COLUMN mensagem.reacao IS
    'O emoji com que NÓS reagimos a esta mensagem. Um por mensagem: reagir de '
    'novo troca. Reação do cliente ainda não é tratada.';

ALTER TABLE mensagem ADD COLUMN IF NOT EXISTS encaminhada_de bigint
    REFERENCES mensagem(id) ON DELETE SET NULL;

COMMENT ON COLUMN mensagem.encaminhada_de IS
    'A mensagem original, quando esta foi encaminhada. NULL = escrita aqui.';

-- A tela desenha "encaminhada" no balão; sem índice, descobrir isso numa
-- conversa longa é varredura. Parcial: a imensa maioria é NULL.
CREATE INDEX IF NOT EXISTS ix_mensagem_encaminhada
    ON mensagem (encaminhada_de) WHERE encaminhada_de IS NOT NULL;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('034', now(), 'reacao e encaminhamento na mensagem');
