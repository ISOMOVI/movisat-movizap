-- ============================================================================
-- MoviZap — migração 082: a OS do chamado (Bloco A do pipeline da operação)
--
-- 🔵 Duas decisões dele, de 29/10, que juntas obrigam esta tabela:
--   · D4: *"todo chamado de suporte abrirá uma OS"* — automático no envio;
--   · D3: **uma OS por placa**, e não uma por envio (que era a decisão de
--     23/10, e ele mudou).
--
-- 🚨 POR QUE UMA TABELA, E NÃO MAIS UMA COLUNA: `formulario_solicitacao.os_id`
-- é UMA OS, e a partir de D3 um envio com 4 placas abre 4. Enfiar quatro
-- números numa coluna (ou criar `os_id_2`) é o caminho que não tem fim. Aqui
-- cada linha é **um par solicitação ↔ placa**, e a OS é o que ele gerou.
--
-- ⚠️ `placa` É NULA QUANDO O CHAMADO NÃO INFORMOU NENHUMA, e aí a solicitação
-- tem UMA linha, com a placa nula — é o caso "uma OS só" convivendo com o
-- mesmo desenho, sem `if` em quem lê.
--
-- 🚨 A LINHA NASCE ANTES DA OS EXISTIR, com `os_id` nulo e `erro` nulo. É o
-- ponto do plano: *"a falha tem de ser visível: chamado gravado e OS não
-- criada é o pior caso — o cliente recebe 'recebemos' e ninguém abre OS"*.
-- A linha sem `os_id` e com `erro` preenchido é o que o painel conta e diz.
--
-- ⚠️ `formulario_solicitacao.os_id` CONTINUA EXISTINDO e passa a significar
-- **a primeira OS desta solicitação** — não "a OS". Quem precisa de todas lê
-- esta tabela. Não foi removida porque o painel de hoje a lê, e trocar as duas
-- coisas na mesma volta esconderia qual delas quebrou.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS solicitacao_os (
    id             serial PRIMARY KEY,
    solicitacao_id integer NOT NULL
                   REFERENCES formulario_solicitacao(id) ON DELETE CASCADE,
    -- A placa como a pessoa escreveu, já na forma canônica que a validação
    -- devolveu. ⚠️ Nula = o chamado não informou placa (ver o cabeçalho).
    placa          varchar(10),
    criada_em      timestamptz NOT NULL DEFAULT now(),
    -- A OS no Harmonit. Nulos até a escrita voltar.
    os_id          integer,
    numero_ordem   integer,
    -- 🚨 O motivo da falha, por extenso, como o Harmonit (ou a ponte) o disse.
    -- Nulo quando a OS nasceu.
    erro           text,
    -- Quantas vezes se tentou. ⚠️ Serve para NÃO tentar para sempre: chamado
    -- cujo cliente não existe no cadastro falharia em todo ciclo.
    tentativas     integer NOT NULL DEFAULT 0,
    tentada_em     timestamptz
);

COMMENT ON TABLE solicitacao_os IS
    'Uma linha por par solicitacao x placa, e a OS de analise que o par gerou '
    'no Harmonit. 🔵 D3 dele (29/10): uma OS por placa. 🚨 A linha nasce ANTES '
    'da OS: os_id nulo com erro preenchido e o chamado cuja OS nao abriu, e e '
    'isso que o painel tem de dizer em vez de esconder.';

COMMENT ON COLUMN solicitacao_os.placa IS
    'A placa do chamado, na forma canonica. NULA = o chamado nao informou '
    'placa nenhuma, e entao a solicitacao tem UMA linha com placa nula.';

COMMENT ON COLUMN solicitacao_os.erro IS
    'Por que a OS nao nasceu, nas palavras de quem recusou. Nulo quando '
    'nasceu. 🚨 Linha com os_id nulo E erro nulo e uma tentativa que nunca '
    'aconteceu -- nao e sucesso.';

-- 🚨 UMA PLACA, UMA OS, POR SOLICITAÇÃO: sem isto, dois cliques no mesmo
-- envio abrem duas OS para a mesma placa. É a camada 1 da decisão 3.7
-- ("duplicata: aviso, não trava") -- mas aqui, dentro do MESMO envio, é trava:
-- a mesma placa duas vezes no mesmo chamado não é pedido legítimo em dobro.
-- ⚠️ `coalesce` porque em SQL dois nulos não são iguais, e sem ele a
-- solicitação sem placa poderia ganhar duas linhas.
CREATE UNIQUE INDEX IF NOT EXISTS idx_solicitacao_os_unica
    ON solicitacao_os (solicitacao_id, coalesce(placa, ''));

CREATE INDEX IF NOT EXISTS idx_solicitacao_os_numero
    ON solicitacao_os (numero_ordem) WHERE numero_ordem IS NOT NULL;

-- As que falharam, que é o que o painel vai procurar.
CREATE INDEX IF NOT EXISTS idx_solicitacao_os_falha
    ON solicitacao_os (criada_em DESC) WHERE os_id IS NULL;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('082', now(), 'a OS do chamado: uma OS por placa, com o rastro da falha');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA:
--   SELECT count(*) FROM solicitacao_os;
--     -- esperado agora: 0 -- a tabela nasce vazia, e nenhum chamado novo
--     -- entrou desde que ela existe
--
--   SELECT indexname FROM pg_indexes WHERE tablename = 'solicitacao_os';
--     -- esperado: a chave primaria + os 3 indices acima
-- ----------------------------------------------------------------------------
