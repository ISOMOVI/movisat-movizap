"""Os testes da senha de 1 dia (15/10)."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ALVO = RAIZ / "tests" / "teste_ligacoes_alistar.py"
texto = ALVO.read_text(encoding="utf-8")

VELHO = '    assert r["segundos"] <= ligacoes_alistar.JANELA_S'
NOVO = '''    # 🔵 15/10: a senha vale 1 DIA, e o prazo informado é o REAL -- enquanto
    # media só a janela de geração, a ferramenta dizia "7 min" de uma senha
    # que valia um dia.
    assert r["segundos"] > 20 * 3600
    assert r["segundos"] <= ligacoes_alistar.JANELAS_ACEITAS * ligacoes_alistar.JANELA_S'''

EXTRA = '''

class TestSenhaDeUmDia:
    """🔵 15/10: *"podemos prolongar as senhas para 1 dia por enquanto?"*.

    🚨 O que estes testes guardam é a SEPARAÇÃO entre as duas coisas: a senha
    TROCA a cada 10 minutos e é ACEITA por 24 h. Se alguém "simplificar" isso
    pondo `JANELA_S = 86400`, o `UNIQUE (ramal, janela)` passa a significar um
    alistamento por ramal por dia -- e um alistamento que falhe no meio tranca
    o ramal até o dia seguinte.
    """

    def test_a_senha_troca_a_cada_dez_minutos(self):
        assert ligacoes_alistar.JANELA_S == 600, (
            "mexer na janela de GERAÇÃO troca o prazo de retentativa: "
            "uma falha passaria a custar o tamanho da janela")

    def test_e_e_aceita_por_um_dia(self):
        assert (ligacoes_alistar.JANELAS_ACEITAS
                * ligacoes_alistar.JANELA_S) == 24 * 3600

    def test_senha_de_ontem_a_noite_ainda_serve(self):
        """23 h atrás: é o caso dele, de ditar a senha hoje e a pessoa rodar o
        instalador amanhã de manhã."""
        pessoa("99130")
        import time as _t
        janela_velha = ligacoes_alistar.janela_de(_t.time() - 23 * 3600)
        senha = ligacoes_alistar.senha_da_janela("99130", janela_velha)
        r = ligacoes_alistar.alistar("99130", senha, pedido("99130"), pc="PC-VELHA")
        assert r["ok"] and r["ramal"] == "99130"

    def test_senha_de_mais_de_um_dia_nao_serve(self):
        pessoa("99131")
        import time as _t
        janela_antiga = ligacoes_alistar.janela_de(_t.time() - 25 * 3600)
        senha = ligacoes_alistar.senha_da_janela("99131", janela_antiga)
        with pytest.raises(ligacoes_alistar.SenhaInvalida):
            ligacoes_alistar.alistar("99131", senha, pedido("99131"), pc="PC-ANTIGA")

    def test_continua_de_uso_unico_dentro_do_dia(self):
        """Valer um dia não é poder usar duas vezes: a primeira utilização
        queima a janela."""
        pessoa("99132")
        senha = senha_de("99132")
        assert ligacoes_alistar.alistar("99132", senha, pedido("99132"),
                                        pc="PC-UM")["ok"]
        with pytest.raises(ligacoes_alistar.SenhaInvalida):
            ligacoes_alistar.alistar("99132", senha, pedido("99132"), pc="PC-DOIS")

    def test_uma_janela_queimada_nao_tranca_a_seguinte(self):
        """🚨 É O MOTIVO DE A GERAÇÃO FICAR EM 10 MIN. Queimada a senha de
        agora, a de 10 minutos atrás (ou a da próxima janela) continua
        servindo -- é isso que faz "peça outra senha" funcionar."""
        pessoa("99133")
        import time as _t
        agora = ligacoes_alistar.janela_de()
        assert ligacoes_alistar.alistar(
            "99133", ligacoes_alistar.senha_da_janela("99133", agora),
            pedido("99133"), pc="PC-A")["ok"]
        anterior = ligacoes_alistar.janela_de(_t.time() - 600)
        assert anterior != agora
        assert ligacoes_alistar.alistar(
            "99133", ligacoes_alistar.senha_da_janela("99133", anterior),
            pedido("99133"), pc="PC-B")["ok"]
'''

if "class TestSenhaDeUmDia:" in texto:
    print("ja aplicado")
else:
    assert texto.count(VELHO) == 1, f"ancora {texto.count(VELHO)}x"
    novo = texto.replace(VELHO, NOVO, 1).rstrip("\n") + "\n" + EXTRA
    compile(novo, str(ALVO), "exec")
    ALVO.write_text(novo, encoding="utf-8")
    print("aplicado")
