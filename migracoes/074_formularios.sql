-- ============================================================================
-- MoviZap — migração 074: os formulários próprios, e eles são DADO
--
-- 🔵 Decisão dele, 22/10: *"nenhuma possibilidade irá usar o bitrix, esse
-- projeto é movizap"*. Os 15 formulários de `solicite.movisat.com.br` são
-- Bitrix24 CRM Webforms e hoje concentram toda a entrada de demanda da
-- Movisat. Eles passam a viver aqui, e o Bitrix fica no ar só até ele
-- desligar.
--
-- 🚨 FORMULÁRIO NOVO É LINHA EM TABELA, NÃO ARQUIVO `.vue`. É o mesmo desenho
-- do `movizap/telas.py` -- *"o menu é DESENHADO, não decidido"*: a definição
-- (campos, rótulos, opções, regras) é dado, e UMA tela a desenha. Os 239
-- campos dos 15 não viram 15 telas.
--
-- 🚨 E NÃO SE ESPELHA NADA DO BITRIX: a decisão é que o nosso é a fonte. O
-- `bitrix_id`/`bitrix_sec` ficam aqui só como PROCEDÊNCIA -- de onde a
-- definição foi lida em 22/10 (`dados/formularios_bitrix/mapa_bruto.json`) --,
-- nunca como endereço de escrita. Nada neste projeto manda dado para lá.
--
-- ⚠️ O QUE ESTA MIGRAÇÃO NÃO FAZ: não carrega formulário nenhum. A carga é do
-- `scripts/carregar_formularios.py`, e é separada de propósito -- a tabela
-- vazia é um estado válido, e a carga tem de poder ser repetida.
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- O formulário
-- ----------------------------------------------------------------------------
-- 🚨 `ativo` NASCE FALSO. É a regra da casa para recurso novo, e aqui tem
-- consequência direta: enquanto for falso, o link público responde 404. Quem
-- liga é ele, formulário por formulário, depois de olhar a tela.
CREATE TABLE IF NOT EXISTS formulario (
    id            serial PRIMARY KEY,
    codigo        varchar(20)  NOT NULL UNIQUE,
    slug          varchar(40)  NOT NULL UNIQUE,
    titulo        varchar(120) NOT NULL,
    setor         varchar(40)  NOT NULL DEFAULT '',
    botao         varchar(60)  NOT NULL DEFAULT 'Enviar',
    descricao     text,
    ativo         boolean      NOT NULL DEFAULT false,
    ordem         integer      NOT NULL DEFAULT 100,
    -- A ponte com o Harmonit, para a Etapa 2/3. Nula aqui: 🔴 o mapa
    -- formulário -> problema ainda espera a confirmação dele, e número de
    -- catálogo chutado é pior que nulo.
    gera_os       boolean      NOT NULL DEFAULT false,
    problema_id   integer,
    tipo_os_id    integer,
    prioridade_id integer,
    -- Procedência, não destino.
    bitrix_id     varchar(10),
    bitrix_sec    varchar(20),
    criado_em     timestamptz  NOT NULL DEFAULT now(),
    atualizado_em timestamptz
);

COMMENT ON COLUMN formulario.slug IS
    'O que aparece na URL publica: /f/<slug>. 🚨 Muda-lo quebra todo link ja '
    'distribuido -- e o link do formulario vai por WhatsApp e por e-mail, '
    'onde ninguem o atualiza depois.';
COMMENT ON COLUMN formulario.ativo IS
    'Falso = o link publico responde 404. Nasce falso: carregar a definicao e '
    'publicar o formulario sao dois atos, e so o segundo e dele.';
COMMENT ON COLUMN formulario.bitrix_sec IS
    'O `sec` do webform de origem. PROCEDENCIA: diz de onde a definicao veio '
    'em 22/10. 🚨 Nao e endereco de escrita -- nada daqui envia ao Bitrix.';

