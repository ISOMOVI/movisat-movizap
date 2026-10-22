"""O unico vermelho da suite, e ele e a mudanca pedida.

`test_inicio_e_email_tem_nome_de_verdade` defendia que INI e EML nao saem
CRUS no menu (antes de 21/10 nao estavam no mapa e apareciam como "EML").
Essa defesa continua valendo e continua aqui. O que muda e o destino do
EML_1.1, por decisao dele em 22/10.
"""
import shutil
import sys

ALVO = "tests/teste_menu_grupos.py"

ANTES = '''    def test_inicio_e_email_tem_nome_de_verdade(self):
        """Antes de hoje `INI` e `EML` não estavam no mapa do menu e saíam crus."""
        por_codigo = {t["codigo"]: t for t in telas.do_usuario({"owner": True})}
        assert por_codigo["INI_1.1"]["grupo"] == "Início"
        assert por_codigo["EML_1.1"]["grupo"] == "E-mail"'''

DEPOIS = '''    def test_inicio_e_email_tem_nome_de_verdade(self):
        """Antes de 21/10 `INI` e `EML` não estavam no mapa do menu e saíam crus.

        🔵 22/10: o E-mail passou a morar DENTRO de "Atendimento", abaixo do
        Chat interno (*"pessoal deu feedback que é melhor nessa ordem"*), e ele
        confirmou que é só visual -- o módulo continua `EML`, com rota, caixa e
        permissão próprias. Por isso o grupo esperado mudou e o resto não.

        🚨 A DEFESA ORIGINAL CONTINUA AQUI, e é a segunda linha de cada par:
        o que este teste existe para impedir é o grupo sair CRU ("EML", "INI").
        Trocar o destino do EML não pode levar essa garantia embora.
        """
        por_codigo = {t["codigo"]: t for t in telas.do_usuario({"owner": True})}
        assert por_codigo["INI_1.1"]["grupo"] == "Início"
        assert por_codigo["INI_1.1"]["grupo"] != "INI"
        assert por_codigo["EML_1.1"]["grupo"] == "Atendimento"
        assert por_codigo["EML_1.1"]["grupo"] != "EML"

    def test_o_fallback_do_EML_continua_apontando_para_E_mail(self):
        """⚠️ O grupo do EML_1.1 agora vem GRAVADO na tela, não do prefixo --
        mas o fallback tem de continuar correto. Tela sem `grupo` (backend um
        passo atrás da tela, que o `M16` diz que acontece) cai aqui, e cair
        em "E-mail" é degradar; cair em "EML" seria rótulo cru na tela."""
        assert telas.grupo_da({"codigo": "EML_1.1"}) == "E-mail"

    def test_o_grupo_E_mail_ficou_declarado_e_vazio(self):
        """🚨 TELA QUE MENTE É DEFEITO, e grupo vazio não mente: ele existe no
        registro e o `MenuLateral` não desenha grupo sem tela visível -- como
        "Painéis › Operacional" desde 19/10. Este teste é o que impede alguém
        "limpar" a entrada de GRUPOS e levar o fallback de cima com ela."""
        assert "E-mail" in telas.GRUPOS
        assert not [t for t in telas.ativas() if telas.grupo_da(t) == "E-mail"]'''


def main() -> int:
    texto = open(ALVO, encoding="utf-8").read()
    if texto.count(ANTES) != 1:
        raise SystemExit(f"achei {texto.count(ANTES)} ocorrencias, esperava 1")
    shutil.copyfile(ALVO, ALVO + ".bak_2026-10-22_atendimento")
    open(ALVO, "w", encoding="utf-8").write(texto.replace(ANTES, DEPOIS, 1))
    print("ok: tests/teste_menu_grupos.py (com .bak)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
