"""Consulta de CEP — 🔵 pedido dele, 21/10: *"não poderíamos ter a consulta do
CEP dentro do modal nesse momento? daí preenche os campos e ela ainda edita se
precisar?"*.

🚨 A CONSULTA SAI DAQUI, NÃO DO NAVEGADOR, e foi escolha declarada: o CEP não
trafega do computador do atendente para um terceiro, a resposta dá para
guardar, e não há CORS nem conteúdo misto no caminho.

🚨 O HARMONIT NÃO TEM ROTA DE CEP -- conferido em 21/10 nas 17 rotas de OS e
nas de dados de suporte. Então a fonte é externa, e é o **ViaCEP**: público,
sem chave, e é o que o resto do mercado usa. ⚠️ Serviço de fora da casa: ele
pode cair, e cair **não é "CEP não existe"** -- a tela tem de dizer qual dos
dois foi, senão o operador apaga um CEP certo achando que errou.

⚠️ O QUE ELE PREENCHE É SUGESTÃO, NÃO VERDADE: os campos continuam editáveis
depois (*"ela ainda edita se precisar"*). Endereço de serviço tem exceção --
condomínio, zona rural, rua renomeada -- e o cadastro do Harmonit é que manda.
"""
import logging

import httpx

log = logging.getLogger(__name__)

# Curto: isto roda dentro de um clique do operador.
TEMPO_LIMITE = 5.0

URL = "https://viacep.com.br/ws/{cep}/json/"

# 🚨 Memória de processo, e de propósito: CEP não muda, e a mesma rua volta a
# ser consultada no agendamento seguinte. Não vira tabela porque cache que
# sobrevive a deploy é cache que guarda erro para sempre.
_memoria: dict[str, dict] = {}


class CepInvalido(ValueError):
    """Não são 8 dígitos. Nem chega a sair da VPS."""


class CepIndisponivel(RuntimeError):
    """O serviço não respondeu. 🚨 NÃO é "este CEP não existe"."""


def so_digitos(cep: str) -> str:
    return "".join(c for c in (cep or "") if c.isdigit())


def consultar(cep: str) -> dict | None:
    """O endereço de um CEP. `None` quando o CEP não existe.

    🚨 TRÊS RESPOSTAS DIFERENTES, e a tela precisa das três: dicionário (achou),
    `None` (o serviço respondeu "não existe") e exceção (não deu para
    perguntar). Juntar as duas últimas faria a tela chamar de CEP errado um CEP
    que ela não conseguiu conferir.
    """
    limpo = so_digitos(cep)
    if len(limpo) != 8:
        raise CepInvalido("o CEP tem 8 dígitos")
    if limpo in _memoria:
        return _memoria[limpo] or None

    try:
        r = httpx.get(URL.format(cep=limpo), timeout=TEMPO_LIMITE)
    except httpx.HTTPError as e:
        log.warning("ViaCEP nao respondeu para %s: %s", limpo, e)
        raise CepIndisponivel("não deu para consultar o CEP agora") from None
    if r.status_code >= 400:
        raise CepIndisponivel(f"a consulta de CEP respondeu {r.status_code}")
    try:
        dados = r.json()
    except ValueError:
        raise CepIndisponivel("a consulta de CEP respondeu algo que não é JSON") \
            from None

    # ⚠️ O ViaCEP responde **200 com `{"erro": true}`** para CEP inexistente --
    # medido em 21/10. Quem olhasse só o código HTTP trataria "não existe" como
    # sucesso e preencheria a tela com campos vazios.
    if dados.get("erro"):
        _memoria[limpo] = {}
        return None

    achado = {
        "cep": limpo,
        # 🚨 Os nomes saem daqui JÁ NO VOCABULÁRIO DO HARMONIT: `logradouro` e
        # `bairro` coincidem, mas `localidade` é `cidade`. Traduzir aqui, num
        # lugar só, evita que a tela e a gravação discordem.
        "logradouro": (dados.get("logradouro") or "").strip() or None,
        "bairro": (dados.get("bairro") or "").strip() or None,
        "cidade": (dados.get("localidade") or "").strip() or None,
        "uf": (dados.get("uf") or "").strip() or None,
    }
    _memoria[limpo] = achado
    return achado
