"""Importa o pacote retroativo de um PC que ainda nao tinha agente (Bloco 9, 15/10).

🔵 15/10: *"import retroativo"* — o PC que passou meses sem agente também tem
histórico, e esse histórico é trabalho perdido se só quem está alistado
consegue mandar.

Uso:
    ./venv/bin/python scripts/importar_ligacoes.py <pacote.zip> [--conferir]
                                                   [--atendente <login|id>]

  --conferir   lê, confere e NÃO grava nada (é o que se roda primeiro)
  --atendente  de quem é este ramal, quando o ramal ainda não tem agente

🚨 ENTRA PELO MESMO `ligacoes.registrar()` DO AGENTE. Não existe um segundo
caminho de uma ligação nascer no banco: a idempotência é a mesma
(`UNIQUE (ramal, call_id)` e `arquivo_sha256` único), então importar duas vezes
o mesmo pacote grava ZERO na segunda. Um importador próprio, com `INSERT`
próprio, seria uma segunda verdade.

🚨 RECUSA, E DIZ O QUE RECUSOU. Linha sem `call_id` não entra (sem ela a
idempotência não existe, e a mesma ligação voltaria a cada import). Áudio que
não corresponde a nenhuma ligação do pacote também não entra: ele viraria uma
ligação inventada, com data tirada do nome do arquivo e nenhum registro por
trás. O relatório conta cada caso.

🚨 O AGENTE DE IMPORTAÇÃO NASCE REVOGADO. Quando o ramal nunca teve agente,
este script cria a linha de `agente_ligacao` que a ligação precisa apontar --
com uma chave aleatória que ninguém nunca vê e `revogado_em` já preenchido.
Ela serve para carimbar de quem é a ligação, e **não** para enviar nada. Nunca
revoga o agente vivo de um ramal: o PC que está mandando hoje não pode cair
porque alguém importou um arquivo velho.

⚠️ Outra origem (PABX, Intelbras, planilha à mão) fica FORA. Muda a chave de
idempotência e precisa de desenho aprovado por ele.

⚠️ O pacote é dado de fora: todo caminho de dentro do zip é lido pelo nome que
o `pacote.json` declara, nunca pelo que o zip diz, e nada é extraído para o
disco.
"""
import argparse
import hashlib
import json
import secrets
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, "/home/claude/movizap_painel")

from movizap import banco, ligacoes  # noqa: E402
from movizap.operacao import DadoInvalido  # noqa: E402

PACOTE = "movizap-ligacoes"
VERSAO_MAX = 1
DENTRO_GRAVACOES = "gravacoes/"


def mapa_de_arquivos(z: zipfile.ZipFile) -> dict[str, str]:
    """Os arquivos de `gravacoes/` do zip, por nome simples.

    🚨 MEDIDO EM 15/10: o `Compress-Archive` do **Windows PowerShell 5.1**
    grava os nomes com BARRA INVERTIDA (`gravacoes\\x.mp3`), e não com a barra
    do zip. O pacote vem dos PCs dos operadores, onde não se escolhe a versão
    do PowerShell -- então quem tem de aceitar os dois é este lado. Procurar só
    por `gravacoes/` fazia o importador recusar 19 gravações boas dizendo que
    elas estavam "ausentes do zip".
    """
    mapa = {}
    for nome in z.namelist():
        if nome.endswith("/") or nome.endswith("\\"):
            continue
        pedacos = nome.replace("\\", "/").split("/")
        if len(pedacos) == 2 and pedacos[0] == "gravacoes" and pedacos[1]:
            mapa[pedacos[1]] = nome
    return mapa


def ja_tem_ligacao(ramal: str, call_id: str) -> bool:
    """A conferência pergunta ao BANCO, não ao pacote.

    🚨 Sem isto, `--conferir` diria "11 entrariam" num pacote cujas 11 já
    estão todas na base -- e relatório que promete mais do que vai acontecer é
    a mesma doença de tela que mente.
    """
    return banco.um("SELECT 1 FROM ligacao WHERE ramal = %s AND call_id = %s",
                    (ramal, call_id)) is not None


def ja_tem_gravacao(sha: str) -> bool:
    return banco.um("SELECT 1 FROM ligacao_gravacao WHERE arquivo_sha256 = %s",
                    (sha,)) is not None


