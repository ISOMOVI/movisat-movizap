-- ============================================================================
-- MoviZap — migração 024: `admin` sai do vocabulário de perfil
--
-- Decisão do usuário em 12/08: **owner é o único administrador, e não nascem
-- mais owners.** O `admin` existia como perfil e como permissão, e destravava
-- exatamente duas telas -- `CFG_2.2` (Fase 2) e `REL_1.1` (Fase 3) --,
-- nenhuma das quais existe. Na prática seu alcance era idêntico ao de
-- `atendimento` + `cadastro`.
--
-- 🚨 A DOC PROMETIA O QUE O CÓDIGO NÃO DAVA. O `03_Registro_Telas` listava
-- Canais, Sincronização, Classificações, Atendentes, Times e IA-prompt como
-- `admin`; no código as seis sempre foram `owner`, e `pode_acessar` recusa
-- tela `owner` a quem não é owner. Quem lesse a doc criaria um admin e levaria
-- 403 sem entender. As duas fontes só param de divergir quando uma delas
-- deixa de existir -- e quem sai é a que ninguém usava.
--
-- ⚠️ ESTA MIGRAÇÃO RECUSA RODAR SE AINDA EXISTIR ALGUÉM COM `perfil='admin'`,
-- e isso é de propósito. `permissoes_do_perfil` devolve conjunto VAZIO para
-- perfil desconhecido -- ou seja, menu vazio. Converter no escuro deixaria
-- alguém sem acesso sem nada acusar; o CHECK falhando é ruidoso e reversível.
-- Medido antes de escrever: 1 `owner` e 3 `atendimento`, nenhum `admin`.
-- ============================================================================

ALTER TABLE atendente DROP CONSTRAINT IF EXISTS atendente_perfil_check;
ALTER TABLE atendente ADD CONSTRAINT atendente_perfil_check
    CHECK (perfil IN ('owner', 'atendimento', 'cadastro'));

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('024', now(), 'perfil de atendente perde o valor admin');
