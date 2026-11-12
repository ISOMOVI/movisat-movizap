-- 105 — a etapa `Serviço Realizado`: a primeira NOSSA que recebe card COM OS
--
-- 🔵 Decisão dele (11/11): *"Criar nova etapa de 'Serviço Realizado'"* ·
-- **nossa, fora do Harmonit** · *"a coluna nova é para evitar reverificação de
-- item esquecido, então moverão para la e depois auditarão o card e por fim,
-- atendimento finalizado"*.
--
-- 🚨 ATÉ AQUI, CARD NOSSO ERA CARD SEM OS. A coluna `Chamados` (092) é de
-- chamados que ainda não viraram OS, e `pipeline_card` só sabia apontar para
-- `solicitacao_id`. A `Serviço Realizado` é o **primeiro caso de card COM OS
-- numa etapa nossa**: a OS fica parada em **1316** no Harmonit enquanto o card
-- está aqui, e só sai de 1316 quando alguém move para `Atendimento finalizado`.
--
-- ⚠️ ISSO É CONSEQUÊNCIA DA DECISÃO DELE, e está dita: enquanto o card estiver
-- nesta etapa, o Harmonit não reflete que a auditoria está em curso. Em troca,
-- a operação ganha o passo de conferir antes de finalizar -- que é exatamente o
-- que ele pediu.

BEGIN;

-- 1. O CARD PASSA A TER DOIS DONOS POSSÍVEIS ------------------------------
--
-- 🚨 Molde EXATO da `os_observacao` (migração 092), que resolveu o mesmo
-- problema: um registro que pertence ou a uma solicitação, ou a uma OS.
ALTER TABLE pipeline_card
  ADD COLUMN IF NOT EXISTS numero_os INTEGER;

COMMENT ON COLUMN pipeline_card.numero_os IS
  'A OS deste card, quando ele e de uma OS. 🚨 Nulo para card de CHAMADO, que '
  'nao tem numero. Sem FK: nao existe tabela de OS nossa -- a OS vive no '
  'Harmonit e o cache e do FPSL, outro banco (mesma razao da os_observacao).';

-- ⚠️ UMA OS NÃO PODE ESTAR EM DUAS ETAPAS NOSSAS AO MESMO TEMPO. Sem isto, um
-- clique duplo no arrasto deixaria o card em duas colunas, e o quadro mostraria
-- a mesma OS duas vezes.
CREATE UNIQUE INDEX IF NOT EXISTS idx_pipeline_card_os_unica
  ON pipeline_card (aba_id, numero_os)
  WHERE numero_os IS NOT NULL AND desfecho IS NULL;

-- 2. ONDE A ETAPA NOSSA SE ENCAIXA ENTRE AS 17 ----------------------------
--
-- 🚨 O PROBLEMA QUE ISTO RESOLVE: as colunas da Operação são as 17 situações do
-- ERP, calculadas no código; as nossas vivem aqui. A `Chamados` ia na frente de
-- todas, e `ordem = 0` bastava. A `Serviço Realizado` tem de entrar **entre a
-- 1316 e a 15694** -- e "entre" não se diz com um número solto.
--
-- ⚠️ Então a etapa nossa diz DEPOIS DE QUEM ela vem. Nulo = na frente de tudo
-- (a `Chamados`). Renumerar as 17 no banco seria copiar para cá uma lista que
-- vive no código e que o ERP manda.
ALTER TABLE pipeline_etapa
  ADD COLUMN IF NOT EXISTS depois_da_situacao INTEGER;

COMMENT ON COLUMN pipeline_etapa.depois_da_situacao IS
  'Para etapa NOSSA dentro da aba da Operacao: a situacao do ERP depois da qual '
  'ela aparece no quadro. NULO = na frente de todas (a coluna Chamados). '
  '⚠️ So faz sentido na PNL_1.1, que mistura as 17 do ERP com as nossas.';

-- 3. A ETAPA ---------------------------------------------------------------
--
-- 🔵 Ela entra depois de **1316 Serviço Agendado** e antes de **15694
-- Atendimento finalizado**, que é a ordem que ele descreveu.
-- ⚠️ `final = false`: a última da Operação continua sendo o fim do fluxo do ERP,
-- não esta.
INSERT INTO pipeline_etapa (aba_id, titulo, ordem, ativo, final,
                            depois_da_situacao)
SELECT a.id, 'Serviço Realizado', 10, true, false, 1316
  FROM painel_aba a
 WHERE a.codigo_tela = 'PNL_1.1'
   AND NOT EXISTS (SELECT 1 FROM pipeline_etapa e
                    WHERE e.aba_id = a.id AND e.titulo = 'Serviço Realizado');

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('105', now(), 'etapa Servico Realizado: card com OS em etapa nossa, e onde a etapa nossa entra entre as 17');

COMMIT;
