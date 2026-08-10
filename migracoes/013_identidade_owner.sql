-- ============================================================================
-- MoviZap — migração 013: o owner assume tudo e não recebe transferência
--
-- Decisão do usuário em 10/08: *"Admin deve poder ter todos os canais e
-- conversas vinculados, mas não faz parte da lista de transferências"*.
--
-- ----------------------------------------------------------------------------
-- O PROBLEMA QUE ISTO RESOLVE
--
-- Ele é **login `Admin`, perfil `owner`, nome `Iago`** — três chaves para a
-- mesma pessoa. O `buscar_usuario` consulta a conta do `.env` primeiro (de
-- propósito: se o banco cair, o dono ainda entra), e essa conta identifica-se
-- como `Admin`. A linha da tabela `atendente` tinha `login = 'iago'`.
--
-- 🚨 Resultado medido em 10/08: `_atendente_do_usuario` devolvia NULL, e daí
--   · `POST /assumir` respondia **409** -- o dono não conseguia assumir nada;
--   · `responder` funcionava, mas gravava a mensagem **sem autor** (aconteceu
--     de verdade: a mensagem 1768 saiu do painel e ficou com autor nulo).
--
-- O `login` da linha passa a ser `Admin` para casar com a conta do `.env`, e o
-- `nome` passa a ser a pessoa, não o cargo.
--
-- ----------------------------------------------------------------------------
-- POR QUE UMA COLUNA, E NÃO "TIRAR DO TIME"
--
-- Tirar o owner de `atendente_time` também o esconderia da lista de
-- transferências -- e junto tiraria a informação de que ele É do time Geral.
-- São duas perguntas diferentes: *de que time faz parte* e *pode receber
-- conversa transferida*. Colapsar as duas num campo só custa faxina depois.
--
-- ⚠️ `transferivel` nasce `true` para todo mundo: o comportamento de hoje não
-- muda para ninguém, exceto para quem for marcado. Padrão que altera o sistema
-- em silêncio é o que faz ninguém confiar na migração.
--
-- ⚠️ Quando o login `iago@movisat.com.br` entrar pelo Google, ele casa pelo
-- `google_sub` NESTA MESMA LINHA. Criar um segundo atendente partiria o
-- histórico de atendimento em duas pessoas que são a mesma.
-- ============================================================================

ALTER TABLE atendente ADD COLUMN IF NOT EXISTS transferivel boolean NOT NULL DEFAULT true;

COMMENT ON COLUMN atendente.transferivel IS
    'Aparece na lista de destino de transferência. O owner assume qualquer '
    'conversa mas não recebe transferência (decisão de 10/08).';

-- A conta do dono: login casa com o `.env`, nome é a pessoa, não recebe fila.
UPDATE atendente
   SET login = 'Admin',
       nome = 'Iago',
       transferivel = false,
       atualizado_em = now()
 WHERE owner IS TRUE;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('013', now(), 'Owner assume tudo e sai da lista de transferências')
ON CONFLICT (versao) DO NOTHING;
