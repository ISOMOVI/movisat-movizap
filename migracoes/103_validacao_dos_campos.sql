-- 103 — a validação declarada nos 14 formulários (o padrão do Suporte)
--
-- 🔵 Pedido dele (11/11): *"Os formulários devem seguir como a padronização do
-- formulário de suporte, no quesito de estilo, validação de campos, disposição e
-- lógica"* · *"o formulario suporte é a base, os erros de bitrix ficam para tras,
-- ja temos validações uteis no suporte"*.
--
-- 🚨 O BURACO QUE ISTO FECHA, MEDIDO EM 11/11: os 14 formulários tinham **215
-- campos e ZERO validação declarada**. Aceitavam CNPJ inválido, telefone de três
-- dígitos e e-mail sem arroba — porque herdamos a definição do Bitrix e
-- herdamos o buraco dele (*"o servidor deles não valida obrigatório"*).
--
-- 🚨 POR LISTA EXPLÍCITA, NUNCA POR `LIKE`. Um `LIKE '%cnpj%'` pegaria também o
-- campo **`cnpj-e-nome-da-empresa-que-sera-transferida`**, que pede CNPJ **e
-- nome na mesma caixa** — e passaria a RECUSAR a resposta certa
-- ("12.345.678/0001-90 Acme Ltda"). É a mesma armadilha do *"Veículo e Placa"*
-- do Suporte, que está anotada em `movizap/formularios.py`: por isso a placa
-- nunca entrou na conferência de tamanho de documento.
--
-- ⚠️ O QUE NÃO GANHA VALIDAÇÃO, E POR QUÊ:
--   · `rg` — não há dígito verificador padrão: cada estado emite o seu, e
--     recusar formato aqui recusaria RG de verdade;
--   · `cnpj-e-nome-da-empresa-que-sera-transferida` — dois dados numa caixa
--     (ver acima);
--   · `website` — não há validação de URL no catálogo, e inventar uma recusaria
--     `movisat.com.br` escrito sem `https://`;
--   · `data-*` — o campo é `date` e o navegador já cuida;
--   · os `list` — o valor vem de uma lista fechada, não há o que conferir.
--
-- 🚨 ISTO NÃO ACRESCENTA NEM REMOVE CAMPO, e é a régua dele: *"Os formulários
-- que não tem os dados que existem no suporte, por exemplo, não inventar - Só
-- ajustar"*. Nenhuma linha aqui mexe em `obrigatorio`.
--
-- ⚠️ E A VALIDAÇÃO NÃO É BARREIRA DE NAVEGADOR: quem recusa o envio é o
-- servidor (`formularios.validar`), e esta coluna é o que ele lê. A máscara e a
-- frase que a pessoa vê saem do mesmo dado.

BEGIN;

-- E-mail: o `tipo` já diz (14 campos), mais UM que veio como texto do Bitrix.
UPDATE formulario_campo SET validacao = 'email'
 WHERE validacao IS NULL
   AND (tipo = 'email' OR nosso_nome = 'e-mail-do-novo-titular');

-- Telefone: idem (15 campos), mais o do novo titular, que veio como texto.
UPDATE formulario_campo SET validacao = 'telefone'
 WHERE validacao IS NULL
   AND (tipo = 'phone' OR nosso_nome = 'telefone-com-ddd-do-novo-titular');

-- Documentos: por NOME EXATO. O `tipo` do Bitrix é `double` em CNPJ, CPF e RG
-- (o tipo sugere número decimal e o campo é documento) -- então o tipo não
-- serve para decidir aqui, e o nome serve.
UPDATE formulario_campo SET validacao = 'cnpj'
 WHERE validacao IS NULL AND nosso_nome = 'cnpj';

UPDATE formulario_campo SET validacao = 'cpf'
 WHERE validacao IS NULL AND nosso_nome = 'cpf';

UPDATE formulario_campo SET validacao = 'cep'
 WHERE validacao IS NULL AND nosso_nome = 'cep';

-- A placa: o campo é "Veículo e placa", e a conferência PROCURA a placa dentro
-- do texto (não exige que o texto SEJA a placa) -- `SAVEIRO ABC1234` é resposta
-- certa. É a mesma função do Suporte.
UPDATE formulario_campo SET validacao = 'placa'
 WHERE validacao IS NULL AND nosso_nome = 'veiculo-e-placa';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('103', now(), 'validacao declarada nos campos dos 14 formularios (padrao do Suporte)');

COMMIT;
