-- ============================================================================
-- MoviZap — migração 088: a marca "Preenche OS" na ficha do técnico
--
-- 🔵 Pedido dele em 04/11, no fechamento da tela: *"apenas mais um ajuste na
-- ficha do tecnico, crie um campo de flag, junto com os do deslocamento chamado
-- 'Preenche OS'"*.
--
-- ⚠️ ELA MORA NO BLOCO DO DESLOCAMENTO PORQUE ELE PEDIU ALI, e não porque
-- "preencher OS" seja deslocamento. Está anotado aqui para que ninguém a
-- "arrume" de lugar mais tarde achando que foi descuido: é onde ele quer ver,
-- junto das outras perguntas de sim/não que se responde sobre o prestador.
--
-- 🚨 TRÊS ESTADOS, COMO AS OUTRAS TRÊS DO BLOCO: sim, não e **não respondido**.
-- `boolean` anulável, sem DEFAULT. Nascer `false` diria, das 303 fichas, que
-- nenhum técnico preenche OS -- uma afirmação que ninguém fez. É a mesma régua
-- do `ponto_fixo`, do `vai_ao_cliente` e do `cobra_deslocamento`, e a mesma
-- lição do `0` ≠ `NULL` da situação da OS (migração 076).
--
-- ⚠️ ESTA MARCA NÃO LIGA NEM DESLIGA NADA HOJE. É registro de cadastro: a tela
-- grava e mostra. Fazer a criação de OS depender dela seria regra nova sobre o
-- fluxo do Harmonit, e regra é decisão dele -- quando quiser, ela já está
-- gravada e medível.
-- ============================================================================

BEGIN;

ALTER TABLE tecnico_ficha
  ADD COLUMN IF NOT EXISTS preenche_os boolean;

COMMENT ON COLUMN tecnico_ficha.preenche_os IS
  'Se este técnico preenche a OS. Três estados: sim, não e NULL (não '
  'respondido). Registro de cadastro -- não condiciona nenhum fluxo hoje.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('088', now(), 'ficha do tecnico: a marca Preenche OS, junto das perguntas do deslocamento');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA:
--
--   SELECT column_name, is_nullable, column_default
--     FROM information_schema.columns
--    WHERE table_name = 'tecnico_ficha' AND column_name = 'preenche_os';
--     -- esperado: boolean, YES, sem default
--
--   SELECT count(*) FROM tecnico_ficha WHERE preenche_os IS NOT NULL;
--     -- esperado hoje: 0 -- ninguém respondeu ainda
--
-- DESFAZER:
--
--   BEGIN;
--   ALTER TABLE tecnico_ficha DROP COLUMN IF EXISTS preenche_os;
--   DELETE FROM schema_migracao WHERE versao = '088';
--   COMMIT;
-- ----------------------------------------------------------------------------
