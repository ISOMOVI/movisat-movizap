-- ===========================================================================
-- 064 — EVENTO na conversa: o log de ações como nota interna (Bloco 11, 15/10)
-- ---------------------------------------------------------------------------
-- 🔵 Pedido dele: *"ao final proponha log dentro da conversa interno apenas
-- sobre ações de transfernecia, inserir pessoas, etc, pode ser em Nota interna
-- do Movizap"*, aprovado em 15/10 ("o 3 pode seguir").
--
-- 🚨 POR QUE UMA COLUNA, E NÃO UM `tipo` NOVO. O CHECK `ck_nota_e_interna`
-- amarra `tipo = 'nota'` a `direcao = 'interna'` nos DOIS sentidos: um
-- `tipo = 'sistema'` interna seria recusado pelo banco, e afrouxar esse CHECK
-- abriria a porta para uma nota vazar como mensagem de saída -- que é
-- exatamente o que ele impede desde a 001. Então o evento É uma nota interna,
-- com uma marca a mais.
--
-- 🚨 EVENTO NÃO SE EDITA NEM SE APAGA. Log que se reescreve não é log. O banco
-- não tem como impedir um UPDATE vindo do código, mas o caminho de editar e
-- apagar nota (`conversas.editar_nota` / `apagar_nota`) passa a recusar
-- `evento IS NOT NULL`, e é por isso que esta coluna existe aqui em vez de
-- viver num texto convencionado dentro do `conteudo`.
--
-- ⚠️ NADA RETROATIVO, e isto é decisão declarada: transferência, encerramento
-- e convite dariam para reconstituir por `transferencia`/`conversa`, mas
-- vínculo e tipo NÃO TÊM HISTÓRICO -- e um log pela metade, com data inventada
-- para o que falta, é pior do que um log que começa hoje e diz desde quando.
--
-- ⚠️ Evento NÃO conta como não lida: só `direcao = 'entrada'` conta, e isso
-- não muda aqui. Nota nunca contou.
-- ===========================================================================

ALTER TABLE mensagem ADD COLUMN IF NOT EXISTS evento text;

-- A lista fechada das ações registradas. Valor novo exige migração -- é o que
-- impede o log de ganhar um verbo solto, escrito de duas formas diferentes em
-- dois lugares do código.
ALTER TABLE mensagem DROP CONSTRAINT IF EXISTS ck_evento_conhecido;
ALTER TABLE mensagem ADD CONSTRAINT ck_evento_conhecido CHECK (
  evento IS NULL OR evento IN (
    'assumiu',        -- assumiu a conversa (inclui reabrir e assumir)
    'entrou',         -- entrou numa conversa de outra pessoa
    'convidou',       -- chamou alguém para acompanhar
    'saiu',           -- saiu por conta própria
    'removeu',        -- tirou alguém de dentro
    'devolveu',       -- devolveu à fila (a conversa fica sem dono)
    'transferiu',     -- passou para pessoa ou time
    'encerrou',       -- encerrou o atendimento
    'vinculou',       -- ligou o número a um cadastro
    'desvinculou',    -- desfez o vínculo
    'mudou_tipo',     -- mudou o que a pessoa é (CFG_5.1)
    'bloqueou',
    'desbloqueou'
  )
);

-- 🚨 EVENTO SÓ EXISTE EM NOTA INTERNA. Sem esta trava, um evento poderia ser
-- gravado numa mensagem de saída e ir para o cliente: o log interno da equipe
-- no WhatsApp de quem está do outro lado.
ALTER TABLE mensagem DROP CONSTRAINT IF EXISTS ck_evento_e_nota_interna;
ALTER TABLE mensagem ADD CONSTRAINT ck_evento_e_nota_interna CHECK (
  evento IS NULL OR (tipo = 'nota' AND direcao = 'interna')
);

-- A conversa inteira já é lida por `conversa_id, id`; este índice serve a
-- quem quiser SÓ o log de uma conversa, que é o uso que vem depois (auditoria
-- de "o que aconteceu com este atendimento").
CREATE INDEX IF NOT EXISTS ix_mensagem_evento
    ON mensagem (conversa_id, id) WHERE evento IS NOT NULL;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('064', now(), 'evento na conversa: log de ações como nota interna (Bloco 11)');

-- ----------------------------------------------------------------------------
-- DESFAZER, se precisar:
--   ALTER TABLE mensagem DROP CONSTRAINT ck_evento_e_nota_interna;
--   ALTER TABLE mensagem DROP CONSTRAINT ck_evento_conhecido;
--   DROP INDEX ix_mensagem_evento;
--   ALTER TABLE mensagem DROP COLUMN evento;   -- 🚨 isto APAGA o log
--   DELETE FROM schema_migracao WHERE versao = '064';
-- ----------------------------------------------------------------------------
