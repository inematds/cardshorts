#!/usr/bin/env python3
"""cardshorts — short 9:16 narrado a partir de cards HTML.

Um roteiro (roteiro.yaml) lista as cenas: cada cena tem uma fala e um card (molde de um estilo
ou HTML livre). O comando gera a voz (Chatterbox local, com a voz clonada), confere a fala por
transcrição, gera as imagens (FLUX.2 klein local), fotografa os cards e monta o MP4 com legenda
palavra a palavra e trilha opcional, ajustando a velocidade para caber no tempo máximo.

Uso:
  cardshorts.py novo <pasta> [--estilo versus]   cria uma pasta com roteiro de exemplo
  cardshorts.py estilos                            lista estilos e moldes
  cardshorts.py voz <roteiro.yaml>                 só a narração (com cache)
  cardshorts.py imagens <roteiro.yaml>             só as imagens (com cache)
  cardshorts.py cards <roteiro.yaml>               só os cards + previa.png
  cardshorts.py montar <roteiro.yaml>              tudo: voz, imagens, cards e vídeo
  cardshorts.py enviar <roteiro.yaml> [texto]      manda o vídeo pelo Telegram (config telegram_env)
  cardshorts.py musica <saida.wav> [prompt]        gera uma trilha local (MusicGen-small)
"""
import argparse, base64, difflib, hashlib, html, json, os, re, shutil, subprocess, sys, unicodedata, urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
ESTILOS = RAIZ / "estilos"
HOME = Path.home()

# Caminhos locais. Cada um pode ser trocado por variável de ambiente ou por config.yaml na raiz.
CFG = {
    "inemavox": os.environ.get("CS_INEMAVOX", str(HOME / "projetos/inemavox")),
    "vozes": os.environ.get("CS_VOZES", str(HOME / "projetos/timesmkt3/media/voice-refs")),
    "imagem_api": os.environ.get("CS_IMAGEM_API", "http://localhost:8000/generate"),
    "imagem_modelo": os.environ.get("CS_IMAGEM_MODELO", "flux2-klein"),
    "chrome": os.environ.get("CS_CHROME", ""),
    "musica_python": os.environ.get("CS_MUSICA_PY", str(HOME / "miniconda3/envs/chatterbox/bin/python")),
    "telegram_env": os.environ.get("CS_TELEGRAM_ENV", str(HOME / "projetos/openpcbotv3/.env")),
    "telegram_chat_env": os.environ.get("CS_TELEGRAM_CHAT_ENV", str(HOME / "projetos/openpcbotv2/.env")),
}
if (RAIZ / "config.yaml").exists():
    import yaml
    CFG.update({k: str(v) for k, v in (yaml.safe_load((RAIZ / "config.yaml").read_text()) or {}).items()})

# Voz: 0.6/0.6 é o ponto testado. Exagero 0.85 com cfg 0.35 deixava o "s" chiado (sotaque carioca).
VOZ_PADRAO = {"ref": "nei", "exaggeration": 0.6, "cfg_weight": 0.6, "temperature": 0.75}
FPS, PAD = 30, 0.25
TEMPO_MIN, TEMPO_MAX = 1.0, 1.2


def log(*a):
    print(*a, flush=True)


def sh(*a, **k):
    subprocess.run([str(x) for x in a], check=True, **k)


def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]))


_UN = "zero um dois tres quatro cinco seis sete oito nove dez onze doze treze quatorze quinze dezesseis dezessete dezoito dezenove".split()
_DZ = "_ _ vinte trinta quarenta cinquenta sessenta setenta oitenta noventa".split()
_CT = "_ cento duzentos trezentos quatrocentos quinhentos seiscentos setecentos oitocentos novecentos".split()
# feminino e variantes que o texto escrito usa e o Whisper não (ou vice-versa)
_EQUIV = {"duzentas": "duzentos", "trezentas": "trezentos", "quatrocentas": "quatrocentos", "quinhentas": "quinhentos",
          "seiscentas": "seiscentos", "setecentas": "setecentos", "oitocentas": "oitocentos", "novecentas": "novecentos",
          "uma": "um", "duas": "dois", "catorze": "quatorze", "pra": "para"}


