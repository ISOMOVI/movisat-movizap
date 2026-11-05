-- ============================================================================
-- MoviZap — migração 093: a passagem da pipeline é RETRATO, não referência
--
-- 🚨 CONSERTA UM DEFEITO DE DESENHO DA 092, achado pela suíte minutos depois
-- de aplicá-la: `pipeline_passagem.de_etapa` e `para_etapa` referenciavam
-- `pipeline_etapa(id)` **sem `ON DELETE`**. Com isso, apagar uma aba era
-- IMPOSSÍVEL: o CASCADE da aba tentava levar as etapas, e a passagem as
-- segurava --
--     ForeignKeyViolation: update or delete on table "pipeline_etapa" violates
--     foreign key constraint "pipeline_passagem_de_etapa_fkey"
--
-- ⚠️ E o conserto NÃO é pôr CASCADE: isso apagaria o histórico junto, e
-- *"deve ter o log de quem faz o que SEMPRE"* é condição dele.
--
-- 🚨 O PADRÃO CERTO JÁ EXISTE NESTA CASA, e é o do `orcamento_item.servico`:
-- *"continua `text` RETRATO, sem FK: mudar o preço na ficha amanhã não pode
-- reescrever orçamento já emitido"*. O mesmo vale aqui, e vale duas vezes:
--   1. renomear uma etapa não pode reescrever o que a passagem dizia;
--   2. desativar ou apagar uma etapa não pode apagar o histórico.
-- A passagem guarda o ID (para quem quiser cruzar) e o TÍTULO de então.
--
-- ✅ Seguro agora: `pipeline_passagem` tem 0 linhas (a 092 foi aplicada hoje e
-- nenhum card nasceu em produção). Os títulos das linhas existentes são
-- copiados de qualquer modo, para o caso de a ordem de aplicação mudar.
-- ============================================================================

BEGIN;

ALTER TABLE pipeline_passagem
    ADD COLUMN IF NOT EXISTS de_titulo text,
    ADD COLUMN IF NOT EXISTS para_titulo text;

-- Copia o título de agora para as linhas que existirem (0 hoje).
UPDATE pipeline_passagem p
   SET de_titulo = de.titulo
  FROM pipeline_etapa de
 WHERE de.id = p.de_etapa AND p.de_titulo IS NULL;

UPDATE pipeline_passagem p
   SET para_titulo = para.titulo
  FROM pipeline_etapa para
 WHERE para.id = p.para_etapa AND p.para_titulo IS NULL;

-- 🚨 As FKs saem. Os ids FICAM, como inteiros soltos: quem quiser cruzar com a
-- etapa atual ainda pode, e quem só quer ler o histórico lê o título.
ALTER TABLE pipeline_passagem
    DROP CONSTRAINT IF EXISTS pipeline_passagem_de_etapa_fkey,
    DROP CONSTRAINT IF EXISTS pipeline_passagem_para_etapa_fkey;

-- ⚠️ `para_titulo` é obrigatório a partir de agora: passagem sem para onde é
-- linha que não diz nada. `de_titulo` segue anulável -- a primeira passagem
-- não vem de etapa nenhuma.
ALTER TABLE pipeline_passagem
    ALTER COLUMN para_titulo SET NOT NULL;

COMMENT ON COLUMN pipeline_passagem.para_titulo IS
  'O titulo da etapa NO MOMENTO da passagem -- retrato, nao referencia. '
  'Renomear a etapa amanha nao reescreve o historico, e apagar a aba nao o '
  'leva. Mesmo desenho do orcamento_item.servico.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('093', now(),
        'a passagem da pipeline guarda o titulo da etapa como retrato, sem FK');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA
--   SELECT count(*) FROM pg_constraint
--    WHERE conrelid = 'pipeline_passagem'::regclass
--      AND conname LIKE '%etapa_fkey';          -- esperado: 0
--
--   🚨 E a prova que motivou a migração: apagar uma aba de teste funciona.
--     INSERT INTO painel_aba (painel, codigo_tela, titulo)
--          VALUES ('operacao', 'zz-PROVA', 'zz');
--     -- criar etapa, card e passagem, e então:
--     DELETE FROM painel_aba WHERE codigo_tela = 'zz-PROVA';
--     -- esperado: apaga, e o histórico vai com o card (CASCADE por card_id)
-- ----------------------------------------------------------------------------
