# -*- coding: utf-8 -*-
"""Patch 29/10 (parte 8b): a regra da placa cobrada na rota, e a tela avisando.

🔵 *"so e possivel abrir chamados para placas ativas na weso [...] essa e a
regra"*.
"""
import pathlib
import sys

MOVI = pathlib.Path("/home/claude/movizap_painel")


def trocar(caminho: pathlib.Path, velho: str, novo: str, rotulo: str) -> None:
    texto = caminho.read_text(encoding="utf-8")
    if novo in texto:
        print(f"  = {rotulo}: ja aplicado")
        return
    if texto.count(velho) != 1:
        sys.exit(f"  ! {rotulo}: achei {texto.count(velho)} ocorrencias, "
                 f"esperava 1 -- PAREI sem gravar nada")
    caminho.write_text(texto.replace(velho, novo), encoding="utf-8")
    print(f"  + {rotulo}")


f = MOVI / "movizap" / "formularios.py"
print(f.name)

trocar(f, '''def novo_desafio() -> dict:''',
       '''# ----------------------------------------------------------------------------
# A REGRA DA PLACA (29/10)
# ----------------------------------------------------------------------------
# 🔵 Dita por ele em uma linha: *"so e possivel abrir chamados para placas
# ativas na weso. o match e basicamente de 100% mesmo. essa e a regra"*.
#
# 🚨 ISTO INVERTEU O QUE EU HAVIA ESCRITO de manha. Eu tratava a lista da frota
# como SUGESTAO -- *"lista nossa incompleta nao pode barrar chamado"* -- e a
# regra dele diz o contrario: placa ativa na WESO e a CONDICAO do chamado.
#
# 🚨 E A MINHA CONTA DE 95% ESTAVA GROSSEIRA. Medido em 29/10, normalizando a
# placa dos dois lados, nas 1.998 linhas da WESO: **50 nao sao placa** (a
# coluna tem chassi e numero de serie) e **30 sao placa que o Harmonit nao
# tem**. Entre as que SAO placa o casamento e 1.918 de 1.948 = **98,5%** -- e
# os 80 restantes sao dado sujo de um lado, nao cliente de fora. A frase dele
# bate com o dado; o meu "1 em 20 vai digitar" nao batia.
#
# ⚠️ POR QUE NAO ENTRA NO `validar`: ele e sincrono, puro, e roda na suite sem
# rede. Pendurar nele uma chamada a outro servico faria 1.874 testes
# depenaderem do FPSL de pe. A conferencia mora na ROTA, ao lado da guarda de
# anexo.
def placas_informadas(d: dict, valores: dict) -> list[str]:
    """O que a pessoa escreveu nos campos de placa -- os que declaram
    `fonte = 'weso_placas'`."""
    saida = []
    for campo in d["campos"]:
        if campo.get("fonte") != "weso_placas":
            continue
        bruto = valores.get(campo["nome"])
        partes = bruto if isinstance(bruto, list) else [bruto]
        saida += [str(p).strip() for p in partes if str(p or "").strip()]
    return saida


def conferir_regra_da_placa(d: dict, valores: dict) -> bool | None:
    """Levanta `DadoInvalido` se alguma placa informada não está ativa na WESO.

    Devolve `True` (conferidas), `False` (**não deu para conferir** -- a ponte
    não respondeu) ou `None` (não havia placa).

    🚨 PONTE FORA DO AR DEIXA PASSAR, MARCADO. Recusar o chamado por causa de
    uma indisponibilidade nossa transformaria o nosso problema no problema do
    cliente -- e o cliente não tem como consertar. O rastro fica em
    `formulario_solicitacao.placas_conferidas` (migração 081).
    """
    placas = placas_informadas(d, valores)
    if not placas:
        return None
    try:
        resposta = fpsl_ponte.conferir_placas(placas)
    except Exception as e:  # noqa: BLE001 -- qualquer falha da ponte
        log.warning("regra da placa: nao deu para conferir %s: %s", placas, e)
        return False

    inativas = [p for p in placas
                if not (resposta.get(p) or {}).get("ativa")]
    if inativas:
        # ⚠️ A FRASE DIZ O QUE FAZER. "Placa não permitida" deixaria a pessoa
        # sem saída; ela não sabe o que é a WESO nem tem como consertar o
        # cadastro sozinha.
        raise DadoInvalido(
            "Só conseguimos abrir chamado para veículo com rastreador ativo. "
            + ("Esta placa não está ativa no seu cadastro: "
               if len(inativas) == 1 else
               "Estas placas não estão ativas no seu cadastro: ")
            + ", ".join(inativas)
            + ". Confira a placa ou fale com a Movisat pelo WhatsApp.")
    return True


def novo_desafio() -> dict:''',
       "formularios.py: conferir_regra_da_placa")

