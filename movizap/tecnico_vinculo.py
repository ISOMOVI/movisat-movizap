"""O vínculo do contato técnico com o cadastro do Harmonit — 21/10.

🔵 Pedido dele: *"podemos pensar em um vínculo de dados técnicos dentro do
cadastro do tipo 'técnico', assim já traz sugerido pelo número dele"*, para
que técnico novo — ou ainda sem o tipo — já sirva ao agendamento.

🚨 A CHAVE É O TELEFONE, porque o e-mail do técnico no Harmonit **é o telefone
dele**: `Franck` → `997394026@movisat.com.br`, contato `+5519997394026`.
Medido em 21/10: vale em **186 dos 200** cadastros. Os 14 que fogem são contas
internas (`comercial@`, `parceiros@`, pessoas da casa) e **não podem casar**;
se casassem, todo usuário interno viraria técnico.

🔵 Decisões dele (21/10):
  · a varredura **nasce ligada** — exceção consciente à régua da casa, porque
    ela só grava o que a trava do agendamento já calcula ao vivo;
  · a chave tenta **9 dígitos e depois 8** (número antigo, sem o nono: ganha 7
    vínculos), e **só vincula quando o candidato for único**.

🚨 ELA NUNCA MUDA O `relacao` DO CONTATO. Trocar para `tecnico` esconde
empresas na ficha e muda regra de negócio — isso continua sendo clique de
gente. A varredura grava o vínculo e nada mais.

🚨 E NUNCA ENCOSTA EM VÍNCULO `manual`. É o que faz a exceção dele funcionar:
o 6168 aponta para o Iago, que `iago@movisat.com.br` jamais alcançaria (não é
numérico, e está marcado como usuário do sistema).
"""
import logging
import re

from . import banco, fpsl_ponte

log = logging.getLogger(__name__)

CHAVE_LIGADO = "tecnico_vinculo_ligado"

# 1x/dia, como a `sync_tecnicos` do outro lado -- varrer mais que a fonte
# muda seria gastar chamada para reconfirmar o mesmo.
INTERVALO_SEG = 86_400

ORIGENS = ("automatico", "manual")


def ligado(cfg: dict | None = None) -> bool:
    """O interruptor. `cfg` existe para o TESTE não tocar na configuração de
    produção -- mesmo desenho de `distribuicao.distribuir(cfg=...)`."""
    if cfg is not None:
        return str(cfg.get(CHAVE_LIGADO, "false")).lower() == "true"
    linha = banco.um("SELECT valor FROM config WHERE chave = %s", (CHAVE_LIGADO,))
    return bool(linha) and str(linha["valor"]).lower() == "true"


def chaves_do_telefone(e164: str | None) -> list[str]:
    """As chaves que este telefone pode ter, da mais específica para a menos.

    🔵 Nove e depois oito, por decisão dele. Oito é o número antigo, sem o
    nono dígito -- medido: ganha 7 vínculos e, hoje, não cria nenhuma
    ambiguidade. A regra de candidato único é que impede o estrago se criar.
    """
    so = re.sub(r"[^0-9]", "", e164 or "")
    chaves = []
    if len(so) >= 9:
        chaves.append(so[-9:])
    if len(so) >= 8:
        chaves.append(so[-8:])
    return chaves


def _indice(tecnicos: list[dict]) -> dict[str, list[dict]]:
    """chave -> técnicos com ela. Lista, e não um só, porque é a contagem que
    decide: candidato único vincula, dois ou mais não vinculam nada."""
    por_chave: dict[str, list[dict]] = {}
    for t in tecnicos:
        # 9 dígitos e também os 8 finais: é assim que o telefone antigo acha o
        # cadastro novo, e vice-versa.
        crua = (t.get("chave") or "").strip()
        if not crua:
            continue
        for k in {crua[-9:], crua[-8:]}:
            por_chave.setdefault(k, []).append(t)
    return por_chave


