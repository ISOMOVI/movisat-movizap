-- 104 — dois campos que o Bitrix tipou errado, e por isso o SERVIDOR não os via
--
-- 🔵 Ele, 11/11: *"o formulario suporte é a base, os erros de bitrix ficam para
-- tras, ja temos validações uteis no suporte"*.
--
-- 🚨 O PROBLEMA MEDIDO: a validação do servidor (`formularios._um_valor`) decide
-- pelo **`tipo`** nos casos de e-mail e telefone — `tipo = 'email'` roda o regex,
-- `tipo = 'phone'` normaliza pelo módulo da casa. E dois campos do formulário de
-- transferência vieram do Bitrix como **`string`**:
--
--   · `e-mail-do-novo-titular`
--   · `telefone-com-ddd-do-novo-titular`
--
-- Com eles em `string`, a migração 103 lhes deu `validacao`, mas **só o
-- navegador** aplicaria: o servidor cairia no ramo genérico de texto e aceitaria
-- `abc` como e-mail do novo titular. 🚨 **E é justamente o campo que identifica
-- quem passa a ser o dono do contrato.**
--
-- ⚠️ ISTO NÃO ACRESCENTA NEM REMOVE CAMPO — é o mesmo campo, com o tipo que ele
-- sempre deveria ter. A régua dele (*"não inventar - Só ajustar"*) está de pé.
--
-- ⚠️ E muda o WIDGET junto, de propósito: `email` dá teclado de e-mail no
-- celular, `phone` dá o teclado numérico e a máscara. Era o que faltava para
-- esses dois campos parecerem com os do Suporte.
--
-- 🚨 O QUE ESTA MIGRAÇÃO **NÃO** FAZ: conferir dígito verificador de CNPJ/CPF no
-- servidor. Hoje ele garante o FORMATO (quantidade de caracteres) e a frase que
-- a pessoa lê vem da tela — está escrito em `formularios.py:294-297` que passar a
-- recusar DV no servidor **é mudança de régua, e régua é decisão dele**.

BEGIN;

UPDATE formulario_campo SET tipo = 'email'
 WHERE nosso_nome = 'e-mail-do-novo-titular' AND tipo = 'string';

UPDATE formulario_campo SET tipo = 'phone'
 WHERE nosso_nome = 'telefone-com-ddd-do-novo-titular' AND tipo = 'string';

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('104', now(), 'o tipo certo em e-mail e telefone do novo titular (vinham string do Bitrix)');

COMMIT;
