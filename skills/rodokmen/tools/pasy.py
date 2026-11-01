#!/usr/bin/env python3
"""Pásy pro síto Jev: každou stranu snímku rozřeže na překrývající se vodorovné pásy a zvětší je
(postup a měření viz reference/sito_jev.md; celé dvoustrany Jev nepřečte).

Použití (z kořene projektu):
  pasy.py <výstupní složka> <snímek.jpg>… [--strany N]
    snímky    stačí zmenšené (náhled), číslo snímku se bere z poslední skupiny číslic v názvu souboru
              (s065_q.jpg → 65)
    --strany  kolik stran je vedle sebe na snímku (výchozí 2 = dvoustrana; 1 = jedna strana)
Vytvoří <výstupní složka>/<snímek 4 číslice><strana L/R/P><pás 2 číslice>.jpg, např. 0065R01.jpg.
Strana se zmenší nebo zvětší na šířku 1569 px a rozřeže na pásy 600 px vysoké s krokem 420 px
(= ověřené půlstrana 523 px × 200 px, krok 140 px, zvětšeno 3×). Hotové snímky se znovu neřežou.
"""
import glob, os, re, shutil, subprocess, sys
for _s in (sys.stdout, sys.stderr):   # UTF-8 výstup i na Windows bez -X utf8 (cp1250 neumí třeba „→“)
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

SIRKA, VYSKA, KROK = 1569, 600, 420   # px po zvětšení strany na šířku SIRKA


def magick():
    """Cesta k ImageMagicku; když chybí, skončí hned srozumitelnou hláškou."""
    m = (shutil.which("magick") or next(iter(sorted(glob.glob(r"C:\Program Files\ImageMagick*\magick.exe"))), None)
         or (os.name != "nt" and shutil.which("convert")))   # ImageMagick 6 bez magick; na Windows je convert.exe jiný program
    if not m:
        sys.exit("Chybí ImageMagick (příkaz magick). Nainstaluj ho (macOS: brew install imagemagick, "
                 "Windows: winget install ImageMagick.ImageMagick a restart Claude Code / Codexu / OMP) a spusť nástroj znovu.")
    return m


def main():
    a, strany, args = [], 2, iter(sys.argv[1:])
    for x in args:
        if x == "--strany":
            strany = int(next(args))
        else:
            a.append(x)
    if len(a) < 2 or strany not in (1, 2):
        sys.exit(__doc__)
    out, snimky = a[0], a[1:]
    cisla = {}
    for f in snimky:
        c = re.findall(r"\d+", os.path.splitext(os.path.basename(f))[0])
        if not c:
            sys.exit(f"{f}: v názvu chybí číslo snímku")
        n = int(c[-1])
        if n in cisla:
            sys.exit(f"{f} a {cisla[n]} mají stejné číslo snímku {n}")
        cisla[n] = f
    MAGICK = magick()
    os.makedirs(out, exist_ok=True)
    celkem = novych = 0
    for n, f in sorted(cisla.items()):
        w, h = (int(v) for v in subprocess.run([MAGICK, f + "[0]", "-format", "%w %h", "info:"],
                                                capture_output=True, text=True, check=True).stdout.split())
        cmd = [MAGICK, f, "-write", "mpr:s", "+delete"]
        hrany = [0, w // 2, w] if strany == 2 else [0, w]
        for s in range(strany):
            x0, sw = hrany[s], hrany[s + 1] - hrany[s]
            meritko = SIRKA / sw
            ph, krok = round(VYSKA / meritko), round(KROK / meritko)   # pás a krok v pixelech snímku
            ys = [min(y, h - ph) for y in range(0, max(h - ph, 0) + krok, krok)]
            for i, y in enumerate(dict.fromkeys(ys)):
                p = os.path.join(out, f"{n:04d}{'LR'[s] if strany == 2 else 'P'}{i:02d}.jpg")
                celkem += 1
                if not os.path.exists(p):
                    novych += 1
                    cmd += ["(", "mpr:s", "-crop", f"{sw}x{min(ph, h)}+{x0}+{max(y, 0)}", "+repage",
                            "-resize", f"{SIRKA}x", "-write", p, ")"]
        if len(cmd) > 5:
            subprocess.run(cmd + ["null:"], check=True)
    print(f"{len(cisla)} snímků → {celkem} pásů v {out} (nově {novych})")


if __name__ == "__main__":
    main()