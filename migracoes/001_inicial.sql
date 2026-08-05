-- ============================================================================
-- MoviZap — migração 001: esquema inicial
-- Implementa docs/02_Modelo_Dados.md v2, aprovado em 2026-08-05.
--
-- Decisões de implementação que o documento não fixa:
--
--   ENUM como text + CHECK, não como tipo nativo. Acrescentar valor a um
--   ENUM nativo funciona, mas remover ou reordenar não, e o valor fica
--   invisível para quem lê a tabela. CHECK aparece no \d e se altera com uma
--   linha.
--
--   Sem ORM e sem alembic. O backend do MoviZap não tem SQLAlchemy, e
--   alembic traria alembic.ini -- que nos outros projetos guarda senha em
--   texto puro. Migração é arquivo .sql numerado, registrado em
--   schema_migracao.
--
--   `time` é palavra não reservada no PostgreSQL e funciona como nome de
--   tabela, mas exige atenção em cast. Mantido por ser o nome aprovado.
-- ============================================================================

BEGIN;

CREATE TABLE schema_migracao (
    versao      text PRIMARY KEY,
    aplicada_em timestamptz NOT NULL DEFAULT now(),
    descricao   text
);

-- ============================================================ CADASTRO

CREATE TABLE cliente (
    id             bigserial PRIMARY KEY,
    nome           text NOT NULL,
    nome_fantasia  text,
    -- CNPJ alfanumérico já existe na base: nunca validar como só dígitos
    documento      text,
    tipo_pessoa    smallint,
    email          text,
    origem         text NOT NULL CHECK (origem IN ('harmonit','movizap')),
    harmonit_id    text,
    ativo          boolean NOT NULL DEFAULT true,
    criado_em      timestamptz NOT NULL DEFAULT now(),
    atualizado_em  timestamptz NOT NULL DEFAULT now()
);
-- UNIQUE parcial: só vale para linha vinda do Harmonit
CREATE UNIQUE INDEX ux_cliente_harmonit ON cliente (harmonit_id)
    WHERE harmonit_id IS NOT NULL;
CREATE INDEX ix_cliente_documento ON cliente (documento);
CREATE INDEX ix_cliente_nome ON cliente (lower(nome));

