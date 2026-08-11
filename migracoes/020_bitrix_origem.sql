-- ============================================================================
-- MoviZap — migração 020: o cadastro passa a saber dizer "isto veio do Bitrix"
--
-- É o que falta para o passo 3 do docs/11 (promover ao cadastro o que casar por
-- documento). Sem ela, promover exigiria gravar `origem = 'movizap'` -- e em
-- três meses ninguém saberia distinguir o que uma pessoa digitou na tela do que
-- um script importou de um sistema que já estava saindo.
--
-- ----------------------------------------------------------------------------
-- 🚨 POR QUE O TELEFONE DO BITRIX NÃO PODE IR PARA UM CONTATO DO HARMONIT
--
-- Seria mais curto pendurar o número no contato que o cliente já tem. Faz duas
-- coisas erradas de uma vez:
--
--   1. ATRIBUIÇÃO FALSA — o número é de uma PESSOA (a que está no Bitrix), e
--      pendurá-lo no contato do Harmonit afirma que é de OUTRA pessoa. É o
--      mesmo erro da régua: coincidência tratada como prova;
--
--   2. O SYNC APAGA — `_remover_em_revisao` faz DELETE filtrando
--      `c.origem = 'harmonit'`. Um número do Bitrix pendurado ali seria apagado
--      na primeira vez que caísse na lista de compartilhados, **sem WhatsApp
--      verificado para protegê-lo** -- some em silêncio, e a próxima
--      importação o traz de volta. Ficaria oscilando a cada 12h sem ninguém ver.
--
-- Com `origem = 'bitrix'`, o contato fica FORA do alcance do sync do Harmonit,
-- que é exatamente a proteção que o `origem = 'harmonit'` já dá ao cadastro
-- feito no painel.
--
-- ----------------------------------------------------------------------------
-- ⚠️ `bitrix_id` É O QUE TORNA A PROMOÇÃO REPETÍVEL
--
-- Sem uma chave estável, rodar o cruzamento duas vezes criaria o mesmo contato
-- duas vezes -- e a segunda execução nem saberia disso, porque nome não é
-- chave. É a mesma função do `harmonit_id`, para a outra origem.
-- ============================================================================

ALTER TABLE contato DROP CONSTRAINT IF EXISTS contato_origem_check;
ALTER TABLE contato ADD CONSTRAINT contato_origem_check
    CHECK (origem IN ('harmonit', 'movizap', 'bitrix'));

ALTER TABLE contato DROP CONSTRAINT IF EXISTS contato_email_origem_check;
ALTER TABLE contato ADD CONSTRAINT contato_email_origem_check
    CHECK (email_origem IS NULL
           OR email_origem IN ('harmonit', 'atendimento', 'bitrix'));

ALTER TABLE contato ADD COLUMN IF NOT EXISTS bitrix_id text;

-- Índice único PARCIAL: 945 contatos existentes têm bitrix_id nulo, e NULL não
-- colide em índice único -- mas o parcial deixa a intenção explícita e não
-- carrega as linhas que nunca serão consultadas por aqui.
CREATE UNIQUE INDEX IF NOT EXISTS ux_contato_bitrix
    ON contato (bitrix_id) WHERE bitrix_id IS NOT NULL;

ALTER TABLE contato_telefone DROP CONSTRAINT IF EXISTS contato_telefone_origem_campo_check;
ALTER TABLE contato_telefone ADD CONSTRAINT contato_telefone_origem_campo_check
    CHECK (origem_campo IN ('telefone', 'telefone2', 'celular', 'whatsapp',
                            'manual', 'atendimento', 'bitrix'));

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('020', now(), 'origem bitrix no cadastro + bitrix_id do contato');
