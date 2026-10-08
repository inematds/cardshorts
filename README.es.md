# cardshorts

[![cardshorts](guia/assets/banner-es.jpg)](https://inematds.github.io/cardshorts/guia/es/)

**🇧🇷 [Português](README.md) · 🇺🇸 [English](README.en.md) · 🇪🇸 [Español](README.es.md)**

## Qué es

cardshorts es una herramienta de línea de comandos que crea videos cortos verticales (Reels, Shorts, TikTok) a partir de un archivo de texto. Cada escena tiene un diálogo y una pantalla lista (un "card"). La herramienta graba la narración con una voz clonada, verifica que la voz haya dicho bien el texto, genera las imágenes y entrega el MP4 con subtítulos palabra por palabra, en 30 segundos como máximo. Es para quien quiere publicar videos provocadores con frecuencia sin editar a mano. Corre en tu computadora, con tarjeta de video y los proyectos de voz e imagen de INEMA instalados.

## 📖 Guía de uso

Guía completa (landing + paso a paso): **https://inematds.github.io/cardshorts/guia/es/**

Short 9:16 provocador y narrado, a partir de **cards HTML**, con un archivo de guion y un comando.

```
roteiro.yaml ──▶ voz (Chatterbox local, voz clonada) ──▶ verificación por transcripción (Whisper local)
             ──▶ imágenes (FLUX.2 klein local) ──▶ cards (Chrome headless) ──▶ MP4 1080×1920
                 con subtítulos palabra por palabra, música opcional y velocidad ajustada para caber en 30 s
```

Todo corre en tu máquina. Nada de pago, ninguna API externa.

## Uso rápido

```bash
./cardshorts.py estilos                              # estilos y moldes disponibles
./cardshorts.py novo meu-video --estilo extrato      # crea meu-video/roteiro.yaml
./cardshorts.py cards meu-video/roteiro.yaml         # solo imágenes + cards + previa.png (rápido)
./cardshorts.py montar meu-video/roteiro.yaml        # video completo
./cardshorts.py musica musicas/minha.mp3 "calm lofi" # música local (MusicGen-small)
```

## Guion

```yaml
titulo: "Você × humanoides"
saida: versus.mp4
estilo: versus
max_seg: 30
legenda: true
musica: true            # musicas/tensa.mp3 o una ruta
voz: {ref: nei}         # <carpeta de voces>/nei.wav
imagens:
  dupla: {prompt: "two modern faceless humanoid robots...", w: 1088, h: 640}
cenas:
  - fala: "De um lado, quem trabalha. Do outro, os humanoides."
    molde: capa-dupla
    campos: {foto_cima: "img:equipe", foto_baixo: "img:dupla", faixa: "VOCÊ × ELES", tag_cima: "...", tag_baixo: "..."}
  - fala: "..."
    html: |               # card libre cuando ningún molde sirve
      <section class="card" style="background:#000">...</section>
```

Escribe los diálogos como se habla: números en letras, "inema ponto club".

## Estilos

| estilo | apariencia | moldes |
|---|---|---|
| `versus` | editorial en blanco y negro + rojo | capa-dupla, tela-dividida, pergunta-foto, foto-cheia, cta-faixa, cta-lista |
| `cracha` | diana, credenciales selladas, boleta | capa-mira, dois-crachas, cedula, cracha-destaque |
| `documento` | papel mecanografiado | capa-pergunta, formulario, aviso, formulario-preenchido, certificado |
| `extrato` | factura / estado de cuenta | recibo-total, recibo, recibo-carimbo, recibo-enquete |
| `celular` | interfaz de teléfono | notificacao, busca, fila, enquete |

Ejemplos listos en `exemplos/<estilo>/roteiro.yaml`.

## Lo que garantiza el comando

- **Habla fiel:** cada fragmento se transcribe; por debajo de 85 % de similitud con el texto, lo genera de nuevo (hasta 3×).
- **Sin balbuceo:** corta lo que la voz suelta después de la última palabra.
- **Cabe en el tiempo:** acelera el habla hasta 1,2× para que quepa en `max_seg`; si no cabe, se detiene y pide recortar.
- **Caché:** la voz y las imágenes solo se generan de nuevo cuando cambia el texto/prompt (`.obra/`).

## Requisitos

- inemavox (proyecto INEMA) con `tts_direct.py` (Chatterbox) y `transcrever_v1.py` (Whisper)
- servidor de imágenes compatible con `POST /generate` (inemaimg, FLUX.2 klein)
- `ffmpeg` con libass, Chrome headless shell de Playwright, Python 3 + PyYAML
- Rutas ajustables con variables `CS_*` o `config.yaml` (ver el inicio de `cardshorts.py`)

## Skill

`skill/SKILL.md` le enseña al agente (Claude Code / Codex) a usar el motor con las reglas de contenido.
Instálala con un enlace: `ln -s $PWD/skill ~/.claude/skills/cardshorts`.

Música de ejemplo generada con MusicGen-small (Meta, CC-BY-NC). Licencia del código: MIT.
