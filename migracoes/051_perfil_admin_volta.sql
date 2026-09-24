-- ============================================================================
-- MoviZap — migração 051: `admin` volta ao vocabulário de perfil
--
-- 🔵 Decisão dele em 24/09: *"o perfil admin deve possuir exibição de telas de
-- atendimento + Times + Atendentes + Configurações > Minha conta, apenas"*.
--
-- ⚠️ NÃO É O ADMIN QUE A 024 TIROU. Aquele destravava duas telas que não
-- existiam. Este destrava `atendimento` + `equipe` (Times e Atendentes), e o
-- alcance está em `telas.PERFIS`, não aqui -- o banco só aceita o nome.
--
-- 🚨 O OWNER CONTINUA ÚNICO. O admin administra a equipe, mas não mexe na
-- conta do owner nem cria outro admin: a trava está nas rotas de `main.py`
-- (`_so_owner_mexe_no_owner`, `_so_owner_da_admin`). O e-mail do owner é a
-- chave da conta dele; um admin que pudesse trocá-lo viraria owner.
-- ============================================================================

ALTER TABLE atendente DROP CONSTRAINT IF EXISTS atendente_perfil_check;
ALTER TABLE atendente ADD CONSTRAINT atendente_perfil_check
    CHECK (perfil IN ('owner', 'admin', 'atendimento', 'cadastro'));

INSERT INTO schema_migracao (versao, aplicada_em, descricao)
VALUES ('051', now(), 'perfil admin volta: atendimento + equipe');
