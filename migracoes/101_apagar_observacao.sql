-- 101 — apagar observação do card, mantendo o log (11/11)
--
-- 🔵 Pedido dele: *"Permitir excluir OBS's, porém manter os logs e somente
-- owner pode visualizar o exlcuido, com botão, como no chat interno, sem que
-- vejam essa informação. Se excluírem, aparecerá como 'Observação excluida' e
-- log's."* · e as três respostas de 11/11: **(1)** podem apagar *"todos que tem
-- acesso a visualização do painel"*; **(2)** *"não tem"* janela de tempo —
-- *"pode ser apagada conforme disponivel mesmo"*; **(3)** *"deve ter disponivel
-- exibição da autoria sim, é um dos objetivos, rastreabilidade"*.
--
-- 🚨 ISTO INVERTE UMA DECISÃO ESCRITA, E O TEXTO VELHO TEM DE MORRER JUNTO.
-- A migração 084 diz, no comentário da coluna `texto`: *"Nao ha coluna de
-- 'apagada' nem de 'editada', de proposito: reescrever recado e reescrever a
-- historia que a operacao leu."* A tela repetia isso em palavras. Ele decidiu
-- outra coisa, e o comentário da 084 e a frase da tela são atualizados na mesma
-- entrega — senão o sistema passa a mentir sobre si mesmo (`M12`).
--
-- ⚠️ **O TEXTO NÃO É DESTRUÍDO**, e é o que torna a decisão reversível e o owner
-- capaz de ver o que dizia. Quem esconde é a LEITURA, não o banco — molde exato
-- do `chat_mensagem.apagada_em` (migração 061).
--
-- 🚨 **E AQUI PRECISA DE `apagada_por`, QUE O CHAT NÃO TEM.** No chat interno
-- **só o autor** apaga, então "quem apagou" é o próprio `atendente_id` da
-- mensagem e uma coluna seria redundante. Aqui **qualquer pessoa com o painel**
-- apaga o recado de qualquer um (decisão dele), então sem esta coluna a
-- pergunta *"quem apagou?"* não teria resposta — e rastreabilidade é
-- justamente o objetivo que ele nomeou.

BEGIN;

ALTER TABLE os_observacao
  ADD COLUMN IF NOT EXISTS apagada_em  TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS apagada_por INTEGER REFERENCES atendente(id)
                                       ON DELETE SET NULL;

COMMENT ON COLUMN os_observacao.apagada_em IS
  'Quando alguem apagou o recado. NULL = nunca apagado. 🚨 O `texto` NAO e '
  'destruido -- quem esconde e a leitura (mesma regra do chat_mensagem, 061), e '
  'e isso que permite ao owner ver o que dizia.';
COMMENT ON COLUMN os_observacao.apagada_por IS
  'Quem apagou. 🚨 Existe porque aqui QUALQUER PESSOA com o painel apaga o '
  'recado de qualquer um (decisao dele, 11/11) -- no chat interno so o autor '
  'apaga, e lá a coluna seria redundante. Nulo = atendente removido depois '
  '(ON DELETE SET NULL): sumir com a pessoa nao pode levar o log.';

-- 🚨 E o comentário da 084 deixa de mentir: ele afirmava que a coluna não
-- existia DE PROPÓSITO, e agora existe por decisão dele.
COMMENT ON COLUMN os_observacao.texto IS
  'O recado. ⚠️ NAO SE EDITA (nao ha coluna de "editada", e isso continua de '
  'proposito: reescrever recado e reescrever a historia que a operacao leu). '
  'APAGAR passou a existir em 11/11, por decisao dele -- e apagar nao destroi '
  'este texto: ver `apagada_em`.';

-- A leitura que esconde precisa do par; e o índice de "quem apagou o que"
-- serve a pergunta de auditoria que motivou a coluna.
CREATE INDEX IF NOT EXISTS idx_observacao_apagada
  ON os_observacao (apagada_em) WHERE apagada_em IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_observacao_apagada_por
  ON os_observacao (apagada_por, apagada_em DESC) WHERE apagada_em IS NOT NULL;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('101', now(), 'apagar observacao do card: apagada_em e apagada_por, sem destruir o texto');

COMMIT;
