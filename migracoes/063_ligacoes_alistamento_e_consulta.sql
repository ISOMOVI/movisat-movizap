-- ============================================================================
-- MoviZap — migração 063: alistamento por senha e a camada de CONSULTA das
-- ligações (15/10/2026)
--
-- 🔵 Pedido dele: *"o .exe deve rodar livre assim, porém validar o atendente
-- do MicroSip com uma senha que será gerada sempre via algoritmo e é mutável
-- para rodar"*, *"se trocarem de PC é só executar novamente e me pedir a
-- senha de uso"*, e a aba nova: *"um grid simples que tenha as ligações do
-- histórico do MicroSip, consultadas por cliente ... ou por Atendente, ou por
-- data ou por numero"*.
--
-- Três peças, e nenhuma delas muda o que já está no ar:
--
--   · `alistamento_queimado`: é o que faz a senha ser de USO ÚNICO. A senha
--     não é guardada em lugar nenhum -- ela é derivada por HMAC do segredo
--     `MOVIZAP_LIGACOES_SENHA_SEGREDO` sobre (ramal, janela de 10 min). Esta
--     tabela só registra que aquela janela daquele ramal já foi gasta, e
--     `UNIQUE (ramal, janela)` é a trava: a segunda tentativa com a mesma
--     senha bate na constraint e é recusada.
--
--   · Índices de consulta em `ligacao`. Hoje existe só
--     `ix_ligacao_telefone (telefone_e164, inicio DESC)`, que serve ao modal
--     da ficha (por número). O grid da aba ordena por data e filtra por
--     atendente, ramal e sentido -- daí os três índices novos, mais o da FK
--     `agente_id` (o projeto já tem migrações dedicadas a índice de FK: 002 e
--     016). 🚨 Índice sem consulta é palpite: estes nascem JUNTO das consultas
--     que os usam (`ligacoes.consultar`), não antes.
--
--   · `ligacao_exportacao`: quem exportou CSV, quando, com que filtros e
--     quantas linhas. Exportar ligação é número de telefone e áudio de
--     conversa saindo do sistema; sem registro não há como responder depois
--     quem levou o quê.
--
-- ⚠️ NÃO mexe em `ligacao`, `ligacao_gravacao` nem `agente_ligacao`: o envio
-- que está no ar desde 25/09 (28 ligações e 19 gravações no dia desta
-- migração) continua idêntico. Só acrescenta.
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------- alistamento

CREATE TABLE alistamento_queimado (
    id         bigserial PRIMARY KEY,
    ramal      text        NOT NULL,
    janela     bigint      NOT NULL,
    usado_em   timestamptz NOT NULL DEFAULT now(),
    pc         text,
    ip         text,
    agente_id  bigint REFERENCES agente_ligacao (id),
    UNIQUE (ramal, janela)
);

COMMENT ON TABLE alistamento_queimado IS
    'Senha de alistamento já gasta. A senha NUNCA é guardada: é derivada por '
    'HMAC do segredo MOVIZAP_LIGACOES_SENHA_SEGREDO sobre (ramal, janela de '
    '10 min). Esta tabela só diz que aquela janela foi usada, e o UNIQUE é o '
    'que impede usar a mesma senha duas vezes.';

COMMENT ON COLUMN alistamento_queimado.janela IS
    'Número da janela de 10 minutos (epoch / 600). Duas janelas são aceitas '
    'na conferência (a atual e a anterior, por tolerância de relógio), e cada '
    'uma só pode ser gasta uma vez.';

CREATE INDEX ix_alistamento_queimado_quando ON alistamento_queimado (usado_em DESC);

-- ------------------------------------------------------- índices de consulta

-- O grid da aba: ordem por data, com ou sem filtro.
CREATE INDEX ix_ligacao_inicio ON ligacao (inicio DESC);
-- "as ligações de uma pessoa", que é como a aba e o fechamento olham.
CREATE INDEX ix_ligacao_atendente ON ligacao (atendente_id, inicio DESC);
-- O ramal é o que o agente manda; o atendente pode mudar de ramal um dia.
CREATE INDEX ix_ligacao_ramal ON ligacao (ramal, inicio DESC);
-- FK sem índice: o padrão do projeto (002, 016) é dar índice a toda FK usada.
CREATE INDEX ix_ligacao_agente ON ligacao (agente_id);

-- ---------------------------------------------------------------- exportação

CREATE TABLE ligacao_exportacao (
    id            bigserial PRIMARY KEY,
    atendente_id  bigint      NOT NULL REFERENCES atendente (id),
    quando        timestamptz NOT NULL DEFAULT now(),
    filtros       jsonb       NOT NULL,
    linhas        integer     NOT NULL
);

COMMENT ON TABLE ligacao_exportacao IS
    'Uma linha por exportação de CSV da aba Ligações: quem, quando, com que '
    'filtros e quantas linhas saíram. Dado pessoal saindo do sistema se '
    'registra -- a tabela não guarda o conteúdo exportado, só o rastro.';

CREATE INDEX ix_ligacao_exportacao_quando ON ligacao_exportacao (quando DESC);

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('063', now(), 'ligações: alistamento por senha de uso único, índices de consulta e rastro de exportação');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA (a prova é RELER O ESTADO):
--
--   \d alistamento_queimado
--   \d ligacao_exportacao
--   SELECT indexname FROM pg_indexes WHERE tablename = 'ligacao' ORDER BY 1;
--     -- ix_ligacao_agente, ix_ligacao_atendente, ix_ligacao_inicio,
--     -- ix_ligacao_ramal, ix_ligacao_telefone, ligacao_pkey, ligacao_ramal_call_id_key
--   SELECT count(*) FROM ligacao;             -- 28 no dia desta migração
--   SELECT count(*) FROM ligacao_gravacao;    -- 19 no dia desta migração
--   SELECT count(*) FROM alistamento_queimado;-- 0 antes do primeiro alistamento
--   SELECT versao FROM schema_migracao WHERE versao = '063';         -- 063
--
-- DESFAZER, se precisar:
--   DROP TABLE ligacao_exportacao;
--   DROP TABLE alistamento_queimado;
--   DROP INDEX ix_ligacao_inicio, ix_ligacao_atendente, ix_ligacao_ramal, ix_ligacao_agente;
--   DELETE FROM schema_migracao WHERE versao = '063';
-- ----------------------------------------------------------------------------
