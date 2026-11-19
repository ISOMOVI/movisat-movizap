-- ===========================================================================
-- Migração 112 — o rastro do compromisso NO HARMONIT, por OS
-- 🔵 Demanda dele, 18/11: reagendar e cancelar no Harmonit.
-- ===========================================================================
--
-- 🚨 POR QUE ISTO DEIXOU DE SER CONVENIÊNCIA E VIROU PRÉ-REQUISITO. A medição
-- na Velasco (OS 17105, 18/11) provou três coisas sobre o ERP:
--
--   1. não existe caminho de ALTERAÇÃO de compromisso -- `AgendarTecnico` com
--      o `id` de um compromisso existente recusa (*"Erro ao alterar Evento:
--      TecnicoJaAgendado"*), e mexer em `statusCompromisso` /
--      `motivoCancelamento` recusa igual;
--   2. o único caminho é `DELETE(osId, id, agendaId)`;
--   3. 🚨 e o DELETE leva **o compromisso E a linha do técnico** juntos: a OS
--      ficou com zero linhas.
--
-- Logo, cancelar é apagar a linha do técnico. 🔵 E a regra dele: *"apaga, só
-- se a linha for nossa"* -- porque quando reusamos a linha de um técnico que
-- já estava na OS (🔵 *"usa a linha existente"*), apagá-la levaria o vínculo e
-- o compromisso de outra pessoa. Sem guardar QUEM CRIOU A LINHA, não há como
-- saber se apagar é seguro, e aí cancelar não pode existir.
--
-- 🚨 E POR QUE EM `agendamento_os`, NÃO EM `agendamento`: um compromisso do
-- MoviZap pode cobrir VÁRIAS OS, e do lado do Harmonit **cada OS tem a sua
-- linha e o seu compromisso** -- não existe "agendar as três de uma vez". O
-- `agendamento.harmonit_agendamento_id` (migração 070) guarda só o PRIMEIRO id
-- que voltou, o que serve para o selo da tela e não serve para apagar: apagar
-- com o id da OS errada arrancaria a linha errada.
--
-- ⚠️ A coluna de 070 FICA onde está. Ela não mente -- ela responde outra
-- pergunta ("foi para o Harmonit?") e é o que o selo já no ar lê.

BEGIN;

ALTER TABLE agendamento_os
    -- O compromisso daquela OS (`agendamentoId` do Harmonit).
    ADD COLUMN IF NOT EXISTS harmonit_agendamento_id bigint,
    -- A linha do técnico daquela OS (`ordemServicoxTecnicoId`).
    ADD COLUMN IF NOT EXISTS harmonit_vinculo_id bigint,
    -- 🚨 NULO É "NÃO SEI", e não é o mesmo que `false`. As linhas que já
    -- existem nasceram antes deste rastro: para elas não sabemos quem criou o
    -- vínculo, e `pode_apagar` trata nulo como "não apaga" -- igual a `false`
    -- na prática, mas a tela pode dizer a verdade ("não sei de quem é esta
    -- linha") em vez de afirmar que é de outro.
    ADD COLUMN IF NOT EXISTS vinculo_criado boolean,
    -- Quando o rastro foi colhido. ⚠️ Serve para a auditoria saber a idade do
    -- dado, do mesmo jeito que `atualizado_em` serve no cache de OS do FPSL.
    ADD COLUMN IF NOT EXISTS harmonit_em timestamptz;

-- Cancelar e reagendar entram pelo par (agendamento, OS); o índice de
-- `numero_os` já existe desde 069 e cobre a busca pelo outro lado.
COMMENT ON COLUMN agendamento_os.vinculo_criado IS
    'true = a linha do tecnico nesta OS foi criada por nos e pode ser apagada; '
    'false = e de um tecnico que ja estava na OS; NULL = rastro anterior a '
    'migracao 112, nao se sabe -- e nao se apaga.';
COMMENT ON COLUMN agendamento_os.harmonit_vinculo_id IS
    'O ordemServicoxTecnicoId daquela OS. Sem ele o DELETE do Harmonit nao tem '
    'o que apontar, e apontar a linha errada apagaria o vinculo de outra pessoa.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('112', now(), 'o rastro do compromisso no Harmonit passa a ser por OS (vinculo, compromisso e quem criou a linha), para cancelar e reagendar poderem existir');

COMMIT;