-- ----------------------------------------------------------------------------
-- Os campos
-- ----------------------------------------------------------------------------
-- 🚨 `nome` É O NOME DE ORIGEM, E É ILEGÍVEL DE PROPÓSITO:
-- `DEAL_UF_CRM_DEAL_1649449139431` é um campo personalizado do Bitrix, e o
-- número é o timestamp em que alguém o criou. Guardar esse nome é o que
-- permite reler a definição e comparar com o que já foi carregado.
--
-- 🚨 `nosso_nome` É O NOME QUE A CASA VAI USAR -- em relatório, em exportação,
-- na OS. Nasce derivado do rótulo (que já é humano: 'Primeiro Nome',
-- 'Assunto'), e ele revisa depois. É único por formulário: dois campos com o
-- mesmo nome legível tornariam a solicitação ambígua justamente na leitura.
--
-- ⚠️ `tipo` É O VOCABULÁRIO DO BITRIX, não um nosso. São os 15 tipos medidos
-- nos 239 campos, e o CHECK existe para que um tipo desconhecido pare na
-- carga -- não na tela do cliente, que o renderizaria como caixa de texto e
-- ninguém notaria.
CREATE TABLE IF NOT EXISTS formulario_campo (
    id            serial PRIMARY KEY,
    formulario_id integer NOT NULL REFERENCES formulario(id) ON DELETE CASCADE,
    nome          varchar(80) NOT NULL,
    nosso_nome    varchar(80) NOT NULL,
    rotulo        text        NOT NULL DEFAULT '',
    tipo          varchar(20) NOT NULL,
    obrigatorio   boolean     NOT NULL DEFAULT false,
    multiplo      boolean     NOT NULL DEFAULT false,
    visivel       boolean     NOT NULL DEFAULT true,
    ordem         integer     NOT NULL,
    opcoes        jsonb       NOT NULL DEFAULT '[]'::jsonb,
    ajuda         text,
    UNIQUE (formulario_id, nome),
    UNIQUE (formulario_id, nosso_nome),
    CONSTRAINT formulario_campo_tipo_check CHECK (tipo IN (
        'string', 'text', 'list', 'double', 'date', 'file', 'product',
        'phone', 'email', 'name', 'last-name', 'second-name',
        'company-name', 'page', 'layout'))
);

COMMENT ON COLUMN formulario_campo.opcoes IS
    'As opcoes de `list`, como vieram: [{"value":"1756","label":"Pessoa '
    'fisica"}]. 🚨 O `value` e o ID NUMERICO do Bitrix, e e ele que as regras '
    'condicionais comparam -- trocar por texto legivel quebraria as regras.';
COMMENT ON COLUMN formulario_campo.visivel IS
    'Falso = o campo nasce escondido e so aparece por regra. ⚠️ Nao e '
    '"desligado": escondido com regra que o mostra e um campo que existe.';

-- ----------------------------------------------------------------------------
-- As regras condicionais
-- ----------------------------------------------------------------------------
-- 🚨 9 DOS 15 TÊM REGRA (medido em 22/10), e a estrutura é a do Bitrix:
--   {"condition": {"target": <campo>, "event": "change",
--                  "value": "<id da opcao>", "operation": "="},
--    "action":    {"target": <campo>, "type": "show"}}
--
-- 🚨 ELA FICA COMO VEIO, NUMA SÓ FORMA, porque os DOIS lados a avaliam: o
-- servidor (que é a autoridade: decide quem é exigido e descarta o valor de
-- campo escondido) e o navegador (que mostra e esconde enquanto a pessoa
-- preenche). Traduzir para um formato nosso aqui criaria duas verdades -- e
-- 22/10 já ensinou o preço disso num `WHERE` copiado em dois lugares, que
-- divergiu no mesmo dia.
CREATE TABLE IF NOT EXISTS formulario_regra (
    id            serial PRIMARY KEY,
    formulario_id integer NOT NULL REFERENCES formulario(id) ON DELETE CASCADE,
    ordem         integer NOT NULL,
    logica        varchar(3) NOT NULL DEFAULT 'or',
    lista         jsonb      NOT NULL,
    CONSTRAINT formulario_regra_logica_check CHECK (logica IN ('and', 'or'))
);

-- ----------------------------------------------------------------------------
-- A solicitação recebida
-- ----------------------------------------------------------------------------
-- 🚨 OS VALORES FICAM EM UM JSONB, não em uma linha por campo: a definição
-- muda com o tempo (o Bitrix mudou a dele em quatro anos), e solicitação é
-- RETRATO -- tem de continuar legível depois de o campo mudar de rótulo, de
-- obrigatoriedade ou de existir. A chave é o `nome` de origem, que é estável.
--
-- ⚠️ AS COLUNAS DE VÍNCULO NASCEM NULAS E É O ESPERADO: na Etapa 1 o
-- formulário é genérico e anônimo. Elas existem desde já porque a Etapa 2 (o
-- botão "Tarefas", com link travado) grava nelas, e acrescentar coluna depois
-- obrigaria a mexer em quem lê.
CREATE TABLE IF NOT EXISTS formulario_solicitacao (
    id            serial PRIMARY KEY,
    formulario_id integer NOT NULL REFERENCES formulario(id),
    criada_em     timestamptz NOT NULL DEFAULT now(),
    ip            varchar(45),
    valores       jsonb       NOT NULL DEFAULT '{}'::jsonb,
    estado        varchar(20) NOT NULL DEFAULT 'nova',
    lida_por      integer     REFERENCES atendente(id) ON DELETE SET NULL,
    lida_em       timestamptz,
    -- Etapa 2: de onde a solicitação veio, quando vier de uma conversa.
    conversa_id   integer REFERENCES conversa(id) ON DELETE SET NULL,
    contato_id    integer REFERENCES contato(id)  ON DELETE SET NULL,
    cliente_id    integer REFERENCES cliente(id)  ON DELETE SET NULL,
    -- Etapa 3: a OS que esta solicitação gerou no Harmonit.
    os_id         integer,
    numero_ordem  varchar(30),
    CONSTRAINT formulario_solicitacao_estado_check
        CHECK (estado IN ('nova', 'em_andamento', 'concluida'))
);

