-- ============================================================================
-- MoviZap — migração 075: a que painel cada formulário pertence
--
-- 🔵 O mapa é decisão dele, escrita no plano (§2.1) e confirmada em 22/10:
--
--     OPERAÇÃO    Suporte · Demonstração · Teste gratuito · Credenciamento
--     PÓS VENDA   NPS · CES
--     CONTRATUAL  Ficha cadastral · Aditivo · Substituição · Rescisão
--     FINANCEIRO  Financeiras · Pagamento de técnicos · Administrativas ·
--                 Fornecedores
--     SEM PAINEL  Contato
--
-- 🚨 `painel` É COLUNA, NÃO LISTA NO CÓDIGO, pelo mesmo motivo que a definição
-- do formulário é dado: o dia em que ele mover "Administrativas" de Financeiro
-- para Contratual não pode exigir deploy. Quem escreve o mapa é o
-- `scripts/carregar_formularios.py` (a tabela `NOSSOS`), e é de lá que ele sai
-- -- UM lugar, para não haver duas verdades.
--
-- ⚠️ NULO É UM VALOR LEGÍTIMO, e tem nome: *"SEM PAINEL — Contato"*. O painel
-- não é obrigatório, e formulário sem painel não é formulário mal cadastrado.
--
-- ⚠️ ESTA MIGRAÇÃO NÃO PREENCHE NADA: acrescenta a coluna e o CHECK. O mapa
-- entra quando a carga rodar, e é por isso que ele pode mudar sem migração
-- nova.
-- ============================================================================

BEGIN;

ALTER TABLE formulario
    ADD COLUMN IF NOT EXISTS painel varchar(20);

-- 🚨 O CHECK aceita NULO de propósito (ver acima). São os quatro painéis que
-- ele nomeou, em snake_case porque o valor vai para a URL da rota
-- (`/api/paineis/<painel>`) e para o `name` da rota do Vue.
ALTER TABLE formulario
    DROP CONSTRAINT IF EXISTS formulario_painel_check;
ALTER TABLE formulario
    ADD CONSTRAINT formulario_painel_check CHECK (
        painel IS NULL OR painel IN
            ('operacao', 'pos_venda', 'contratual', 'financeiro'));

COMMENT ON COLUMN formulario.painel IS
    'Em qual dos quatro paineis as solicitacoes deste formulario aparecem. '
    'NULO = nenhum, e e um valor legitimo: o formulario de Contato fica "sem '
    'painel" por decisao dele (plano, 2.1). 🚨 O mapa vive no '
    'scripts/carregar_formularios.py e e reescrito a cada carga -- mudar de '
    'painel nao exige migracao.';

CREATE INDEX IF NOT EXISTS idx_formulario_painel
    ON formulario (painel) WHERE painel IS NOT NULL;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('075', now(), 'a que painel cada formulario pertence (Operacao, Pos venda, Contratual, Financeiro)');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA (a prova é RELER O ESTADO, nunca o retorno do comando):
--
--   SELECT column_name, data_type, is_nullable
--     FROM information_schema.columns
--    WHERE table_name = 'formulario' AND column_name = 'painel';
--     -- esperado: varchar, anulável
--
--   SELECT painel, count(*) FROM formulario GROUP BY painel ORDER BY 1;
--     -- antes da carga: 15 linhas com painel NULO
--     -- depois: operacao 4 · pos_venda 2 · contratual 4 · financeiro 4 · NULO 1
-- ----------------------------------------------------------------------------
