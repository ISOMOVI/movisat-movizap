-- ============================================================================
-- MoviZap — migração 028: grupo fica na MESMA lista, como no WhatsApp
--
-- Desfaz o `atender` que a 027 criou, três horas depois de criá-lo.
--
-- 🚨 O QUE EU ERREI: propus como régua que "o atendente não deve sentir que
-- trocou de aplicativo" e desenhei uma aba "Grupos" que o WhatsApp não tem.
-- O usuário apontou a contradição.
--
-- 🚨 E A ABA RESOLVIA UM PROBLEMA QUE QUASE NÃO EXISTE. O medo era que ligar
-- grupo despejasse de uma vez todo grupo de que o número participa -- medido:
-- **62 grupos**. Mas o painel NÃO IMPORTA GRUPO: `garantir_conversa` só é
-- chamada quando CHEGA MENSAGEM. Grupo parado nunca vira conversa, e a lista
-- ordena por atividade, então grupo quieto afunda sozinho. Só aparece o que
-- está falando -- que é o que o WhatsApp faz.
--
-- ⚠️ O QUE FICA DA 027: `tipo`, `grupo_jid`, `grupo_nome`, o CHECK de
-- identidade, o índice único por `COALESCE` e as colunas de remetente. Essas
-- eram necessárias e continuam. O que sai é só a separação artificial.
--
-- ⚠️ SE UM GRUPO BARULHENTO INCOMODAR, o conserto é silenciar/arquivar -- que
-- é outra coisa, vale para conversa de cliente também, e só se faz quando
-- alguém pedir. Não se deixa coluna morta esperando.
-- ============================================================================

DROP INDEX IF EXISTS ix_conversa_atender;
ALTER TABLE conversa DROP COLUMN atender;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('028', now(), 'grupo volta para a lista unica: sai a coluna atender');
