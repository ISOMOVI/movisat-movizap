-- ===========================================================================
-- MoviZap — migração 116: a mudança feita no ERP avisa UMA VEZ, não toda noite
-- ===========================================================================
--
-- 🚨 DEFEITO MEU, achado em 18/11 ao conferir o que a rodada seguinte diria.
-- As duas linhas que o ensaio a seco abriu --
--
--     OS 17054  mudou_no_erp  nossa=251    erp=16490  fechada=None
--     OS 17114  mudou_no_erp  nossa=15696  erp=16490  fechada=None
--
-- -- ficam com `fechada_em` nulo para sempre, e `para_a_red_flag` as pega por
-- `veredito = 'mudou_no_erp' AND fechada_em IS NULL`. Ou seja: **as mesmas duas
-- OS sairiam na mensagem TODAS as noites, indefinidamente.**
--
-- ⚠️ Isso quebra exatamente a regra dele que o resto do desenho respeita:
-- *"aviso que aparece todo dia vira aviso que ninguém lê"*. Um vigia que repete
-- o mesmo recado para sempre treina a pessoa a ignorá-lo -- e aí ele deixa de
-- avisar do que importa.
--
-- 🚨 E O PROBLEMA É MAIS FUNDO QUE A COLUNA QUE FALTAVA. `coluna_nossa` é a
-- última passagem que nós confirmamos. Quando alguém move a OS dentro do
-- Harmonit, o card segue o ERP (vem do cache), mas a nossa passagem antiga
-- continua ali, dizendo 251 -- e ela **nunca** vai voltar a bater. A
-- divergência é permanente por construção, então avisar dela sem parar é
-- avisar de um fato que não tem conserto.
--
-- A regra que isto fecha: **mudança feita no ERP é ACEITA, e aceitar é
-- lembrar.** Avisa uma vez, fecha a linha, e só volta a falar se o ERP for
-- para um terceiro valor que também não é nosso.

BEGIN;

ALTER TABLE auditoria_os
    -- ⚠️ Nulo = ainda não foi avisada. Marcada DEPOIS de o envio dar certo:
    -- marcar antes perderia o aviso se o WhatsApp falhasse, e ninguém nota a
    -- ausência de um aviso.
    ADD COLUMN IF NOT EXISTS avisada_em timestamptz;

CREATE INDEX IF NOT EXISTS auditoria_os_a_avisar_idx
    ON auditoria_os (rodada DESC)
 WHERE avisada_em IS NULL;

-- 🚨 Para o auditor reconhecer o que já foi aceito sem varrer a tabela inteira:
-- a pergunta é "esta OS já teve `mudou_no_erp` fechada com ESTA situação do
-- ERP?".
CREATE INDEX IF NOT EXISTS auditoria_os_aceitas_idx
    ON auditoria_os (numero_os, situacao_do_erp)
 WHERE veredito = 'mudou_no_erp';

COMMENT ON COLUMN auditoria_os.avisada_em IS
    'Quando esta linha entrou numa mensagem. NULO = ainda nao avisada. Existe '
    'para a mesma divergencia nao sair em toda rodada do cron -- aviso que '
    'aparece todo dia vira aviso que ninguem le.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('116', now(), 'mudanca feita dentro do Harmonit avisa UMA vez e a linha fecha: aceitar e lembrar, senao as mesmas OS sairiam na red flag todas as noites para sempre');

COMMIT;
