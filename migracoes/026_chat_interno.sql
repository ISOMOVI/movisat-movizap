-- ============================================================================
-- MoviZap — migração 026: chat entre atendentes
--
-- 🚨 EM TABELAS PRÓPRIAS, E ISSO É UMA MUDANÇA DE OPINIÃO. Eu tinha proposto
-- "reaproveitar conversa e mensagem, com um filtro separando das conversas de
-- cliente". Olhando o que isso custa, é a decisão errada:
--
--   · `conversa.telefone_e164` é NOT NULL e `canal_id` também -- um chat
--     interno teria de inventar telefone e canal falsos;
--   · `ux_conversa_aberta` é único por (canal, telefone): duas salas internas
--     colidiriam;
--   · e o principal -- TODA consulta sobre conversa de cliente passaria a
--     precisar do filtro. `listar`, `fila`, `resumo`, `historico`, a INI_1.1.
--     Esquecer o filtro UMA vez faz chat interno aparecer na caixa de entrada
--     como se fosse cliente, ou entrar na contagem de mensagens do painel.
--     Filtro que precisa ser lembrado em seis lugares é defeito esperando data.
--
-- Tabela própria não tem esse risco: quem consulta conversa de cliente não
-- enxerga isto, e nem precisa saber que existe.
--
-- ⚠️ NÃO É O SUBSTITUTO DA NOTA INTERNA. A nota responde "falar sobre ESTA
-- conversa" e continua onde está. Isto responde "falar sobre qualquer coisa".
-- ============================================================================

CREATE TABLE chat_sala (
    id         bigserial PRIMARY KEY,
    tipo       text NOT NULL CHECK (tipo IN ('direta', 'grupo')),
    nome       text,          -- só grupo tem nome; direta é "o outro"
    -- 🚨 A CHAVE QUE IMPEDE SALA DUPLICADA. Sem ela, dois atendentes clicando
    -- um no outro ao mesmo tempo criam DUAS salas para o mesmo par, e a
    -- conversa se parte em duas metades sem ninguém entender por quê. O valor
    -- é 'menor:maior' dos dois ids, calculado por quem cria.
    par        text UNIQUE,
    criada_em  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chat_sala_par_coerente CHECK (
        (tipo = 'direta' AND par IS NOT NULL AND nome IS NULL) OR
        (tipo = 'grupo'  AND par IS NULL AND nome IS NOT NULL))
);

CREATE TABLE chat_membro (
    sala_id       bigint NOT NULL REFERENCES chat_sala(id) ON DELETE CASCADE,
    atendente_id  bigint NOT NULL REFERENCES atendente(id),
    -- Id da última mensagem que esta pessoa leu. NULL = não leu nada.
    -- ⚠️ Guardar o ID e não a data: duas mensagens no mesmo instante fariam
    -- uma delas contar como não lida para sempre.
    lido_ate      bigint,
    entrou_em     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (sala_id, atendente_id)
);

CREATE INDEX ix_chat_membro_atendente ON chat_membro (atendente_id);

CREATE TABLE chat_mensagem (
    id            bigserial PRIMARY KEY,
    sala_id       bigint NOT NULL REFERENCES chat_sala(id) ON DELETE CASCADE,
    atendente_id  bigint NOT NULL REFERENCES atendente(id),
    texto         text NOT NULL CHECK (length(btrim(texto)) > 0),
    criada_em     timestamptz NOT NULL DEFAULT now()
);

-- 🚨 Postgres NÃO indexa FK sozinho, e esta é a consulta da tela: as
-- mensagens de uma sala, em ordem.
CREATE INDEX ix_chat_mensagem_sala ON chat_mensagem (sala_id, id);
CREATE INDEX ix_chat_mensagem_atendente ON chat_mensagem (atendente_id);

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('026', now(), 'chat entre atendentes: sala, membro e mensagem');
