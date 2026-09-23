-- ============================================================================
-- MoviZap — migração 049: o resumo de transferência que ninguém leu vira nota
--
-- 🔵 Pergunta dele em 23/09: *"Ao transferir ou convidar, o campo 'Resumo'
-- tem uso real? ou apenas front?"*. Medido: era só frente. O texto ia para
-- `transferencia.resumo` e NENHUMA consulta, NENHUMA tela o lia de volta.
--
-- A partir de 23/09 `conversas.transferir` grava, junto com a transferência,
-- uma NOTA INTERNA na conversa. Esta migração faz o mesmo para o que já
-- estava gravado -- com a data da transferência, para a nota aparecer no
-- ponto certo do fio.
--
-- 🚨 SÓ `motivo = 'manual'`. Das 22 linhas com `resumo` preenchido em 23/09,
-- 21 são texto AUTOMÁTICO da saída do dono ("o dono saiu; herdou quem estava
-- há mais tempo", "saiu e não havia quem herdasse") -- não são recado de
-- ninguém para ninguém, e virariam ruído na conversa. Resta 1, escrito por
-- gente: conversa 12853, Claudia para Ludmila, 23/09 11:38.
--
-- ⚠️ O TEXTO É O DE `conversas.texto_da_nota_de_transferencia`. Se um mudar,
-- o outro muda junto.
--
-- ⚠️ IDEMPOTENTE POR CONSTRUÇÃO: o `NOT EXISTS` não duplica a nota se ela já
-- estiver lá -- mas o `schema_migracao` já impede reaplicar.
-- ============================================================================

BEGIN;

INSERT INTO mensagem (conversa_id, direcao, autor, tipo, conteudo,
                      atendente_id, criada_em)
SELECT t.conversa_id, 'interna', 'atendente', 'nota',
       'Transferida para '
         || COALESCE(p.nome, 'o time ' || tm.nome, 'a fila')
         || '. Resumo: ' || btrim(t.resumo),
       t.de_atendente_id, t.em
  FROM transferencia t
  LEFT JOIN atendente p ON p.id = t.para_atendente_id
  LEFT JOIN time tm ON tm.id = t.para_time_id
 WHERE t.motivo = 'manual'
   AND length(btrim(COALESCE(t.resumo, ''))) > 0
   AND NOT EXISTS (
        SELECT 1 FROM mensagem m
         WHERE m.conversa_id = t.conversa_id
           AND m.tipo = 'nota'
           AND m.criada_em = t.em
           AND m.conteudo LIKE 'Transferida para %');

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('049', now(), 'resumo de transferencia manual ja gravado vira nota interna');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA (a prova é RELER O ESTADO):
--
--   SELECT m.conversa_id, m.criada_em, m.conteudo FROM mensagem m
--    WHERE m.tipo = 'nota' AND m.conteudo LIKE 'Transferida para %';
--   -- esperado em 23/09: 1 linha, conversa 12853, 11:38
-- ----------------------------------------------------------------------------
