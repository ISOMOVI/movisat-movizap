-- ============================================================================
-- MoviZap — migração 059: backup das ligações do MicroSIP (Plano 5, 25/09)
--
-- 🔵 Pedido dele: *"inicialmente o backup das ligações na VPS de uma forma bem
-- inteligente -- depois ter uma rotina com histórico de chamadas na ficha da
-- pessoa do chat"* e *"um script que ... fique rodando 2x por dia no pc deles
-- e que se ficar mais 1 dia sem comunicar com VPS, tenhamos um alerta"*.
--
-- ⚠️ A 058 fica reservada ao Plano 4 (nota com versões, chat editar/apagar).
--
-- Três peças:
--   · `atendente.ramal`: o ramal da central Intelbras de cada operador.
--   · `agente_ligacao`: a CHAVE do agente de cada PC (só o hash) e o último
--     contato -- é por ele que sai o alerta de PC mudo há mais de 1 dia.
--   · `ligacao`: uma linha por ligação do histórico do MicroSIP, com ou sem
--     gravação. A gravação mora em disco (`/home/claude/movizap_ligacoes`),
--     e a tabela guarda o caminho e o SHA-256.
--
-- 🚨 IDEMPOTENTE PELO BANCO: `(ramal, call_id)` e o hash de cada arquivo são
-- únicos. O agente pode reenviar à vontade (PC que volta da rede, passada
-- repetida) sem duplicar nada.
-- ============================================================================

BEGIN;

ALTER TABLE atendente ADD COLUMN ramal text;
CREATE UNIQUE INDEX ux_atendente_ramal ON atendente (ramal) WHERE ramal IS NOT NULL;

CREATE TABLE agente_ligacao (
    id                 bigserial PRIMARY KEY,
    atendente_id       bigint NOT NULL REFERENCES atendente(id),
    ramal              text NOT NULL,
    chave_sha256       text NOT NULL UNIQUE,
    criado_em          timestamptz NOT NULL DEFAULT now(),
    ultimo_contato_em  timestamptz,
    ultimo_pc          text,
    ultima_versao      text,
    ultimo_erro        text,
    pendentes          int,
    revogado_em        timestamptz
);
CREATE INDEX ix_agente_ligacao_contato ON agente_ligacao (ultimo_contato_em)
    WHERE revogado_em IS NULL;

CREATE TABLE ligacao (
    id              bigserial PRIMARY KEY,
    agente_id       bigint NOT NULL REFERENCES agente_ligacao(id),
    atendente_id    bigint NOT NULL REFERENCES atendente(id),
    ramal           text NOT NULL,
    call_id         text NOT NULL,
    numero_bruto    text NOT NULL,
    telefone_e164   text,
    sentido         text NOT NULL CHECK (sentido IN ('feita', 'recebida', 'perdida')),
    situacao        text,
    inicio          timestamptz NOT NULL,
    duracao_s       int NOT NULL DEFAULT 0 CHECK (duracao_s >= 0),
    pc              text,
    recebida_em     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (ramal, call_id)
);
CREATE INDEX ix_ligacao_telefone ON ligacao (telefone_e164, inicio DESC);

-- Uma ligação pode ter VÁRIAS gravações: quando a gravação recomeça no meio,
-- o MicroSIP abre outro arquivo (medido em 10/08 13:27 e 18/09 17:34).
CREATE TABLE ligacao_gravacao (
    id              bigserial PRIMARY KEY,
    ligacao_id      bigint NOT NULL REFERENCES ligacao(id) ON DELETE CASCADE,
    nome_original   text NOT NULL,
    arquivo_sha256  text NOT NULL UNIQUE,
    arquivo_bytes   bigint NOT NULL CHECK (arquivo_bytes > 0),
    caminho         text NOT NULL,
    inicio          timestamptz,
    recebida_em     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_ligacao_gravacao_ligacao ON ligacao_gravacao (ligacao_id);

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('059', now(), 'ligacoes do MicroSIP: ramal, agente, ligacao e gravacao');

COMMIT;
