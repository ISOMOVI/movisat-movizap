-- ============================================================================
-- MoviZap — migração 006: antiguidade do cadastro e fila de revisão
--
-- Auditado ANTES de escrever esta migração: docs/08_Identidade.md.
--
-- 🚨 POR QUE `cadastrado_em` EXISTE E NÃO DÁ PARA USAR O `harmonit_id`
--
-- Ordenar por data de cadastro dá resultado DIFERENTE de ordenar por id em
-- 665 de 747 clientes que têm data. O id parece ordem de cadastro e não é.
--
-- 🚨 E POR QUE ELE É NULO EM 29% DAS LINHAS
--
-- O Harmonit manda `dataCadastro` vazio em 291 clientes e manda o sentinela
-- `0001-01-01T00:00:00` -- o vazio do .NET -- em outros 12. Esse sentinela
-- parseia sem erro e vira o ano 1: gravado como está, o registro SEM data
-- ganharia toda disputa de "quem é o mais antigo", e a regra ficaria
-- exatamente invertida sem nada acusar.
--
-- Por isso a coluna é NULL-ável e o sync converte o sentinela para NULL. NULL
-- aqui significa "o Harmonit não sabe", e quem não sabe perde o desempate.
--
-- `revisar` / `motivo_revisao`: o cadastro que precisa de olho humano. Hoje
-- são os 3 marcados `[NÃO USAR]` / `(INATIVADO)`. Marcar não apaga nem
-- esconde -- só diz que alguém precisa olhar.
-- ============================================================================

BEGIN;

ALTER TABLE cliente
    ADD COLUMN IF NOT EXISTS cadastrado_em   timestamptz,
    ADD COLUMN IF NOT EXISTS revisar         boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS motivo_revisao  text;

COMMENT ON COLUMN cliente.cadastrado_em IS
    'dataCadastro do Harmonit. NULL = o Harmonit não sabe (29% da base). '
    'O sentinela 0001-01-01 do .NET vira NULL no sync -- gravado como data, '
    'ele venceria toda disputa de antiguidade.';

COMMENT ON COLUMN cliente.revisar IS
    'Cadastro que precisa de olho humano. Não esconde nem apaga.';

-- Índice parcial: a fila de revisão é minúscula perto da base, e é isso que
-- se consulta. Índice cheio aqui seria pagar por 1.050 linhas para achar 3.
CREATE INDEX IF NOT EXISTS ix_cliente_revisar
    ON cliente (id) WHERE revisar;

-- Ordenação por antiguidade: é a consulta da regra do número compartilhado.
-- NULLS LAST no índice espelha o `ORDER BY` do sync -- quem não tem data
-- perde o desempate, e o índice precisa saber disso para servir.
CREATE INDEX IF NOT EXISTS ix_cliente_antiguidade
    ON cliente (cadastrado_em NULLS LAST, harmonit_id)
    WHERE origem = 'harmonit';

INSERT INTO schema_migracao (versao, descricao)
VALUES ('006', 'Antiguidade do cadastro e fila de revisão (docs/08_Identidade.md)');

COMMIT;
