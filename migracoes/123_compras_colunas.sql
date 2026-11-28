-- ===========================================================================
-- 123 — Compras: as três colunas seguintes e o campo de valor (27/11)
-- ===========================================================================
-- 🔵 Ele, 27/11, decidindo depois de ver o mockup: as colunas são
-- **"Em cotação + Aprovado + Comprado"**, e o valor estimado entra como
-- **"só o campo"** -- sem o painel somar nem ordenar por ele.
--
-- 🚨 POR QUE AS DUAS COISAS NA MESMA MIGRAÇÃO, e isto é desvio do plano com
-- motivo. Eu havia escrito que o campo de formulário é **dado**, não migração
-- -- a frase da casa é *"formulário novo é linha em tabela"*. 📏 Medido hoje:
-- não existe rota, tela nem script que acrescente campo a um formulário que
-- **não vem do Bitrix**. O `gravar_definicao()` monta campos a partir do bruto
-- do loader e é idempotente pelo `bitrix_id`; o COMPRAS tem `bitrix_id NULL`.
-- Então, para este formulário, *"é dado"* significaria **SQL sem rastro** --
-- um `INSERT` solto que ninguém acha depois. A migração é o rastro.
--
-- 🚨 E A MESMA MIGRAÇÃO POR UM SEGUNDO MOTIVO: as colunas mudam o GESTO (o
-- card passa a ter para onde ir) e o campo muda o RESUMO. Separá-las deixaria
-- uma rodada em que a tela promete mover e o card não tem o valor que o resumo
-- vai liderar -- meio deploy é comportamento invertido, e o `M16` existe por
-- isso.
--
-- ⚠️ NÃO MEXE EM ESTRUTURA. Nenhum CREATE, ALTER, CHECK ou índice: só linhas
-- de configuração. O diff de esquema de antes e depois tem de sair **vazio**, e
-- é essa a conferência que ele pediu (*"comparar depois, revalidar e garantir
-- entrega"*).
-- ===========================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. AS TRÊS COLUNAS SEGUINTES
-- ---------------------------------------------------------------------------
-- 🚨 `final = true` SÓ NA ÚLTIMA. É o `final` que diz ao quadro onde o card
-- termina: sem ele o Finalizar não tem desfecho natural e o contador de
-- *"parado nesta etapa desde"* nunca fecha. Marcar as três como final faria o
-- quadro tratar `Em cotação` como conclusão.
--
-- ⚠️ `depois_da_situacao` e `recebe_situacao` ficam NULAS, de propósito: são o
-- casamento com as situações do Harmonit, e Compras não tem OS. Preencher
-- qualquer uma das duas ligaria o semeador de OS a este painel.
--
-- ⚠️ IDEMPOTENTE PELO TÍTULO dentro da aba: rodar duas vezes não duplica.
INSERT INTO pipeline_etapa (aba_id, titulo, ordem, ativo, final)
     SELECT a.id, t.titulo, t.ordem, true, t.final
       FROM painel_aba a
       CROSS JOIN (VALUES
         ('Em cotação', 2, false),
         ('Aprovado',   3, false),
         ('Comprado',   4, true)
       ) AS t(titulo, ordem, final)
      WHERE a.codigo_tela = 'PNL_1.7'
        AND NOT EXISTS (SELECT 1 FROM pipeline_etapa e
                         WHERE e.aba_id = a.id AND e.titulo = t.titulo);

-- ---------------------------------------------------------------------------
-- 2. O CAMPO DE VALOR, E A ORDEM DOS QUE JÁ EXISTIAM
-- ---------------------------------------------------------------------------
-- 🚨 OS DOIS DE BAIXO DESCEM UMA CASA PRIMEIRO. A ordem na tela sai de
-- `ORDER BY ordem, id` (`formularios.definicao`), e o valor tem de vir logo
-- depois da justificativa -- quem informa preço acabou de escrever o que quer
-- comprar. Inserir em 2 sem descer os outros deixaria dois campos na ordem 2 e
-- a tela decidiria pelo `id`, que é ordem de criação: o valor cairia por
-- último, depois do Solicitante.
--
-- ⚠️ IDEMPOTENTE: cada UPDATE tem o destino explícito e a guarda `<>`.
UPDATE formulario_campo c
   SET ordem = 3
  FROM formulario f
 WHERE f.id = c.formulario_id
   AND f.codigo = 'COMPRAS'
   AND c.nome = 'ANEXO'
   AND c.ordem <> 3;

UPDATE formulario_campo c
   SET ordem = 4
  FROM formulario f
 WHERE f.id = c.formulario_id
   AND f.codigo = 'COMPRAS'
   AND c.nome = 'CONTACT_NAME'
   AND c.ordem <> 4;

-- 🚨 A CHAVE TEM 5 LETRAS DE PROPÓSITO, e isto é a armadilha que já me custou
-- uma correção hoje. `formulario_solicitacao.valores` é `jsonb`, e `jsonb`
-- **ordena a chave por TAMANHO**, depois por bytes -- não pela coluna `ordem`.
-- O resumo do card fechado são as duas primeiras respostas de texto nessa
-- ordem. Com `VALOR` (5) < `SUGESTAO` (8) < `CONTACT_NAME` (12), o resumo
-- passa a ler:
--
--     R$ 184,00 · Cabo de rede cat6, 20 metros
--
-- que é o que se decide olhando a coluna. `VALOR_ESTIMADO` (15) cairia para o
-- fim e **não apareceria no resumo**, exatamente como aconteceu com o
-- `JUSTIFICATIVA` (13), que perdia para o `CONTACT_NAME` e fazia o card
-- repetir o nome que já é o título.
--
-- ⚠️ `tipo = 'string'`, NÃO `double`. O `double` da casa é CNPJ, CPF, RG e
-- quantidade, e ele valida como número: *"R$ 184,00"* seria recusado. O campo
-- é texto, e o que diz o formato é a `ajuda`.
--
-- ⚠️ `obrigatorio = false`, e é decisão de desenho: quem pede nem sempre sabe
-- o preço, e campo obrigatório que ninguém consegue preencher vira número
-- inventado -- pior que vazio, porque parece dado.
--
-- 🚨 O PAINEL NÃO SOMA NEM ORDENA POR ELE -- escolha dele em 27/11 (*"só o
-- campo"*). Isto está escrito no `docs/06` para ninguém esperar o total.
INSERT INTO formulario_campo
       (formulario_id, nome, nosso_nome, rotulo, tipo, obrigatorio,
        multiplo, visivel, ordem, opcoes, ajuda, linhas)
     SELECT f.id, 'VALOR', 'valor', 'Valor estimado',
            'string', false,
            false, true, 2, '[]'::jsonb,
            'Se souber. Pode ser aproximado -- ex.: R$ 180,00.', NULL
       FROM formulario f
      WHERE f.codigo = 'COMPRAS'
        AND NOT EXISTS (SELECT 1 FROM formulario_campo c
                         WHERE c.formulario_id = f.id AND c.nome = 'VALOR');

-- ---------------------------------------------------------------------------
-- 3. O DESTINO NÃO MUDA
-- ---------------------------------------------------------------------------
-- ⚠️ `formulario.etapa_destino_id` continua apontando para `Nova solicitação`,
-- e é o certo: o card nasce na primeira coluna e anda por gesto de gente. Esta
-- migração NÃO toca aquele campo -- se ele apontasse para `Comprado`, todo
-- envio nasceria concluído.

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('123', now(),
        'Compras: as colunas Em cotacao, Aprovado e Comprado (final) na aba '
        'PNL_1.7, e o campo VALOR no formulario COMPRAS -- so o campo, o '
        'painel nao soma');

COMMIT;

-- ============================================================================
-- CONFERÊNCIA (rodar depois, e o esperado está escrito)
-- ============================================================================
--   SELECT e.ordem, e.titulo, e.ativo, e.final, e.depois_da_situacao,
--          e.recebe_situacao
--     FROM pipeline_etapa e JOIN painel_aba a ON a.id = e.aba_id
--    WHERE a.codigo_tela = 'PNL_1.7' ORDER BY e.ordem;
--     -- esperado: QUATRO linhas, nesta ordem, as duas últimas colunas NULAS --
--     --   1 | Nova solicitação | t | f
--     --   2 | Em cotação       | t | f
--     --   3 | Aprovado         | t | f
--     --   4 | Comprado         | t | T   <- só esta
--
--   SELECT a.codigo_tela, count(*) FROM pipeline_etapa e
--     JOIN painel_aba a ON a.id = e.aba_id GROUP BY 1 ORDER BY 1;
--     -- 🚨 A CONFERÊNCIA QUE IMPORTA: a contagem POR ABA. O risco de um
--     --    INSERT com JOIN errado é pôr coluna no Financeiro, e o total
--     --    geral não acusaria isso. Só a `PNL_1.7` pode ter mudado.
--
--   SELECT ordem, nome, rotulo, tipo, obrigatorio FROM formulario_campo
--    WHERE formulario_id = (SELECT id FROM formulario WHERE codigo = 'COMPRAS')
--    ORDER BY ordem, id;
--     -- esperado: QUATRO linhas, nesta ordem --
--     --   1 | SUGESTAO     | Justificativa  | text   | t
--     --   2 | VALOR        | Valor estimado | string | f
--     --   3 | ANEXO        | Anexo          | file   | f
--     --   4 | CONTACT_NAME | Solicitante    | string | t
--
--   SELECT etapa_destino_id = (SELECT e.id FROM pipeline_etapa e
--                                JOIN painel_aba a ON a.id = e.aba_id
--                               WHERE a.codigo_tela = 'PNL_1.7'
--                                 AND e.titulo = 'Nova solicitação')
--     FROM formulario WHERE codigo = 'COMPRAS';
--     -- esperado: t -- o card continua nascendo na PRIMEIRA coluna
--
--   SELECT count(*) FROM formulario WHERE codigo = 'COMPRAS' AND ativo;
--     -- esperado: 0 -- quem liga o formulário é ele, pela FRM_1.1
--
--   -- E O DIFF DE ESQUEMA DE ANTES E DEPOIS TEM DE SAIR VAZIO:
--   --   scripts/retrato.py esquema movizap /tmp/S2.sql
--   --   diff /tmp/S1.sql /tmp/S2.sql
--   -- 🚨 Esta migração só insere LINHA. Estrutura diferente aqui é defeito.
-- ============================================================================
