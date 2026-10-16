"""Bloco 8: os testes da sessao do dia, acrescentados ao `teste_auth.py`."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
caminho = RAIZ / "tests" / "teste_auth.py"
texto = caminho.read_text(encoding="utf-8")

MARCA = "class TestSessaoDoDia:"
NOVO = '''

class TestSessaoDoDia:
    """🔵 15/10 — o token vale até a VIRADA DO DIA, no fuso do escritório.

    O que estes testes guardam:
      · a virada é a de São Paulo, não a de UTC (em UTC ela cairia às 21h de
        Brasília, em plena tarde de trabalho);
      · o PISO de 2 horas: quem entra às 23:30 não cai às 00:00;
      · o piso não rouba dia de quem tem folga de sobra;
      · a expiração que a tela recebe é a MESMA que o token obedece.
    """

    FUSO = auth.FUSO_DO_DIA

    def quando(self, ano, mes, dia, hora, minuto=0):
        return datetime(ano, mes, dia, hora, minuto, tzinfo=self.FUSO)

    def test_entrou_de_manha_vale_ate_a_meia_noite_do_mesmo_dia(self):
        fim = auth.expira_na_virada(self.quando(2026, 10, 15, 8)).astimezone(self.FUSO)
        assert (fim.year, fim.month, fim.day, fim.hour) == (2026, 10, 16, 0)

    def test_a_virada_e_a_de_sao_paulo_e_nao_a_de_utc(self):
        fim = auth.expira_na_virada(self.quando(2026, 10, 15, 8))
        # 00:00 de Brasília é 03:00 UTC. Se fosse a virada de UTC, quem entrou
        # de manhã cairia às 21h de Brasília -- no meio da tarde.
        assert fim.utcoffset().total_seconds() == 0, "a conta sai em UTC"
        assert fim.hour == 3

    def test_quem_entra_colado_na_virada_nao_cai_em_meia_hora(self):
        fim = auth.expira_na_virada(self.quando(2026, 10, 15, 23, 30)).astimezone(self.FUSO)
        assert (fim.month, fim.day, fim.hour) == (10, 17, 0), "o piso de 2h falhou"

    def test_duas_horas_exatas_ainda_valem_o_mesmo_dia(self):
        """O piso é "menos de 2 horas". Às 22:00 em ponto sobram 2 horas
        cheias, e o turno termina na virada desta noite."""
        fim = auth.expira_na_virada(self.quando(2026, 10, 15, 22)).astimezone(self.FUSO)
        assert (fim.month, fim.day) == (10, 16)

    def test_o_piso_nao_rouba_dia_de_quem_tem_folga(self):
        fim = auth.expira_na_virada(self.quando(2026, 10, 15, 21, 59)).astimezone(self.FUSO)
        assert (fim.month, fim.day) == (10, 16)

    def test_o_token_obedece_a_mesma_hora_que_a_tela_recebe(self):
        token, expira = auth.criar_token_e_expiracao("movizap")
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[auth.ALGORITMO])
        assert payload["exp"] == int(expira.timestamp())
        # E é no futuro: token nascendo vencido derrubaria todo mundo.
        assert expira > datetime.now(timezone.utc)

    def test_criar_token_continua_devolvendo_so_o_texto(self):
        """`criar_token` é chamado em dois lugares (senha e Google) e em vários
        testes: a assinatura não mudou."""
        assert isinstance(auth.criar_token("movizau"), str)

    def test_get_usuario_carrega_a_expiracao_do_token_validado(self):
        app = FastAPI()

        @app.get("/x")
        def _(u: dict = Depends(auth.get_usuario)):
            return {"exp": u.get("token_exp")}

        token, expira = auth.criar_token_e_expiracao(settings.admin_login)
        r = TestClient(app).get("/x", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        assert r.json()["exp"] == int(expira.timestamp())
'''

if MARCA in texto:
    print("ja aplicado")
else:
    candidato = texto.rstrip("\n") + "\n" + NOVO
    compile(candidato, str(caminho), "exec")
    caminho.write_text(candidato, encoding="utf-8")
    print("aplicado")
