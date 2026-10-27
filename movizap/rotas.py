"""Distância rodada entre dois endereços — a calculadora de KM do técnico.

🔵 Pedido dele em 26/10: *"o km é o calculo a ser feito, é a informação a ser
encontrada. Hoje é feita na mão via 'rotas' do google e dai esse KM é inserido
manualmente"*.

🚨 O SERVIÇO É O DO GOOGLE, E NÃO POR PREFERÊNCIA: é o que ele já usa à mão. Se
o número do sistema divergir do que ele confere no Google Rotas, ele não vai
confiar no sistema -- e divergência entre bases de mapa é real. Por isso a
fonte é a mesma.

🚨 ESTE MÓDULO É O MOLDE DO `cep.py`, de propósito, porque lá o mesmo problema
já foi resolvido com acerto:
  · a consulta sai **da VPS**, nunca do navegador -- aqui com um motivo a mais:
    a chave é paga, e chave que vai ao navegador é chave de qualquer um;
  · **três respostas distinguíveis** -- achou / não localizou o endereço /
    não deu para perguntar. Juntar as duas últimas faria a tela dizer "endereço
    errado" sobre um endereço certo que ela não conseguiu conferir;
  · a tradução de vocabulário (metros -> km) mora aqui dentro, num lugar só.

🚨 E HÁ UMA QUARTA RESPOSTA QUE O `cep.py` NÃO TEM: **sem chave configurada**.
O ViaCEP é público; este serviço não. Enquanto a chave não existir, o módulo
diz `disponivel() is False` e a tela cai no campo manual **dizendo por quê** --
em vez de mostrar um botão que falha, ou pior, um zero silencioso num número
que vai para um orçamento.

⚠️ A FORMA DA CHAMADA HTTP NÃO FOI VERIFICADA AO VIVO, e isto está escrito de
propósito (`M5`: recomendação é afirmação sobre o mundo). Sem chave não há como
exercitar a API de verdade. A chamada está isolada em `_perguntar`, com o corpo
e o caminho da **Routes API** (`computeRoutes`); quando a chave existir, é essa
função -- e só ela -- que precisa ser conferida contra a resposta real. O resto
do módulo (cache, normalização, as quatro respostas) não depende da forma dela.
"""
import logging
import re
import unicodedata
from decimal import Decimal, ROUND_HALF_UP

import httpx

from . import banco
from .config import settings

log = logging.getLogger("movizap.rotas")

# Curto: isto roda dentro de um clique do operador.
TEMPO_LIMITE = 8.0

# 🚨 A Routes API cobra por consulta. O prazo do cache existe porque rota muda
# (obra, estrada nova) -- e porque cache sem prazo é afirmação sem data.
DIAS_DE_CACHE = 90

URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

# Só o que precisamos de volta. Pedir o mínimo é o que a própria API cobra mais
# barato, e é menos coisa para interpretar errado.
CAMPOS = "routes.distanceMeters,routes.duration"


class EnderecoInsuficiente(ValueError):
    """Falta endereço para perguntar. Nem chega a sair da VPS.

    ⚠️ Rua e cidade são o mínimo: só CEP o Google aceita, mas devolve o centro
    do CEP -- e km medido até o centro do bairro é km errado com cara de certo.
    """


class RotaIndisponivel(RuntimeError):
    """O serviço não respondeu, ou não há chave. 🚨 NÃO é "endereço errado"."""


def disponivel() -> bool:
    """Se dá para calcular. `False` enquanto não houver chave no `.env`.

    🚨 A TELA PRECISA DISTO ANTES DE OFERECER O BOTÃO. Botão que abre e falha é
    pior que botão que não existe -- e a alternativa honesta, aqui, é o campo
    manual, que é como o km é preenchido desde 21/10.
    """
    return bool(settings.rotas_chave)


def como_texto(e: dict) -> str:
    """Os campos de endereço viram a linha que o serviço de rotas entende.

    ⚠️ Não é o `linha_do_endereco` do agendamento: aquele é para o cliente LER
    (e omite buraco para não parecer defeito); este é para uma máquina
    GEOCODIFICAR, então leva cidade e UF sempre que existem, e o CEP no fim.
    """
    rua = (e.get("logradouro") or "").strip()
    numero = (e.get("numero") or "").strip()
    partes = [", ".join(p for p in (rua, numero) if p),
              (e.get("bairro") or "").strip()]
    cidade = (e.get("cidade") or "").strip()
    uf = (e.get("uf") or "").strip()
    local = " - ".join(p for p in (cidade, uf) if p)
    if local:
        partes.append(local)
    cep = (e.get("cep") or "").strip()
    if cep:
        partes.append(cep)
    partes.append("Brasil")
    return ", ".join(p for p in partes if p)


