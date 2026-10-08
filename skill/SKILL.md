---
name: cardshorts
description: >-
  Gera SHORTS 9:16 provocativos narrados com a voz do Nei a partir de cards HTML (estilos versus,
  cracha, documento, extrato, celular): roteiro.yaml → voz local conferida por transcrição → imagens
  FLUX.2 klein → cards → MP4 com legenda palavra a palavra e trilha, abaixo de 30 s. Gatilho:
  "/cardshorts", "faz um short provocativo", "vídeo de cards", "3 versões diferentes desse short",
  "no estilo do extrato / do versus / do celular", "short com os dados do X".
---

# cardshorts — shorts de cards narrados

Motor: `~/projetos/cardshorts/cardshorts.py` (repo inematds/cardshorts). Tudo local: voz Chatterbox
(inemavox), conferência Whisper large-v3, imagens FLUX.2 klein (inemaimg :8000), cards no Chrome
headless, montagem ffmpeg. Nada pago, nenhuma API externa (o envio ao Telegram é só quando pedido).

## Fluxo

1. **Ideia → 1 frase-choque.** Cada vídeo defende UMA ideia. A cena 1 é o gancho: imagem forte
   no quadro 0 e a frase-choque como 1ª fala (nada de "Imagine que…").
2. **Escolher o estilo** (`./cardshorts.py estilos` lista moldes e campos). Pedido de "N versões
   diferentes" = N **estilos diferentes**, não o mesmo molde com outro texto (o Nei reclamou que
   F2/F3/F4 saíram iguais).
   - `versus` — editorial P&B + vermelho, X × Y, telas divididas. O preferido do Nei.
   - `cracha` — alvo, crachás SUBSTITUÍDO, cédula com plano em branco.
   - `documento` — formulário datilografado EM BRANCO → preenchido, aviso, certificado.
   - `extrato` — nota fiscal/extrato: previsto × usado × "entregue a você".
   - `celular` — notificação, busca, fila, enquete SIM/NÃO.
3. **Criar a pasta** em `~/projetos/output/<serie>/<video>/`:
   `./cardshorts.py novo <pasta> --estilo <estilo>` e editar o `roteiro.yaml`.
4. **Prévia barata primeiro:** `./cardshorts.py cards <roteiro>` gera imagens + cards + `previa.png`.
   Olhe a prévia (Read) antes de gastar tempo com a voz: texto saindo do card, legenda (faixa
   y 1450–1720) cobrindo título, foto cortando cabeça.
5. **Montar:** `./cardshorts.py montar <roteiro>` (≈2 min por fala na 1ª vez; depois tudo vem do
   cache `.obra/`). Ele confere cada fala por transcrição (refaz até 3× se < 85%), corta o balbucio
   final, ajusta a velocidade (até 1,2×) para caber em `max_seg` e falha se não couber.
6. **Conferir:** ler a linha "legenda:" do log (erros de transcrição → `correcoes:` no roteiro) e
   extrair 4 quadros do MP4 para olhar.
7. **Entregar:** `./cardshorts.py enviar <roteiro> "texto"` manda pelo bot v3 quando o Nei pedir.
   YouTube = yt-pubx (short **sem** miniatura).

## Regras de texto

- Falas **escritas como se fala**: números por extenso ("quatrocentos e trinta e seis milhões"),
  "inema ponto club", siglas que a voz erra viram grafia fonética ("ó ésse uórk").
- 30 s ≈ 65–75 palavras no total. 4–5 cenas. Uma fala por card, 3–9 s cada.
- Fecho com CTA: inema.club grátis (OSWork, Gestão de IA e Agentes).

## Regras de conteúdo (não negociáveis)

- **Política:** nunca gerar imagem ou voz de pessoa real (candidato, autoridade). Foto real só a
  que o Nei forneceu, com etiqueta "FOTO ORIGINAL". Sobre planos de candidatos, **perguntar**
  ("eles têm um plano?"), não afirmar o que não foi pesquisado.
- **Números públicos:** só de fonte oficial ATUAL (ex.: painel do PBIA, pbia.cgee.org.br/resultados),
  com a fonte no card (`fonte`) e no `fontes.md` da série. Relatório antigo não vale como estado atual.
- Cena inventada (notificação, fila) leva "(mensagem imaginária)" / "ilustrativo".
- Humanoides: modelos atuais (cabeça lisa com visor preto, corpo branco/cinza), sem nome de marca
  na imagem gerada, com etiqueta "ilustrativo". Nada de andróide de rosto humano de filme.

## Voz

`voz: {ref: nei}` com exaggeration 0.6 / cfg 0.6 (padrão). **Não** usar 0.85/0.35: deixa o "s"
chiado (sotaque carioca), o Nei reprovou. Vozes ficam em `~/projetos/timesmkt3/media/voice-refs/`.
Se a voz ainda incomodar, as saídas melhores são pagas/externas (clone ElevenLabs) e precisam de
autorização explícita do Nei.

## HTML livre

Quando nenhum molde serve: `html: |` na cena com um `<section class="card" style="background:…">`.
Classes prontas em `estilos/comum.css` (`ph`, `bw`, `anton`, `tag`, `stamp`, `rd`, `y`) e no CSS do
estilo da cena. Imagens geradas: `src="img:nome"`. Bom molde novo vira `<template>` no
`moldes.html` do estilo (e um exemplo em `exemplos/`).
