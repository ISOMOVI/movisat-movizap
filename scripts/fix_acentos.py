# -*- coding: utf-8 -*-
"""Os rotulos que a PESSOA le vao com acento. Eu os escrevi sem, e rotulo
publico sem acento e erro de portugues na cara do cliente."""
import pathlib, sys
c = pathlib.Path('/home/claude/movizap_painel/scripts/carregar_formularios.py')
t = c.read_text(encoding='utf-8')
pares = [
    ('"label": "Problemas com o veiculo"', '"label": "Problemas com o veículo"'),
    ('"label": "Sugestao de melhoria"', '"label": "Sugestão de melhoria"'),
    ('"rotulo": "Veiculo e placa"', '"rotulo": "Veículo e placa"'),
]
for velho, novo in pares:
    if novo in t:
        print('= ja aplicado:', novo); continue
    assert t.count(velho) == 1, (velho, t.count(velho))
    t = t.replace(velho, novo)
    print('+', novo)
c.write_text(t, encoding='utf-8')
