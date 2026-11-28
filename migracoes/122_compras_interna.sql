-- ============================================================================
-- MoviZap — migração 122: o painel de Compras e o formulário INTERNO
-- ============================================================================
-- 🔵 27/11, pedido dele: *"proponha um novo de compras, sem vinculo de OS
-- somente por formularios e controle de compras, nao precisa propor colunas
-- alem da primeira: nova solicitacoes"*, e depois: *"sera somente interno,
-- talvez um botao de acao no chat interno? para forms internos igual no chat
-- com clientes"*.
--
-- 🔵 O rótulo da coluna é escolha dele, perguntada e respondida: **"Nova
-- solicitação"**, singular e com acento.
--
-- 🔵 E O FORMULÁRIO É DE DOIS CAMPOS, por decisão dele depois de eu propor
-- oito: *"nao precisa de setor, só de um campo de justificativa e um campo com
-- anexo para Sugestão de compras - por enquanto"*.
--
-- ⚠️ "POR ENQUANTO" É PARTE DA DECISÃO, não ressalva minha. Item, quantidade,
-- prazo e urgência saíram desta entrega. Formulário é DADO: acrescentar campo
-- depois é linha nesta tabela, não migração nem deploy.
--
-- 🚨 UMA COLUNA SÓ, e é o pedido. Card em coluna única não tem para onde ir, e
-- isso não é defeito -- é o painel no primeiro dia. O Contratual (097) e o
-- Financeiro (096) nasceram vazios pela mesma decisão dele em 06/11.
--
-- 🚨 SEM VÍNCULO DE OS, E ESTÁ ESCRITO NO BANCO: `gera_os = false`. O card
-- nasce com `numero_os` nulo, e `paineis._card_do_chamado` devolve `os_id`,
-- `numero_ordem`, `situacao_id` e `situacao_em` fixos em nulo -- são esses
-- quatro que a tela lê para NÃO oferecer arrastar o card para o Harmonit.
-- Nada aqui fala com o ERP.
--
-- 🚨 O FORMULÁRIO NÃO VEM DO BITRIX, e por isso não passa pelo
-- `scripts/carregar_formularios.py` nem por `formularios.gravar_definicao()`:
-- aquela função exige um `bruto` no formato do loader do Bitrix e é idempotente
-- pelo `bitrix_id`. Fabricar um "bruto" falso apagaria o sentido do
-- `dados/formularios_bitrix/mapa_bruto.json`, que é PROCEDÊNCIA -- a prova de
-- como cada formulário era lá em 22/10. Este nasce à mão, com `bitrix_id` nulo,
-- e a coluna aceita nulo.
--
-- ⚠️ O FORMULÁRIO NASCE DESLIGADO (`ativo = false`), como todo formulário.
-- Quem liga é ele, pelo interruptor da `FRM_1.1`.
--
-- ⚠️ SÃO DOIS CHECK A ALARGAR, não um. Medidos no banco em 27/11 com
-- `pg_get_constraintdef`: `painel_aba_painel_conhecido` (092) e
-- `formulario_painel_check` (075) listam os MESMOS quatro painéis. Sem os dois,
-- nem a aba nem o formulário aceitam `'compras'`.
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. O VOCABULÁRIO DE PAINEL — os dois CHECK
-- ---------------------------------------------------------------------------
-- ⚠️ O comentário do 092 diz por que este CHECK existe: *"aba de painel
-- inventado não nascer: a rota recusa painel desconhecido, e uma linha órfã
-- aqui ficaria invisível e viva"*. Alargar a lista é o gesto certo; tirar o
-- CHECK não é.
ALTER TABLE painel_aba
    DROP CONSTRAINT IF EXISTS painel_aba_painel_conhecido;
ALTER TABLE painel_aba
    ADD CONSTRAINT painel_aba_painel_conhecido CHECK (
        painel IN ('operacao', 'pos_venda', 'contratual', 'financeiro',
                   'compras'));

ALTER TABLE formulario
    DROP CONSTRAINT IF EXISTS formulario_painel_check;
ALTER TABLE formulario
    ADD CONSTRAINT formulario_painel_check CHECK (
        painel IS NULL OR painel IN
            ('operacao', 'pos_venda', 'contratual', 'financeiro', 'compras'));

