-- ============================================================================
-- MoviZap — migração 005: tira o painel de demandas daqui
--
-- A 004 pôs o quadro de demandas no banco do MoviZap porque o domínio e o
-- Postgres já existiam. Estava errado: demanda comercial não tem relação
-- nenhuma com o comunicador, e hospedar por conveniência é como um sistema
-- vira depósito.
--
-- Vai para o FPSL, que é o painel de operação. Decisão do usuário em 05/08.
--
-- Sem perda: o quadro estava zerado, nunca recebeu dado real.
-- ============================================================================

BEGIN;

DROP TABLE IF EXISTS demanda_etapa;
DROP TABLE IF EXISTS demanda_item;
DROP TABLE IF EXISTS demanda_frente;
DROP TABLE IF EXISTS demanda_quadro;

INSERT INTO schema_migracao (versao, descricao)
  VALUES ('005', 'Remove o painel de demandas -- foi para o FPSL');

COMMIT;