def normalizar(texto: str) -> str:
    """A chave do cache: minúsculas, sem acento, sem pontuação, espaço único.

    🚨 "Rua X, 123" e "rua x 123" são a MESMA consulta, e pagar duas vezes por
    isso seria desperdício silencioso -- o tipo que ninguém vê na fatura porque
    cada linha parece legítima.
    """
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", texto or "")
        if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", sem_acento.lower())).strip()


def _do_cache(origem_norm: str, destino_norm: str) -> dict | None:
    linha = banco.um(
        """SELECT km, segundos, consultado_em
             FROM rota_cache
            WHERE origem_norm = %s AND destino_norm = %s
              AND consultado_em > now() - make_interval(days => %s)""",
        (origem_norm, destino_norm, DIAS_DE_CACHE))
    if not linha:
        return None
    return {"km": float(linha["km"]), "segundos": linha["segundos"],
            "consultado_em": linha["consultado_em"], "do_cache": True}


def _guardar(origem_norm: str, destino_norm: str, km: float, segundos) -> None:
    """🚨 SÓ RESULTADO BOM ENTRA AQUI. Falha nunca é gravada: é exatamente o
    "cache que guarda erro para sempre" que o `cep.py` teme."""
    banco.executar(
        """INSERT INTO rota_cache (origem_norm, destino_norm, km, segundos)
           VALUES (%s, %s, %s, %s)
           ON CONFLICT (origem_norm, destino_norm)
             DO UPDATE SET km = EXCLUDED.km, segundos = EXCLUDED.segundos,
                           consultado_em = now()""",
        (origem_norm, destino_norm, km, segundos))


def _perguntar(origem: str, destino: str) -> tuple[int, int | None] | None:
    """A chamada HTTP. Devolve (metros, segundos) ou `None` se não localizou.

    ⚠️ **ESTA É A FUNÇÃO NÃO VERIFICADA AO VIVO** (ver o aviso do topo). Sem
    chave não dá para exercitar a API, e `M5` manda não afirmar o que não se
    mediu. O corpo e os cabeçalhos seguem a Routes API; quando a chave existir,
    confira ESTA função contra a resposta real -- o resto do módulo não depende
    da forma dela.

    🚨 A chave vai no cabeçalho, nunca na URL: URL entra em log de proxy.
    """
    corpo = {
        "origin": {"address": origem},
        "destination": {"address": destino},
        "travelMode": "DRIVE",
        # Sem trânsito em tempo real: o km rodado não muda com
        # engarrafamento, e pedir o cálculo com trânsito custa mais caro.
        "routingPreference": "TRAFFIC_UNAWARE",
    }
    cabecalhos = {
        "X-Goog-Api-Key": settings.rotas_chave,
        "X-Goog-FieldMask": CAMPOS,
        "Content-Type": "application/json",
    }
    try:
        r = httpx.post(URL, json=corpo, headers=cabecalhos, timeout=TEMPO_LIMITE)
    except httpx.HTTPError as e:
        log.warning("rotas: o servico nao respondeu: %s", e)
        raise RotaIndisponivel("não deu para consultar a distância agora") from None

    if r.status_code >= 400:
        # ⚠️ NÃO IMPRIME O CORPO DA RESPOSTA: ela pode repetir a requisição, e a
        # requisição carrega endereço de cliente. Só o código.
        log.warning("rotas: a consulta respondeu %s", r.status_code)
        raise RotaIndisponivel(f"a consulta de distância respondeu {r.status_code}")

    try:
        dados = r.json()
    except ValueError:
        raise RotaIndisponivel("a consulta de distância respondeu algo que não é JSON") \
            from None

    # 🚨 A API responde **200 com `{}`** quando não consegue traçar a rota (é o
    # mesmo formato de armadilha do ViaCEP, que responde 200 com `{"erro":
    # true}`). Quem olhasse só o código HTTP trataria "não achei" como sucesso e
    # calcularia zero km.
    rotas = dados.get("routes") or []
    if not rotas:
        return None

    metros = rotas[0].get("distanceMeters")
    if metros is None:
        return None
    # A duração vem como "1234s".
    bruto = str(rotas[0].get("duration") or "").rstrip("s")
    segundos = int(bruto) if bruto.isdigit() else None
    return int(metros), segundos


