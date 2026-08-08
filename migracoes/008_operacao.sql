-- ============================================================================
-- MoviZap — migração 008: o que falta para as telas de operação
--                          (CAD_2.1 Atendentes · CAD_2.2 Times · CFG_4.1)
--
-- ----------------------------------------------------------------------------
-- O QUE JÁ EXISTIA E NÃO SE MEXE
--
-- Conferido no banco em 07/08, antes de escrever esta migração:
--   - `ux_atendente_login`  UNIQUE em lower(login)   -- já existe
--   - `atendente_estado_check`                        -- já existe
--   - `atendente_jornada`   CHECK dia 0..6 e fim > inicio, e ACEITA VÁRIAS
--     LINHAS POR DIA -- é assim que a pausa do almoço é representada:
--     08:00-12:00 e 13:00-18:00 são DUAS linhas, não uma com buraco
--   - `ux_prompt_ativo`     UNIQUE (ativo) WHERE ativo -- uma versão ativa só
--   - `time.nome` e `classificacao.nome` UNIQUE
--
-- Migração que recria o que já está lá é migração que mente sobre o que mudou.
--
-- ----------------------------------------------------------------------------
-- 1. `atendente.perfil` — DE ONDE VEM A PERMISSÃO DE TELA
--
-- Até aqui existia um usuário só, vindo do .env, e ele era o owner. Com a
-- CAD_2.1 nascem contas de verdade, e cada uma precisa dizer o que enxerga.
--
-- Os valores são exatamente as chaves de `telas.PERFIS`. O CHECK está aqui de
-- propósito: perfil digitado errado vira conta que não vê tela nenhuma, e o
-- sintoma ("entrei e não tem nada no menu") não aponta para a causa.
--
-- 🚨 O DEFAULT É O MENOR PRIVILÉGIO. Conta nova nasce 'atendimento', não
-- 'admin' -- a mesma regra do falha-fechado que já vale no auth.py.
--
-- ----------------------------------------------------------------------------
-- 2. `atendente.origem` — A CHAVE ESTÁVEL DA IMPORTAÇÃO
--
-- Os 4 atendentes nascem do Chatwoot. Sem uma chave estável, reimportar
-- duplicaria todo mundo -- foi exatamente o que quase aconteceu no sync do
-- Harmonit quando `contatoPrincipalId` vinha nulo em 8% dos casos.
--
-- Guarda 'chatwoot:1'. O índice é único e PARCIAL: quem for criado na tela
-- fica com origem NULL, e vários NULL não colidem entre si.
-- ============================================================================

BEGIN;

ALTER TABLE atendente
    ADD COLUMN IF NOT EXISTS perfil text NOT NULL DEFAULT 'atendimento',
    ADD COLUMN IF NOT EXISTS origem text;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'atendente_perfil_check') THEN
        ALTER TABLE atendente
            ADD CONSTRAINT atendente_perfil_check
            CHECK (perfil IN ('owner', 'admin', 'atendimento', 'cadastro'));
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS ux_atendente_origem
    ON atendente (origem) WHERE origem IS NOT NULL;

COMMENT ON COLUMN atendente.perfil IS
    'Chave de telas.PERFIS. Nasce no menor privilégio: conta nova vê só '
    'atendimento, nunca admin.';

COMMENT ON COLUMN atendente.origem IS
    'Chave estável de quem veio de fora -- ''chatwoot:1''. NULL = criado na '
    'CAD_2.1. É o que faz a reimportação atualizar em vez de duplicar.';

-- ----------------------------------------------------------------------------
-- 3. `time.ativo` já existe, mas faltava dizer o que a descrição É
--
-- 🚨 A descrição do time É ENTRADA DA IA, não enfeite de tela. É por ela que
-- a IA escolhe o destino da transferência (camada 5 do prompt, CFG_2.1).
-- Time sem descrição = IA chutando para onde mandar o cliente.
COMMENT ON COLUMN time.descricao IS
    'Entrada da IA, não enfeite: é o texto que a camada 5 do prompt usa para '
    'escolher o destino. Time sem descrição faz a IA chutar.';

COMMENT ON COLUMN time.time_transbordo_id IS
    'Para onde a conversa vai quando este time não atende. NULL = fica na '
    'fila do próprio time (o contorno de 06/08, até o usuário decidir).';

INSERT INTO schema_migracao (versao, descricao)
VALUES ('008', 'Perfil e origem do atendente; telas de operação CAD_2.x/CFG_4.1');

COMMIT;
