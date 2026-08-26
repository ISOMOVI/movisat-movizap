-- ============================================================================
-- MoviZap — migração 036: a reação do CLIENTE, e o fim da coluna única
--
-- 🚨 O QUE ISTO CONSERTA, MEDIDO EM 26/08: **161 mensagens falsas** no
-- histórico de conversas reais, com o texto
-- `[reactionMessage — tipo ainda não tratado]`. Cada vez que alguém reagiu com
-- um emoji, o painel gravou uma MENSAGEM dizendo isso — no meio da conversa,
-- para o atendente ler. A reação nunca foi tratada, e o custo não era ela
-- faltar: era ela virar lixo visível.
--
-- ----------------------------------------------------------------------------
-- POR QUE TABELA, E NÃO MAIS UMA COLUNA
--
-- A migração 034 escolheu coluna, e escreveu a razão: *"no WhatsApp cada
-- participante tem UMA reação por mensagem, e do nosso lado só existe um
-- participante (o painel)"*. Estava certo enquanto só nós reagíamos.
--
-- 🚨 A RAZÃO CAIU QUANDO O CLIENTE ENTROU. Medido nas 161: **64 são em
-- GRUPO** (40%). Num grupo de quinze, uma coluna guarda o último que reagiu e
-- **apaga os outros em silêncio** — e silêncio é o defeito que este projeto
-- mais paga. Duas colunas resolveriam a conversa direta e continuariam erradas
-- no grupo.
--
-- ⚠️ `mensagem.reacao` SAI. Não é perda: **zero linhas** a usavam (medido em
-- 26/08 — a coluna nasceu em 25/08 e ninguém reagiu pelo painel desde então).
-- Deixá-la seria manter DUAS VERDADES sobre a mesma coisa, que é exatamente o
-- que o `docs/02` proíbe no princípio 1.
--
-- ----------------------------------------------------------------------------
-- `quem`: A CHAVE QUE FAZ "REAGIR DE NOVO TROCA"
--
-- No WhatsApp não existe "remover reação": existe reagir com nada. Então a
-- linha é um UPSERT por (mensagem, quem), e emoji vazio APAGA a linha.
--
-- `quem` é o JID de quem reagiu — em grupo o `participant`, em conversa direta
-- o próprio contato — ou o literal `nos` quando a reação saiu do painel.
-- ⚠️ NÃO PODE SER NULL para o nosso lado: `UNIQUE` com NULL não deduplica em
-- Postgres, e cada clique nosso criaria uma linha nova em vez de trocar.
-- ============================================================================

CREATE TABLE IF NOT EXISTS mensagem_reacao (
    id          bigserial PRIMARY KEY,
    mensagem_id bigint NOT NULL REFERENCES mensagem(id) ON DELETE CASCADE,
    -- `nos` = saiu do painel. Qualquer outro valor é o JID de quem reagiu.
    quem        text NOT NULL,
    -- O nome que o WhatsApp mandou de quem reagiu. Só existe em grupo, e é
    -- apelido: quem diz de quem é a conversa continua sendo `contato_id`.
    quem_nome   text,
    emoji       text NOT NULL,
    em          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ux_reacao_por_pessoa UNIQUE (mensagem_id, quem),
    -- Emoji vazio não é reação: é a remoção dela, e remoção APAGA a linha.
    CONSTRAINT ck_reacao_nao_vazia CHECK (emoji <> '')
);

COMMENT ON TABLE mensagem_reacao IS
    'Uma linha por (mensagem, quem reagiu). Reagir de novo TROCA (upsert); '
    'reagir com nada APAGA. `quem` = ''nos'' quando saiu do painel, senão o '
    'JID de quem reagiu.';

-- A tela pede as reações da janela de mensagens que está mostrando.
CREATE INDEX IF NOT EXISTS ix_reacao_mensagem ON mensagem_reacao (mensagem_id);

-- ⚠️ O DROP VEM DEPOIS DA TABELA EXISTIR, e só porque a coluna tem zero
-- linhas. Se algum dia isto rodar num banco em que ela tenha valor, o
-- `scripts/migrar_reacoes.py` é quem move — não esta migração.
ALTER TABLE mensagem DROP COLUMN IF EXISTS reacao;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('036', now(), 'reacao do cliente: tabela por pessoa, sai a coluna unica');
