-- ============================================================================
-- MoviZap — migração 083: a passagem de etapa (Bloco D do pipeline)
--
-- 🔵 TRÊS DECISÕES DELE, 29/10, nas palavras dele:
--   · **o gesto**: *"O card pode ser por arrastar"*;
--   · **o log**: *"deve ter o log de quem faz o que SEMPRE"*;
--   · **a ordem**: *"que tal de caminho proibido é esse??"* — não existe
--     caminho proibido, e a pergunta era minha, não dele. A ordem é LIVRE.
--   · **quem move**: *"pode mover que tiver acesso a tela, por enquanto
--     somente owner"*.
--
-- 🚨 POR QUE ESTA TABELA É A CONDIÇÃO DO BLOCO D, e não um extra: o Harmonit
-- **não registra a situação na linha do tempo** -- só o `status`, conferido em
-- 3 OS em 29/10. Então, movido o card, **não há como saber quem moveu, de onde
-- e quando**, nem aqui nem lá. Sem esta tabela, mover é uma escrita anônima e
-- irreversível no ERP. É exatamente o *"SEMPRE"* dele.
--
-- 🚨 A TENTATIVA RECUSADA TAMBÉM É GRAVADA, e é metade do valor: escrita que o
-- ERP negou e não deixou rastro é a mesma família do `criada: null` da criação
-- de OS -- ninguém descobre depois. `ok = false` com o motivo por extenso.
--
-- ⚠️ ESTA TABELA NÃO É O BLOCO C. O Bloco C quer *"quanto tempo em cada
-- etapa"*, com os dois tempos no card e o tratamento das 11 OS que já existem.
-- Aqui é só o **registro da passagem** -- e é ele que faz o C sair barato
-- depois, porque o dado passa a ser colhido desde já.
--
-- ⚠️ `de_situacao` É NULA QUANDO NÃO SE SABE de onde o card veio: OS cuja
-- situação o ERP tem como `NULL`. **Nula não é zero**: `0` é um valor que o
-- Harmonit grava em 129 OS, e confundir os dois já custou uma coluna em 22/10.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS os_passagem (
    id            serial PRIMARY KEY,
    numero_os     integer NOT NULL,
    os_id         integer,
    -- 🚨 De onde para onde. Ver a advertência sobre nulo x zero, acima.
    de_situacao   integer,
    para_situacao integer NOT NULL,
    -- 🔵 *"o log de quem faz o que SEMPRE"*.
    atendente_id  integer REFERENCES atendente(id) ON DELETE SET NULL,
    em            timestamptz NOT NULL DEFAULT now(),
    -- A escrita no Harmonit deu certo? `false` com `erro` preenchido é a
    -- tentativa recusada, e ela fica registrada de propósito.
    ok            boolean NOT NULL DEFAULT false,
    erro          text,
    -- 🚨 O que a releitura acusou FORA da situação. Preenchido é falha mesmo
    -- com a situação gravada: a OS perdeu ou ganhou algo que esta escrita não
    -- devia tocar, e o remapeamento está errado em algum campo.
    fora_da_situacao jsonb
);

COMMENT ON TABLE os_passagem IS
    'Quem moveu o card de qual etapa para qual, e quando. 🔵 Dele (29/10): "deve '
    'ter o log de quem faz o que SEMPRE". 🚨 E a tabela existe porque o Harmonit '
    'NAO registra situacao na linha do tempo: sem ela, mover e escrita anonima '
    'no ERP. A tentativa RECUSADA tambem entra, com ok = false.';

COMMENT ON COLUMN os_passagem.de_situacao IS
    'A situacao de onde o card saiu. NULA = o ERP tinha a situacao como NULL '
    '(nao se sabe de onde veio). 🚨 NULO NAO E ZERO: 0 e um valor que o '
    'Harmonit grava em 129 OS.';

COMMENT ON COLUMN os_passagem.ok IS
    'A escrita no Harmonit foi confirmada pela releitura. 🚨 false NAO quer '
    'dizer "nao tentou": a linha so nasce quando se tenta, e o erro diz o que '
    'o ERP respondeu.';

-- A linha do tempo de uma OS, que é o que o card aberto vai ler (Bloco E).
CREATE INDEX IF NOT EXISTS idx_passagem_os
    ON os_passagem (numero_os, em DESC);

-- 🔵 *"o log de quem faz o que"* — por pessoa, para a pergunta "o que o X fez
-- hoje" ter resposta sem varrer a tabela inteira.
CREATE INDEX IF NOT EXISTS idx_passagem_quem
    ON os_passagem (atendente_id, em DESC);

-- As recusadas, que é o que se procura quando algo não entrou no ERP.
CREATE INDEX IF NOT EXISTS idx_passagem_recusada
    ON os_passagem (em DESC) WHERE NOT ok;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('083', now(), 'passagem de etapa: quem moveu o card de onde para onde, e a tentativa recusada');

COMMIT;

-- ----------------------------------------------------------------------------
-- CONFERÊNCIA:
--   SELECT count(*) FROM os_passagem;
--     -- esperado agora: 0 -- a tabela nasce vazia e ninguem moveu card ainda
--
--   SELECT indexname FROM pg_indexes WHERE tablename = 'os_passagem';
--     -- esperado: a chave primaria + os 3 indices acima
-- ----------------------------------------------------------------------------
