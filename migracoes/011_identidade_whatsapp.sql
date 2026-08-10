-- ============================================================================
-- MoviZap — migração 011: o nome do WhatsApp e a mensagem citada
--
-- Decisão do usuário em 10/08: *"o nome que ele tiver no whatsapp é o que deve
-- aparecer"*. O painel lateral é que traz os dados da empresa, e só quando há
-- vínculo — igual a clicar no contato dentro do WhatsApp.
--
-- ----------------------------------------------------------------------------
-- POR QUE ISTO ERA URGENTE
--
-- Medido em 10/08 nos 722 eventos `messages.upsert` guardados: o `pushName`
-- chega em **721 deles** e era **descartado inteiro**. Ao mesmo tempo, 35 das
-- 37 conversas não têm vínculo com o cadastro — ou seja, o atendente via um
-- número cru numa tela em que o nome da pessoa já tinha chegado.
--
-- 🚨 `nome_whatsapp` NÃO É IDENTIFICAÇÃO. É o apelido que a própria pessoa
-- escolheu e pode trocar quando quiser; duas pessoas podem usar o mesmo. Ele
-- serve para a tela ter cara de gente, nunca para decidir quem é o cliente --
-- isso continua sendo `contato_id`, que vem do cadastro ou do vínculo manual.
-- Guardar os dois separados é o que impede um apelido de virar cadastro.
--
-- ----------------------------------------------------------------------------
-- A CITAÇÃO
--
-- `contextInfo` chega em 382 dos 722 eventos — **53%**. Em metade das
-- mensagens o cliente está respondendo a algo específico, e o painel mostra
-- tudo como fio corrido. Conversa com foto seguida de "esse aqui" fica
-- ininteligível sem isto.
--
-- A coluna `mensagem.citada_id` já existia desde a 001 e nunca foi preenchida
-- (0 de 722). Aqui ela ganha o índice que a leitura da tela precisa.
-- ============================================================================

-- O apelido do WhatsApp, por conversa. Fica na conversa e não no contato de
-- propósito: o contato é cadastro, a conversa é quem está falando agora.
ALTER TABLE conversa ADD COLUMN IF NOT EXISTS nome_whatsapp text;

-- Quando o apelido foi visto pela última vez. Sem isto não dá para saber se o
-- nome na tela é de hoje ou de três meses atrás.
ALTER TABLE conversa ADD COLUMN IF NOT EXISTS nome_whatsapp_em timestamptz;

-- A tela lê as citações de uma conversa inteira de uma vez. Sem índice isso é
-- varredura na tabela que mais cresce do sistema.
CREATE INDEX IF NOT EXISTS ix_mensagem_citada ON mensagem (citada_id)
    WHERE citada_id IS NOT NULL;

-- 🚨 A mídia é buscada POR MENSAGEM na hora de desenhar a conversa. `midia`
-- nasceu na 001 sem índice por conversa e está vazia justamente porque nada
-- nunca a preencheu; o índice entra agora, antes de existir volume.
CREATE INDEX IF NOT EXISTS ix_midia_conversa ON midia (conversa_id);

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('011', now(), 'Nome do WhatsApp na conversa e índice da mensagem citada')
ON CONFLICT (versao) DO NOTHING;