def extenso(n):
    """Inteiro por extenso em português (até bilhões), só para comparar fala com transcrição."""
    if n < 20:
        return _UN[n]
    if n < 100:
        return _DZ[n // 10] + ("" if n % 10 == 0 else " e " + _UN[n % 10])
    if n < 1000:
        if n == 100:
            return "cem"
        return _CT[n // 100] + ("" if n % 100 == 0 else " e " + extenso(n % 100))
    for base, sing, plur in ((10**9, "um bilhao", "bilhoes"), (10**6, "um milhao", "milhoes"), (1000, "mil", "mil")):
        if n >= base:
            q, r = divmod(n, base)
            cab = sing if q == 1 else f"{extenso(q)} {plur}"
            return cab + ("" if r == 0 else (" e " if r < 100 or r % 100 == 0 else " ") + extenso(r))


def _numeros(s):
    def troca(m):
        txt = m.group(0)
        if "," in txt:  # 1,5 → um virgula cinco
            a, b = txt.split(",", 1)
            return f" {extenso(int(a.replace('.', '')))} virgula {extenso(int(b))} "
        return f" {extenso(int(txt.replace('.', '')))} "
    return re.sub(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?", troca, s)


def norm(s):
    s = unicodedata.normalize("NFD", s.lower()).encode("ascii", "ignore").decode()
    s = _numeros(s)
    return [_EQUIV.get(w, w) for w in re.sub(r"[^a-z0-9 ]", " ", s).split()]


def h(*partes):
    return hashlib.sha1(json.dumps(partes, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]


# ---------------------------------------------------------------- roteiro

def carregar(arq):
    import yaml
    arq = Path(arq).resolve()
    r = yaml.safe_load(arq.read_text())
    r["_dir"] = arq.parent
    r["_obra"] = arq.parent / ".obra"
    r["_obra"].mkdir(exist_ok=True)
    r.setdefault("estilo", "versus")
    r.setdefault("max_seg", 30)
    r.setdefault("legenda", True)
    r.setdefault("musica", False)
    r.setdefault("saida", arq.parent.name + ".mp4")
    r["voz"] = {**VOZ_PADRAO, **(r.get("voz") or {})}
    if not r.get("cenas"):
        sys.exit("roteiro sem cenas")
    for i, c in enumerate(r["cenas"], 1):
        if not c.get("fala"):
            sys.exit(f"cena {i}: falta a fala")
        if not (c.get("molde") or c.get("html") or c.get("video")):
            sys.exit(f"cena {i}: precisa de molde, html ou video")
    return r


# ---------------------------------------------------------------- voz

def transcrever(wav, pasta, palavras=False):
    """Transcrição local (Whisper large-v3 pelo inemavox). Devolve a lista de palavras ou segmentos."""
    pasta.mkdir(parents=True, exist_ok=True)
    w16 = pasta / "a16.wav"
    sh("ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-ar", "16000", "-ac", "1", w16)
    cmd = ["python3", "transcrever_v1.py", "--in", w16, "--outdir", pasta / "t", "--whisper-model", "large-v3", "--src", "pt"]
    if palavras:
        cmd.append("--words")
    sh(*cmd, cwd=CFG["inemavox"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    segs = json.loads((pasta / "t/transcript.json").read_text())
    segs = segs.get("segments", segs) if isinstance(segs, dict) else segs
    return [w for s in segs for w in s.get("words", [])] if palavras else segs


def conferir_e_cortar(wav, texto, pasta):
    """Confere a fala pela transcrição e corta o balbucio que o Chatterbox às vezes solta no fim.
    Devolve (semelhança 0–1, texto ouvido)."""
    palavras = transcrever(wav, pasta, palavras=True)
    ouvido = " ".join(w["word"].strip() for w in palavras)
    esperado = norm(texto)
    alvo = esperado[-1]
    hits = [w for w in palavras if norm(w["word"])[-1:] == [alvo]]
    d = dur(wav)
    if hits and d - (hits[-1]["end"] + 0.35) > 0.3:
        fim = hits[-1]["end"] + 0.35
        bruto = wav.with_suffix(".bruto.wav")
        shutil.move(wav, bruto)
        sh("ffmpeg", "-y", "-loglevel", "error", "-i", bruto, "-t", f"{fim:.2f}", "-af", f"afade=t=out:st={fim - 0.08:.2f}:d=0.08", wav)
        palavras = [w for w in palavras if w["start"] < fim]
        ouvido = " ".join(w["word"].strip() for w in palavras)
    sem = difflib.SequenceMatcher(None, esperado, norm(ouvido)).ratio()
    return sem, ouvido


def gerar_voz(r):
    v = r["voz"]
    ref = Path(v["ref"]) if "/" in v["ref"] else Path(CFG["vozes"]) / f"{v['ref']}.wav"
    if not ref.exists():
        sys.exit(f"voz de referência não encontrada: {ref}")
    pasta = r["_obra"] / "voz"
    pasta.mkdir(exist_ok=True)
    for i, c in enumerate(r["cenas"], 1):
        chave = h(c["fala"], v)
        dst = pasta / f"{chave}.wav"
        c["_wav"] = dst
        if dst.exists():
            continue
        for tentativa in range(1, 4):
            tmp = pasta / f"tmp_{chave}"
            shutil.rmtree(tmp, ignore_errors=True)
            tmp.mkdir()
            log(f"voz {i}/{len(r['cenas'])} (tentativa {tentativa}): {c['fala'][:60]}")
            with open(tmp / "log.txt", "w") as lg:
                subprocess.run(["timeout", "900", "python3", "tts_direct.py", "--text", c["fala"], "--lang", "pt",
                                "--engine", "chatterbox", "--ref", str(ref), "--outdir", str(tmp),
                                "--exaggeration", str(v["exaggeration"]), "--cfg-weight", str(v["cfg_weight"]),
                                "--temperature", str(v["temperature"])], cwd=CFG["inemavox"], stdout=lg, stderr=lg)
            g = tmp / "generated.wav"
            if not g.exists():
                log("  falhou a geração; veja", tmp / "log.txt")
                continue
            cand = pasta / f"{chave}.cand.wav"
            shutil.move(g, cand)
            sem, ouvido = conferir_e_cortar(cand, c["fala"], tmp / "conf")
            log(f"  ouvido ({sem:.0%}): {ouvido}")
            if sem >= 0.85:
                shutil.move(cand, dst)
                shutil.rmtree(tmp, ignore_errors=True)
                break
        else:
            sys.exit(f"cena {i}: a voz não saiu fiel ao texto em 3 tentativas. Reescreva a fala (números por extenso, siglas soletradas).")


# ---------------------------------------------------------------- imagens

def gerar_imagens(r):
    pasta = r["_obra"] / "img"
    pasta.mkdir(exist_ok=True)
    r["_img"] = {}
    for nome, spec in (r.get("imagens") or {}).items():
        if isinstance(spec, str):
            spec = {"prompt": spec}
        w, hgt = spec.get("w", 768), spec.get("h", 1344)
        prompt = spec["prompt"]
        if spec.get("estilo_foto", True):
            prompt = "realistic press photograph, 2026, sharp detail, no text, no logos, " + prompt
        dst = pasta / f"{nome}-{h(prompt, w, hgt, spec.get('seed', 7))}.png"
        r["_img"][nome] = dst
        if dst.exists():
            continue
        log(f"imagem {nome}: {spec['prompt'][:60]}")
        req = urllib.request.Request(CFG["imagem_api"], headers={"content-type": "application/json"},
                                     data=json.dumps({"model": CFG["imagem_modelo"], "prompt": prompt, "width": w, "height": hgt,
                                                      "steps": spec.get("steps", 4), "seed": spec.get("seed", 7)}).encode())
        with urllib.request.urlopen(req, timeout=1800) as resp:
            dst.write_bytes(base64.b64decode(json.loads(resp.read())["image"]))


# ---------------------------------------------------------------- cards

def moldes(estilo):
    arq = ESTILOS / estilo / "moldes.html"
    if not arq.exists():
        sys.exit(f"estilo desconhecido: {estilo} (veja: cardshorts.py estilos)")
    return {m.group(1): m.group(2) for m in re.finditer(r'<template id="([\w-]+)"[^>]*>(.*?)</template>', arq.read_text(), re.S)}


def valor(v, r):
    """Resolve o valor de um campo: img:nome → imagem gerada; caminho de arquivo → file://; texto → como está."""
    if not isinstance(v, str):
        return str(v)
    if v.startswith("img:"):
        return r["_img"][v[4:]].as_uri()
    if re.search(r"\.(png|jpe?g|webp|gif|svg)$", v, re.I):
        p = (r["_dir"] / v).resolve()
        if not p.exists():
            sys.exit(f"imagem não encontrada: {p}")
        return p.as_uri()
    return v


def chrome():
    if CFG["chrome"]:
        return CFG["chrome"]
    cands = sorted((HOME / ".cache/ms-playwright").glob("chromium_headless_shell-*/*/chrome-headless-shell"))
    if not cands:
        sys.exit("chrome-headless-shell não encontrado (npx playwright install chromium-headless-shell, ou CS_CHROME)")
    return str(cands[-1])


def pagina(corpo, estilo):
    fontes = ("https://fonts.googleapis.com/css2?family=Anton&family=Courier+Prime:wght@400;700"
              "&family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@500;700&family=Permanent+Marker&display=block")
    css = (ESTILOS / "comum.css").read_text() + "\n" + (ESTILOS / estilo / "estilo.css").read_text()
    return f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><link href="{fontes}" rel="stylesheet"><style>{css}</style></head><body>{corpo}</body></html>'


def gerar_cards(r):
    pasta = r["_obra"] / "cards"
    pasta.mkdir(exist_ok=True)
    for i, c in enumerate(r["cenas"], 1):
        if c.get("video"):
            c["_card"] = (r["_dir"] / c["video"]).resolve()
            continue
        estilo = c.get("estilo", r["estilo"])
        if c.get("html"):
            corpo = c["html"]
        else:
            ms = moldes(estilo)
            if c["molde"] not in ms:
                sys.exit(f"cena {i}: molde '{c['molde']}' não existe no estilo {estilo}. Há: {', '.join(ms)}")
            corpo = ms[c["molde"]]
            campos = {k: valor(v, r) for k, v in (c.get("campos") or {}).items()}
            faltam = sorted(set(re.findall(r"\{\{(\w+)\}\}", corpo)) - set(campos))
            if faltam:
                sys.exit(f"cena {i} ({c['molde']}): faltam campos {faltam}")
            corpo = re.sub(r"\{\{(\w+)\}\}", lambda m: campos[m.group(1)], corpo)
        corpo = re.sub(r'src="img:([\w-]+)"', lambda m: f'src="{r["_img"][m.group(1)].as_uri()}"', corpo)
        htm = pasta / f"c{i:02d}.html"
        htm.write_text(pagina(corpo, estilo))
        png = pasta / f"c{i:02d}.png"
        subprocess.run([chrome(), "--no-sandbox", "--hide-scrollbars", "--window-size=1080,1920", "--virtual-time-budget=10000",
                        f"--screenshot={png}", htm.as_uri()], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
        if not png.exists():
            sys.exit(f"cena {i}: o card não renderizou ({htm})")
        c["_card"] = png
    pngs = [c["_card"] for c in r["cenas"] if c["_card"].suffix == ".png"]
    if pngs:
        ent = sum((["-i", str(p)] for p in pngs), [])
        fc = "".join(f"[{k}]scale=270:480[p{k}];" for k in range(len(pngs))) + "".join(f"[p{k}]" for k in range(len(pngs))) + f"hstack={len(pngs)}"
        if len(pngs) == 1:
            fc = "[0]scale=270:480"
        sh("ffmpeg", "-y", "-loglevel", "error", *ent, "-filter_complex", fc, r["_dir"] / "previa.png")
        log("prévia:", r["_dir"] / "previa.png")


# ---------------------------------------------------------------- montagem

def ts(t):
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


CORRECOES = {"garanda": "garanta", "enema": "inema"}


def legenda_ass(voz, tmp, correcoes):
    palavras = transcrever(voz, tmp / "leg", palavras=True)
    fix = {**CORRECOES, **{k.lower(): v for k, v in (correcoes or {}).items()}}
    for w in palavras:
        k = w["word"].strip().lower().strip(".,?!")
        if k in fix:
            w["word"] = w["word"].lower().replace(k, fix[k])
    junt = []  # ".club" chega como palavra separada
    for w in palavras:
        if junt and w["word"].strip().startswith("."):
            junt[-1] = dict(junt[-1], word=junt[-1]["word"].rstrip() + w["word"].strip(), end=w["end"])
        else:
            junt.append(w)
    blocos, atual = [], []  # até 3 palavras, sem atravessar fim de frase
    for w in junt:
        atual.append(w)
        if len(atual) == 3 or w["word"].strip()[-1:] in ".?!":
            blocos.append(atual)
            atual = []
    if atual:
        blocos.append(atual)
    ev = []
    for b in blocos:
        for j, w in enumerate(b):
            fim = b[j + 1]["start"] if j + 1 < len(b) else w["end"]
            txt = " ".join(("{\\c&H2E3BD2&}" + x["word"].strip().upper() + "{\\c&HE7EFF3&}") if k == j else x["word"].strip().upper()
                           for k, x in enumerate(b))
            ev.append(f"Dialogue: 0,{ts(w['start'])},{ts(max(fim, w['start'] + 0.08))},W,,0,0,0,,{txt}")
    (tmp / "legenda.txt").write_text(" | ".join(" ".join(x["word"].strip() for x in b) for b in blocos))
    cab = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n[V4+ Styles]\n"
           "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
           "Style: W,Inter,74,&H00E7EFF3,&H00E7EFF3,&H00000000,&HB0000000,1,0,0,0,100,100,1,0,3,18,0,2,60,60,260,1\n\n"
           "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    ass = tmp / "leg.ass"
    ass.write_text(cab + "\n".join(ev) + "\n")
    return ass


def escolher_tempo(r):
    total = sum(dur(c["_wav"]) for c in r["cenas"])
    if r.get("tempo"):
        return float(r["tempo"]), total
    folga = r["max_seg"] - 0.6 - PAD * len(r["cenas"])
    t = max(TEMPO_MIN, round(total / folga + 0.005, 2))
    if t > TEMPO_MAX:
        sys.exit(f"a narração tem {total:.1f}s; para caber em {r['max_seg']}s precisaria acelerar {t:.2f}x "
                 f"(máximo {TEMPO_MAX}). Corte falas.")
    return t, total


def montar(r):
    tempo, bruto = escolher_tempo(r)
    log(f"narração {bruto:.1f}s → velocidade {tempo:.2f}x")
    tmp = r["_obra"] / "montagem"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    lista = []
    for i, c in enumerate(r["cenas"]):
        d = dur(c["_wav"]) / tempo + PAD
        seg = tmp / f"s{i:02d}.mp4"
        audio = f"[1]atempo={tempo},aresample=48000,aformat=channel_layouts=stereo,apad=pad_dur={PAD}[a]"
        if c["_card"].suffix == ".mp4":
            vf = f"[0]scale=1080:1920,tpad=stop_mode=clone:stop_duration={d:.3f},fps={FPS},format=yuv420p[v];"
            ent = ["-i", c["_card"]]
        else:
            q = int(d * FPS) + 1
            z = f"1+0.05*on/{q}" if i % 2 == 0 else f"1.05-0.05*on/{q}"
            vf = f"[0]scale=2160:3840,zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={q}:s=1080x1920:fps={FPS},format=yuv420p[v];"
            ent = ["-loop", "1", "-i", c["_card"]]
        sh("ffmpeg", "-y", "-loglevel", "error", *ent, "-i", c["_wav"], "-filter_complex", vf + audio, "-map", "[v]", "-map", "[a]",
           "-t", f"{d:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-c:a", "aac", "-b:a", "192k", seg)
        lista.append(f"file '{seg.name}'")
    (tmp / "lista.txt").write_text("\n".join(lista) + "\n")
    voz = tmp / "voz.mp4"
    sh("ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", tmp / "lista.txt", "-c", "copy", voz)
    total = dur(voz)
    saida = r["_dir"] / r["saida"]
    vf = ["-c:v", "copy"]
    if r["legenda"]:
        log("legenda palavra a palavra…")
        ass = legenda_ass(voz, tmp, r.get("correcoes"))
        vf = ["-vf", f"ass={ass}", "-c:v", "libx264", "-preset", "medium", "-crf", "19"]
    musica = r["musica"]
    if musica:
        trilha = (r["_dir"] / musica).resolve() if isinstance(musica, str) else RAIZ / "musicas/tensa.mp3"
        if not trilha.exists():
            sys.exit(f"trilha não encontrada: {trilha} (gere com: cardshorts.py musica {trilha})")
        af = (f"[0:a]asplit=2[v1][v2];[1:a]volume=0.35,afade=t=in:d=1.5[m];[m][v1]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[md];"
              f"[v2][md]amix=inputs=2:duration=first:normalize=0,afade=t=out:st={total - 2:.2f}:d=2[a]")
        sh("ffmpeg", "-y", "-loglevel", "error", "-i", voz, "-stream_loop", "-1", "-i", trilha, "-filter_complex", af,
           "-map", "0:v", "-map", "[a]", *vf, "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", saida)
    else:
        sh("ffmpeg", "-y", "-loglevel", "error", "-i", voz, *vf, "-c:a", "copy", "-movflags", "+faststart", saida)
    final = dur(saida)
    log(f"pronto: {saida} ({final:.1f}s)")
    if final > r["max_seg"]:
        sys.exit(f"ATENÇÃO: {final:.1f}s passou do máximo de {r['max_seg']}s")
    if r["legenda"]:
        log("legenda:", (tmp / "legenda.txt").read_text())


# ---------------------------------------------------------------- utilidades

def env_val(path, chave):
    try:
        for linha in open(os.path.expanduser(path)):
            if linha.startswith(chave + "="):
                return linha.split("=", 1)[1].strip().strip('"').strip("'")
    except FileNotFoundError:
        return None


def enviar(r, texto):
    """Envia o vídeo pelo bot do Telegram. Token e chat lidos na hora; nada é impresso."""
    import uuid
    token = env_val(CFG["telegram_env"], "TELEGRAM_BOT_TOKEN_V3") or env_val(CFG["telegram_env"], "TELEGRAM_BOT_TOKEN")
    chat = env_val(CFG["telegram_env"], "ALLOWED_CHAT_ID") or env_val(CFG["telegram_chat_env"], "ALLOWED_CHAT_ID")
    if not (token and chat):
        sys.exit("token/chat do Telegram não encontrados (CS_TELEGRAM_ENV)")
    video = r["_dir"] / r["saida"]
    b = uuid.uuid4().hex
    partes = [f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
              for k, v in (("chat_id", chat), ("caption", texto or r.get("titulo", video.stem)), ("supports_streaming", "true"),
                           ("width", "1080"), ("height", "1920"))]
    partes.append(f'--{b}\r\nContent-Disposition: form-data; name="video"; filename="{video.name}"\r\nContent-Type: video/mp4\r\n\r\n'.encode()
                  + video.read_bytes() + b"\r\n")
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendVideo", data=b"".join(partes) + f"--{b}--\r\n".encode(),
                                 headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    resp = json.loads(urllib.request.urlopen(req, timeout=300).read())
    log("enviado" if resp.get("ok") else f"falhou: {resp.get('description')}")


MUSICA_PROMPT = ("dark tense cinematic documentary underscore, pulsing low synth bass, ticking clock percussion, steady driving rhythm, "
                 "ominous strings, news investigation mood, instrumental, no vocals, 100 bpm")


def musica(saida, prompt):
    cod = f"""
import sys, torch, scipy.io.wavfile as wf
from transformers import AutoProcessor, MusicgenForConditionalGeneration
dev = "cuda" if torch.cuda.is_available() else "cpu"
proc = AutoProcessor.from_pretrained("facebook/musicgen-small")
m = MusicgenForConditionalGeneration.from_pretrained("facebook/musicgen-small").to(dev)
inp = proc(text=[{prompt!r}], padding=True, return_tensors="pt").to(dev)
a = m.generate(**inp, max_new_tokens=1500, do_sample=True, guidance_scale=3.5)
wf.write({str(saida)!r}, m.config.audio_encoder.sampling_rate, a[0, 0].cpu().numpy())
"""
    Path(saida).parent.mkdir(parents=True, exist_ok=True)
    sh(CFG["musica_python"], "-c", cod)
    log("trilha:", saida)


def novo(pasta, estilo):
    pasta = Path(pasta)
    if (pasta / "roteiro.yaml").exists():
        sys.exit(f"já existe: {pasta / 'roteiro.yaml'}")
    ex = RAIZ / "exemplos" / estilo / "roteiro.yaml"
    if not ex.exists():
        ex = RAIZ / "exemplos/versus/roteiro.yaml"
    pasta.mkdir(parents=True, exist_ok=True)
    shutil.copy(ex, pasta / "roteiro.yaml")
    log(f"criado {pasta / 'roteiro.yaml'} (a partir de {ex.parent.name}). Edite e rode: cardshorts.py montar {pasta / 'roteiro.yaml'}")


def listar_estilos():
    for d in sorted(p for p in ESTILOS.iterdir() if p.is_dir()):
        desc = re.search(r"/\*\s*(.*?)\s*\*/", (d / "estilo.css").read_text())
        log(f"{d.name:10s} {desc.group(1) if desc else ''}")
        arq = (d / "moldes.html").read_text()
        for m in re.finditer(r'<template id="([\w-]+)"[^>]*>(.*?)</template>', arq, re.S):
            campos = sorted(set(re.findall(r"\{\{(\w+)\}\}", m.group(2))))
            log(f"    {m.group(1):16s} campos: {', '.join(campos) or '—'}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["novo", "estilos", "voz", "imagens", "cards", "montar", "enviar", "musica"])
    ap.add_argument("alvo", nargs="?")
    ap.add_argument("extra", nargs="?")
    ap.add_argument("--estilo", default="versus")
    a = ap.parse_args()
    if a.cmd == "estilos":
        return listar_estilos()
    if not a.alvo:
        sys.exit("falta o argumento (pasta ou roteiro.yaml)")
    if a.cmd == "novo":
        return novo(a.alvo, a.estilo)
    if a.cmd == "musica":
        return musica(Path(a.alvo).resolve(), a.extra or MUSICA_PROMPT)
    r = carregar(a.alvo)
    if a.cmd == "enviar":
        return enviar(r, a.extra)
    if a.cmd in ("voz", "montar"):
        gerar_voz(r)
    if a.cmd in ("imagens", "cards", "montar"):
        gerar_imagens(r)
    if a.cmd in ("cards", "montar"):
        gerar_cards(r)
    if a.cmd == "montar":
        montar(r)


if __name__ == "__main__":
    main()
