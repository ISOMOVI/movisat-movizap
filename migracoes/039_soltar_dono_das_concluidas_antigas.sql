-- ============================================================================
-- MoviZap — migração 039: soltar o dono das concluídas anteriores à 029
--
-- 🚨 A REGRA ESTÁ CERTA; O DADO É QUE FICOU PARA TRÁS.
--
-- Ele perguntou em 28/08: *"na aba 'minhas', porque continuam conversas lá que
-- eu encerrei?"*. Medido: as 3 conversas concluídas do painel INTEIRO estão
-- com `atendente_id` preenchido -- 100% delas --, e uma ainda tem participante
-- sem `saiu_em`.
--
-- Não é defeito da conclusão. `encerrar()` solta o dono e faz os convidados
-- saírem desde a 029, que subiu em 25/08 10:27 (commit 89c2381). As três
-- conversas foram concluídas ANTES disso:
--
--     id 12778  17/08 09:13   dono 121 (Iago)
--     id  2157  17/08 09:23   dono 123 (Erika)
--     id 12826  25/08 08:47   dono 121 (Iago)   <- 1h40 antes do deploy
--
-- A 029 criou a coluna e mudou o comportamento, mas não corrigiu as linhas
-- que já existiam. Esta faz isso, e só isso.
--
-- ----------------------------------------------------------------------------
-- 🚨 A ORDEM É A REGRA: GRAVAR QUEM CONCLUIU **ANTES** DE SOLTAR O DONO
--
-- Nestas três, `resolvida_por` é NULL e `atendente_id` é o ÚNICO lugar onde o
-- autor do fechamento existe. Zerar `atendente_id` sem copiar antes apagaria o
-- desfecho para sempre -- é o mesmo cuidado que o `encerrar()` toma ao fazer as
-- duas coisas na MESMA instrução, e pelo mesmo motivo.
--
-- ⚠️ `resolvida_por` só é preenchido onde está NULL: se alguma linha futura já
-- tiver autor gravado, ela não é sobrescrita pelo dono.
-- ============================================================================

BEGIN;

UPDATE conversa
   SET resolvida_por = COALESCE(resolvida_por, atendente_id),
       atendente_id  = NULL
 WHERE estado = 'resolvida'
   AND atendente_id IS NOT NULL;

-- Os convidados que ficaram presos na conversa concluída. `saiu_em` recebe a
-- data da CONCLUSÃO, não `now()`: a pessoa saiu quando o atendimento fechou,
-- e datar com hoje faria o histórico dizer que ela ficou dentro por 11 dias.
UPDATE conversa_participante p
   SET saiu_em = c.resolvida_em
  FROM conversa c
 WHERE c.id = p.conversa_id
   AND c.estado = 'resolvida'
   AND p.saiu_em IS NULL;

-- 🚨 SEM ESTA LINHA A MIGRAÇÃO NEM RODA. O `scripts/aplicar_migracao.py`
-- procura o `INSERT INTO schema_migracao` no próprio arquivo e recusa aplicar
-- quem não registra a própria versão -- "sem isso não dá para saber o que já
-- rodou". A minha primeira versão deste arquivo não tinha, e teria sido
-- rejeitada na hora. Achado na auditoria de backup, não no teste.
INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('039', now(), 'solta o dono das conversas concluidas antes da 029');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA (a prova é RELER O ESTADO, nunca o código de retorno):
--
--   SELECT COUNT(*) FROM conversa
--    WHERE estado='resolvida' AND atendente_id IS NOT NULL;          -- 0
--
--   SELECT COUNT(*) FROM conversa_participante p JOIN conversa c
--     ON c.id=p.conversa_id
--    WHERE c.estado='resolvida' AND p.saiu_em IS NULL;               -- 0
--
--   SELECT id, resolvida_por FROM conversa WHERE estado='resolvida';
--   -- 12778 -> 121, 2157 -> 123, 12826 -> 121 (nenhum NULL)
-- ----------------------------------------------------------------------------
