-- ============================================================================
-- MoviZap — migração 107: o CONVITE de formulário, que é o que faz o link do
--                         chat abrir o formulário já preenchido
--
-- 🔵 PEDIDO DELE, no bloco de 11/11: formulários *"pré-preenchidos quando
-- abertos pelo botão dentro do chat"*.
--
-- 📏 MEDIDO ANTES: a página pública **não lê nada da URL** (`grep` por
-- `URLSearchParams` em `frontend/publico/` → zero), e não existe botão nenhum
-- no chat. Nenhuma peça existia.
--
-- ----------------------------------------------------------------------------
-- 🚨 POR QUE UMA TABELA, E NÃO OS VALORES NA URL
-- ----------------------------------------------------------------------------
--
-- O caminho curto seria `/f/suporte?cnpj=...&telefone=...`. 🚨 **Isso põe dado
-- de cliente no ENDEREÇO**, e endereço não é lugar de dado: ele entra no log de
-- acesso do nginx, no histórico do navegador de quem abriu, no `Referer` de
-- qualquer link que a página carregue, e em qualquer repasse do link por
-- WhatsApp ou e-mail. Base64 não resolve nada disso -- esconde do olho, não do
-- log.
--
-- ⚠️ E não é hipótese: o `access.log` da casa guarda a linha de requisição
-- inteira, com a query string.
--
-- Então o que viaja na URL é **um bilhete opaco** (`secrets.token_urlsafe`), e
-- os valores ficam aqui. Quem tem o bilhete lê os valores **daquele** convite e
-- nada mais.
--
-- ----------------------------------------------------------------------------
-- AS QUATRO DECISÕES QUE ESTA TABELA CARREGA
-- ----------------------------------------------------------------------------
--
-- 1. 🚨 O convite **vence** (`expira_em`). Link de formulário pré-preenchido é
--    um ponteiro para dado de cliente: sem prazo, um link repassado em 2027
--    ainda abriria a ficha de alguém. O prazo nasce em 7 dias.
--
-- 2. ⚠️ Abrir **não gasta** o convite -- `aberto_em` é marca, não trava. A
--    pessoa recarrega a página, perde a aba, volta no dia seguinte: gastar no
--    primeiro `GET` transformaria isso em "o link não funciona mais", que é o
--    pior jeito de proteger.
--
-- 3. ⚠️ Enviar **não apaga** o convite (`usado_em`): o histórico de quem
--    convidou quem fica. Apagar o convite ao usar deixaria a solicitação sem
--    origem.
--
-- 4. 🚨 Os valores são **sugestão**, nunca verdade. O envio continua validando
--    tudo pelo `formularios.validar`, e o que vem do convite é só o que a
--    pessoa vê escrito na tela antes de confirmar. Se fosse verdade, um convite
--    velho com CNPJ antigo gravaria o CNPJ antigo sem ninguém olhar.
--
-- ----------------------------------------------------------------------------

BEGIN;

CREATE TABLE IF NOT EXISTS formulario_convite (
    id            BIGSERIAL PRIMARY KEY,

    -- 🚨 O que viaja na URL. Opaco e aleatório: não deriva de nada, então não
    -- se adivinha a partir do id nem da data.
    bilhete       TEXT        NOT NULL UNIQUE,

    -- ⚠️ `slug` e não `formulario_id`: é o slug que monta o link, e é por ele
    -- que a página pública pede a definição. Guardar o id obrigaria a traduzir
    -- nos dois lados.
    slug          TEXT        NOT NULL,

    -- Os valores sugeridos, pelo NOME do campo do formulário.
    -- ⚠️ Campo que não existe mais na definição é ignorado na leitura, não
    -- apagado daqui: o convite é o retrato do que se quis sugerir.
    valores       JSONB       NOT NULL DEFAULT '{}'::jsonb,

    -- De onde o convite saiu, para o rastro. Os dois podem ser nulos: um
    -- convite pode nascer fora de conversa (a tela de Solicitações, amanhã).
    conversa_id   BIGINT      REFERENCES conversa(id) ON DELETE SET NULL,
    cliente_id    BIGINT      REFERENCES cliente(id)  ON DELETE SET NULL,

    criado_por    BIGINT      REFERENCES atendente(id),
    criado_em     TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- 🚨 Vence. Ver a decisão 1 acima.
    expira_em     TIMESTAMPTZ NOT NULL,

    -- Marcas, não travas. Ver as decisões 2 e 3.
    aberto_em     TIMESTAMPTZ,
    aberturas     INTEGER     NOT NULL DEFAULT 0,
    usado_em      TIMESTAMPTZ,
    solicitacao_id INTEGER    REFERENCES formulario_solicitacao(id)
                              ON DELETE SET NULL
);

COMMENT ON TABLE formulario_convite IS
  'Link de formulario pre-preenchido: o bilhete viaja na URL, os valores ficam '
  'aqui. Dado de cliente NUNCA vai na query string -- ela entra no access.log, '
  'no historico do navegador e em qualquer repasse do link.';

COMMENT ON COLUMN formulario_convite.aberto_em IS
  'Marca da PRIMEIRA abertura. Abrir nao gasta o convite: recarregar a pagina '
  'nao pode quebrar o link.';

COMMENT ON COLUMN formulario_convite.valores IS
  'SUGESTAO, nunca verdade: o envio revalida tudo. Convite velho com dado '
  'velho sugere dado velho, e quem confirma e a pessoa na tela.';

-- 🚨 O índice que o caminho quente usa: a página pública procura PELO BILHETE,
-- uma vez por abertura. O `UNIQUE` acima já o dá.
-- ⚠️ E este, para a pergunta do outro lado: "quais convites desta conversa?",
-- que é o que a tela do chat vai mostrar.
CREATE INDEX IF NOT EXISTS idx_convite_da_conversa
    ON formulario_convite (conversa_id, criado_em DESC)
    WHERE conversa_id IS NOT NULL;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('107', now(), 'convite de formulario: o bilhete viaja na URL e os valores ficam na tabela');

COMMIT;
