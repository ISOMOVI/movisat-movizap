-- ============================================================================
-- MoviZap — migração 057: mensagens rápidas (Plano 3, 25/09)
--
-- 🔵 Decisões dele em 25/09:
--   · três tipos, cada um uma aba em Configurações: **Padrões** (owner e admin
--     criam), **Minhas notas** (cada um as suas), **Formulários** (*"serão
--     links"*; owner e admin criam);
--   · *"apelido curto como 'Mensagem de encerramento' ... e ele quem aparecerá
--     na lista da conversa"*;
--   · o texto vai para o campo de escrever e ainda pode ser editado.
--
-- ⚠️ `nota` TEM DONO; `padrao` e `formulario` NÃO. É o que decide quem vê:
-- a nota de um nunca aparece para outro. O CHECK prende isso no banco.
--
-- ⚠️ APAGAR É SEGURO: a mensagem já enviada é texto na conversa, sem vínculo
-- com esta linha. Por isso não há `ativo` para "apagar", só para esconder
-- da lista sem perder o texto.
-- ============================================================================

BEGIN;

CREATE TABLE mensagem_rapida (
    id            bigserial PRIMARY KEY,
    tipo          text NOT NULL CHECK (tipo IN ('padrao', 'nota', 'formulario')),
    apelido       text NOT NULL CHECK (length(btrim(apelido)) BETWEEN 1 AND 60),
    conteudo      text NOT NULL CHECK (length(btrim(conteudo)) BETWEEN 1 AND 4000),
    atendente_id  bigint REFERENCES atendente(id) ON DELETE CASCADE,
    ativo         boolean NOT NULL DEFAULT true,
    ordem         int NOT NULL DEFAULT 0,
    criada_em     timestamptz NOT NULL DEFAULT now(),
    atualizada_em timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_mensagem_rapida_dono CHECK (
        (tipo = 'nota') = (atendente_id IS NOT NULL))
);

-- Apelido único dentro do tipo (e do dono, para as notas): é pelo apelido
-- que se escolhe na conversa, e dois iguais seriam uma escolha às cegas.
CREATE UNIQUE INDEX ux_mensagem_rapida_apelido
    ON mensagem_rapida (tipo, COALESCE(atendente_id, 0), lower(btrim(apelido)));

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('057', now(), 'mensagens rapidas: padroes, minhas notas, formularios');

COMMIT;
