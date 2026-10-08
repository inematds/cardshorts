# cardshorts

[![cardshorts](guia/assets/banner.jpg)](https://inematds.github.io/cardshorts/guia/)

**🇧🇷 [Português](README.md) · 🇺🇸 [English](README.en.md) · 🇪🇸 [Español](README.es.md)**

## O que é

O cardshorts é uma ferramenta de linha de comando que cria vídeos curtos verticais (Reels, Shorts, TikTok) a partir de um arquivo de texto. Cada cena tem uma fala e uma tela pronta (um "card"). A ferramenta grava a narração com uma voz clonada, confere se a voz falou certo, gera as imagens e entrega o MP4 com legenda palavra a palavra, cabendo em 30 segundos. É para quem quer publicar vídeos provocativos com frequência sem editar na mão. Roda no seu computador, com placa de vídeo e os projetos de voz e imagem do INEMA instalados.

## 📖 Guia de uso

Guia completo (landing + passo a passo): **https://inematds.github.io/cardshorts/guia/**

Short 9:16 provocativo, narrado, a partir de **cards HTML** — com um arquivo de roteiro e um comando.

```
roteiro.yaml ──▶ voz (Chatterbox local, voz clonada) ──▶ conferência por transcrição (Whisper local)
             ──▶ imagens (FLUX.2 klein local) ──▶ cards (Chrome headless) ──▶ MP4 1080×1920
                 com legenda palavra a palavra, trilha opcional e velocidade ajustada para caber em 30 s
```

Tudo roda na sua máquina. Nada pago, nenhuma API externa.

## Uso rápido

```bash
./cardshorts.py estilos                              # estilos e moldes disponíveis
./cardshorts.py novo meu-video --estilo extrato      # cria meu-video/roteiro.yaml
./cardshorts.py cards meu-video/roteiro.yaml         # só imagens + cards + previa.png (rápido)
./cardshorts.py montar meu-video/roteiro.yaml        # vídeo completo
./cardshorts.py musica musicas/minha.mp3 "calm lofi" # trilha local (MusicGen-small)
```

## Roteiro

```yaml
titulo: "Você × humanoides"
saida: versus.mp4
estilo: versus
max_seg: 30
legenda: true
musica: true            # musicas/tensa.mp3 ou caminho
voz: {ref: nei}         # <pasta de vozes>/nei.wav
imagens:
  dupla: {prompt: "two modern faceless humanoid robots...", w: 1088, h: 640}
cenas:
  - fala: "De um lado, quem trabalha. Do outro, os humanoides."
    molde: capa-dupla
    campos: {foto_cima: "img:equipe", foto_baixo: "img:dupla", faixa: "VOCÊ × ELES", tag_cima: "...", tag_baixo: "..."}
  - fala: "..."
    html: |               # card livre quando nenhum molde serve
      <section class="card" style="background:#000">...</section>
```

Escreva as falas como se fala: números por extenso, "inema ponto club".

## Estilos

| estilo | cara | moldes |
|---|---|---|
| `versus` | editorial P&B + vermelho | capa-dupla, tela-dividida, pergunta-foto, foto-cheia, cta-faixa, cta-lista |
| `cracha` | alvo, crachás carimbados, cédula | capa-mira, dois-crachas, cedula, cracha-destaque |
| `documento` | papel datilografado | capa-pergunta, formulario, aviso, formulario-preenchido, certificado |
| `extrato` | nota fiscal / extrato | recibo-total, recibo, recibo-carimbo, recibo-enquete |
| `celular` | interface de telefone | notificacao, busca, fila, enquete |

Exemplos prontos em `exemplos/<estilo>/roteiro.yaml`.

## O que o comando garante

- **Fala fiel:** cada trecho é transcrito; abaixo de 85 % de semelhança com o texto, gera de novo (até 3×).
- **Sem balbucio:** corta o que a voz solta depois da última palavra.
- **Cabe no tempo:** acelera a fala até 1,2× para caber em `max_seg`; se não couber, para e pede corte.
- **Cache:** voz e imagens só são geradas de novo quando o texto/prompt muda (`.obra/`).

## Requisitos

- inemavox (projeto INEMA) com `tts_direct.py` (Chatterbox) e `transcrever_v1.py` (Whisper)
- servidor de imagem compatível com `POST /generate` (inemaimg, FLUX.2 klein)
- `ffmpeg` com libass, Chrome headless shell do Playwright, Python 3 + PyYAML
- Caminhos ajustáveis por variáveis `CS_*` ou `config.yaml` (veja o topo de `cardshorts.py`)

## Skill

`skill/SKILL.md` ensina o agente (Claude Code / Codex) a usar o motor com as regras de conteúdo.
Instale com um link: `ln -s $PWD/skill ~/.claude/skills/cardshorts`.

Trilha de exemplo gerada com MusicGen-small (Meta, CC-BY-NC). Licença do código: MIT.