def ler_pacote(caminho: Path) -> tuple[dict, zipfile.ZipFile]:
    z = zipfile.ZipFile(caminho)
    nomes = set(z.namelist())
    if "pacote.json" not in nomes:
        raise SystemExit("Isto nao parece um pacote do MoviZap: falta pacote.json.")
    dados = json.loads(z.read("pacote.json").decode("utf-8"))
    if dados.get("pacote") != PACOTE:
        raise SystemExit(f"Pacote de outra origem ({dados.get('pacote')!r}): nao importo.")
    if int(dados.get("versao") or 0) > VERSAO_MAX:
        raise SystemExit(
            f"Pacote versao {dados.get('versao')}, e este script entende ate {VERSAO_MAX}.")
    ramal = str(dados.get("ramal") or "").strip()
    if not ramal.isdigit():
        raise SystemExit(f"Ramal invalido no pacote: {ramal!r}.")
    return dados, z


def agente_do_ramal(ramal: str, atendente: str | None, conferir: bool) -> dict:
    """O agente a que as ligações importadas vão pertencer.

    Nesta ordem: o agente VIVO do ramal; o último revogado dele; e só então um
    agente de importação novo, se `--atendente` disser de quem é.
    """
    vivo = banco.um("""SELECT id, atendente_id, ramal FROM agente_ligacao
                        WHERE ramal = %s AND revogado_em IS NULL
                        ORDER BY id DESC LIMIT 1""", (ramal,))
    if vivo:
        return dict(vivo) | {"origem": "agente vivo do ramal"}

    velho = banco.um("""SELECT id, atendente_id, ramal FROM agente_ligacao
                         WHERE ramal = %s ORDER BY id DESC LIMIT 1""", (ramal,))
    if velho:
        return dict(velho) | {"origem": "agente revogado do ramal (o mais recente)"}

    if not atendente:
        raise SystemExit(
            f"O ramal {ramal} nunca teve agente, e sem agente a ligacao nao tem\n"
            f"de quem ser. Diga de quem e o ramal:\n"
            f"  --atendente <login ou id>")

    pessoa = banco.um(
        "SELECT id, nome FROM atendente WHERE id::text = %s OR lower(login) = lower(%s)",
        (str(atendente), str(atendente)))
    if not pessoa:
        raise SystemExit(f"Atendente {atendente!r} nao encontrado.")
    if conferir:
        return {"id": None, "atendente_id": pessoa["id"], "ramal": ramal,
                "origem": f"criaria agente de importacao para {pessoa['nome']}"}

    # Chave aleatoria que ninguem ve, e ja revogada: esta linha existe para
    # carimbar de quem e a ligacao, nunca para enviar.
    with banco.cursor() as cur:
        cur.execute(
            """INSERT INTO agente_ligacao (atendente_id, ramal, chave_sha256,
                                           revogado_em, ultima_versao, ultimo_pc)
               VALUES (%s, %s, %s, now(), 'import', 'importacao retroativa')
               RETURNING id, atendente_id, ramal""",
            (pessoa["id"], ramal,
             hashlib.sha256(secrets.token_bytes(32)).hexdigest()))
        novo = cur.fetchone()
    print(f"  agente de importacao criado (id {novo['id']}, ja revogado) "
          f"para {pessoa['nome']}")
    return dict(novo) | {"origem": f"agente de importacao de {pessoa['nome']}"}


