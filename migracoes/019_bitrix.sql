-- ============================================================================
-- MoviZap — migração 019: o Bitrix entra como OBSERVAÇÃO, nunca como cadastro
--
-- Decisão do usuário em 10/08, depois da medição: a base do Bitrix é
-- comercial, não cadastro. Dos 14.222 contatos, 7.113 são prospect, 309 são
-- ex-cliente e 1.810 não têm tipo. Só **305 empresas** casam com cliente nosso
-- -- e casam **por nome**, que não é prova.
--
-- ----------------------------------------------------------------------------
-- 🚨 POR QUE TABELA PRÓPRIA, E NÃO DENTRO DO CADASTRO
--
-- Enfiar 8.401 telefones de prospect em `contato_telefone` faria três estragos
-- de uma vez:
--   1. o alcance "subiria" no papel -- e o painel ofereceria conversa com quem
--      nunca foi cliente;
--   2. ex-cliente voltaria para uma base de onde acabamos de remover 106
--      empresas inativas;
--   3. o cadastro deixaria de responder "quem é cliente" para responder "quem
--      já foi abordado", que é outra pergunta.
--
-- Aqui o Bitrix responde *"o que se sabe sobre este número?"* -- nunca *"de
-- quem é este número?"*. A segunda pergunta continua sendo do cadastro.
--
-- ⚠️ O ARQUIVO EXPORTADO NÃO É DUPLICADO AQUI. Ele fica em
-- `/home/claude/movizap_bitrix/`, fora do backup, como a mídia. É a mesma
-- lição da migração 015: só se guarda cru o que é efêmero, e um arquivo que
-- está no disco não é.
--
-- ----------------------------------------------------------------------------
-- A CHAVE SEPARADA DO CONTATO
--
-- Uma pessoa tem vários telefones e vários e-mails. `bitrix_chave` é uma linha
-- por (contato, tipo, valor) -- é o que faz a consulta por telefone ser um
-- índice, e não uma varredura em campo de texto com vírgulas dentro.
-- ============================================================================

CREATE TABLE IF NOT EXISTS bitrix_contato (
    id            bigserial PRIMARY KEY,
    id_externo    text NOT NULL UNIQUE,      -- o ID do Bitrix
    nome          text,
    sobrenome     text,
    cargo         text,
    empresa_nome  text,
    empresa_id_externo text,
    -- 'Cliente', 'Prospect', 'Ex Cliente', 'Parceiro de instalação'...
    -- ⚠️ SEM CHECK: é vocabulário de um sistema que não é nosso e que está
    -- saindo. Travar valor aqui faria a importação falhar por causa de um
    -- rótulo que alguém criou no Bitrix, e não é papel deste banco opinar.
    tipo          text,
    importado_em  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_bitrix_empresa
    ON bitrix_contato (lower(empresa_nome)) WHERE empresa_nome IS NOT NULL;

CREATE TABLE IF NOT EXISTS bitrix_chave (
    contato_id  bigint NOT NULL REFERENCES bitrix_contato(id) ON DELETE CASCADE,
    tipo        text NOT NULL CHECK (tipo IN ('telefone', 'email', 'documento')),
    valor       text NOT NULL,               -- já normalizado (E164, minúscula)
    PRIMARY KEY (contato_id, tipo, valor)
);

-- 🚨 É POR AQUI QUE A CONSULTA ENTRA: "quem é este número?" precisa ser um
-- índice. Sem ele, cada conversa desconhecida varreria 14 mil linhas.
CREATE INDEX IF NOT EXISTS ix_bitrix_chave_valor ON bitrix_chave (tipo, valor);

-- Espera a exportação de COMPANY. É ela que traz o CNPJ e transforma o
-- casamento por NOME (indício) em casamento por DOCUMENTO (prova).
CREATE TABLE IF NOT EXISTS bitrix_empresa (
    id           bigserial PRIMARY KEY,
    id_externo   text NOT NULL UNIQUE,
    nome         text,
    documento    text,                        -- CNPJ/CPF só dígitos
    tipo         text,
    importada_em timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_bitrix_empresa_doc
    ON bitrix_empresa (documento) WHERE documento IS NOT NULL;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('019', now(), 'Bitrix como observação, fora do cadastro');
