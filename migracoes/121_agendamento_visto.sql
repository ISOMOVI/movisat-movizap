-- ===========================================================================
-- 121 — "VISTO" por pessoa nos compromissos da ATD_7.1 (26/11)
-- ---------------------------------------------------------------------------
-- 🔵 Pedido dele, ao aprovar o layout de cartões: *"pode ter um flag de
-- 'Visto' para que o usuário saiba o que já viu e o que não, pois podem
-- aparecer agendamentos no dia mesmo"*.
--
-- 🔵 E a escolha do lugar foi dele: **no banco, por card e por pessoa** — e não
-- no `localStorage`, que é por máquina. Quem abre a tela no PC e depois no
-- celular veria tudo como não visto outra vez, e aí o selo mentiria na segunda
-- máquina.
--
-- 🚨 O MOLDE É A `nota_leitura` DA 065, de propósito: PK composta (alvo +
-- pessoa), `visto_em` com `now()` e o índice do caminho inverso. Inventar outra
-- forma para a mesma pergunta — *"o que esta pessoa já viu"* — faria as duas
-- divergirem na primeira mudança.
--
-- 🚨 `NOVO` É A AUSÊNCIA DE LINHA, e não um campo. Compromisso criado antes
-- desta migração nasce "não visto" para todo mundo, que é a verdade: não havia
-- registro. Um `visto boolean` na tabela `agendamento` seria por COMPROMISSO e
-- não por pessoa — o que a Aline viu apagaria o aviso do Thiago.
--
-- ⚠️ `automatico` separa *"eu disse que vi"* de *"abri e o sistema marcou"*.
-- 🔵 Ele pediu os DOIS caminhos: botão no cartão fechado, e a marca automática
-- ao abrir, *"que já confirma e avisa que confirmou também"*. A tela só pode
-- avisar *"marquei porque você abriu"* se o dado souber a diferença.
--
-- ⚠️ `ON DELETE CASCADE` nos dois lados: compromisso apagado não deixa marca
-- órfã, e atendente desligado não segura linha de histórico de leitura.
-- ===========================================================================

CREATE TABLE IF NOT EXISTS agendamento_visto (
  agendamento_id bigint      NOT NULL REFERENCES agendamento(id) ON DELETE CASCADE,
  atendente_id   bigint      NOT NULL REFERENCES atendente(id)   ON DELETE CASCADE,
  visto_em       timestamptz NOT NULL DEFAULT now(),
  automatico     boolean     NOT NULL DEFAULT false,
  PRIMARY KEY (agendamento_id, atendente_id)
);

-- A PK já serve a "quem viu este compromisso". Este índice serve ao caminho que
-- a tela usa de verdade: "o que ESTA pessoa já viu", na semana carregada.
CREATE INDEX IF NOT EXISTS ix_agendamento_visto_atendente
    ON agendamento_visto (atendente_id, visto_em DESC);

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('121', now(), 'visto por pessoa nos compromissos da ATD_7.1');

-- ----------------------------------------------------------------------------
-- DESFAZER, se precisar:
--   DROP TABLE agendamento_visto;     -- 🚨 isto APAGA o que cada um já viu
--   DELETE FROM schema_migracao WHERE versao = '121';
-- ----------------------------------------------------------------------------