-- ---------------------------------------------------------------------------
-- 2. A TRAVA DO "INTERNO" — a coluna que faz o pedido dele ser verificável
-- ---------------------------------------------------------------------------
-- 🔵 *"sera somente itnerno"*.
--
-- 🚨 SEM ESTA COLUNA, "INTERNO" SERIA COMBINADO, NÃO GARANTIDO. O único
-- caminho de envio que existe hoje é `POST /api/publico/formulario/{slug}`:
-- protegido por isca, token de abertura, desafio e rate-limit, mas **não por
-- login**. Um formulário "interno" nessa rota seria interno só por ninguém
-- divulgar a URL -- e trava mede uso, não palavra.
--
-- ⚠️ `DEFAULT false` é o que mantém os 16 formulários de hoje exatamente como
-- estão: nenhum deles vira interno por causa desta migração.
ALTER TABLE formulario
    ADD COLUMN IF NOT EXISTS interno boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN formulario.interno IS
    'Formulario de uso interno: NAO tem pagina publica. As rotas '
    '/api/publico/formulario/{slug} recusam com 404 e a MESMA frase de um slug '
    'inexistente ("Formulario nao encontrado."), para nao contar de fora que '
    'ele existe. O envio entra por /api/interno/formulario/{slug}, atras da '
    'permissao do Chat interno (ATD_6.1).';

-- ---------------------------------------------------------------------------
-- 3. A ABA DO PAINEL
-- ---------------------------------------------------------------------------
-- ⚠️ A ENTRADA DA TELA NÃO MORA AQUI, mora no `movizap/telas.py` (código,
-- rota, ícone e quem entra) e no `frontend/src/router/index.js`. Esta linha é
-- o QUADRO: é por ela que `paineis.quadro_da_aba('PNL_1.7')` acha as colunas.
-- 🚨 Registro e roteador andam juntos -- `tests/teste_router.py` cobra os dois
-- sentidos e compara o caminho dos dois lados.
INSERT INTO painel_aba (painel, codigo_tela, titulo, ordem, ativo)
     SELECT 'compras', 'PNL_1.7', 'Compras', 1, true
      WHERE NOT EXISTS (SELECT 1 FROM painel_aba WHERE codigo_tela = 'PNL_1.7');

-- ---------------------------------------------------------------------------
-- 4. A COLUNA — uma, a dele
-- ---------------------------------------------------------------------------
-- ⚠️ `final = false`: "Nova solicitação" é onde o card NASCE, não um desfecho.
-- Marcá-la como final diria que chegar nela é terminar, e isso é falso.
INSERT INTO pipeline_etapa (aba_id, titulo, ordem, ativo, final)
     SELECT a.id, 'Nova solicitação', 1, true, false
       FROM painel_aba a
      WHERE a.codigo_tela = 'PNL_1.7'
        AND NOT EXISTS (SELECT 1 FROM pipeline_etapa e
                         WHERE e.aba_id = a.id
                           AND e.titulo = 'Nova solicitação');

-- ---------------------------------------------------------------------------
-- 5. O FORMULÁRIO
-- ---------------------------------------------------------------------------
-- ⚠️ O TÍTULO É A PALAVRA DELE: *"Sugestão de compras"*. O `slug` fica
-- `compras` porque é interno e não tem URL pública -- mas o slug é o que o
-- código cita (`etapa_de_destino(slug)`), então ele não muda depois sem motivo.
INSERT INTO formulario (codigo, slug, titulo, setor, botao, descricao,
                        ativo, ordem, gera_os, painel, interno, formato,
                        bitrix_id)
     SELECT 'COMPRAS', 'compras', 'Sugestão de compras', 'Administrativo',
            'Enviar sugestão',
            'Sugestão interna de compra. Vai para o painel de Compras.',
            false, 100, false, 'compras', true, 'classico', NULL
      WHERE NOT EXISTS (SELECT 1 FROM formulario WHERE codigo = 'COMPRAS');

