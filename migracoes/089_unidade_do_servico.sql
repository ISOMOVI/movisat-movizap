-- ============================================================================
-- MoviZap — migração 089: a unidade de cada serviço do técnico
--
-- 🔵 Pedido dele em 04/11: ligar a tabela de preço da ficha ao orçamento, com a
-- premissa que destravou tudo — *"o orçamento não vai ao cliente, somente ao
-- técnico."* Se o papel é o acerto do que será pago a ele, o custo cadastrado
-- pode preencher a linha direto.
--
-- 🚨 POR QUE UMA COLUNA DE UNIDADE, E NÃO "assume `un` no código": o botão da
-- calculadora de KM no modal aparece por **`l.unidade === 'km'`**, não pelo nome
-- do serviço -- e isso está escrito no `ModalAgendar.vue` de propósito, *"para
-- um serviço novo por km ganhar a calculadora sozinho"*. Assumir `un` no código
-- faria essa regra passar a depender de nome, que é exatamente o que ela evita.
--
-- ⚠️ E O BANCO JÁ TEM A MESMA RÉGUA DO OUTRO LADO: `orcamento_item.unidade` tem
-- `CHECK (unidade IN ('un','km'))` desde a 069, espelhando `UNIDADES` em
-- `movizap/orcamento.py`. Esta coluna nasce com o MESMO par de valores -- duas
-- listas de unidade que não batem seriam uma delas recusando no `INSERT` o que a
-- outra ofereceu na tela.
--
-- 🚨 OS DEZ NASCEM `un`, e isso é afirmação, não acomodação: Instalação,
-- Retirada, Manutenção, Substituição, Socorro, Laudo, Treinamento e
-- Acompanhamento são todos cobrados por unidade de serviço. Deslocamento é o que
-- se cobra por km, e ele **não é um dos dez** -- vive em
-- `tecnico_ficha.km_valor_centavos` e na linha `KM DESLOCAMENTO` do catálogo
-- fixo do orçamento.
--
-- ⚠️ `NOT NULL DEFAULT 'un'` para não haver serviço sem unidade: o `<select>` do
-- orçamento lê este campo para decidir a unidade da linha, e `NULL` ali faria a
-- linha nascer sem unidade e o `INSERT` do item recusar no fim, longe da causa.
-- ============================================================================

BEGIN;

ALTER TABLE servico_tecnico
  ADD COLUMN IF NOT EXISTS unidade varchar(4) NOT NULL DEFAULT 'un'
      CHECK (unidade IN ('un', 'km'));

COMMENT ON COLUMN servico_tecnico.unidade IS
  'Como este serviço é cobrado: un ou km. Mesmo par de valores do CHECK de '
  'orcamento_item.unidade (069). É esta coluna que faz o botão da calculadora '
  'de KM aparecer na linha do orçamento -- o modal decide pela UNIDADE, nunca '
  'pelo nome do serviço.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('089', now(), 'unidade de cada servico do tecnico (un/km), para a linha do orcamento');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA:
--
--   SELECT nome, unidade FROM servico_tecnico ORDER BY ordem;
--     -- esperado: os 10, todos 'un'
--
--   SELECT column_name, is_nullable, column_default
--     FROM information_schema.columns
--    WHERE table_name = 'servico_tecnico' AND column_name = 'unidade';
--     -- esperado: character varying, NO, 'un'::character varying
--
--   SELECT count(*) FROM servico_tecnico WHERE unidade NOT IN ('un','km');
--     -- esperado: 0 (e o CHECK garante que continue)
--
-- DESFAZER:
--
--   BEGIN;
--   ALTER TABLE servico_tecnico DROP COLUMN IF EXISTS unidade;
--   DELETE FROM schema_migracao WHERE versao = '089';
--   COMMIT;
--     -- ⚠️ Quem lê esta coluna é `tecnico_ficha.precos_para_orcamento()`, que
--     --    alimenta o catálogo do orçamento: derrubá-la sem derrubar o código
--     --    deixa o modal sem unidade nas linhas da ficha.
-- ----------------------------------------------------------------------------