COMMENT ON COLUMN formulario_solicitacao.valores IS
    'O que a pessoa escreveu, pela chave de ORIGEM do campo. 🚨 Retrato: nao '
    'se reescreve quando a definicao muda. Campo escondido por regra NAO '
    'entra, nem vazio -- some do registro, e e isso que o servidor garante.';
COMMENT ON COLUMN formulario_solicitacao.ip IS
    'IP de quem enviou, para o limite por IP e para investigar abuso. '
    '⚠️ Vem do X-Real-IP e so quando a conexao chega pelo proxy local '
    '(`movizap/ratelimit.py`); atras do nginx, `request.client.host` e '
    'sempre 127.0.0.1.';
COMMENT ON COLUMN formulario_solicitacao.os_id IS
    'A OS do Harmonit que esta solicitacao gerou. Nula na Etapa 1: nenhum '
    'formulario gera OS ainda, e 🔴 qual problema cada um gera ainda espera '
    'decisao dele.';

CREATE INDEX IF NOT EXISTS idx_solicitacao_formulario
    ON formulario_solicitacao (formulario_id, criada_em DESC);
CREATE INDEX IF NOT EXISTS idx_solicitacao_estado
    ON formulario_solicitacao (estado, criada_em DESC);
CREATE INDEX IF NOT EXISTS idx_solicitacao_conversa
    ON formulario_solicitacao (conversa_id) WHERE conversa_id IS NOT NULL;

-- ----------------------------------------------------------------------------
-- Os anexos
-- ----------------------------------------------------------------------------
-- 🚨 O ARQUIVO FICA FORA DO PROJETO, em `/home/claude/movizap_formularios_anexos`,
-- como o anexo de e-mail já faz (`movizap/enviar.py`). Duas razões, e as duas
-- doem: dentro do projeto ele entraria no `git` e no `dist` -- e o `dist` é
-- servido; e aqui o arquivo vem de QUALQUER UM na internet.
--
-- 🚨 `nome_original` É TEXTO PARA LER, NUNCA CAMINHO. O caminho é o `caminho`,
-- montado pelo servidor com um id próprio. Um anexo chamado `../../.env` é um
-- nome de arquivo esquisito, e nada além disso.
CREATE TABLE IF NOT EXISTS formulario_arquivo (
    id             serial PRIMARY KEY,
    solicitacao_id integer NOT NULL
                   REFERENCES formulario_solicitacao(id) ON DELETE CASCADE,
    campo          varchar(80)  NOT NULL,
    nome_original  varchar(255) NOT NULL,
    caminho        text         NOT NULL,
    bytes          bigint       NOT NULL DEFAULT 0,
    mime           varchar(100),
    criado_em      timestamptz  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_formulario_arquivo_solicitacao
    ON formulario_arquivo (solicitacao_id);

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('074', now(), 'formularios proprios: definicao como dado, solicitacoes e anexos');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA (a prova é RELER O ESTADO, nunca o retorno do comando):
--
--   SELECT table_name FROM information_schema.tables
--    WHERE table_name LIKE 'formulario%' ORDER BY table_name;
--     -- esperado: formulario, formulario_arquivo, formulario_campo,
--     --           formulario_regra, formulario_solicitacao
--
--   SELECT count(*) FROM formulario;
--     -- esperado: 0. A migração não carrega nada; a carga é do script.
--
--   SELECT conname FROM pg_constraint
--    WHERE conrelid = 'formulario_campo'::regclass AND contype = 'c';
--     -- esperado: o CHECK dos 15 tipos
-- ----------------------------------------------------------------------------