CREATE TABLE contato (
    id             bigserial PRIMARY KEY,
    cliente_id     bigint REFERENCES cliente(id),   -- NULL: lead e fornecedor
    nome           text NOT NULL,
    relacao        text NOT NULL DEFAULT 'lead'
                   CHECK (relacao IN ('cliente','fornecedor','parceiro','tecnico','lead')),
    email          text,
    origem         text NOT NULL CHECK (origem IN ('harmonit','movizap')),
    harmonit_id    text,
    ativo          boolean NOT NULL DEFAULT true,
    criado_em      timestamptz NOT NULL DEFAULT now(),
    atualizado_em  timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_contato_harmonit ON contato (harmonit_id)
    WHERE harmonit_id IS NOT NULL;
CREATE INDEX ix_contato_cliente ON contato (cliente_id);
CREATE INDEX ix_contato_nome ON contato (lower(nome));

-- Papel DENTRO do cliente. Eixo diferente de `relacao`: um técnico não é
-- "papel de contato de cliente". Na Fase 1 grava e não aciona nada.
CREATE TABLE contato_papel (
    contato_id  bigint NOT NULL REFERENCES contato(id) ON DELETE CASCADE,
    papel       text NOT NULL
                CHECK (papel IN ('assinar','central_24h','financeiro')),
    PRIMARY KEY (contato_id, papel)
);

CREATE TABLE contato_telefone (
    id            bigserial PRIMARY KEY,
    contato_id    bigint NOT NULL REFERENCES contato(id) ON DELETE CASCADE,
    -- normalizado. É por aqui que se busca, NUNCA por `bruto`
    e164          text NOT NULL,
    bruto         text NOT NULL,
    origem_campo  text CHECK (origem_campo IN ('telefone','telefone2','celular','whatsapp','manual')),
    -- NULL = não verificado. Diferente de false = verificado e não tem.
    -- 🚨 Nunca deduzir do formato: fixo e 0800 têm WhatsApp.
    tem_whatsapp  boolean,
    verificado_em timestamptz,
    principal     boolean NOT NULL DEFAULT false,
    criado_em     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_telefone_e164 ON contato_telefone (e164);
CREATE UNIQUE INDEX ux_telefone_contato_e164 ON contato_telefone (contato_id, e164);

-- ============================================================ OPERAÇÃO

CREATE TABLE atendente (
    id                bigserial PRIMARY KEY,
    login             text NOT NULL,
    nome              text NOT NULL,           -- é o que o cliente vê
    email             text,
    senha_hash        text,
    google_sub        text,                    -- Fase 2, sem migração depois
    ativo             boolean NOT NULL DEFAULT true,
    owner             boolean NOT NULL DEFAULT false,
    estado            text NOT NULL DEFAULT 'disponivel'
                      CHECK (estado IN ('disponivel','ausente','nao_perturbe')),
    fuso              text NOT NULL DEFAULT 'America/Sao_Paulo',
    max_conversas     int,                     -- NULL = sem teto
    convite_token     text,
    convite_expira_em timestamptz,
    criado_em         timestamptz NOT NULL DEFAULT now(),
    atualizado_em     timestamptz NOT NULL DEFAULT now()
);
-- 🚨 UNIQUE sobre lower(login): 'Admin' e 'admin' são a MESMA conta.
-- O login ignora maiúscula desde 05/08 -- sem este índice, nasceriam duas.
CREATE UNIQUE INDEX ux_atendente_login ON atendente (lower(login));
CREATE UNIQUE INDEX ux_atendente_google ON atendente (google_sub)
    WHERE google_sub IS NOT NULL;

-- Uma linha por faixa: cobre almoço e escala partida sem gambiarra.
CREATE TABLE atendente_jornada (
    id           bigserial PRIMARY KEY,
    atendente_id bigint NOT NULL REFERENCES atendente(id) ON DELETE CASCADE,
    dia_semana   smallint NOT NULL CHECK (dia_semana BETWEEN 0 AND 6),  -- 0=domingo
    inicio       time NOT NULL,
    fim          time NOT NULL,
    CHECK (fim > inicio)
);
CREATE INDEX ix_jornada_atendente ON atendente_jornada (atendente_id, dia_semana);

CREATE TABLE time (
    id                 bigserial PRIMARY KEY,
    nome               text NOT NULL UNIQUE,
    -- 🚨 A descrição é ENTRADA DA IA, não enfeite: é por ela que a IA
    -- escolhe o destino. Time sem descrição = IA chutando.
    descricao          text,
    ativo              boolean NOT NULL DEFAULT true,
    time_transbordo_id bigint REFERENCES time(id),
    criado_em          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE atendente_time (
    atendente_id bigint NOT NULL REFERENCES atendente(id) ON DELETE CASCADE,
    time_id      bigint NOT NULL REFERENCES time(id) ON DELETE CASCADE,
    PRIMARY KEY (atendente_id, time_id)
);

-- Permissão de DADO, não de tela. telas.py responde "pode abrir a ATD_1.3?";
-- isto responde "quais conversas aparecem lá dentro".
-- SEM linha aqui = vê a fila inteira. Padrão permissivo de propósito: time
-- novo não pode deixar ninguém cego sem que se perceba.
CREATE TABLE atendente_time_permissao (
    atendente_id bigint NOT NULL REFERENCES atendente(id) ON DELETE CASCADE,
    time_id      bigint NOT NULL REFERENCES time(id) ON DELETE CASCADE,
    PRIMARY KEY (atendente_id, time_id)
);

CREATE TABLE classificacao (
    id             bigserial PRIMARY KEY,
    nome           text NOT NULL UNIQUE,
    -- 'Outro' sem texto vira o vale-tudo onde metade das conversas acaba
    exige_comentario boolean NOT NULL DEFAULT false,
    ativo          boolean NOT NULL DEFAULT true,
    ordem          int NOT NULL DEFAULT 0
);

CREATE TABLE config (
    chave         text PRIMARY KEY,
    valor         text NOT NULL,
    descricao     text,
    atualizado_em timestamptz NOT NULL DEFAULT now()
);

-- ============================================================ CANAL

CREATE TABLE canal (
    id        bigserial PRIMARY KEY,
    nome      text NOT NULL,
    tipo      text NOT NULL CHECK (tipo IN ('atendimento','informativo')),
    gateway   text NOT NULL DEFAULT 'evolution'
              CHECK (gateway IN ('evolution','email')),
    instancia text,
    modo      text CHECK (modo IN ('baileys','cloud_api')),
    ativo     boolean NOT NULL DEFAULT true,
    criado_em timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_canal_instancia ON canal (instancia)
    WHERE instancia IS NOT NULL;

-- 🚨 É o que responde "desde quando parou de chegar mensagem?".
-- Sem histórico essa pergunta não se responde, só se chuta.
CREATE TABLE canal_evento (
    id       bigserial PRIMARY KEY,
    canal_id bigint NOT NULL REFERENCES canal(id) ON DELETE CASCADE,
    estado   text NOT NULL CHECK (estado IN
             ('desconectado','aguardando_qr','pareando','conectado','caiu')),
    motivo   text,
    em       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_canal_evento ON canal_evento (canal_id, em DESC);

-- ============================================================ CONVERSA

CREATE TABLE conversa (
    id                    bigserial PRIMARY KEY,
    canal_id              bigint NOT NULL REFERENCES canal(id),
    contato_id            bigint REFERENCES contato(id),  -- NULL até identificar
    telefone_e164         text NOT NULL,
    estado                text NOT NULL DEFAULT 'nova' CHECK (estado IN
                          ('nova','bot','fila','humano','resolvida','adiada')),
    time_id               bigint REFERENCES time(id),
    atendente_id          bigint REFERENCES atendente(id),
    prompt_versao_id      bigint,   -- FK adicionada depois de prompt_versao
    classificacao_id      bigint REFERENCES classificacao(id),
    classificacao_texto   text,
    adiada_ate            timestamptz,

    -- base do repasse por inatividade
    ultima_atividade_em   timestamptz NOT NULL DEFAULT now(),

    -- métricas congeladas no fechamento: derivar de `mensagem` funciona uma
    -- vez e fica caro toda vez
    primeira_resposta_em  timestamptz,
    resolvida_em          timestamptz,
    segundos_ate_resposta int,
    segundos_total        int,
    qtd_transferencias    int NOT NULL DEFAULT 0,
    resolvida_pela_ia     boolean NOT NULL DEFAULT false,

    avaliacao             smallint CHECK (avaliacao BETWEEN 1 AND 5),
    avaliacao_pedida_em   timestamptz,
    avaliacao_comentario  text,

    criada_em             timestamptz NOT NULL DEFAULT now(),
    atualizada_em         timestamptz NOT NULL DEFAULT now()
);

-- 🚨 Uma conversa ABERTA por telefone, por canal. É isto que faz o cliente
-- que volta REABRIR em vez de criar outra conversa.
CREATE UNIQUE INDEX ux_conversa_aberta ON conversa (canal_id, telefone_e164)
    WHERE estado <> 'resolvida';
CREATE INDEX ix_conversa_fila ON conversa (estado, time_id);
CREATE INDEX ix_conversa_inatividade ON conversa (estado, ultima_atividade_em);
CREATE INDEX ix_conversa_resolvida ON conversa (resolvida_em);
CREATE INDEX ix_conversa_contato ON conversa (contato_id);

CREATE TABLE transferencia (
    id                bigserial PRIMARY KEY,
    conversa_id       bigint NOT NULL REFERENCES conversa(id) ON DELETE CASCADE,
    de_atendente_id   bigint REFERENCES atendente(id),
    para_atendente_id bigint REFERENCES atendente(id),
    para_time_id      bigint REFERENCES time(id),
    motivo            text NOT NULL CHECK (motivo IN
                      ('manual','inatividade','ia_triagem','sem_time')),
    -- o que a IA apurou, para o humano não pedir tudo de novo
    resumo            text,
    em                timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_transferencia_conversa ON transferencia (conversa_id, em);

CREATE TABLE midia (
    id            bigserial PRIMARY KEY,
    conversa_id   bigint NOT NULL REFERENCES conversa(id) ON DELETE CASCADE,
    mime          text,
    tamanho       bigint,
    caminho       text NOT NULL,      -- arquivo em disco, não no banco
    nome_original text,
    hash          text,               -- evita guardar duas vezes o mesmo áudio
    baixada_em    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_midia_hash ON midia (hash);

CREATE TABLE mensagem (
    id           bigserial PRIMARY KEY,
    conversa_id  bigint NOT NULL REFERENCES conversa(id) ON DELETE CASCADE,
    -- 🚨 A IDEMPOTÊNCIA DO WEBHOOK. Sem este UNIQUE, reentrega do Evolution
    -- duplica a conversa na tela do atendente. Reentrega é conflito
    -- esperado: ignora e responde 200.
    id_externo   text,
    direcao      text NOT NULL CHECK (direcao IN ('entrada','saida','interna')),
    autor        text NOT NULL CHECK (autor IN ('cliente','ia','atendente','sistema')),
    tipo         text NOT NULL CHECK (tipo IN ('texto','imagem','audio','video',
                 'documento','figurinha','localizacao','contato','sistema','nota')),
    conteudo     text,
    midia_id     bigint REFERENCES midia(id),
    citada_id    bigint REFERENCES mensagem(id),
    atendente_id bigint REFERENCES atendente(id),
    entrega      text CHECK (entrega IN ('pendente','enviada','entregue','lida','falhou')),
    criada_em    timestamptz NOT NULL,   -- DO PROVEDOR: é por ela que a tela ordena
    recebida_em  timestamptz NOT NULL DEFAULT now(),  -- nossa; webhook chega fora de ordem

    -- 🚨 Nota interna NUNCA sai. A trava é de código (o envio filtra
    -- direcao='saida'), e esta é a segunda ponta.
    CONSTRAINT ck_nota_e_interna CHECK (
        (tipo = 'nota') = (direcao = 'interna')
    )
);
CREATE UNIQUE INDEX ux_mensagem_id_externo ON mensagem (id_externo)
    WHERE id_externo IS NOT NULL;
CREATE INDEX ix_mensagem_conversa ON mensagem (conversa_id, criada_em);

-- ============================================================ IA E SYNC

CREATE TABLE prompt_versao (
    id        bigserial PRIMARY KEY,
    versao    int NOT NULL UNIQUE,
    conteudo  text NOT NULL,
    autor_id  bigint REFERENCES atendente(id),
    criado_em timestamptz NOT NULL DEFAULT now(),
    ativo     boolean NOT NULL DEFAULT false
);
-- Prompt NÃO é editado por cima: cada alteração é versão nova, e a conversa
-- grava qual a atendeu. É o que responde "por que a IA disse isso" depois.
CREATE UNIQUE INDEX ux_prompt_ativo ON prompt_versao (ativo) WHERE ativo;

ALTER TABLE conversa
    ADD CONSTRAINT fk_conversa_prompt
    FOREIGN KEY (prompt_versao_id) REFERENCES prompt_versao(id);

CREATE TABLE sync_execucao (
    id            bigserial PRIMARY KEY,
    iniciado_em   timestamptz NOT NULL DEFAULT now(),
    terminado_em  timestamptz,
    origem        text NOT NULL CHECK (origem IN ('cron','manual')),
    atendente_id  bigint REFERENCES atendente(id),
    lidos         int NOT NULL DEFAULT 0,
    criados       int NOT NULL DEFAULT 0,
    atualizados   int NOT NULL DEFAULT 0,
    inativados    int NOT NULL DEFAULT 0,
    -- 🚨 `vazio` é coluna própria e NÃO é erro. Não separar ok/vazio/erro
    -- fez um painel acusar 76% de falha num sistema saudável.
    vazios        int NOT NULL DEFAULT 0,
    erros         int NOT NULL DEFAULT 0,
    mensagem_erro text
);
CREATE INDEX ix_sync_iniciado ON sync_execucao (iniciado_em DESC);

-- ============================================================ SEMENTE

INSERT INTO time (nome, descricao) VALUES
  ('Contratual', 'Contratos, aditivos, rescisão, assinatura de documento.'),
  ('Comercial',  'Novas propostas, orçamento, ampliação de frota.'),
  ('Financeiro', 'Boleto, fatura, segunda via, negociação de débito.'),
  ('Suporte',    'Equipamento sem sinal, dúvida de uso da plataforma, falha técnica.'),
  ('Geral',      'Destino quando não se encaixa em nenhum outro, e transbordo padrão.'),
  ('Pós Venda',  'Acompanhamento depois da instalação, satisfação, retenção.'),
  ('agendamento','Agendamento de instalação e manutenção.');

INSERT INTO classificacao (nome, ordem, exige_comentario) VALUES
  ('Dúvida de fatura', 1, false),
  ('Segunda via', 2, false),
  ('Solicitação de instalação', 3, false),
  ('Manutenção', 4, false),
  ('Rastreador sem sinal', 5, false),
  ('Dúvida de uso da plataforma', 6, false),
  ('Comercial', 7, false),
  ('Cancelamento', 8, false),
  ('Outro', 99, true);

INSERT INTO config (chave, valor, descricao) VALUES
  ('repasse_inatividade_min', '30',
   'Minutos sem atividade antes de a conversa voltar para a fila.'),
  ('adiamento_padrao_min', '60',
   'Minutos padrão ao adiar uma conversa.'),
  ('atendimento_inicio', '08:00',
   'Horário oficial de atendimento geral — início.'),
  ('atendimento_fim', '18:00',
   'Horário oficial de atendimento geral — fim.'),
  ('avaliacao_ativa', 'true',
   'Pedir nota de 1 a 5 ao encerrar a conversa.');

INSERT INTO schema_migracao (versao, descricao)
  VALUES ('001', 'Esquema inicial — docs/02_Modelo_Dados.md v2');

COMMIT;
