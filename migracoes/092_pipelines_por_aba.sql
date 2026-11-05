-- ============================================================================
-- MoviZap — migração 092: as pipelines por aba, e a observação com dono duplo
--
-- 🔵 Pedido dele em 05/11, em duas partes que são a mesma coisa:
--   1. *"vamos criar uma coluna nova antes de 'Nova solicitação', chamada
--      'Chamados' (…) nessa coluna não são OS ainda, somente o CARD mesmo"*;
--   2. *"a aba 'Operação' do Movizap é a mesma lógica para os demais"* — com as
--      pipelines de Pós-venda, e Contratual/Financeiro depois.
--
-- 🚨 POR QUE AS DUAS SÃO A MESMA COISA, e é o que desenha esta migração: a
-- coluna do painel da Operação é uma SITUAÇÃO DA OS NO HARMONIT, e mover
-- escreve no ERP. Já `Chamados`, `Treinamentos` e `Pós-venda` têm colunas que
-- NÃO existem no Harmonit — são etapas NOSSAS, e mover nelas escreve só aqui.
-- Fazer a coluna Chamados sozinha seria fazer o mesmo motor duas vezes.
--
-- ⚠️ ISTO INVERTE PARCIALMENTE O AVISO DE 22/10 no `movizap/paineis.py`, que
-- diz *"os outros três painéis não são este com outro filtro"*. Na FORMA
-- passam a ser: todos kanban. O que muda é DE QUEM É A COLUNA.
--
-- 🚨 E A COLUNA NOVA NÃO ENTRA NA TUPLA `SITUACOES`. Duas travas dependem de
-- ela ter 17: `tests/teste_rotas_formularios.py` afirma `len(SITUACOES) == 17`,
-- e `checklist._etapa_conhecida` recusa situação fora das 17. A coluna Chamados
-- é prefixada ao quadro com `situacao_id` NULO — outra natureza, não uma 18ª
-- situação do ERP.
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. AS ABAS — e cada uma tem código de tela PRÓPRIO
-- ---------------------------------------------------------------------------
-- 🔵 Ele: *"a Karla terá permissão para ver o 'Financeiro' e todas as abas. A
-- Erika, apenas a aba 3 do financeiro. Todas hoje nascem somente para o
-- owner."*
--
-- 🚨 O `codigo_tela` É O QUE TORNA A PERMISSÃO REAL, e ele tem de ter entrada
-- no `movizap/telas.py` — é a lição dele de 03/11: *"ESTÁ NO AR NÃO É 200"*. A
-- tela da CAR subiu sem registro e ficou INVISÍVEL no menu, sem nem dar 403.
-- Aba sem entrada no catálogo é aba que não existe para quem não digita a URL.
CREATE TABLE IF NOT EXISTS painel_aba (
    id           serial PRIMARY KEY,
    painel       text NOT NULL,
    codigo_tela  text NOT NULL UNIQUE,
    titulo       text NOT NULL,
    ordem        integer NOT NULL DEFAULT 0,
    ativo        boolean NOT NULL DEFAULT true,
    criada_em    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT painel_aba_titulo_nao_vazio CHECK (btrim(titulo) <> ''),
    -- ⚠️ Os quatro painéis são os do `paineis.PAINEIS`, e o CHECK existe para
    -- aba de painel inventado não nascer: a rota recusa painel desconhecido, e
    -- uma linha órfã aqui ficaria invisível e viva.
    CONSTRAINT painel_aba_painel_conhecido CHECK (
        painel IN ('operacao', 'pos_venda', 'contratual', 'financeiro'))
);
CREATE INDEX IF NOT EXISTS idx_painel_aba_painel
    ON painel_aba (painel, ordem);

-- ---------------------------------------------------------------------------
-- 2. AS ETAPAS — as colunas de cada aba, e a ORDEM é a dele
-- ---------------------------------------------------------------------------
-- ⚠️ `final` marca a etapa de onde o card não precisa sair. Não é o mesmo que
-- "arquivado": arquivar é o DESFECHO (abaixo), e um card pode estar numa etapa
-- final sem ter desfecho — esperando alguém decidir.
CREATE TABLE IF NOT EXISTS pipeline_etapa (
    id        serial PRIMARY KEY,
    aba_id    integer NOT NULL REFERENCES painel_aba(id) ON DELETE CASCADE,
    titulo    text NOT NULL,
    ordem     integer NOT NULL DEFAULT 0,
    ativo     boolean NOT NULL DEFAULT true,
    final     boolean NOT NULL DEFAULT false,
    CONSTRAINT pipeline_etapa_titulo_nao_vazio CHECK (btrim(titulo) <> '')
);
CREATE INDEX IF NOT EXISTS idx_pipeline_etapa_aba
    ON pipeline_etapa (aba_id, ordem);

