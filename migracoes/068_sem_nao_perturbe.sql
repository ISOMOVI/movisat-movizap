-- ============================================================================
-- MoviZap — migração 068: "Não perturbe" sai do produto
--
-- 🔵 Decisão dele, 19/10: *"pode remover esse status então"*. O motivo veio da
-- medição que eu levei junto: "Não perturbe" NÃO PERTURBAVA NADA. Quem barra
-- receber conversa é `presenca.pode_receber`, e lá só `offline` e afastamento
-- barram — então a pessoa marcava "não perturbe", continuava recebendo
-- distribuição e transferência, e o botão não dizia isso. Estado que promete o
-- que não cumpre é defeito, não recurso.
--
-- Sobram TRÊS estados, cada um com um trabalho:
--   · `disponivel`  — atende;
--   · `ausente`     — "em pausa": almoço, reunião, café. Recebe, mas quem
--                     transfere à mão passa a ser avisado (19/10);
--   · `offline`     — "fora do expediente": não recebe. E, desde 19/10, é
--                     IMPOSSÍVEL dentro da jornada cadastrada.
--
-- 🚨 O CHECK NÃO MORA NO `information_schema.columns`, MORA NO
-- `pg_constraint` — foi o tropeço de 22/09 (regra M15), que custou a migração
-- 048: eu conferi as colunas, não vi o CHECK, e escrevi uma migração que o
-- violava. O CHECK vigente é o da 044 (`044_minha_conta.sql:35-37`), que já
-- havia substituído o da 001.
--
-- ⚠️ ZERO LINHAS A CONVERTER, medido antes de escrever: 11 atendentes ativos,
-- 6 em `offline`, 5 em `disponivel`, nenhum em `nao_perturbe` (nem em
-- `ausente`). Mas a migração **não pode depender disso**: se alguém marcar o
-- estado entre a medição e a aplicação, o `ALTER` falharia com a mensagem crua
-- do Postgres. Então o `UPDATE` vem antes, na MESMA transação, convertendo
-- para `ausente` — que é o vizinho semântico ("estou aqui, mas ocupado") — e
-- dizendo em voz alta quantas linhas mudou.
-- ============================================================================

BEGIN;

DO $$
DECLARE n integer;
BEGIN
    UPDATE atendente SET estado = 'ausente', estado_automatico = false,
                         atualizado_em = now()
     WHERE estado = 'nao_perturbe';
    -- ⚠️ `ROW_COUNT`, não um `count(*)` por janela de tempo: contar por
    -- `atualizado_em > now() - 1s` pegaria quem outra coisa acabou de mexer.
    GET DIAGNOSTICS n = ROW_COUNT;
    IF n > 0 THEN
        RAISE NOTICE 'A 068 converteu % atendente(s) de nao_perturbe para ausente.', n;
    END IF;
END $$;

ALTER TABLE atendente DROP CONSTRAINT IF EXISTS atendente_estado_check;
ALTER TABLE atendente ADD CONSTRAINT atendente_estado_check
    CHECK (estado IN ('disponivel', 'ausente', 'offline'));

COMMENT ON COLUMN atendente.estado IS
    'Presenca do atendente: disponivel, ausente ("em pausa") ou offline '
    '("fora do expediente"). O "nao_perturbe" saiu na 068 (19/10/2026), por '
    'decisao dele: nao barrava receber conversa, so a tela dizia que barrava. '
    'Dentro da jornada cadastrada, offline e impossivel -- a regra mora em '
    'presenca.definir_estado_manual e em presenca.aplicar_regra.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('068', now(), 'estado do atendente: sai o nao_perturbe, ficam 3 valores');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA (a prova é RELER O ESTADO, nunca o retorno do comando):
--
--   SELECT pg_get_constraintdef(oid) FROM pg_constraint
--    WHERE conrelid = 'atendente'::regclass AND conname = 'atendente_estado_check';
--     -- esperado: CHECK ((estado = ANY (ARRAY['disponivel','ausente','offline'])))
--
--   SELECT estado, count(*) FROM atendente GROUP BY 1 ORDER BY 2 DESC;
--   SELECT versao FROM schema_migracao WHERE versao = '068';   -- 068
--
-- DESFAZER, se precisar (devolve o CHECK da 044):
--   ALTER TABLE atendente DROP CONSTRAINT atendente_estado_check;
--   ALTER TABLE atendente ADD CONSTRAINT atendente_estado_check
--       CHECK (estado IN ('disponivel', 'ausente', 'nao_perturbe', 'offline'));
--   DELETE FROM schema_migracao WHERE versao = '068';
-- ----------------------------------------------------------------------------
