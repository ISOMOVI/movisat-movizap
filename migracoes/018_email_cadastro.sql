-- ============================================================================
-- MoviZap — migração 018: o e-mail passa a somar cadastro
--
-- É o objetivo que o usuário declarou em 10/08: *"só deve estar no MoviZap
-- pela facilidade em atender e somar cadastro, pois no sync devemos ter
-- e-mails e daí sabemos empresas e depois no cad pessoas por número, data do
-- último e-mail recebido"*.
--
-- ----------------------------------------------------------------------------
-- `ultimo_email_em` -- POR QUE É COLUNA, E NÃO CONSULTA
--
-- Daria para calcular com um MAX sobre `email_mensagem`. Não serve por dois
-- motivos:
--
--   1. a pergunta é *"por onde essa pessoa responde?"*, e ela vai ser feita ao
--      lado de `tem_whatsapp` e da última conversa -- numa lista de 944
--      clientes. Um MAX por linha é varredura por cliente;
--   2. e-mail antigo sai da base pelo corte de histórico (`puxar_desde`), mas
--      a DATA em que a pessoa escreveu não deveria sumir junto. A coluna
--      sobrevive ao expurgo; o MAX não.
--
-- ⚠️ É preenchida na leitura, só quando o remetente casa com UM cadastro. Sem
-- certeza, fica NULL -- mesma regra da conversa de WhatsApp.
--
-- ----------------------------------------------------------------------------
-- 🚨 O VÍNCULO MANUAL É O QUE FAZ O CADASTRO CRESCER
--
-- Hoje o painel identifica só quem já casa sozinho: 11 de 25. Os outros 14 não
-- têm o que fazer -- e é aí que o e-mail deixa de somar cadastro e vira só
-- caixa de mensagem.
--
-- `email_mensagem.cliente_id` já existe (migração 014). O que faltava era
-- registrar o ENDEREÇO no cadastro quando alguém vincula à mão, para a próxima
-- mensagem daquele remetente casar sozinha. Daí `contato.email` ganhar índice
-- e a origem ser rastreável.
-- ============================================================================

ALTER TABLE cliente ADD COLUMN IF NOT EXISTS ultimo_email_em timestamptz;
COMMENT ON COLUMN cliente.ultimo_email_em IS
    'Quando esta empresa escreveu pela última vez. Coluna e não MAX: sobrevive '
    'ao corte de histórico e responde "por onde essa pessoa responde?" em lista.';

ALTER TABLE contato ADD COLUMN IF NOT EXISTS ultimo_email_em timestamptz;

-- O casamento do remetente é por endereço, em toda mensagem que chega.
-- `cliente` já ganhou o dele na 014; `contato` não tinha.
CREATE INDEX IF NOT EXISTS ix_contato_email
    ON contato (lower(email)) WHERE email IS NOT NULL;

-- ⚠️ De onde veio o e-mail do contato -- mesma ideia do `origem_campo` do
-- telefone: separa o que o sync trouxe do que o atendimento afirmou. Sem isso
-- não dá para medir se a tela está consertando o cadastro.
ALTER TABLE contato ADD COLUMN IF NOT EXISTS email_origem text
    CHECK (email_origem IS NULL OR email_origem IN ('harmonit', 'atendimento'));

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('018', now(), 'E-mail soma cadastro: ultimo_email_em e vínculo manual');
