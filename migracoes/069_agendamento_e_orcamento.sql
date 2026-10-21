-- ============================================================================
-- MoviZap — migração 069: agendamento de serviço e orçamento
--
-- 🔵 Decisão dele, 19/10: **o MoviZap é o dono do agendamento**. A escrita no
-- Harmonit é 2º passo, testada antes na OS 16991 da Velasco -- então o
-- compromisso precisa de casa própria aqui, e não de um campo emprestado.
--
-- 🚨 A OS NÃO TEM CAMPO DE DATA AGENDADA EM LUGAR NENHUM, medido em 19/10 e
-- reconferido em 21/10: no FPSL (SQLite, `os_historico`, 572 OS) existe
-- `data_previsao`, que é a PREVISÃO do Harmonit, 100% preenchida e com outro
-- significado; o resto é texto livre nos checklists da Solução Técnica. Por
-- isso nada aqui tenta "achar" o agendamento do lado do Harmonit.
--
-- 🚨 `cliente_harmonit_id` É text, NÃO int -- e o plano de 19/10 dizia int.
-- Medido hoje: `cliente.harmonit_id` do MoviZap é `text` (959 clientes, todos
-- preenchidos, todos numéricos), e é por ele que se cruza com a OS do FPSL.
-- Gravar int aqui obrigaria um cast em toda junção com a tabela `cliente` --
-- e cast em junção é o tipo de detalhe que ninguém lembra seis meses depois.
--
-- 🚨 DINHEIRO EM CENTAVOS, INTEIRO. Documento com valor não usa float: o
-- orçamento é impresso, enviado ao cliente e some do controle do sistema.
--
-- ⚠️ A ligação com a OS vive em `agendamento_os`, e não numa coluna: ele
-- decidiu que um compromisso pode cobrir VÁRIAS OS (decisão 10, "a tela junta
-- OS, técnico e cliente").
--
-- ⚠️ "Uma OS não entra em dois compromissos ativos" é regra de código, não
-- constraint: `agendamento_os` não carrega o estado, e espalhar o estado nas
-- duas tabelas criaria duas versões do mesmo fato. A regra mora no serviço e
-- tem teste.
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- O orçamento vem primeiro: o agendamento aponta para ele.
-- ---------------------------------------------------------------------------
CREATE TABLE orcamento (
    id                  bigserial PRIMARY KEY,
    -- 🔵 Decisão 9 dele: numeração PRÓPRIA, com aba de configuração só do
    -- owner. UNIQUE porque número repetido em documento emitido não tem
    -- conserto depois -- o sistema atual, fora desta VPS, segue emitindo.
    numero              bigint      NOT NULL UNIQUE,
    tecnico_contato_id  bigint      NOT NULL REFERENCES contato (id),
    conversa_id         bigint      NOT NULL REFERENCES conversa (id),
    total_centavos      bigint      NOT NULL,
    -- O PDF reaproveita a mídia que a conversa já usa: anexo de orçamento é
    -- anexo, e assim ele aparece no histórico como qualquer outro.
    midia_id            bigint      REFERENCES midia (id),
    criado_por          bigint      NOT NULL REFERENCES atendente (id),
    criado_em           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX orcamento_conversa_idx ON orcamento (conversa_id);
CREATE INDEX orcamento_tecnico_idx  ON orcamento (tecnico_contato_id);

CREATE TABLE orcamento_item (
    orcamento_id         bigint   NOT NULL REFERENCES orcamento (id) ON DELETE CASCADE,
    ordem                integer  NOT NULL,
    servico              text     NOT NULL,
    preco_unit_centavos  bigint   NOT NULL,
    quantidade           numeric(12, 3) NOT NULL,
    -- 🔵 Decisão 13 dele: deslocamento é POR KM (R$ 1,00 x 77,7 km = R$ 77,70).
    -- O documento de hoje imprime "77.7 un", e é isso que faz a coluna
    -- parecer trocada -- a unidade é dado, não enfeite do PDF.
    unidade              text     NOT NULL DEFAULT 'un'
                                  CHECK (unidade IN ('un', 'km')),
    valor_centavos       bigint   NOT NULL,
    PRIMARY KEY (orcamento_id, ordem)
);

-- ---------------------------------------------------------------------------
-- O compromisso.
-- ---------------------------------------------------------------------------
CREATE TABLE agendamento (
    id                   bigserial PRIMARY KEY,
    -- A conversa de ORIGEM. ⚠️ É conversa de TÉCNICO: nela
    -- `contato.cliente_id` é NULL por desenho (decisão dele de 07/10), e é
    -- por isso que o cliente abaixo é escolhido à mão, com busca própria.
    conversa_id          bigint      NOT NULL REFERENCES conversa (id),
    tecnico_contato_id   bigint      NOT NULL REFERENCES contato (id),
    -- A CHAVE DA PONTE com o FPSL. text, igual ao `cliente.harmonit_id`.
    cliente_harmonit_id  text        NOT NULL,
    -- Retrato do nome, para a tela de Agendamentos não depender do Harmonit
    -- estar no ar nem do cliente continuar cadastrado com o mesmo nome.
    cliente_nome         text        NOT NULL,
    inicio               timestamptz NOT NULL,
    fim                  timestamptz,
    -- 🔵 Decisão 11 dele: o operador DIGITA o endereço, sugerido com o último
    -- usado para aquele cliente. Sugestão sai desta própria coluna.
    endereco             text,
    -- Quem acompanha o técnico. Nulo até o cliente confirmar (aba Confirmar).
    responsavel_cliente  text,
    estado               text        NOT NULL DEFAULT 'rascunho'
                                     CHECK (estado IN ('rascunho', 'aguardando',
                                                       'confirmado', 'cancelado')),
    orcamento_id         bigint      REFERENCES orcamento (id),
    criado_por           bigint      NOT NULL REFERENCES atendente (id),
    criado_em            timestamptz NOT NULL DEFAULT now(),
    confirmado_em        timestamptz,
    cancelado_em         timestamptz,
    motivo_cancelamento  text
);
-- O carrossel da semana varre por data; o resto são as junções da tela.
CREATE INDEX agendamento_inicio_idx  ON agendamento (inicio);
CREATE INDEX agendamento_cliente_idx ON agendamento (cliente_harmonit_id);
CREATE INDEX agendamento_conversa_idx ON agendamento (conversa_id);
CREATE INDEX agendamento_estado_idx  ON agendamento (estado);

CREATE TABLE agendamento_os (
    agendamento_id  bigint NOT NULL REFERENCES agendamento (id) ON DELETE CASCADE,
    numero_os       bigint NOT NULL,
    -- A placa vem do `oficinas_json` da OS, no FPSL. ⚠️ Só 236 das 572 OS têm
    -- oficina, então a placa É NULA com frequência -- e a tela tem de dizer
    -- isso em vez de mostrar vazio.
    placa           text,
    PRIMARY KEY (agendamento_id, numero_os)
);
-- "Uma OS não entra em dois compromissos ativos" é checado no serviço; este
-- índice é o que torna essa checagem barata.
CREATE INDEX agendamento_os_numero_idx ON agendamento_os (numero_os);

-- ---------------------------------------------------------------------------
-- A numeração, com casa no `config` -- o mesmo lugar de todo interruptor do
-- sistema (CFG_7.1, regra dele).
-- ---------------------------------------------------------------------------
INSERT INTO config (chave, valor, descricao, atualizado_em)
VALUES (
    'orcamento_proximo_numero', '1',
    'Proximo numero de orcamento a ser emitido. 🔵 Decisao 9 dele (19/10): '
    'numeracao propria do MoviZap, configuravel so pelo owner. 🚨 O numero so '
    'e GASTO quando o PDF existe -- reservar antes deixa buraco na sequencia '
    'quando alguem fecha o modal. ⚠️ Mudar este valor pode repetir documento '
    'ja emitido pelo sistema atual, que segue existindo fora desta VPS.',
    now()
)
ON CONFLICT (chave) DO NOTHING;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('069', now(), 'agendamento de servico e orcamento: 4 tabelas e a numeracao');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA (a prova é RELER O ESTADO, nunca o retorno do comando):
--
--   SELECT table_name FROM information_schema.tables
--    WHERE table_name IN ('agendamento','agendamento_os','orcamento','orcamento_item');
--     -- esperado: as quatro
--
--   SELECT pg_get_constraintdef(oid) FROM pg_constraint
--    WHERE conrelid = 'agendamento'::regclass AND contype = 'c';
--     -- esperado: CHECK (estado IN ('rascunho','aguardando','confirmado','cancelado'))
--
--   SELECT valor FROM config WHERE chave = 'orcamento_proximo_numero';  -- 1
--   SELECT versao FROM schema_migracao WHERE versao = '069';            -- 069
--
-- DESFAZER, se precisar (nenhuma tabela tem dado antes da primeira emissão):
--   DROP TABLE agendamento_os, agendamento, orcamento_item, orcamento;
--   DELETE FROM config WHERE chave = 'orcamento_proximo_numero';
--   DELETE FROM schema_migracao WHERE versao = '069';
-- ----------------------------------------------------------------------------
