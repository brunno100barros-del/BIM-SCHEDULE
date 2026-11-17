"""Preparação para inteligência artificial.

- ``exchange``: formato padronizado de pedido/resposta (comum a todas as IAs).
- ``providers``: interface comum, Ollama (somente verificação de disponibilidade)
  e intercâmbio manual por arquivo (Claude).
- ``service``: montagem do pacote a partir do projeto e validação de respostas.

A IA nunca calcula o cronograma: propostas validadas serão aplicadas pelo motor
de engenharia (``app.engine``) em etapa futura.
"""
