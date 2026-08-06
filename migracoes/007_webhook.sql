-- ============================================================================
-- MoviZap — migração 007: o canal informativo, o interruptor da IA e o
--                          registro cru do webhook
--
-- ----------------------------------------------------------------------------
-- 1. CANAL INFORMATIVO
--
-- A migração 003 deixou este canal de fora de propósito: "código de canal que
-- existe sem tela é convite a alguém mandar mensagem por ele antes da hora".
-- O usuário pediu em 06/08 para subir os dois chips e tratar depois.
--
-- 🚨 O DISPARO EM MASSA CONTINUA FORA DA FASE 1. Conectar e receber não é
-- disparar. Não existe rota de envio em lote neste projeto, e este canal
-- existir não cria uma.
--
-- ----------------------------------------------------------------------------
-- 2. INTERRUPTOR DA IA — POR CANAL, NASCENDO DESLIGADO
--
-- Decisão do usuário em 06/08: "somente o canal Atendimento terá IA, o
-- informativo nem recebe mensagem". E: validar conexão -> bot -> ligar
-- ativamente.
--
-- Por canal, e não global, porque global obrigaria alguém a lembrar de
-- desligar antes de cada disparo -- e "lembrar" é exatamente o que falha.
-- Aqui o informativo não tem como ligar: a coluna nasce false e a tela dele
-- não oferece o interruptor.
--
-- ----------------------------------------------------------------------------
-- 3. `webhook_evento` — O PAYLOAD CRU, ANTES DE QUALQUER INTERPRETAÇÃO
--
-- 🚨 Esta tabela é a mitigação escrita do risco de parear o chip por último.
-- Todo parser deste projeto foi escrito contra a DOCUMENTAÇÃO do Evolution
-- 2.3.7, não contra o que ele de fato manda. Guardar o corpo inteiro, antes de
-- interpretar, é o que permite reprocessar quando o formato surpreender --
-- em vez de descobrir com 14 telas prontas em cima de uma suposição errada.
--
-- 🚨 A IDEMPOTÊNCIA É DO BANCO, NÃO DA DISCIPLINA. O Evolution reenvia e não
-- garante ordem. `ux_webhook_externo` faz da reentrega um conflito esperado:
-- ignora e responde 200. Nunca deduplicar por conteúdo ou timestamp -- cliente
-- manda "ok" duas vezes de propósito, e isso é legítimo.
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------- 1 e 2

ALTER TABLE canal
    ADD COLUMN IF NOT EXISTS ia_ligada     boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS ia_ligada_em  timestamptz,
    ADD COLUMN IF NOT EXISTS ia_ligada_por text;

COMMENT ON COLUMN canal.ia_ligada IS
    'Interruptor da IA, por canal. Nasce DESLIGADO e só liga por ação '
    'deliberada na CFG_1.1. O canal informativo nunca liga.';

INSERT INTO canal (nome, tipo, gateway, instancia, modo, ativo)
VALUES ('Informativos', 'informativo', 'evolution', 'informativos', 'baileys', true)
ON CONFLICT DO NOTHING;

-- Estado inicial explícito, como na 003: sem esta linha o histórico começaria
-- na primeira consulta da tela, e "desde quando está assim?" mentiria.
INSERT INTO canal_evento (canal_id, estado, motivo)
SELECT id, 'desconectado', 'cadastrado pela migração 007'
FROM canal WHERE instancia = 'informativos'
  AND NOT EXISTS (SELECT 1 FROM canal_evento ce WHERE ce.canal_id = canal.id);

-- ---------------------------------------------------------------- 3

CREATE TABLE IF NOT EXISTS webhook_evento (
    id           bigserial PRIMARY KEY,
    canal_id     bigint REFERENCES canal(id),
    instancia    text,
    evento       text,
    id_externo   text,
    de_mim       boolean,
    telefone     text,
    recebido_em  timestamptz NOT NULL DEFAULT now(),
    processado   boolean NOT NULL DEFAULT false,
    processado_em timestamptz,
    erro         text,
    payload      jsonb NOT NULL
);

-- 🚨 A trava da reentrega. Parcial porque nem todo evento tem id -- os de
-- conexão não têm, e não podem ser deduplicados por um NULL.
CREATE UNIQUE INDEX IF NOT EXISTS ux_webhook_externo
    ON webhook_evento (instancia, id_externo)
    WHERE id_externo IS NOT NULL;

-- O que se consulta: o que ainda não foi processado, e o que chegou por
-- último de um telefone.
CREATE INDEX IF NOT EXISTS ix_webhook_pendente
    ON webhook_evento (recebido_em) WHERE NOT processado;

CREATE INDEX IF NOT EXISTS ix_webhook_telefone
    ON webhook_evento (telefone, recebido_em DESC) WHERE telefone IS NOT NULL;

-- 🚨 Postgres NÃO indexa chave estrangeira sozinho.
CREATE INDEX IF NOT EXISTS ix_webhook_canal
    ON webhook_evento (canal_id);

COMMENT ON TABLE webhook_evento IS
    'O corpo cru de todo webhook do Evolution, antes de qualquer '
    'interpretação. Existe para o formato real poder ser conferido e '
    'reprocessado -- os parsers foram escritos contra a documentação.';

INSERT INTO schema_migracao (versao, descricao)
VALUES ('007', 'Canal informativo, interruptor da IA por canal e webhook_evento');

COMMIT;
