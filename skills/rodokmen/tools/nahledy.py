#!/usr/bin/env python3
"""Náhledová mřížka: rozsah snímků knihy složený do jednoho obrázku – rychlé procházení knihy bez rejstříku.

Použití (z kořene projektu):
  nahledy.py <portál> <kniha> <od> <do> [x0,y0,x1,y1] [--po N] [--sirka PX]
    portál   pf (Porta fontium, kniha např. „chvalenice-28“) | ebad (eBadatelna SOA Praha, matrikaId např. 8931)
             | trebon (SOA Třeboň, id knihy např. 6854; výřez se dělá až po stažení celého snímku)
    od, do   rozsah snímků (včetně)
    x0..y1   jen tato část každého snímku (zlomky 0..1), např. sloupec data, domu a jména: 0,0,0.5,1
             (stahuje se v plném rozlišení, takže výřez je čitelný; bez výřezu se bere náhled 1/4)
    --po N   kolik snímků do jednoho obrázku (výchozí 3)
    --sirka  šířka jedné dlaždice v px (výchozí 950)
Vytvoří pracovni/nahledy/<kniha>_<od>-<do>_<i>.jpg (každá dlaždice má v rohu číslo snímku) a vypíše cesty.
Stažené snímky se ukládají do pracovni/nahledy/snimky/ a znovu se nestahují.
"""
import glob, os, shutil, subprocess, sys
for _s in (sys.stdout, sys.stderr):   # UTF-8 výstup i na Windows bez -X utf8 (cp1250 neumí třeba „→“)
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NASTROJ = {"pf": "portafontium.py", "ebad": "ebadatelna.py", "trebon": "trebon.py"}
FONT = next((f for f in ("/System/Library/Fonts/Supplemental/Arial.ttf", r"C:\Windows\Fonts\arial.ttf",
                         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf") if os.path.exists(f)), None)


def magick():
    """Cesta k ImageMagicku; když chybí, skončí hned (před stahováním) srozumitelnou hláškou."""
    m = (shutil.which("magick") or next(iter(sorted(glob.glob(r"C:\Program Files\ImageMagick*\magick.exe"))), None)
         or (os.name != "nt" and shutil.which("convert")))   # ImageMagick 6 bez magick; na Windows je convert.exe jiný program
    if not m:
        sys.exit("Chybí ImageMagick (příkaz magick). Nainstaluj ho (macOS: brew install imagemagick, "
                 "Windows: winget install ImageMagick.ImageMagick a restart Claude Code / Codexu / OMP) a spusť nástroj znovu.")
    return m


def main():
    a, volby, args = [], {}, iter(sys.argv[1:])
    for x in args:
        if x.startswith("--"):
            volby[x] = int(next(args))
        else:
            a.append(x)
    if len(a) < 4 or a[0] not in NASTROJ:
        sys.exit(__doc__)
    portal, kniha, od, do = a[0], a[1], int(a[2]), int(a[3])
    vyrez = a[4] if len(a) > 4 else None
    po, sirka = volby.get("--po", 3), volby.get("--sirka", 950)
    MAGICK = magick()
    sdir = os.path.join(ROOT, "pracovni", "nahledy", "snimky")
    os.makedirs(sdir, exist_ok=True)
    dlazdice = []
    for n in range(od, do + 1):
        out = os.path.join(sdir, f"{kniha}_{n}_{(vyrez or 'nahled').replace(',', '-')}.jpg")
        if not os.path.exists(out):
            cmd = [sys.executable, "-I", os.path.join(ROOT, "tools", NASTROJ[portal]), "snimek", kniha, str(n), out]
            celý = portal == "trebon" and vyrez   # trebon.py výřez neumí – stáhne se celý snímek a ořízne tady
            if celý:
                cmd[-1] = out[:-4] + "_cely.jpg"
            cmd += [] if celý else ([vyrez] if vyrez else ["nahled"])
            r = subprocess.run(cmd, capture_output=True, text=True)
            if celý and os.path.exists(cmd[-1]):
                x0, y0, x1, y1 = (float(v) for v in vyrez.split(","))
                w, h = (int(v) for v in subprocess.run([MAGICK, cmd[-1] + "[0]", "-format", "%w %h", "info:"],
                                                        capture_output=True, text=True, check=True).stdout.split())
                # pixely, ne %[fx:] v geometrii – to ImageMagick 6 (convert) neumí
                subprocess.run([MAGICK, cmd[-1], "-crop", f"{round((x1 - x0) * w)}x{round((y1 - y0) * h)}"
                                f"+{round(x0 * w)}+{round(y0 * h)}", "+repage", out], check=True)
            if r.returncode or not os.path.exists(out):
                print(f"snímek {n}: nestaženo ({(r.stderr or r.stdout).strip()[:150]})")
                continue
        tile = out[:-4] + f"_t{sirka}.jpg"
        if not os.path.exists(tile):
            cmd = [MAGICK, out, "-resize", f"{sirka}x", "-gravity", "northwest", "-fill", "red",
                   "-undercolor", "white", "-pointsize", "42"]
            cmd += (["-font", FONT] if FONT else []) + ["-annotate", "+8+8", f"sn. {n}", tile]
            subprocess.run(cmd, check=True)
        dlazdice.append(tile)
    ndir = os.path.dirname(sdir)
    for i in range(0, len(dlazdice), po):
        cast = dlazdice[i:i + po]
        out = os.path.join(ndir, f"{kniha}_{od}-{do}_{i // po + 1}.jpg")
        subprocess.run([MAGICK, *cast, "+append", "-quality", "85", out], check=True)
        print(out)


if __name__ == "__main__":
    main()
