-- ============================================================================
-- MoviZap — migração 010: estrutura de envio do canal informativo (ATD_3.1)
--
-- Decisão do usuário em 07/08: "o informativo é o que vai enviar, sem resposta
-- de cliente". O canal já está pareado e entregando (TESTE BOT confirmado com
-- DELIVERY_ACK em 2s).
--
-- ----------------------------------------------------------------------------
-- POR QUE UMA TABELA, E NÃO UM LAÇO QUE MANDA
--
-- Metodologia §4, sobre escrita no WhatsApp: *"o canal é irreversível --
-- mensagem enviada não volta"*. Disso saem três exigências que um laço simples
-- não atende:
--
--   1. **Começar com 1.** O primeiro destino é enviado e conferido antes de o
--      resto sair. Só dá para fazer isso se o resto estiver GUARDADO em algum
--      lugar, esperando.
--   2. **A confirmação é o estado de entrega, não o retorno do POST.** Cada
--      destino guarda o `id_externo` para o webhook casar o `DELIVERY_ACK`
--      depois -- exatamente como a conversa faz.
--   3. **Retomar sem repetir.** Se o serviço reiniciar no meio de 369 envios,
--      um laço em memória perde o ponto e reenvia. Aqui o estado é por
--      destino, no banco.
--
-- 🚨 `UNIQUE (disparo_id, telefone_e164)` -- o mesmo número não recebe duas
-- vezes o mesmo informativo, mesmo que esteja em dois contatos. Dez números da
-- base estão em mais de um contato, um deles em oito: sem esta trava, uma
-- central de empresa receberia o mesmo boleto oito vezes.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS disparo (
    id              bigserial PRIMARY KEY,
    canal_id        bigint NOT NULL REFERENCES canal(id),
    titulo          text NOT NULL,
    corpo           text NOT NULL,
    estado          text NOT NULL DEFAULT 'rascunho'
                    CHECK (estado IN ('rascunho', 'enviando', 'pausado',
                                      'concluido', 'cancelado')),
    -- Ritmo é REGRA DE CÓDIGO, não disciplina de quem aperta o botão
    -- (metodologia §4: "ritmo, não rajada").
    intervalo_seg   integer NOT NULL DEFAULT 5 CHECK (intervalo_seg >= 1),
    teto_por_hora   integer NOT NULL DEFAULT 200 CHECK (teto_por_hora >= 1),
    criado_por      bigint REFERENCES atendente(id),
    criado_em       timestamptz NOT NULL DEFAULT now(),
    iniciado_em     timestamptz,
    concluido_em    timestamptz
);

CREATE TABLE IF NOT EXISTS disparo_destino (
    id              bigserial PRIMARY KEY,
    disparo_id      bigint NOT NULL REFERENCES disparo(id) ON DELETE CASCADE,
    cliente_id      bigint REFERENCES cliente(id),
    contato_id      bigint REFERENCES contato(id),
    telefone_e164   text NOT NULL,
    estado          text NOT NULL DEFAULT 'pendente'
                    CHECK (estado IN ('pendente', 'enviado', 'entregue',
                                      'lido', 'falhou', 'cancelado')),
    id_externo      text,
    erro            text,
    enviado_em      timestamptz,
    atualizado_em   timestamptz NOT NULL DEFAULT now()
);

-- 🚨 Um número, um envio por disparo. Ver o cabeçalho.
CREATE UNIQUE INDEX IF NOT EXISTS ux_disparo_destino
    ON disparo_destino (disparo_id, telefone_e164);

-- A fila de quem ainda não recebeu, que é a consulta do laço de envio.
CREATE INDEX IF NOT EXISTS ix_disparo_pendente
    ON disparo_destino (disparo_id, estado) WHERE estado = 'pendente';

-- O webhook casa o DELIVERY_ACK por aqui.
CREATE INDEX IF NOT EXISTS ix_disparo_id_externo
    ON disparo_destino (id_externo) WHERE id_externo IS NOT NULL;

COMMENT ON TABLE disparo IS
    'Informativo a enviar pelo canal informativo (ATD_3.1). O ritmo e o teto '
    'por hora vivem aqui porque são regra, não disciplina de quem dispara.';

COMMENT ON COLUMN disparo_destino.id_externo IS
    'key.id que o WhatsApp devolveu. É por ele que o DELIVERY_ACK do webhook '
    'encontra este destino -- a confirmação é o estado de entrega, nunca o '
    'retorno do POST.';

INSERT INTO schema_migracao (versao, descricao)
VALUES ('010', 'Estrutura de envio do canal informativo (ATD_3.1)');

COMMIT;
