-- ============================================================================
-- MoviZap — migração 040: preferência por pessoa
--
-- Pedido dele em 28/08: *"crie nas configurações tela de atalhos e interruptor
-- desligado para eles e permita edição por lá também"*.
--
-- 🚨 POR QUE POR PESSOA, E NÃO NA TABELA `config`. A `config` é GLOBAL
-- (chave/valor do sistema): repasse por inatividade, horário de atendimento,
-- avaliação ligada. Atalho de teclado não é regra do sistema, é a MÃO de quem
-- usa -- e ele já fixou isso em 27/08: *"quais teclas é decisão sua -- atalho é
-- regra de uso"*. Guardar em `config` faria a tecla de uma pessoa mudar a de
-- todas, com nove pessoas em teste.
--
-- ⚠️ GENÉRICA DE PROPÓSITO (`chave`/`valor`), não uma coluna `atalhos` no
-- `atendente`. A próxima preferência -- tema, densidade, ordenação padrão --
-- entra sem migração. Coluna por preferência faz a tabela crescer de lado a
-- cada gosto novo.
--
-- 🚨 SEM LINHA = PADRÃO DO CÓDIGO, e o padrão dos atalhos é DESLIGADO. Ele
-- pediu o interruptor desligado, e ausência de linha tem de significar isso:
-- se significasse "ligado", quem nunca abriu a tela teria atalho sem saber --
-- que é exatamente o risco que este pedido veio fechar.
--
-- ⚠️ ON DELETE CASCADE aqui é seguro, ao contrário do resto do painel:
-- preferência não é histórico. Se o atendente sumisse (não some -- é
-- desativado), o gosto dele não faz falta a ninguém.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS preferencia_atendente (
    atendente_id  BIGINT NOT NULL REFERENCES atendente(id) ON DELETE CASCADE,
    chave         TEXT   NOT NULL,
    valor         TEXT   NOT NULL,
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (atendente_id, chave)
);

COMMENT ON TABLE preferencia_atendente IS
    'Gosto de cada pessoa, chave/valor. Ausencia de linha = padrao do codigo. A `config` continua sendo a do SISTEMA.';

COMMENT ON COLUMN preferencia_atendente.chave IS
    'atalhos_ligados (bool) e atalhos_teclas (json) sao as primeiras. Chave nova nao pede migracao.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('040', now(), 'preferencia por pessoa: atalhos de teclado nascem desligados');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA (a prova é RELER O ESTADO):
--
--   SELECT COUNT(*) FROM preferencia_atendente;                 -- 0
--   \d preferencia_atendente
--   SELECT versao FROM schema_migracao WHERE versao = '040';    -- 040
-- ----------------------------------------------------------------------------