def casar(e164: str | None, por_chave: dict[str, list[dict]]) -> tuple[dict | None, str]:
    """O técnico deste telefone, ou o motivo de não ter dado.

    🚨 CANDIDATO ÚNICO OU NADA (decisão dele). Dois técnicos com o mesmo final
    de número é raro e não existe hoje -- mas escolher um deles no escuro
    poria o orçamento no nome de outra pessoa.
    """
    for chave in chaves_do_telefone(e164):
        candidatos = por_chave.get(chave) or []
        # Desempata pelo `tecnico_id`: o mesmo técnico pode entrar pelas duas
        # chaves (9 e 8), e isso não é ambiguidade.
        unicos = {t["tecnico_id"]: t for t in candidatos}
        if len(unicos) == 1:
            return next(iter(unicos.values())), ""
        if len(unicos) > 1:
            nomes = sorted(t["nome"] for t in unicos.values())
            return None, f"telefone {chave} casa com mais de um tecnico: {nomes}"
    return None, "nenhum tecnico do Harmonit com este telefone"


def _contatos_com_telefone() -> list[dict]:
    """Todo contato com telefone — e **não** só os do tipo técnico.

    🔵 É o pedido dele: *"para técnicos novos ou ainda sem o tipo 'técnico'"*.
    Medido em 21/10: hoje há **zero** contatos que casam sem ser do tipo, mas
    a varredura existe para quando houver.
    """
    return banco.varios(
        """SELECT ct.id, ct.nome, ct.relacao, ct.harmonit_tecnico_id,
                  ct.harmonit_vinculo_origem,
                  (SELECT e164 FROM contato_telefone
                    WHERE contato_id = ct.id
                    ORDER BY principal DESC, id LIMIT 1) AS e164
             FROM contato ct
            WHERE EXISTS (SELECT 1 FROM contato_telefone
                           WHERE contato_id = ct.id)""")


def vincular(contato_id: int, tecnico: dict, origem: str = "automatico") -> None:
    if origem not in ORIGENS:
        raise ValueError(f"origem inválida: {origem!r}")
    banco.executar(
        "UPDATE contato SET harmonit_tecnico_id = %s, harmonit_tecnico_nome = %s, "
        "       harmonit_vinculo_origem = %s, harmonit_vinculo_em = now() "
        " WHERE id = %s",
        (tecnico["tecnico_id"], tecnico["nome"], origem, contato_id))


def desvincular(contato_id: int) -> None:
    """Tira o vínculo. ⚠️ Em contato `manual`, isto é o único jeito de voltar
    a deixar a varredura cuidar dele."""
    banco.executar(
        "UPDATE contato SET harmonit_tecnico_id = NULL, "
        "       harmonit_tecnico_nome = NULL, harmonit_vinculo_origem = NULL, "
        "       harmonit_vinculo_em = NULL WHERE id = %s", (contato_id,))


def do_contato(contato_id: int) -> dict | None:
    return banco.um(
        "SELECT harmonit_tecnico_id, harmonit_tecnico_nome, "
        "       harmonit_vinculo_origem, harmonit_vinculo_em "
        "  FROM contato WHERE id = %s", (contato_id,))


