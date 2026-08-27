-- ============================================================================
-- MoviZap — migração 037: menção no chat interno
--
-- Pedido do usuário em 27/08: *"interessante e pode ser, tanto no interno
-- quanto no do whatsa"*.
--
-- ----------------------------------------------------------------------------
-- POR QUE TABELA, E NÃO UMA COLUNA COM A LISTA
--
-- 🚨 É A LIÇÃO DA 036, APLICADA ANTES DE DOER. Lá a reação nasceu como coluna
-- (034), com a razão escrita, e a razão caiu quando o cliente entrou: numa
-- conversa com várias pessoas, uma coluna guarda a última e **apaga as outras
-- em silêncio**. Menção tem a mesma forma: uma mensagem pode chamar três
-- pessoas, e um grupo do chat interno tem até cinco.
--
-- Uma linha por (mensagem, quem foi chamado). `ON DELETE CASCADE` nas duas
-- pontas: menção sem mensagem não significa nada, e atendente removido não
-- pode deixar linha órfã apontando para ninguém.
--
-- ----------------------------------------------------------------------------
-- POR QUE A MENÇÃO NÃO É ADIVINHADA DO TEXTO
--
-- 🚨 QUEM RESOLVE O `@` É QUEM ESCREVE, NA HORA DE ESCOLHER -- não um regex
-- lendo o texto depois. Regex teria de adivinhar onde o nome termina
-- ("@Suporte Erika" tem espaço no meio), casar apelido e desempatar homônimo,
-- e erraria em silêncio nos três casos. O compositor manda os IDS escolhidos;
-- o backend só CONFERE que cada um é membro da sala.
--
-- ⚠️ O texto continua sendo o que a pessoa escreveu, sem marcação embutida.
-- Guardar `@[12:Erika]` no texto tornaria o histórico ilegível fora da tela --
-- e o texto do chat é lido em relatório, em log e em busca.
-- ============================================================================

CREATE TABLE IF NOT EXISTS chat_mencao (
    mensagem_id   BIGINT NOT NULL REFERENCES chat_mensagem(id) ON DELETE CASCADE,
    atendente_id  BIGINT NOT NULL REFERENCES atendente(id)     ON DELETE CASCADE,
    criada_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (mensagem_id, atendente_id)
);

-- "o que me chamaram e eu ainda não li" é a pergunta que esta tabela existe
-- para responder, e ela é feita por atendente.
CREATE INDEX IF NOT EXISTS ix_chat_mencao_atendente
    ON chat_mencao (atendente_id, mensagem_id DESC);

COMMENT ON TABLE chat_mencao IS
    'Quem foi chamado por @ em cada mensagem do chat interno. Uma linha por pessoa: uma mensagem pode chamar varias.';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('037', now(), 'mencao no chat interno: tabela por pessoa, resolvida por quem escreve');
