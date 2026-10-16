"""As senhas de alistamento de TODOS os ramais, num arquivo (15/10, pedido dele).

🔵 *"lista de ramais, para deixar as senhas prontas para mim ... salve como .txt
na mesma pasta as senhas para cada ramal"*.

🚨 CADA SENHA ALISTA UM PC COMO AQUELE RAMAL, e alistar revoga o PC anterior.
Este arquivo, inteiro, vale por 48 h: quem o tiver pode por o MicroSIP dele no
lugar do de qualquer operador da lista. Ele e do PC dele e e para ser apagado
depois do mutirao -- esta escrito dentro do proprio arquivo.

⚠️ O ramal precisa estar amarrado a um ATENDENTE ATIVO. Quem nao estiver sai na
secao "ficaram de fora", com o motivo -- nunca com uma senha inventada e nunca
criando conta para ninguem.

Uso: ./venv/bin/python scripts/senhas_dos_ramais.py [--gravar <arquivo>]
"""
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, "/home/claude/movizap_painel")

from movizap import banco, ligacoes_alistar  # noqa: E402
from movizap.operacao import DadoInvalido  # noqa: E402

BR = ZoneInfo("America/Sao_Paulo")

# A lista que ele mandou, na ordem dele.
RAMAIS = [
    ("3347", "Aline"), ("3348", "Ludmila"), ("3399", "Rodrigo"),
    ("3400", "Karla"), ("3401", "Erika"), ("3402", "Caio"),
    ("3403", "Fabio"), ("3404", "Iago"), ("3405", "Claudia"),
    ("3406", None), ("3407", None),           # "Livre" na planilha dele
]

destino = None
if "--gravar" in sys.argv:
    destino = Path(sys.argv[sys.argv.index("--gravar") + 1])

banco.abrir()
try:
    prontas, fora = [], []
    for ramal, nome in RAMAIS:
        if nome is None:
            fora.append((ramal, "-", "livre na planilha: sem dono, sem senha"))
            continue
        # Quem já é dono do ramal ganha a senha sem precisar do nome; quem
        # ainda não é, é amarrado agora (é o que `--nome` sempre fez).
        try:
            r = ligacoes_alistar.preparar(ramal, nome)
        except DadoInvalido as e:
            try:
                r = ligacoes_alistar.preparar(ramal)
            except DadoInvalido:
                fora.append((ramal, nome, str(e)))
                continue
        agente = banco.um(
            """SELECT ultimo_pc, ultimo_contato_em FROM agente_ligacao
                WHERE ramal = %s AND revogado_em IS NULL""", (ramal,))
        prontas.append({
            "ramal": ramal, "atendente": r["atendente"],
            # 🚨 QUEM JA ENVIA NAO LEVA SENHA. Usar a senha de um ramal ja
            # alistado REVOGA o PC que esta funcionando -- senha que ninguem
            # deve usar nao precisa estar no papel.
            "senha": "-" if agente else r["senha"],
            "ja_instalado": bool(agente),
            "pc": (agente or {}).get("ultimo_pc"),
        })

    agora = datetime.now(BR)
    validade = agora.fromtimestamp(
        agora.timestamp() + ligacoes_alistar.JANELAS_ACEITAS
        * ligacoes_alistar.JANELA_S, BR)

    linhas = [
        "MoviZap - Ligacoes | SENHAS DE ALISTAMENTO",
        "=" * 64,
        f"Geradas em {agora:%d/%m/%Y %H:%M} - valem ate {validade:%d/%m/%Y %H:%M}",
        "",
        "COMO USAR: no PC da pessoa, dois cliques em",
        "'MoviZap-Instalar-Ligacoes.exe', conferir o ramal que aparece na tela e",
        "digitar a senha deste arquivo correspondente AQUELE ramal.",
        "",
        "!! QUEM JA ENVIA NAO TEM SENHA AQUI (coluna com '-'): alistar de novo",
        "   derrubaria o PC que esta funcionando.",
        "!! CADA SENHA SERVE UMA VEZ SO. Depois de usada, ela morre -- mesmo",
        "   dentro das 48 h. Se precisar de outra, e so pedir.",
        "!! ALISTAR UM PC REVOGA O PC ANTERIOR daquele ramal. Quem ja esta",
        "   enviando (marcado abaixo) NAO precisa ser alistado de novo.",
        "!! ESTE ARQUIVO E UMA CHAVE. Quem o tiver pode por o MicroSIP dele no",
        "   lugar do de qualquer operador desta lista, por 48 h. Apagar depois",
        "   do mutirao.",
        "",
        "-" * 64,
        f"{'RAMAL':<8}{'PESSOA':<22}{'SENHA':<12}SITUACAO",
        "-" * 64,
    ]
    for p in prontas:
        situacao = (f"ja envia (PC {p['pc'] or '?'}) - NAO precisa"
                    if p["ja_instalado"] else "falta instalar")
        linhas.append(f"{p['ramal']:<8}{p['atendente'][:21]:<22}{p['senha']:<12}{situacao}")

    if fora:
        linhas += ["", "-" * 64, "FICARAM DE FORA (sem senha, e por que):", "-" * 64]
        for ramal, nome, motivo in fora:
            linhas.append(f"{ramal:<8}{nome[:21]:<22}{motivo}")

    linhas += [
        "", "-" * 64,
        "Conferir quem ja subiu: 2-PC-DO-IAGO\\Conferir agentes.cmd",
        "Senha avulsa de um ramal: 2-PC-DO-IAGO\\Senha de alistamento.cmd",
    ]

    texto = "\n".join(linhas) + "\n"
    if destino:
        destino.write_text(texto, encoding="utf-8")
        print(f"gravado: {destino} ({len(prontas)} senha(s), {len(fora)} de fora)")
    else:
        print(texto)
finally:
    banco.fechar()
