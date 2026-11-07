-- ============================================================================
-- 095 — A CONCESSÃO DE TELA POR PESSOA, para a aba de permissão dos painéis
-- ============================================================================
-- 🔵 06/11, pedido dele: *"em configuração, crie uma aba de permissão para os
-- paineis, ali vou definir quem pode ver o que e por aba tbm, como notará que o
-- pós venda ja possui abas"*.
--
-- 🚨 ISTO É UM CONCEITO NOVO, E É O ÚNICO JEITO DE ATENDER O PEDIDO. Até hoje
-- a permissão do MoviZap era SÓ por perfil: `atendente.perfil` → um conjunto de
-- nomes (`PERFIS` no `telas.py`), e cada tela declara UM desses nomes. Nesse
-- modelo não existe *"esta pessoa, esta aba"*: as três telas de painel são
-- `permissao: owner`, e `pode_acessar` devolve `False` para qualquer não-owner
-- numa tela `owner` — não há caminho de concessão nenhum. Medido em 06/11: a
-- `atendente_time_permissao` está VAZIA e só o Iago (121) alcança os painéis.
--
-- 🚨 A CONCESSÃO EXPLÍCITA VENCE O `permissao: owner`, e é a linha mais
-- importante desta entrega. Sem isso a aba nova seria um formulário que grava e
-- não muda nada — o pior defeito possível numa tela de permissão. ⚠️ Ela NÃO
-- rebaixa a tela: a tela continua `owner` no registro, e quem não tem linha
-- aqui continua barrado. O que existe é uma lista de exceções NOMEADAS, cada
-- uma com quem concedeu e quando.
--
-- 🚨 SÓ TELA DE PAINEL ENTRA, e a trava é no BACKEND, não na tela: a rota
-- recusa qualquer código que não esteja no grupo "Painéis" do registro. Uma
-- tabela de concessão genérica com uma tela de marcar tudo seria um caminho
-- para conceder `CFG_1.1` (os canais do WhatsApp) por descuido.
--
-- ⚠️ A TABELA É GENÉRICA DE PROPÓSITO (`codigo_tela`, e não `aba_id`): a
-- concessão é da TELA, que é quem carrega permissão no MoviZap. As colunas das
-- abas vivem em `pipeline_etapa`, e isso não muda.
--
-- 🔵 Decisão dele de 06/11 sobre a porta trancada: *"ok"* — conceder só a
-- `PNL_1.3` passa a desenhar item de menu. O conserto é no `MenuLateral`, sem
-- banco.
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS tela_concedida (
  id            bigserial PRIMARY KEY,
  atendente_id  bigint NOT NULL REFERENCES atendente(id) ON DELETE CASCADE,
  codigo_tela   varchar(16) NOT NULL,
  -- ⚠️ Quem concedeu NÃO é obrigatório e NÃO cai em cascata: se a conta de
  -- quem concedeu for apagada, a concessão continua valendo (ela é da pessoa
  -- que recebeu), e só o autor some. Apagar o registro de quem recebeu, sim,
  -- apaga a concessão -- ela não tem sentido sem ele.
  concedida_por bigint REFERENCES atendente(id) ON DELETE SET NULL,
  concedida_em  timestamptz NOT NULL DEFAULT now(),
  -- 🚨 UMA LINHA POR PESSOA E TELA. Sem isto, conceder duas vezes daria duas
  -- linhas e revogar apagaria uma só -- a pessoa continuaria vendo a tela, e a
  -- tela de permissão mostraria "não concedido". Tela que mente é defeito
  -- (`M12`), e aqui ela mentiria sobre quem vê o quê.
  UNIQUE (atendente_id, codigo_tela)
);

COMMENT ON TABLE tela_concedida IS
  'Exceções nomeadas de permissão: esta pessoa alcança esta tela, mesmo que a '
  'tela seja `owner` no registro. Criada em 06/11 para a aba de permissão dos '
  'painéis -- o perfil continua valendo para todo o resto.';
COMMENT ON COLUMN tela_concedida.codigo_tela IS
  'Código do `movizap/telas.py`. NÃO tem FK: o catálogo de telas é o código, '
  'não uma tabela -- a mesma razão pela qual `painel_aba.codigo_tela` também '
  'não tem. A rota só aceita código do grupo "Painéis".';

-- ⚠️ O índice da leitura mais quente: `buscar_usuario` lê as concessões DESTA
-- pessoa a cada requisição (o `get_usuario` não guarda nada no token). A chave
-- UNIQUE acima já serve a esse acesso, então não há índice a mais a criar --
-- está escrito para ninguém "descobrir" que falta um.

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('095', now(),
        'tela_concedida: concessao de tela por pessoa (aba de permissao dos paineis)');

COMMIT;

-- ============================================================================
-- CONFERÊNCIA (rodar depois, e o esperado está escrito)
-- ============================================================================
--   SELECT count(*) FROM tela_concedida;
--     -- esperado: 0 -- quem concede é ELE, na aba nova. A migração não
--     -- concede nada a ninguém, de propósito.
--   \d tela_concedida
--     -- esperado: a UNIQUE (atendente_id, codigo_tela) e as duas FK
-- ============================================================================