def uma_passada(*, cfg: dict | None = None, tecnicos: list[dict] | None = None) -> dict:
    """Uma volta da varredura. Devolve o retrato do que fez.

    `tecnicos` existe para o teste medir a regra sem rede; em produção a lista
    vem da ponte, do cadastro que o FPSL sincroniza 1×/dia.
    """
    if not ligado(cfg):
        return {"ligado": False}

    if tecnicos is None:
        try:
            tecnicos = (fpsl_ponte.tecnicos_do_harmonit() or {}).get("tecnicos") or []
        except fpsl_ponte.FpslIndisponivel as e:
            # 🚨 Lista vazia NÃO é resposta aqui: ela desvincularia ninguém
            # (não desvinculamos), mas relataria "0 casaram" como se fosse
            # fato. Dizer que não deu para consultar é o que vale.
            log.warning("varredura de vínculo: %s", e)
            return {"ligado": True, "erro": str(e)}

    por_chave = _indice(tecnicos)
    novos = refeitos = mantidos = manuais = sem_casar = ambiguos = 0

    for ct in _contatos_com_telefone():
        if ct["harmonit_vinculo_origem"] == "manual":
            # 🚨 Vínculo de gente não se mexe. É o que sustenta a exceção dele.
            manuais += 1
            continue
        achado, motivo = casar(ct["e164"], por_chave)
        if not achado:
            if "mais de um" in motivo:
                ambiguos += 1
                log.info("vínculo ambíguo no contato %s: %s", ct["id"], motivo)
            elif ct["relacao"] == "tecnico":
                sem_casar += 1
            continue
        if ct["harmonit_tecnico_id"] == achado["tecnico_id"]:
            mantidos += 1
            continue
        if ct["harmonit_tecnico_id"]:
            refeitos += 1
        else:
            novos += 1
        vincular(ct["id"], achado, "automatico")

    retrato = {"ligado": True, "novos": novos, "refeitos": refeitos,
               "mantidos": mantidos, "manuais": manuais,
               "tecnicos_sem_casar": sem_casar, "ambiguos": ambiguos}
    log.info("varredura de vínculo do técnico: %s", retrato)
    return retrato


def pendencias() -> dict:
    """O que falta no cadastro — a lista que a tela mostra.

    🚨 São três buracos DIFERENTES, e juntá-los num número só esconderia o que
    fazer com cada um:
      · técnico daqui sem cadastro lá (ou com outro número);
      · cadastro lá sem contato aqui;
      · contato que casa e **ainda não** é do tipo técnico (o caso que ele
        previu) -- a varredura não muda o tipo, então ele vira sugestão.
    """
    # Deixa a `FpslIndisponivel` subir: quem desenha a tela tem de dizer
    # "não deu para consultar", e não listar zero pendência.
    tecnicos = (fpsl_ponte.tecnicos_do_harmonit() or {}).get("tecnicos") or []

    por_chave = _indice(tecnicos)
    sem_cadastro, para_marcar = [], []
    vistos: set[int] = set()

    for ct in _contatos_com_telefone():
        achado, _ = casar(ct["e164"], por_chave)
        if achado:
            vistos.add(achado["tecnico_id"])
            if ct["relacao"] != "tecnico":
                para_marcar.append({"contato_id": ct["id"], "nome": ct["nome"],
                                    "relacao": ct["relacao"],
                                    "tecnico": achado["nome"]})
        elif ct["relacao"] == "tecnico":
            sem_cadastro.append({"contato_id": ct["id"], "nome": ct["nome"],
                                 "e164": ct["e164"]})

    sem_contato = [t for t in tecnicos if t["tecnico_id"] not in vistos]
    return {
        "tecnicos_sem_cadastro_no_harmonit": sem_cadastro,
        "cadastro_sem_contato_no_movizap": [
            {"tecnico_id": t["tecnico_id"], "nome": t["nome"], "email": t["email"]}
            for t in sem_contato],
        "casam_e_nao_sao_do_tipo": para_marcar,
    }


async def rodar(parar) -> None:
    """Laço da varredura. Mesmo desenho do `vigia.rodar`.

    🚨 UMA PASSADA JÁ NO INÍCIO: esperar 24 h para o primeiro vínculo faria o
    recurso nascer sem efeito nenhum, e ninguém saberia se ele funciona.
    """
    import asyncio

    log.info("varredura de vínculo do técnico ativa (a cada %ds)", INTERVALO_SEG)
    while not parar.is_set():
        try:
            await asyncio.to_thread(uma_passada)
        except Exception:
            # Laço que morre em silêncio é pior que laço nenhum.
            log.exception("varredura de vínculo falhou -- segue tentando")
        try:
            await asyncio.wait_for(parar.wait(), timeout=INTERVALO_SEG)
        except asyncio.TimeoutError:
            pass
    log.info("varredura de vínculo do técnico encerrada")
