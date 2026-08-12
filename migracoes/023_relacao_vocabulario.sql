-- ============================================================================
-- MoviZap — migração 023: `contato.relacao` ganha `colaborador` e `teste`
--
-- Pedido do usuário em 12/08: o cadastro precisa dizer o que a pessoa é —
-- técnico, cliente, colaborador, teste, fornecedor, lead. Faltavam dois.
--
-- 🚨 O VOCABULÁRIO CRESCEU, MAS NINGUÉM FOI RECLASSIFICADO. Medido antes de
-- escrever isto: 1.751 dos 1.752 contatos estão como 'cliente'. Não é que a
-- base seja toda de clientes -- é que `sync._gravar_contato` grava
-- `relacao = 'cliente'` LITERAL, para todo mundo que vem do Harmonit. O
-- número não mede a realidade, mede uma constante no código.
--
-- 🚨 NÃO EXISTE CHAVE DURA DE FORNECEDOR, e por isso este arquivo não marca
-- ninguém. O `docs/12` diz "os IDs 141–193 são uma faixa contígua de
-- fornecedores"; conferido linha a linha em 12/08, a faixa é `cliente.id`
-- (bigserial local, não chave de negócio) e NÃO é contígua de fornecedor:
-- convivem ali fornecedor de verdade (vivo, SUNTECH, concox, ESEYE, NIATRON,
-- HINOVA), cliente de verdade (Rodovias do Tietê, CEASA CAMPINAS, THYSSEN
-- KRUPP, ITAU EMPRESAS, IMA INFORMATICA, Pague Menos) e lixo ('a', 'FERNANDO
-- apagar', 'RETIRADA MOVISAT', um telefone e dois CNPJs no campo nome).
-- Marcar a faixa inteira transformaria cliente pagante em fornecedor no
-- cadastro. Quem classifica é gente, na CAD_1.2.
--
-- ⚠️ A MARCAÇÃO SOBREVIVE AO SYNC. O `ON CONFLICT ... DO UPDATE` de
-- `_gravar_contato` atualiza nome, e-mail, cliente_id e ativo -- e NÃO toca
-- em `relacao`. Então o que uma pessoa marcar aqui não é desfeito amanhã.
--
-- ⚠️ CHECK é contrato (docs/02). Ampliar vocabulário é decisão, e fica
-- registrado aqui para quem ler o histórico saber quando o valor nasceu.
-- ============================================================================

ALTER TABLE contato DROP CONSTRAINT IF EXISTS contato_relacao_check;
ALTER TABLE contato ADD CONSTRAINT contato_relacao_check
    CHECK (relacao IN ('cliente', 'fornecedor', 'parceiro', 'tecnico',
                       'lead', 'colaborador', 'teste'));

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('023', now(), 'contato.relacao aceita colaborador e teste');
