-- ============================================================================
-- MoviZap — migração 071: o contato técnico ganha vínculo com o Harmonit
--
-- 🔵 Pedido dele, 21/10: *"podemos pensar em um vínculo de dados técnicos
-- dentro do cadastro do tipo 'técnico', assim já traz sugerido pelo número
-- dele... para técnicos novos ou ainda sem o tipo 'técnico' no nome, é
-- possível já vincular para o agendamento e varredura de dados"*.
--
-- 🚨 A CHAVE É O TELEFONE, PORQUE O E-MAIL DO TÉCNICO NO HARMONIT É O
-- TELEFONE DELE. Medido em 21/10: `Franck` → `997394026@movisat.com.br`, e o
-- contato no MoviZap é `+5519997394026`. Vale em **186 dos 200** cadastros; os
-- 14 que fogem são contas internas (`comercial@`, `parceiros@`, pessoas da
-- casa), e é bom que não casem: senão todo usuário interno viraria técnico.
--
-- 🔵 Decisão dele: a chave tenta **9 dígitos e depois 8** (número antigo, sem
-- o nono -- ganha 7 vínculos), e **só vincula quando o candidato for único**.
--
-- ⚠️ MESMO DESENHO DO `cliente.harmonit_id`, que já é o precedente da casa:
-- colunas no próprio cadastro, e não tabela de ligação. O nome vem junto como
-- RETRATO, para a ficha não depender do FPSL estar no ar.
--
-- 🚨 O `relacao` DO CONTATO NÃO É TOCADO AQUI NEM PELA VARREDURA. Trocar para
-- `tecnico` esconde empresas na ficha e muda regra de negócio -- isso continua
-- sendo clique de gente.
-- ============================================================================

BEGIN;

ALTER TABLE contato
    -- O `tecnico_id` do Harmonit (tabela `tecnicos` do FPSL, sincronizada
    -- 1x/dia por `sync_tecnicos`).
    ADD COLUMN harmonit_tecnico_id   bigint,
    -- Retrato do nome do CADASTRO, que é o que o orçamento imprime -- 🔵
    -- *"mesmo que nomeiem errado, ele vai trazer no orçamento o nome do
    -- cadastro harmonit"*.
    ADD COLUMN harmonit_tecnico_nome text,
    -- `automatico` se refaz todo dia; `manual` a varredura NUNCA toca.
    ADD COLUMN harmonit_vinculo_origem text
        CHECK (harmonit_vinculo_origem IN ('automatico', 'manual')),
    ADD COLUMN harmonit_vinculo_em   timestamptz;

CREATE INDEX contato_harmonit_tecnico_idx
    ON contato (harmonit_tecnico_id)
 WHERE harmonit_tecnico_id IS NOT NULL;

COMMENT ON COLUMN contato.harmonit_vinculo_origem IS
    'automatico = a varredura diaria refaz; manual = pessoa vinculou e a '
    'varredura nao encosta. 🔵 A excecao do numero dele (6168 -> Iago) e '
    'manual de proposito: `iago@movisat.com.br` nao e numerico e esta marcado '
    'como usuario do sistema, entao nenhuma regra automatica o alcanca.';

-- 🚨 O INTERRUPTOR MORA NO `config` (regra dele, CFG_7.1 Geral).
-- 🔵 NASCE LIGADO por decisao dele em 21/10 -- excecao consciente a regua da
-- casa ("recurso novo nasce desligado"), e a razao esta escrita: a varredura
-- so GRAVA o que a trava do agendamento ja calcula ao vivo a cada chamada, e
-- vinculo errado aparece na ficha e se corrige a mao.
INSERT INTO config (chave, valor, descricao, atualizado_em)
VALUES (
    'tecnico_vinculo_ligado', 'true',
    'Varredura diaria que liga o contato tipo tecnico ao cadastro do Harmonit '
    'pelo telefone (9 digitos, depois 8; so vincula com candidato unico). '
    '🚨 Nunca sobrescreve vinculo manual e nunca muda o tipo do contato.',
    now()
)
ON CONFLICT (chave) DO NOTHING;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('071', now(), 'contato: vinculo com o cadastro de tecnicos do Harmonit');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA (a prova é RELER O ESTADO, nunca o retorno do comando):
--
--   SELECT column_name FROM information_schema.columns
--    WHERE table_name = 'contato' AND column_name LIKE 'harmonit_%';
--     -- esperado: harmonit_id (já existia), harmonit_tecnico_id,
--     --           harmonit_tecnico_nome, harmonit_vinculo_origem,
--     --           harmonit_vinculo_em
--
--   SELECT pg_get_constraintdef(oid) FROM pg_constraint
--    WHERE conrelid = 'contato'::regclass
--      AND pg_get_constraintdef(oid) LIKE '%vinculo_origem%';
--
--   SELECT valor FROM config WHERE chave = 'tecnico_vinculo_ligado';  -- true
--   SELECT versao FROM schema_migracao WHERE versao = '071';          -- 071
--
--   Depois da primeira varredura, o esperado medido em 21/10:
--   SELECT count(*) FROM contato WHERE harmonit_tecnico_id IS NOT NULL;
--     -- ~186 (179 pelos 9 dígitos + 7 pelos 8)
--
-- DESFAZER, se precisar:
--   ALTER TABLE contato DROP COLUMN harmonit_tecnico_id,
--                       DROP COLUMN harmonit_tecnico_nome,
--                       DROP COLUMN harmonit_vinculo_origem,
--                       DROP COLUMN harmonit_vinculo_em;
--   DELETE FROM config WHERE chave = 'tecnico_vinculo_ligado';
--   DELETE FROM schema_migracao WHERE versao = '071';
-- ----------------------------------------------------------------------------