-- ---------------------------------------------------------------------------
-- 6. OS CAMPOS — três linhas, e só DUAS para preencher
-- ---------------------------------------------------------------------------
-- 🚨 `CONTACT_NAME` NÃO É ENFEITE, E É A LINHA MAIS IMPORTANTE DO ARQUIVO.
-- `paineis._nome_do_chamado` lê **só** `COMPANY_TITLE` e `CONTACT_NAME`.
-- Compras não tem cliente -- tem solicitante. Com os dois nulos, o card fechado
-- escreveria literalmente *"cliente ?, fora do nosso cadastro"*
-- (`CorpoDoCard.vue:242-243`), que é tela que mente (`M12`). Chamando o campo
-- de `CONTACT_NAME`, o `registrar()` o chaveia assim em `valores` e o card
-- mostra quem pediu -- **sem uma linha alterada em `paineis.py` nem no
-- `CorpoDoCard.vue`**.
--
-- 🚨 E ELE NÃO É PERGUNTA: a rota interna injeta o nome de quem está logado em
-- `valores` ANTES do `validar()`, e a tela o mostra travado (prop `travados` do
-- `CamposDoFormulario`). Quem pede não digita o próprio nome, e não dá para
-- registrar outro no lugar -- se a rota confiasse no que a tela manda, bastaria
-- abrir o inspetor.
--
-- ⚠️ POR ISSO ELE FICA `visivel = true`, e não escondido: medido, `validar()`
-- DESCARTA valor de campo fora do visível (*"Escondido SOME, não vira
-- vazio"*). Campo invisível perderia o solicitante e o card voltaria a mentir.
-- ⚠️ E `fantasma` NÃO é campo oculto -- é o **placeholder** do input
-- (`CamposDoFormulario.vue:421,510,533`). Eu supus o contrário e conferi.
--
-- 🚨 O NOME DA CHAVE DECIDE O QUE O CARD FECHADO DIZ, E NÃO A COLUNA `ordem`.
-- `paineis._resumo` são as duas primeiras respostas de TEXTO **na ordem em que
-- o `valores` as devolve** -- e `valores` é `jsonb`, que REORDENA as chaves por
-- TAMANHO e depois por byte. Medido em 27/11:
--     '{"JUSTIFICATIVA":1,"CONTACT_NAME":2}'::jsonb
--       -> {"CONTACT_NAME": 2, "JUSTIFICATIVA": 1}
-- Ou seja: `CONTACT_NAME` (12 letras) passa na frente de `JUSTIFICATIVA` (13)
-- por mais que o campo seja o 3º na tela, e o card repetiria o nome que já é o
-- seu próprio título.
--
-- ⚠️ POR ISSO A CHAVE É `SUGESTAO` (8 letras) e não `JUSTIFICATIVA`: com 8 ela
-- vem antes das 12 do `CONTACT_NAME`, e o resumo passa a liderar com o que se
-- quer comprar. O RÓTULO na tela continua "Justificativa", que é a palavra
-- dele -- a chave é canalização interna, o rótulo é o que a pessoa lê.
-- 🚨 E `CONTACT_NAME` não pode ser renomeada para fugir disso:
-- `_nome_do_chamado` procura exatamente por este nome.
--
-- ⚠️ `nome` é a chave que vai para `formulario_solicitacao.valores`;
-- `nosso_nome` é o apelido legível que ajustes e etapas citam. Os dois seguem a
-- convenção já em uso (conferida no formulário 337).
INSERT INTO formulario_campo
       (formulario_id, nome, nosso_nome, rotulo, tipo, obrigatorio,
        multiplo, visivel, ordem, opcoes, ajuda, linhas)
     SELECT f.id, t.nome, t.nosso_nome, t.rotulo, t.tipo, t.obrigatorio,
            false, true, t.ordem, '[]'::jsonb, t.ajuda, t.linhas
       FROM formulario f
       CROSS JOIN (VALUES
         ('SUGESTAO',      'justificativa', 'Justificativa',
          'text',   true,  1,
          'O que precisa ser comprado e para quê.', 5),
         ('ANEXO',         'anexo',         'Anexo',
          'file',   false, 2,
          'Orçamento, foto ou print, se tiver.', NULL),
         ('CONTACT_NAME',  'solicitante',   'Solicitante',
          'string', true,  3,
          'Vem de quem está logado.', NULL)
       ) AS t(nome, nosso_nome, rotulo, tipo, obrigatorio, ordem, ajuda, linhas)
      WHERE f.codigo = 'COMPRAS'
        AND NOT EXISTS (SELECT 1 FROM formulario_campo c
                         WHERE c.formulario_id = f.id AND c.nome = t.nome);

-- ---------------------------------------------------------------------------
-- 7. O ELO QUE FAZ O ENVIO VIRAR CARD
-- ---------------------------------------------------------------------------
-- 🚨 É `formulario.etapa_destino_id`, E SÓ ELE. `main.py`, logo depois de
-- `registrar()`, chama `formularios.etapa_de_destino(slug)` e, se achar,
-- `pipeline.criar(...)`. Formulário sem destino não gera card -- é assim que o
-- de Contato e o de IDEIAS ficam fora de painel, de propósito.
--
-- ⚠️ ESTE UPDATE É O PASSO QUE NÃO PODE FALTAR. Sem ele o formulário existe, a
-- coluna existe, o envio grava -- e o card simplesmente não nasce. Na tela isso
-- é um card que falta, e ninguém sabe que deveria estar lá.
UPDATE formulario f
   SET etapa_destino_id = e.id,
       atualizado_em    = now()
  FROM pipeline_etapa e
  JOIN painel_aba a ON a.id = e.aba_id
 WHERE f.codigo = 'COMPRAS'
   AND a.codigo_tela = 'PNL_1.7'
   AND e.titulo = 'Nova solicitação'
   AND f.etapa_destino_id IS DISTINCT FROM e.id;

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('122', now(),
        'painel de Compras (PNL_1.7) com 1 coluna, formulario COMPRAS interno '
        'sem OS (justificativa + anexo), e a coluna formulario.interno');

COMMIT;

-- ============================================================================
-- CONFERÊNCIA (rodar depois, e o esperado está escrito)
-- ============================================================================
--   SELECT painel, codigo_tela, titulo FROM painel_aba ORDER BY painel, ordem;
--     -- esperado: compras/PNL_1.7 · contratual/PNL_1.5 · financeiro/PNL_1.4 +
--     --           PNL_1.6 · operacao/PNL_1.1 · pos_venda/PNL_1.2 + PNL_1.3
--
--   SELECT e.ordem, e.titulo, e.ativo, e.final FROM pipeline_etapa e
--     JOIN painel_aba a ON a.id = e.aba_id
--    WHERE a.codigo_tela = 'PNL_1.7' ORDER BY e.ordem;
--     -- esperado: UMA linha -- 1 | Nova solicitação | t | f
--
--   SELECT codigo, slug, titulo, ativo, interno, gera_os, painel,
--          etapa_destino_id
--     FROM formulario WHERE codigo = 'COMPRAS';
--     -- esperado: COMPRAS | compras | Sugestão de compras | f | t | f |
--     --           compras | <id da etapa acima>
--     -- 🚨 `ativo = f` é o certo: quem liga é ele, pela FRM_1.1.
--
--   SELECT ordem, nome, nosso_nome, rotulo, tipo, obrigatorio
--     FROM formulario_campo
--    WHERE formulario_id = (SELECT id FROM formulario WHERE codigo = 'COMPRAS')
--    ORDER BY ordem;
--     -- esperado: TRÊS linhas, nesta ordem --
--     --   1 | SUGESTAO     | justificativa | Justificativa | text   | t
--     --   2 | ANEXO        | anexo         | Anexo         | file   | f
--     --   3 | CONTACT_NAME | solicitante   | Solicitante   | string | t
--     -- 🚨 `SUGESTAO` tem 8 letras e `CONTACT_NAME` tem 12: é isso, e não a
--     --    coluna `ordem`, que faz o RESUMO do card liderar com o que se quer
--     --    comprar (o `valores` é jsonb e reordena por tamanho de chave).
--     --    E o `CONTACT_NAME` é o que faz o TÍTULO do card dizer quem pediu,
--     --    em vez de "cliente ?, fora do nosso cadastro".
--
--   -- A PROVA QUE VALE, rodada na cópia em 27/11:
--   --   cliente = 'Iago (do login)'      <- título do card
--   --   resumo  = 'Cabo de rede cat6 … · Iago (do login)'
--   --   origem  = 'chamado' · numero_os/numero_ordem/situacao_id = None
--
--   SELECT count(*) FROM formulario WHERE interno;
--     -- esperado: 1 -- nenhum dos 16 de hoje virou interno
--
--   SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
--    WHERE conname IN ('painel_aba_painel_conhecido', 'formulario_painel_check');
--     -- esperado: os dois com 'compras' na lista
-- ============================================================================
