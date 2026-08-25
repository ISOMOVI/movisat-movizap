-- ============================================================================
-- MoviZap — migração 033: estrela no e-mail
--
-- Pedido do usuário em 25/08: *"o recurso de 'estrela' do gmail não poderíamos
-- ter? selecionar, botão de leitura de e-mails, etc"*.
--
-- 🚨 NÃO PRECISA DE CONSENTIMENTO NOVO. O escopo concedido é `gmail.modify` +
-- `gmail.send` -- o comentário no topo do `gmail.py` dizia `readonly` e estava
-- errado desde que o escopo mudou. Foi essa frase, e não a permissão, que
-- atrasou este recurso.
--
-- ----------------------------------------------------------------------------
-- POR QUE UMA COLUNA, SE O MARCADOR `STARRED` JÁ EXISTE
--
-- O marcador existe e é sincronizado, mas a lista da caixa lê `email_mensagem`
-- direto: descobrir a estrela por `EXISTS` em `email_mensagem_marcador` a cada
-- linha custa uma subconsulta por mensagem, numa tela que carrega 60 de uma
-- vez e reordena por data. A coluna é o mesmo padrão de `lida`, que já vive
-- aqui pela mesma razão.
--
-- ⚠️ O MARCADOR CONTINUA SENDO A VERDADE DO GOOGLE. A coluna é reflexo local:
-- quem manda é o Gmail, e a próxima leitura da caixa a corrige se divergirem.
-- Nunca o contrário -- este painel não decide o que está estrelado na caixa
-- de alguém.
-- ============================================================================

ALTER TABLE email_mensagem ADD COLUMN IF NOT EXISTS estrela boolean
    NOT NULL DEFAULT false;

COMMENT ON COLUMN email_mensagem.estrela IS
    'Reflexo local do marcador STARRED do Gmail, para a lista não precisar de '
    'uma subconsulta por linha. Quem manda é o Google.';

-- Semeia a partir do que já foi sincronizado: sem isto, mensagem estrelada no
-- Gmail apareceria sem estrela no painel até alguém mexer nela.
UPDATE email_mensagem e SET estrela = true
 WHERE EXISTS (SELECT 1 FROM email_mensagem_marcador mm
                 JOIN email_marcador mk ON mk.id = mm.marcador_id
                WHERE mm.mensagem_id = e.id AND mk.id_externo = 'STARRED');

-- A tela filtra "com estrela"; sem índice parcial isso varre a caixa inteira.
-- Parcial porque o que interessa é a minoria estrelada.
CREATE INDEX IF NOT EXISTS ix_email_estrela
    ON email_mensagem (conta_id, enviado_em DESC) WHERE estrela;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('033', now(), 'estrela no e-mail, reflexo local do STARRED');
