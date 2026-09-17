"""O aviso de mensagem cifrada diz a verdade (17/09).

🚨 O RÓTULO MENTIU DE 27/08 A 17/09. O `secretEncryptedMessage` era traduzido
para "[mensagem de visualização única]" -- que é OUTRO recurso do WhatsApp, a
foto que some depois de aberta. O commit que criou o rótulo (`adefc9e`) e o
`docs/02` descreviam a coisa certa ("chega criptografado e não temos a
chave"); só o texto que ia para a tela é que não seguiu a razão escrita ao
lado dele.

🚨 CUSTO MEDIDO: 92 linhas em 60 conversas, de 07/08 a 17/09, dizendo ao
atendente que chegou uma foto que some. Corrigidas por
`scripts/corrigir_rotulo_cifrado.py`.

⚠️ ESTE TESTE PRENDE A PROMESSA, NÃO A FRASE. Ele não exige um texto exato --
exige que o aviso NÃO afirme ser coisa que não sabemos que é, e que diga o
que de fato sabemos: que veio algo e que não conseguimos abrir.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/home/claude/movizap_painel")

from movizap.conversas import AVISOS  # noqa: E402

AVISO = AVISOS["secretEncryptedMessage"]


class TestOAvisoDeCifradaDizAVerdade:

    def test_nao_promete_visualizacao_unica(self):
        """É outro recurso do WhatsApp, e foi o erro de 27/08 a 17/09."""
        assert "visualiza" not in AVISO.lower()
        assert "única" not in AVISO.lower()

    def test_nao_promete_nenhum_tipo_de_midia(self):
        """Não sabemos o que é: em 17/09 um destes apareceu no lugar exato de
        uma edição de mensagem, e nem isso dá para afirmar."""
        for palavra in ("foto", "imagem", "vídeo", "video", "áudio", "audio",
                        "figurinha", "documento"):
            assert palavra not in AVISO.lower(), f"o aviso promete ser {palavra}"

    def test_diz_que_veio_algo_e_que_nao_da_para_abrir(self):
        """O atendente precisa saber as duas coisas -- que chegou, e que o
        painel não consegue ler. Sem a primeira, ele não sabe que perdeu algo;
        sem a segunda, acha que o painel está quebrado."""
        assert "cifrada" in AVISO.lower() or "criptograf" in AVISO.lower()
        assert "não consegue" in AVISO.lower() or "nao consegue" in AVISO.lower()

    def test_continua_sendo_aviso_entre_colchetes(self):
        """Colchete é o que distingue texto NOSSO de fala do cliente no balão.
        Sem ele, o aviso teria a mesma cara de uma mensagem digitada."""
        assert AVISO.startswith("[") and AVISO.endswith("]")

    def test_nao_e_o_nome_cru_da_chave(self):
        """A regra de 27/08: o nome da chave nunca chega ao atendente."""
        assert "secretEncryptedMessage" not in AVISO
