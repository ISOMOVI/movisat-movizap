-- ============================================================================
-- MoviZap — migração 076: a situação da OS, guardada na solicitação
--
-- 🔵 Decisão dele em 22/10: *"vamos de A somente para a Operação por
-- enquanto"* -- a opção A é o kanban cujas colunas são as 11 situações da OS
-- do Harmonit. Para um card ter coluna, a solicitação precisa saber em que
-- situação a OS dela está.
--
-- 🚨 ISTO É CACHE, E O NOME DIZ: a VERDADE da situação é do Harmonit. Aqui
-- fica a última que lemos, com a hora em que lemos. Sem a hora, "situação 38"
-- seria uma afirmação sem prazo -- e a tela diria com confiança algo que
-- pode ter mudado há três dias.
--
-- 🚨 E SÃO TRÊS ESTADOS DISTINGUÍVEIS, não dois:
--   · `os_id` nulo              -> a solicitação ainda não virou OS;
--   · `os_id` com `situacao_id` nulo -> tem OS e NUNCA foi lida;
--   · `situacao_id = 0`         -> tem OS, foi lida, e o Harmonit respondeu
--                                  zero -- que é o que 127 das 574 OS têm
--                                  hoje, medido no cache do FPSL em 22/10.
-- Juntar os três numa coluna "sem situação" esconderia 164 OS reais; é por
-- isso que a coluna existe na tela, mas os três casos continuam separados no
-- banco.
--
-- ⚠️ O CAMPO NÃO É ESCRITO POR NINGUÉM AINDA. A rota que lê e a que escreve
-- `situacaoId` no Harmonit são da Etapa 3, e dependem de duas decisões dele
-- (o mapa formulário -> `problemaId` e a prioridade). A coluna nasce agora
-- porque acrescentá-la depois obrigaria a mexer em quem lê.
-- ============================================================================

BEGIN;

ALTER TABLE formulario_solicitacao
    ADD COLUMN IF NOT EXISTS situacao_id   integer,
    ADD COLUMN IF NOT EXISTS situacao_em   timestamptz,
    ADD COLUMN IF NOT EXISTS situacao_erro text;

COMMENT ON COLUMN formulario_solicitacao.situacao_id IS
    'A ultima situacao da OS que LEMOS no Harmonit -- cache, nao verdade. '
    'Nulo com `os_id` preenchido quer dizer "tem OS e nunca foi lida"; zero '
    'quer dizer "lida, e o Harmonit respondeu 0" (127 das 574 OS estao assim, '
    'medido em 22/10). Os dois casos aparecem na mesma coluna da tela e '
    'continuam separados aqui.';
COMMENT ON COLUMN formulario_solicitacao.situacao_em IS
    'Quando a situacao foi lida. 🚨 Sem isto, a tela afirmaria a situacao sem '
    'prazo -- e o painel existe justamente para a situacao passar a ser usada.';
COMMENT ON COLUMN formulario_solicitacao.situacao_erro IS
    'Por que a leitura ou a escrita da situacao falhou. Nulo com `situacao_em` '
    'nulo = nao tentou; nulo com data = deu certo. Mesma regua do '
    '`agendamento.endereco_os_erro` (migracao 073).';

CREATE INDEX IF NOT EXISTS idx_solicitacao_situacao
    ON formulario_solicitacao (situacao_id)
    WHERE situacao_id IS NOT NULL;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('076', now(), 'situacao da OS guardada na solicitacao (cache, com a hora da leitura)');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA:
--
--   SELECT column_name, is_nullable FROM information_schema.columns
--    WHERE table_name = 'formulario_solicitacao'
--      AND column_name IN ('situacao_id','situacao_em','situacao_erro');
--     -- esperado: as três, todas anuláveis
--
--   SELECT count(*) FROM formulario_solicitacao WHERE situacao_id IS NOT NULL;
--     -- esperado hoje: 0 -- ninguém escreve ainda, e é o esperado
-- ----------------------------------------------------------------------------