trocar(f, '''def registrar(d: dict, valores: dict, arquivos: list | None = None,
              ip: str | None = None, vinculo: dict | None = None) -> dict:''',
       '''def registrar(d: dict, valores: dict, arquivos: list | None = None,
              ip: str | None = None, vinculo: dict | None = None,
              placas_conferidas: bool | None = None) -> dict:''',
       "registrar: parametro placas_conferidas")

trocar(f, '''        """INSERT INTO formulario_solicitacao
               (formulario_id, ip, valores, conversa_id, contato_id, cliente_id)
           VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, criada_em""",
        (d["id"], ip, json.dumps(valores, ensure_ascii=False),
         vinculo.get("conversa_id"), vinculo.get("contato_id"),
         vinculo.get("cliente_id")))''',
       '''        """INSERT INTO formulario_solicitacao
               (formulario_id, ip, valores, conversa_id, contato_id, cliente_id,
                placas_conferidas)
           VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id, criada_em""",
        (d["id"], ip, json.dumps(valores, ensure_ascii=False),
         vinculo.get("conversa_id"), vinculo.get("contato_id"),
         vinculo.get("cliente_id"), placas_conferidas))''',
       "registrar: grava placas_conferidas")

# ---------------------------------------------------------------------------
# A rota: cobra a regra e registra o rastro
# ---------------------------------------------------------------------------
m = MOVI / "movizap" / "main.py"
print(m.name)
trocar(m, '''    limpo = formularios_mod.validar(d, enviados, por_campo)
    r = formularios_mod.registrar(d, limpo, guardados, ip=ip)''',
       '''    limpo = formularios_mod.validar(d, enviados, por_campo)
    # 🔵 A REGRA DELE (29/10): chamado só para placa ativa na WESO. ⚠️ Depois do
    # `validar`, porque conferir placa de um envio que já seria recusado por
    # outro motivo é ida à ponte por nada.
    conferidas = formularios_mod.conferir_regra_da_placa(d, limpo)
    r = formularios_mod.registrar(d, limpo, guardados, ip=ip,
                                  placas_conferidas=conferidas)''',
       "main.py: a rota cobra a regra")

trocar(m, '''@app.get("/api/publico/desafio")''',
       '''@app.post("/api/publico/formulario/{slug}/placa")
def conferir_placa_publica(slug: str, request: Request,
                           placa: str = Form(...),
                           abertura: str = Form("")):
    """Esta placa está ativa na WESO? 🔵 Regra dele, 29/10.

    Existe para a tela poder AVISAR na hora, em vez de deixar a pessoa
    preencher tudo e tomar a recusa no envio. ⚠️ A recusa de verdade continua
    sendo no POST do formulário -- aqui é só a mensagem.

    🚨 Devolve `{ativa, apelido}` e nada mais: não diz de quem é a placa. Dizer
    o cliente aqui faria desta rota um jeito de descobrir o dono de qualquer
    placa.
    """
    ip = ratelimit.ip_do_cliente(request)
    try:
        formularios_mod.definicao(slug)
    except formularios_mod.FormularioNaoExiste:
        raise HTTPException(status_code=404, detail="Formulário não encontrado.")
    formularios_mod.conferir_abertura(abertura)
    if formularios_mod.passou_do_teto_de_buscas(ip):
        raise operacao.DadoInvalido("Muitas consultas seguidas. Tente mais tarde.")
    try:
        achado = (fpsl_ponte.conferir_placas([placa]) or {}).get(placa) or {}
    except Exception as e:  # noqa: BLE001
        log.warning("conferir placa %r: %s", placa, e)
        # ⚠️ "Não deu para conferir" NÃO é "inativa": a tela diz isso, e o
        # envio segue permitido (marcado).
        return {"conferiu": False}
    return {"conferiu": True, "ativa": bool(achado.get("ativa")),
            "apelido": achado.get("apelido")}


@app.get("/api/publico/desafio")''',
       "main.py: rota publica de conferencia da placa")

# o teto de buscas, reaproveitado
f2 = MOVI / "movizap" / "formularios.py"
trocar(f2, '''def cliente_por_documento(documento: str, ip: str | None = None) -> dict:''',
       '''def passou_do_teto_de_buscas(ip: str | None) -> bool:
    """⚠️ O mesmo teto da busca por CNPJ, e de propósito: as duas rotas
    consultam a nossa base a partir da internet, e somar no mesmo contador
    impede que alguém use uma para contornar o limite da outra."""
    if not ip:
        return False
    return ratelimit.quantos_eventos(f"busca|{ip}") >= BUSCAS_POR_HORA


def cliente_por_documento(documento: str, ip: str | None = None) -> dict:''',
       "formularios.py: passou_do_teto_de_buscas")

print()
print("ok")