def importar(caminho: Path, atendente: str | None, conferir: bool) -> int:
    dados, z = ler_pacote(caminho)
    ramal = str(dados["ramal"]).strip()
    pc = str(dados.get("pc") or "?")[:60]
    ligs = dados.get("ligacoes") or []

    print(f"Pacote: {caminho.name}")
    print(f"  PC ............ {pc}")
    print(f"  ramal ......... {ramal}")
    print(f"  gerado em ..... {dados.get('gerado_em')}")
    print(f"  agente ........ v{dados.get('agente')}")
    print(f"  ligacoes ...... {len(ligs)}")
    if dados.get("fora_do_padrao"):
        print(f"  ja ficaram de fora no PC: {len(dados['fora_do_padrao'])} "
              f"arquivo(s) com nome fora do padrao")
    if dados.get("em_uso_agora"):
        print(f"  ja ficaram de fora no PC: {len(dados['em_uso_agora'])} "
              f"em uso na hora da exportacao")

    # 🚨 ABRIR E FECHAR O POOL É DO `__main__`, não desta função. Quando
    # estava aqui, dois imports seguidos no mesmo processo (o que a suíte faz)
    # fechavam o banco embaixo do próprio teste.
    try:
        agente = agente_do_ramal(ramal, atendente, conferir)
        print(f"  dono .......... {agente['origem']}")
        if conferir:
            print("  MODO CONFERIR: nada sera gravado.")

        # Tudo o que o pacote declara como arquivo, para achar o que sobrou.
        no_zip = mapa_de_arquivos(z)
        declarados = set()
        novas_grav = ja_grav = 0
        recusadas: list[str] = []
        # 🚨 A LIGAÇÃO É CONTADA UMA VEZ, mesmo tendo duas gravações. Contar
        # por gravação dizia "30 já estavam" onde o pacote tem 28 ligações --
        # e relatório com número errado é a mesma doença de tela que mente.
        vistas_novas: set[str] = set()
        vistas_ja: set[str] = set()

        for l in ligs:
            call_id = str(l.get("call_id") or "").strip()
            if not call_id:
                recusadas.append(
                    f"ligacao sem call_id ({l.get('numero')} em {l.get('inicio')}): "
                    f"sem ele a mesma ligacao voltaria a cada import")
                continue

            meta = {"call_id": call_id, "sentido": l.get("sentido"),
                    "numero": l.get("numero"), "inicio": l.get("inicio"),
                    "duracao_s": l.get("duracao_s") or 0,
                    "situacao": l.get("situacao")}
            gravs = l.get("gravacoes") or []

            try:
                if not gravs:
                    if conferir:
                        alvo = (vistas_ja if ja_tem_ligacao(ramal, call_id)
                                else vistas_novas)
                        alvo.add(call_id)
                        continue
                    r = ligacoes.registrar(agente, meta, None, None,
                                           f"importado:{pc}")
                    (vistas_novas if r["ligacao_nova"] else vistas_ja).add(call_id)
                    continue

                for g in gravs:
                    nome = str(g.get("arquivo") or "")
                    declarados.add(nome)
                    # Lido pelo nome que o `pacote.json` declara, e só se ele
                    # estiver na pasta de gravações: caminho que o zip inventa
                    # ("../../etc") não chega a ser procurado.
                    dentro = no_zip.get(nome) if nome and "/" not in nome \
                        and "\\" not in nome else None
                    if not dentro:
                        recusadas.append(f"{nome or '(sem nome)'}: declarado no "
                                         f"pacote.json e ausente do zip")
                        continue
                    conteudo = z.read(dentro)
                    sha = hashlib.sha256(conteudo).hexdigest()
                    if g.get("sha256") and g["sha256"].lower() != sha:
                        recusadas.append(f"{nome}: sha256 diferente do declarado "
                                         f"(arquivo trocado ou corrompido no caminho)")
                        continue
                    if conferir:
                        if ja_tem_gravacao(sha):
                            ja_grav += 1
                        else:
                            novas_grav += 1
                        if ja_tem_ligacao(ramal, call_id):
                            vistas_ja.add(call_id)
                        else:
                            vistas_novas.add(call_id)
                        continue
                    r = ligacoes.registrar(
                        agente, meta | {"gravacao_inicio": g.get("inicio")},
                        conteudo, g.get("nome_original") or nome, f"importado:{pc}")
                    (vistas_novas if r["ligacao_nova"] else vistas_ja).add(call_id)
                    if r.get("gravacao_nova"):
                        novas_grav += 1
                    else:
                        ja_grav += 1
            except DadoInvalido as e:
                recusadas.append(f"{call_id}: {e}")

        # Áudio no zip que nenhuma ligação do pacote reivindica: ele viraria
        # uma ligação inventada, com data tirada do nome do arquivo.
        for sobra in sorted(set(no_zip) - declarados):
            recusadas.append(f"{sobra}: audio sem ligacao correspondente no pacote")

        # A conta das ligações sai dos conjuntos, nos dois modos: é o que
        # garante que o mesmo pacote relate o mesmo número antes e depois.
        novas, ja = len(vistas_novas), len(vistas_ja)

        print("")
        print("RESULTADO" + (" (conferencia, nada gravado)" if conferir else ""))
        print(f"  ligacoes {'entrariam' if conferir else 'novas'} ......... {novas}")
        print(f"  ligacoes que ja estavam ..... {ja}")
        print(f"  gravacoes {'entrariam' if conferir else 'novas'} ........ {novas_grav}")
        print(f"  gravacoes que ja estavam .... {ja_grav}")
        print(f"  recusadas ................... {len(recusadas)}")
        for r in recusadas:
            print(f"    - {r}")
        return 0
    finally:
        z.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("pacote", type=Path)
    p.add_argument("--atendente", default=None,
                   help="login ou id, quando o ramal nunca teve agente")
    p.add_argument("--conferir", action="store_true",
                   help="le e confere, sem gravar nada")
    a = p.parse_args()
    if not a.pacote.exists():
        raise SystemExit(f"Nao achei {a.pacote}.")
    banco.abrir()
    try:
        sys.exit(importar(a.pacote, a.atendente, a.conferir))
    finally:
        banco.fechar()
