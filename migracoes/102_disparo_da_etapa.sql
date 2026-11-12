-- 102 — a mensagem automática de cada etapa (`CFG_16.1 Disparos Operação`)
--
-- 🔵 Pedido dele (11/11): *"Em configurações tela nova de 'Disparos Operação' ->
-- Deixar o campo de menagens que são enviadas em cada etapa do fluxo com
-- interruptor de 'ligado e desligado'"*, e as respostas do mesmo dia:
--   · *"pode ter um campo para cada uma delas sim, mas nasce em branco e com
--     interruptor desligado ainda, na tela de config exclusiva owner"*;
--   · *"por hora só whatsapp"*;
--   · *"por enquanto somente cliente deixe no painel de disparos uma nota que
--     nenhuma vai ao tecnico"*;
--   · *"inicialmente todo o painel pronto com interuptor desligado, depois será
--     validado em tela as mensagens e ao ligar o interruptor, sairá
--     automaticamente como na regra"*.
--
-- 🚨 ESTA É A PRIMEIRA COISA DO PAINEL QUE FALA COM O CLIENTE SOZINHA. O que
-- protege é nascer DESLIGADA e ele ler o texto antes de ligar -- então o texto
-- na tela é a última conferência que existe, e o `CHECK
-- etapa_mensagem_ligada_tem_texto` garante que **não dá para ligar vazia**.
--
-- 🚨 UMA LINHA POR ETAPA, E AS 17 JÁ NASCEM. Criar a linha só quando ele
-- escrever faria a tela ter dois estados ("não existe" e "existe vazia") para a
-- mesma coisa. A coluna `Chamados` NÃO entra: não é situação do ERP.
--
-- ⚠️ NENHUM TEXTO É SEMEADO, e isto é um fato, não um esquecimento: o texto que
-- ele passou em 04/11 (a mensagem do rastreio) **não sobreviveu em documento
-- nenhum** -- do bloco daquele dia só restaram as três variáveis. Semear um
-- texto inventado no lugar seria pôr palavra dele na boca do sistema. Ele disse
-- *"depois colo"* sobre os demais.

BEGIN;

CREATE TABLE IF NOT EXISTS etapa_mensagem (
  id             BIGSERIAL PRIMARY KEY,
  situacao_id    INTEGER     NOT NULL UNIQUE,
  canal          TEXT        NOT NULL DEFAULT 'whatsapp',
  texto          TEXT,
  ativo          BOOLEAN     NOT NULL DEFAULT false,
  atualizado_em  TIMESTAMPTZ NOT NULL DEFAULT now(),
  atualizado_por INTEGER     REFERENCES atendente(id) ON DELETE SET NULL,
  -- 🔵 *"por hora só whatsapp"*. ⚠️ O dia em que entrar e-mail, é migração que
  -- amplia este CHECK -- e é de propósito: canal novo muda para quem a
  -- mensagem vai, e isso não pode entrar por descuido de tela.
  CONSTRAINT etapa_mensagem_canal_conhecido CHECK (canal IN ('whatsapp')),
  -- 🚨 NÃO DÁ PARA LIGAR VAZIA. Interruptor ligado sem texto mandaria mensagem
  -- em branco ao cliente -- e o banco é o único lugar onde essa garantia não
  -- depende de ninguém ter lembrado.
  CONSTRAINT etapa_mensagem_ligada_tem_texto
    CHECK (NOT ativo OR btrim(coalesce(texto, '')) <> '')
);

COMMENT ON TABLE etapa_mensagem IS
  'A mensagem que a etapa manda ao CLIENTE quando um card chega nela. '
  '🚨 Nasce DESLIGADA e sem texto, por decisao dele (11/11). Primeira coisa do '
  'painel que fala com o cliente sozinha.';
COMMENT ON COLUMN etapa_mensagem.ativo IS
  'Ligado = ao mover um card para esta etapa, a mensagem SAI sozinha. Nasce '
  'false. 🚨 O CHECK impede ligar sem texto.';
COMMENT ON COLUMN etapa_mensagem.texto IS
  'O texto, com as variaveis {{...}} resolvidas no servidor. Nulo = nada a '
  'enviar. ⚠️ Nenhum texto foi semeado: o que ele passou em 04/11 nao '
  'sobreviveu em documento nenhum, e inventar um seria por palavra dele na '
  'boca do sistema.';
COMMENT ON COLUMN etapa_mensagem.atualizado_por IS
  'Quem mexeu por ultimo. Nulo = atendente removido depois (SET NULL): sumir '
  'com a pessoa nao pode levar o rastro de quem ligou um disparo.';

-- As 17 situações do painel da Operação, todas vazias e desligadas.
INSERT INTO etapa_mensagem (situacao_id) VALUES
  (38), (16487), (251), (16488), (677), (15747), (15797), (890), (16489),
  (1316), (15696), (16490), (15694), (16491), (15746), (15695), (16492)
ON CONFLICT (situacao_id) DO NOTHING;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('102', now(), 'etapa_mensagem: a mensagem automatica por etapa (CFG_16.1), nasce vazia e desligada');

COMMIT;
