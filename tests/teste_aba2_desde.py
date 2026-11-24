# -*- coding: utf-8 -*-
"""A DATA INICIAL DA ABA 2, no lado do MoviZap — 🔵 D6 e D7 dele, 23/11.

🔵 *"use 16/11/2026 de inicio para o financeiro, não mexa na data do OP"*.

🚨 **O QUE ESTA ROTA ACRESCENTA À PERMISSÃO DA TELA.** A `PNL_1.6` está
concedida a TRÊS pessoas (Aline, Erika e Karla, desde 19/11 às 14:55 — medido),
e mover a data muda o que todas veem **e** o que a varredura da madrugada cria.
Então a tela é de quem tem a aba e a data é do owner — a mesma régua da data
matriz da Operação (`PUT /api/paineis/operacao/desde`, D9 de 29/10).

🚨 **A GUARDA DO OWNER SE MEDE CHAMANDO A FUNÇÃO**, e não por HTTP: a
dependência de sessão já está montada no app e trocá-la num teste não a
alcançaria. É o molde que o `teste_rotas_pipeline.py::TestADataMatriz` já usa
para a mesma guarda.

⚠️ **ESTE ARQUIVO NÃO FALA COM O FPSL.** A chamada à ponte é dublada: o que se
mede aqui é a GUARDA e o CORPO que sai, não o que o FPSL faz com ele — isso tem
trava própria do outro lado (`fpsl_weso/tests/teste_pagamento_desde.py`, 17
travas, com banco temporário).
"""
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

pytest.importorskip("psycopg")

from movizap import main  # noqa: E402


class TestAGuardaDoOwner:
    def test_quem_nao_e_owner_leva_403_e_NADA_sai_para_a_ponte(self,
                                                               monkeypatch):
        """🚨 Recusa que grava é pior que recusa nenhuma: além do 403, a ponte
        não pode ter sido chamada."""
        from fastapi import HTTPException
        from movizap import fpsl_ponte

        chamadas = []
        monkeypatch.setattr(fpsl_ponte, "_pagamento",
                            lambda c, corpo: chamadas.append((c, corpo)))

        with pytest.raises(HTTPException) as e:
            main.definir_desde_da_aba2(
                dados=main.DataInicialDaAba2(desde="2026-08-01"),
                usuario={"owner": False, "login": "zz", "nome": "zz"})
        assert e.value.status_code == 403
        assert "owner" in str(e.value.detail)
        assert chamadas == [], "nao-owner nao pode alcancar a ponte"

    def test_o_owner_passa_e_o_corpo_leva_a_data_e_QUEM_mudou(self,
                                                              monkeypatch):
        """🔵 *"deve ter o log de quem faz o que SEMPRE"*: o `por` vai no corpo,
        e é o que o `pagamento_evento` do FPSL grava."""
        from movizap import fpsl_ponte

        chamadas = []

        def falso(caminho, corpo):
            chamadas.append((caminho, corpo))
            return {"ok": True, "desde": corpo["desde"]}

        monkeypatch.setattr(fpsl_ponte, "_pagamento", falso)
        r = main.definir_desde_da_aba2(
            dados=main.DataInicialDaAba2(desde="2026-11-16"),
            usuario={"owner": True, "login": "iago", "nome": "Iago"})
        assert r == {"ok": True, "desde": "2026-11-16"}
        assert chamadas == [("/desde", {"desde": "2026-11-16", "por": "Iago"})]


class TestAFormaDaData:
    @pytest.mark.parametrize("torta", ["2026-11", "", "16/11/2026000"])
    def test_tamanho_errado_nao_monta_o_corpo(self, torta):
        """⚠️ O `min_length`/`max_length` do Pydantic pega o tamanho antes de
        qualquer código nosso. O que TEM 10 caracteres e não é data é recusado
        do outro lado, com `ok`+`motivo` — trava própria lá."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            main.DataInicialDaAba2(desde=torta)

    def test_dez_caracteres_que_NAO_sao_data_passam_aqui_e_param_la(self,
                                                                    monkeypatch):
        """🚨 A divisão de trabalho, declarada: aqui só o tamanho; a FORMA é do
        serviço do FPSL, que devolve `ok: False` com o motivo. Esta trava prende
        a divisão, para ninguém concluir que `16/11/2026` é aceito."""
        from movizap import fpsl_ponte

        monkeypatch.setattr(
            fpsl_ponte, "_pagamento",
            lambda c, corpo: {"ok": False,
                              "motivo": "a data tem de estar no formato "
                                        "aaaa-mm-dd"})
        r = main.definir_desde_da_aba2(
            dados=main.DataInicialDaAba2(desde="16/11/2026"),
            usuario={"owner": True, "login": "iago", "nome": "Iago"})
        assert r["ok"] is False
        assert "aaaa-mm-dd" in r["motivo"]


class TestARotaExiste:
    def test_a_rota_esta_registrada_e_e_PUT(self):
        """🚨 `M15`: ausência só se afirma lendo a definição. Contar rota
        registrada não é pedir uma rota — mas rota NÃO registrada é 404 na cara
        de quem usa, e isto é o mínimo que se mede sem subir o app."""
        achadas = [(r.path, sorted(r.methods))
                   for r in main.app.routes
                   if getattr(r, "path", "")
                   == "/api/paineis/servico-dos-tecnicos/desde"]
        assert achadas, "a rota nao esta registrada"
        assert achadas[0][1] == ["PUT"], achadas