-- ---------------------------------------------------------------------------
-- 3. O CARD — e o DESFECHO, que não é o `estado` da solicitação
-- ---------------------------------------------------------------------------
-- 🔵 Ele: *"ter o botão de 'Finalizar Chamado' e daí vai perguntar 'Resolvido'
-- ou 'Não resolvido' — Resolvido encerra o card e ele esmaece e fica no fim da
-- fila arquivado com status de concluído. Se não resolvido, o mesmo
-- procedimento (…) mas o status de 'Virou OS'."*
--
-- 🚨 O DESFECHO MORA AQUI, E NÃO NO `estado` DA SOLICITAÇÃO, e a razão é
-- medida: `formulario_solicitacao_estado_check` aceita só `nova`,
-- `em_andamento` e `concluida`, e `movizap/formularios.py` conta
-- `estado = 'nova'` em dois lugares. `estado` é CICLO DE VIDA; desfecho é COMO
-- TERMINOU. Alargar o CHECK faria todo código que testa `'concluida'` passar a
-- errar — e são duas perguntas diferentes.
--
-- 🚨 E "Virou OS" SÓ MARCA: decisão dele, *"só marca; a OS é pelo Operação"*.
-- Nada nesta tabela escreve no Harmonit, e é isso que torna o botão reversível.
CREATE TABLE IF NOT EXISTS pipeline_card (
    id              serial PRIMARY KEY,
    aba_id          integer NOT NULL REFERENCES painel_aba(id) ON DELETE CASCADE,
    etapa_id        integer NOT NULL REFERENCES pipeline_etapa(id),
    -- ⚠️ A origem do card fica ABERTA por decisão dele (*"deixe em aberto,
    -- depois veremos"*). Hoje só o chamado tem origem: a solicitação do
    -- formulário de suporte. Os dois campos são anuláveis porque um card
    -- criado à mão não terá solicitação, e um de pesquisa não terá cliente.
    solicitacao_id  integer REFERENCES formulario_solicitacao(id) ON DELETE CASCADE,
    cliente_id      integer,
    criado_em       timestamptz NOT NULL DEFAULT now(),
    criado_por      integer REFERENCES atendente(id) ON DELETE SET NULL,
    desfecho        text,
    desfecho_em     timestamptz,
    desfecho_por    integer REFERENCES atendente(id) ON DELETE SET NULL,
    CONSTRAINT pipeline_card_desfecho_conhecido CHECK (
        desfecho IS NULL OR desfecho IN ('resolvido', 'virou_os')),
    -- ⚠️ Desfecho sem data seria arquivo sem quando. O "por" pode ser nulo (o
    -- atendente pode ser apagado), a data não.
    CONSTRAINT pipeline_card_desfecho_tem_data CHECK (
        (desfecho IS NULL) = (desfecho_em IS NULL))
);
CREATE INDEX IF NOT EXISTS idx_pipeline_card_etapa
    ON pipeline_card (aba_id, etapa_id, criado_em DESC);
-- 🚨 UM card por solicitação, e não mais: o envio do formulário é um chamado,
-- e dois cards para o mesmo chamado seriam duas análises da mesma coisa.
CREATE UNIQUE INDEX IF NOT EXISTS ux_pipeline_card_solicitacao
    ON pipeline_card (solicitacao_id) WHERE solicitacao_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 4. AS PASSAGENS — o log de quem moveu o quê, no molde da `os_passagem`
-- ---------------------------------------------------------------------------
-- 🔵 *"deve ter o log de quem faz o que SEMPRE"*.
-- ⚠️ `de_etapa` é nulo na primeira: o card nasce numa etapa, não vem de outra.
CREATE TABLE IF NOT EXISTS pipeline_passagem (
    id         serial PRIMARY KEY,
    card_id    integer NOT NULL REFERENCES pipeline_card(id) ON DELETE CASCADE,
    de_etapa   integer REFERENCES pipeline_etapa(id),
    para_etapa integer NOT NULL REFERENCES pipeline_etapa(id),
    quem       integer REFERENCES atendente(id) ON DELETE SET NULL,
    em         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_pipeline_passagem_card
    ON pipeline_passagem (card_id, em DESC);

-- ---------------------------------------------------------------------------
-- 5. A OBSERVAÇÃO GANHA DONO DUPLO
-- ---------------------------------------------------------------------------
-- 🚨 O MOLDE É O `midia_tem_um_dono` (migração 047): a observação tem UM dono
-- — uma OS ou um chamado —, nunca nenhum. A diferença é que aqui o CHECK é
-- "pelo menos um", e não ou-exclusivo: um card de chamado que vire OS algum dia
-- pode legitimamente ter os dois.
--
-- ⚠️ POR QUE NÃO UMA TABELA NOVA, como foi com o anexo em 091: ali o banco
-- PROIBIA (a `midia` exige conversa ou sala, e recado não é nenhuma das duas).
-- Aqui não há proibição — `os_observacao.numero_os` é `integer NOT NULL` SEM
-- FK e sem CHECK, e nenhuma view a usa (medido em 05/11, com 2 linhas na
-- tabela). Generalizar custa uma coluna; duplicar custaria um segundo
-- `os_observacao_arquivo` e um quarto desenho de bolha.
--
-- ✅ E O ANEXO VEM DE GRAÇA: `os_observacao_arquivo` é chaveado por
-- `observacao_id`, então o recado de um chamado aceita arquivo sem mais nada.
ALTER TABLE os_observacao
    ADD COLUMN IF NOT EXISTS solicitacao_id integer
        REFERENCES formulario_solicitacao(id) ON DELETE CASCADE;

ALTER TABLE os_observacao ALTER COLUMN numero_os DROP NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'os_observacao_tem_um_dono') THEN
        ALTER TABLE os_observacao
            ADD CONSTRAINT os_observacao_tem_um_dono
            CHECK (numero_os IS NOT NULL OR solicitacao_id IS NOT NULL);
    END IF;
END $$;

-- ⚠️ O `idx_observacao_os` é `(numero_os, em DESC)` e NÃO serve para buscar
-- por solicitação — sem este índice, ler os recados de um chamado varreria a
-- tabela.
CREATE INDEX IF NOT EXISTS idx_observacao_solicitacao
    ON os_observacao (solicitacao_id, em DESC)
 WHERE solicitacao_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 6. A ABA E A ETAPA DA OPERAÇÃO — a coluna `Chamados`
-- ---------------------------------------------------------------------------
-- 🔵 *"vamos criar uma coluna nova antes de 'Nova solicitação', chamada
-- 'Chamados'"*. `ordem = 0` é o que a põe à esquerda das 17.
--
-- ⚠️ A aba da Operação reusa o código `PNL_1.1`, que JÁ EXISTE no `telas.py` e
-- já é a permissão do painel: a coluna Chamados é parte do quadro da Operação,
-- não uma tela nova. As abas de Pós-venda é que ganham código próprio, e isso
-- é seed de outra entrega — depois de ele dizer de onde nascem os cards.
INSERT INTO painel_aba (painel, codigo_tela, titulo, ordem)
     VALUES ('operacao', 'PNL_1.1', 'Operação', 0)
ON CONFLICT (codigo_tela) DO NOTHING;

INSERT INTO pipeline_etapa (aba_id, titulo, ordem, final)
     SELECT a.id, 'Chamados', 0, false
       FROM painel_aba a
      WHERE a.codigo_tela = 'PNL_1.1'
        AND NOT EXISTS (SELECT 1 FROM pipeline_etapa e
                         WHERE e.aba_id = a.id AND e.titulo = 'Chamados');

-- ---------------------------------------------------------------------------
-- 7. O REGISTRO DA PRÓPRIA VERSÃO
-- ---------------------------------------------------------------------------
-- 🚨 O `scripts/aplicar_migracao.py` RECUSA migração que não se registra, e a
-- razão está no próprio script: *"sem isso não dá para saber o que já rodou"*.
-- Ele me recusou na primeira tentativa, e estava certo.
INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('092', now(),
        'pipelines por aba, a coluna Chamados, e a observacao com dono duplo');

COMMIT;

-- ============================================================================
-- CONFERÊNCIA (rodar depois, e o esperado está escrito)
-- ============================================================================
--   SELECT count(*) FROM painel_aba;                      -- esperado: 1
--   SELECT count(*) FROM pipeline_etapa;                  -- esperado: 1
--   SELECT count(*) FROM pipeline_card;                   -- esperado: 0
--   SELECT count(*) FROM os_observacao WHERE numero_os IS NULL;  -- esperado: 0
--
-- 🚨 E a prova que importa: o CHECK recusa observação sem dono nenhum.
--   INSERT INTO os_observacao (texto, em) VALUES ('zz', now());
--   -- esperado: ERRO "os_observacao_tem_um_dono"
-- ============================================================================