def distancia(origem: dict, destino: dict) -> dict | None:
    """A distância de ida, em km, entre dois endereços.

    Quatro saídas, e a tela precisa das quatro:
      · dicionário  -> achou (`do_cache` diz se foi consulta nova);
      · `None`      -> o serviço respondeu e **não localizou** a rota;
      · `RotaIndisponivel`   -> não deu para perguntar (ou não há chave);
      · `EnderecoInsuficiente` -> falta endereço; nem saiu da VPS.
    """
    # 🚨 O ENDEREÇO SE CONFERE ANTES DA CHAVE, e a ordem importa: "falta a rua"
    # é sabível sem chave nenhuma, e dizer 503 ("não deu para perguntar") para
    # um endereço incompleto manda o operador procurar defeito no serviço
    # quando o problema está no campo em branco na frente dele. Achado pela
    # prova ao vivo das rotas, não pela leitura.
    for nome, e in (("origem", origem), ("destino", destino)):
        if not (e.get("logradouro") or "").strip() or not (e.get("cidade") or "").strip():
            raise EnderecoInsuficiente(
                f"para calcular, o {nome} precisa de rua e cidade")

    if not disponivel():
        raise RotaIndisponivel(
            "o cálculo de distância não está configurado nesta instalação")

    texto_origem, texto_destino = como_texto(origem), como_texto(destino)

    origem_norm, destino_norm = normalizar(texto_origem), normalizar(texto_destino)
    if origem_norm == destino_norm:
        # Mesmo endereço: zero, sem gastar consulta.
        return {"km": 0.0, "segundos": 0, "consultado_em": None, "do_cache": False}

    guardado = _do_cache(origem_norm, destino_norm)
    if guardado:
        return guardado

    achado = _perguntar(texto_origem, texto_destino)
    if achado is None:
        return None

    metros, segundos = achado
    km = float(Decimal(metros) / 1000)
    _guardar(origem_norm, destino_norm, km, segundos)
    return {"km": km, "segundos": segundos, "consultado_em": None, "do_cache": False}


def arredondar(km: float, *, ida_e_volta: bool = True) -> Decimal:
    """O número que vai para a linha `KM DESLOCAMENTO`, com uma casa.

    🔵 **IDA E VOLTA É O PADRÃO**, decidido por ele em 26/10 -- e casa com os
    três orçamentos já emitidos (77, 77 e 15 km). O técnico volta.

    ⚠️ Meio pra cima, como o `orcamento.centavos`: duas regras de
    arredondamento no mesmo documento é uma delas errada.
    """
    total = Decimal(str(km)) * (2 if ida_e_volta else 1)
    return total.quantize(Decimal("0.1"), ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# A MEMÓRIA do endereço de origem (migração 077)
# ---------------------------------------------------------------------------
# 🔵 *"o endereço do tecnico sempre fica preenchido conforme o ultimo (...) se
# for alterado, permanece alterado"* -- ou seja, UM SOBRESCREVER, não um
# histórico. Daí uma linha por técnico.
#
# ⚠️ ISTO NÃO É CADASTRO: ninguém digita num formulário de cadastro, a linha é
# escrita pelo USO da calculadora. Cadastro é coisa que alguém tem de manter, e
# o projeto já tem 117 contatos de técnico sem cadastro no Harmonit para provar
# o que acontece quando ninguém mantém.
CAMPOS_DE_ORIGEM = ("cep", "logradouro", "numero", "bairro", "cidade", "uf",
                    "complemento")


def origem_do_tecnico(tecnico_contato_id: int) -> dict | None:
    """O último endereço de origem daquele técnico, ou `None` na primeira vez."""
    linha = banco.um(
        f"SELECT {', '.join(CAMPOS_DE_ORIGEM)}, atualizado_em "
        "  FROM tecnico_origem WHERE tecnico_contato_id = %s",
        (int(tecnico_contato_id),))
    return dict(linha) if linha else None


def lembrar_origem(tecnico_contato_id: int, endereco: dict) -> None:
    """Grava (ou sobrescreve) a origem daquele técnico."""
    valores = [(endereco.get(c) or "").strip() or None for c in CAMPOS_DE_ORIGEM]
    colunas = ", ".join(CAMPOS_DE_ORIGEM)
    marcas = ", ".join(["%s"] * len(CAMPOS_DE_ORIGEM))
    atribuicoes = ", ".join(f"{c} = EXCLUDED.{c}" for c in CAMPOS_DE_ORIGEM)
    banco.executar(
        f"""INSERT INTO tecnico_origem (tecnico_contato_id, {colunas})
            VALUES (%s, {marcas})
            ON CONFLICT (tecnico_contato_id)
              DO UPDATE SET {atribuicoes}, atualizado_em = now()""",
        (int(tecnico_contato_id), *valores))
