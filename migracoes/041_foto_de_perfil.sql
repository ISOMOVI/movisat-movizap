-- ============================================================================
-- MoviZap — migração 041: a foto de perfil de quem escreve
--
-- 🟢 Pedido da Erika (15/09): *"permitir exibir as fotos de perfil de cada
-- contato"*.
--
-- 🚨 POR TELEFONE, E NÃO POR CONTATO. A foto é de quem está no WhatsApp, e
-- 61% das conversas não têm cadastro nenhum (medido em 28/08) -- pendurar a
-- foto no `contato` deixaria justamente a maioria sem foto. O telefone é o
-- que sempre existe.
--
-- 🚨 O ARQUIVO FICA EM DISCO, NÃO A URL. Medido em 15/09 no payload real: a
-- URL que o WhatsApp devolve tem `oe=` -- ela EXPIRA. Guardar o link daria
-- uma foto que funciona hoje e vira um quadrado quebrado semana que vem, sem
-- nada no log dizendo por quê. Mesma decisão que já vale para a mídia das
-- mensagens.
--
-- ⚠️ `buscada_em` existe para não perguntar ao Evolution a cada abertura de
-- tela: uma consulta por telefone por dia basta, e quem muda de foto não
-- muda de hora em hora.
--
-- ⚠️ `sem_foto` distingue "nunca perguntei" de "perguntei e a pessoa não tem
-- foto (ou escondeu no privacidade)". Sem isso, todo telefone sem foto vira
-- uma pergunta repetida ao Evolution para sempre.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS foto_perfil (
    e164        TEXT PRIMARY KEY,
    arquivo     TEXT,
    sem_foto    BOOLEAN NOT NULL DEFAULT false,
    buscada_em  TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE foto_perfil IS
    'Foto do WhatsApp por telefone. O ARQUIVO fica em disco: a URL do '
    'WhatsApp expira (oe=), medido em 15/09.';

COMMENT ON COLUMN foto_perfil.sem_foto IS
    'true = perguntamos e nao ha foto (ou esta escondida). Distingue de '
    '"nunca perguntamos", que e a ausencia da linha.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('041', now(), 'foto de perfil do WhatsApp, por telefone');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA (a prova é RELER O ESTADO):
--
--   \d foto_perfil
--   SELECT count(*) FROM foto_perfil;                          -- 0
--   SELECT versao FROM schema_migracao WHERE versao = '041';   -- 041
-- ----------------------------------------------------------------------------
