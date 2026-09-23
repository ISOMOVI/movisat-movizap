-- ============================================================================
-- MoviZap — migração 050: o registro dos números bloqueados PELO PAINEL
--
-- 🔵 Pedido dele em 23/09: *"permitir ler e só bloquear se existir pelo
-- painel tbm"* -- bloquear pelo painel, e poder ver quem está bloqueado.
--
-- 🚨 POR QUE O PAINEL GUARDA O PRÓPRIO REGISTRO. Medido na instância real
-- (Evolution 2.3.7) em 23/09: bloquear existe (`/chat/updateBlockStatus`),
-- mas NÃO EXISTE rota que liste os bloqueados -- cinco nomes testados, todos
-- 404 -- e nenhum evento de bloqueio chega pelo webhook (57 mil eventos, só
-- mensagens, conexão e QR). O bloqueio feito NO CELULAR é invisível para o
-- painel. Só o que o painel bloqueia ele sabe -- e sabe porque anota aqui.
--
-- ⚠️ HISTÓRICO, NÃO ESTADO: desbloquear preenche `desbloqueado_em` em vez de
-- apagar a linha. Quem bloqueou quem, e quando, é o tipo de coisa que alguém
-- vai perguntar depois. O índice único parcial garante UM bloqueio ativo por
-- número e canal.
-- ============================================================================

BEGIN;

CREATE TABLE numero_bloqueado (
    id               bigserial PRIMARY KEY,
    canal_id         bigint NOT NULL REFERENCES canal(id),
    telefone_e164    text   NOT NULL,
    bloqueado_por    bigint REFERENCES atendente(id) ON DELETE SET NULL,
    bloqueado_em     timestamptz NOT NULL DEFAULT now(),
    desbloqueado_por bigint REFERENCES atendente(id) ON DELETE SET NULL,
    desbloqueado_em  timestamptz,
    CONSTRAINT ck_desbloqueio_depois CHECK (
        desbloqueado_em IS NULL OR desbloqueado_em >= bloqueado_em)
);

CREATE UNIQUE INDEX ux_numero_bloqueado_ativo
    ON numero_bloqueado (canal_id, telefone_e164)
    WHERE desbloqueado_em IS NULL;

COMMENT ON TABLE numero_bloqueado IS
    'Bloqueios feitos PELO PAINEL. O WhatsApp nao expoe a lista de bloqueados '
    '(medido 23/09): bloqueio feito no celular nao aparece aqui.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('050', now(), 'numero_bloqueado: registro dos bloqueios feitos pelo painel');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA (a prova é RELER O ESTADO):
--
--   \d numero_bloqueado
--   SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'numero_bloqueado';
-- ----------------------------------------------------------------------------
