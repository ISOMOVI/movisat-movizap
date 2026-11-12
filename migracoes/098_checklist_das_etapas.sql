-- 098 — os itens de checklist das etapas que ele escreveu em 11/11
--
-- 🔵 Origem: o bloco dele de 11/11, seção "Checklist do Fluxo". As listas são
-- DELE, literais, e só entram as etapas em que ele escreveu algo.
--
-- 🚨 ESTA MIGRAÇÃO SÓ ACRESCENTA MODELO -- ela não toca em `checklist_item`.
-- ✅ E ISSO BASTA: a cópia do modelo para o card é ADITIVA. O `do_card` procura
-- o que ainda não foi copiado (`NOT EXISTS ... de_modelo_id = m.id`), então o
-- card que já estava aberto na 251 ganha o 'Detalhes dos itens' na próxima vez
-- que alguém o abrir -- sem tocar no que já estava marcado.
-- ⚠️ O que a 090 proíbe é outra coisa: item de modelo DESATIVADO depois não é
-- copiado para card novo, e continua no card de quem já o tinha. Registro não
-- se reescreve; acrescentar não é reescrever.
--
-- ⚠️ As etapas que ele deixou EM BRANCO continuam sem item, e continuam sem
-- botão: 38 (Nova solicitação), 16487 (Pendente Ação Movisat), 15747
-- (Aguardando recebimento), 16489 (Confirmação agendamento), 15694
-- (Atendimento Finalizado), 16491 (Não atendido), 15696 (Aguardando
-- devolução). Para a 15696 e a 677 ele pediu CAMPO DE TEXTO
-- (Devolução / Rastreamento), que é outra frente -- não é item de marcar.
--
-- ⚠️ A etapa "Serviço Realizado" NÃO entra aqui: ele decidiu em 11/11 que ela
-- é etapa NOSSA, fora do Harmonit (`pipeline_etapa`), e não uma situação do
-- ERP -- o nome pertenceu à 15694, que hoje se chama "Atendimento finalizado".

BEGIN;

INSERT INTO checklist_modelo (situacao_id, texto, ordem) VALUES
  -- 251 — Configurar equipamentos e Sistemas (acrescenta ao que já existe)
  (251,   'Detalhes dos itens',                                        4),
  -- 15797 — Rescisão Aguardando Aviso Prévio
  (15797, 'Verificar com o Customer Success, se cliente irá rescindir.', 1),
  -- 890 — Agendar serviço
  (890,   'Agendar com Cliente',                                       1),
  (890,   'Agendar com técnico',                                       2),
  -- 1316 — Serviço Agendado
  (1316,  'Verificar OS do Harmonit',                                  1),
  (1316,  'Verificar OS do Técnico',                                   2),
  (1316,  'Verificar Checklist',                                       3),
  (1316,  'Verificar Central 24hrs',                                   4),
  -- 16490 — Analise de Equipamentos Retornados
  (16490, 'Inserir foto do ID',                                        1)
ON CONFLICT DO NOTHING;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('098', now(), 'itens de checklist das etapas 251, 15797, 890, 1316 e 16490 (pedido de 11/11)');

COMMIT;
