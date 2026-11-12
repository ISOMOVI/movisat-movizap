-- 100 — "Solicitação" vira "Nova solicitação" nas abas de Pós-venda
--
-- 🔵 Pedido dele (11/11): *"criar do Contratual e do pós venda, já tem na aba 1
-- 'Solicitação' ajustar par 'Nova solicitação' para padronizar"*.
--
-- O Financeiro (`PNL_1.4`) já nasceu com "Nova solicitação" (096); as duas abas
-- do Pós-venda (094) nasceram com "Solicitação". Esta migração padroniza.
--
-- 🚨 RENOMEAR A ETAPA NÃO REESCREVE O HISTÓRICO, e isso é a 093 funcionando: a
-- `pipeline_passagem` guarda `de_titulo`/`para_titulo` como RETRATO, sem FK.
-- Passagem gravada antes continua dizendo "Solicitação", que é o nome que a
-- coluna tinha quando o card passou por ela. Isso é certo, não defeito.
--
-- ⚠️ O ALVO É NOMEADO PELA ABA, e não um `WHERE titulo = 'Solicitação'` solto:
-- etapa é única DENTRO da aba, e um dia outra aba pode ter uma "Solicitação"
-- que ele não pediu para renomear.

BEGIN;

UPDATE pipeline_etapa e
   SET titulo = 'Nova solicitação'
  FROM painel_aba a
 WHERE a.id = e.aba_id
   AND a.codigo_tela IN ('PNL_1.2', 'PNL_1.3')
   AND e.titulo = 'Solicitação';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('100', now(), 'Solicitacao -> Nova solicitacao nas abas PNL_1.2 e PNL_1.3 (padronizacao)');

COMMIT;
