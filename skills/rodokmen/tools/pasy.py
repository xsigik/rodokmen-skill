#!/usr/bin/env python3
"""Pásy pro síto Jev: každou stranu snímku rozřeže na překrývající se vodorovné pásy a zvětší je
(postup a měření viz reference/sito_jev.md; celé dvoustrany Jev nepřečte).

Použití (z kořene projektu):
  pasy.py <výstupní složka> <snímek.jpg>… --kniha <id> [--strany N]
    snímky    stačí zmenšené (náhled) nebo výřez sloupce; číslo snímku se bere z poslední skupiny číslic
              v názvu souboru (s065_q.jpg → 65)
    --kniha   označení knihy (např. pf_dobrany-56, ahmp_NEM_Z8); složka patří jedné knize
    --strany  kolik stran je vedle sebe na snímku (výchozí 2 = dvoustrana; 1 = jedna strana)
Vytvoří <výstupní složka>/<snímek 4 číslice><strana L/R/P><pás 2 číslice>.jpg, např. 0065R01.jpg, a záznam
<výstupní složka>/pasy.json (kniha, nastavení, po snímcích zdrojový soubor, jeho otisk a pásy).
Strana se zmenší nebo zvětší na šířku 1569 px a rozřeže na pásy 600 px vysoké s krokem 420 px
(= ověřené půlstrana 523 px × 200 px, krok 140 px, zvětšeno 3×). Hotové snímky se znovu neřežou;
další snímky téže knihy jde přidat dalším spuštěním. Jiná kniha, jiné nastavení nebo jiný obsah snímku
se stejným číslem skončí chybou dřív, než se cokoli zapíše – pro každou knihu vlastní složka.
"""
import glob, hashlib, json, os, re, shutil, subprocess, sys
for _s in (sys.stdout, sys.stderr):   # UTF-8 výstup i na Windows bez -X utf8 (cp1250 neumí třeba „→“)
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

SIRKA, VYSKA, KROK = 1569, 600, 420   # px po zvětšení strany na šířku SIRKA
ZAZNAM = "pasy.json"
PAS = re.compile(r"^\d{4}[LRP]\d{2}\.jpg$")


def magick():
    """Cesta k ImageMagicku; když chybí, skončí hned srozumitelnou hláškou."""
    m = (shutil.which("magick") or next(iter(sorted(glob.glob(r"C:\Program Files\ImageMagick*\magick.exe"))), None)
         or (os.name != "nt" and shutil.which("convert")))   # ImageMagick 6 bez magick; na Windows je convert.exe jiný program
    if not m:
        sys.exit("Chybí ImageMagick (příkaz magick). Nainstaluj ho (macOS: brew install imagemagick, "
                 "Windows: winget install ImageMagick.ImageMagick a restart Claude Code / Codexu / OMP) a spusť nástroj znovu.")
    return m


def otisk(f):
    with open(f, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def uloz(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)   # atomicky: přerušení nenechá napůl zapsaný záznam


def main():
    a, strany, kniha, args = [], 2, None, iter(sys.argv[1:])
    for x in args:
        if x == "--strany":
            strany = int(next(args))
        elif x == "--kniha":
            kniha = next(args).strip()
        else:
            a.append(x)
    if len(a) < 2 or strany not in (1, 2) or not kniha:
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

    # Kontroly před jakýmkoli zápisem.
    nastaveni = {"strany": strany, "sirka": SIRKA, "vyska": VYSKA, "krok": KROK}
    zpath = os.path.join(out, ZAZNAM)
    if os.path.exists(zpath):
        with open(zpath, encoding="utf-8") as fh:
            z = json.load(fh)
        if z["kniha"] != kniha:
            sys.exit(f"{out} patří knize „{z['kniha']}“, ne „{kniha}“ – pro každou knihu vlastní složka.")
        if z["nastaveni"] != nastaveni:
            sys.exit(f"{out} má pásy s jiným nastavením ({z['nastaveni']}) – pro jiné nastavení vlastní složka.")
    else:
        if os.path.isdir(out) and any(PAS.match(f) for f in os.listdir(out)):
            sys.exit(f"{out} obsahuje pásy bez záznamu {ZAZNAM} (starší verze) – nepoznám, z jaké knihy jsou. "
                     "Nařež pásy do nové složky; staré výsledky zůstávají jen ke čtení.")
        z = {"kniha": kniha, "nastaveni": nastaveni, "snimky": {}}
    otisky = {n: otisk(f) for n, f in cisla.items()}
    for n, f in sorted(cisla.items()):
        old = z["snimky"].get(str(n))
        if old and old["sha256"] != otisky[n]:
            sys.exit(f"{f}: snímek {n} už má v {out} pásy z jiného obsahu ({old['soubor']}) – jiná kniha nebo "
                     "přepsaný soubor; pro jinou knihu vlastní složka.")

    MAGICK = magick()
    os.makedirs(out, exist_ok=True)
    celkem = novych = 0
    for n, f in sorted(cisla.items()):
        w, h = (int(v) for v in subprocess.run([MAGICK, f + "[0]", "-format", "%w %h", "info:"],
                                                capture_output=True, text=True, check=True).stdout.split())
        cmd = [MAGICK, f, "-write", "mpr:s", "+delete"]
        hrany = [0, w // 2, w] if strany == 2 else [0, w]
        klice = []
        for s in range(strany):
            x0, sw = hrany[s], hrany[s + 1] - hrany[s]
            meritko = SIRKA / sw
            ph, krok = round(VYSKA / meritko), round(KROK / meritko)   # pás a krok v pixelech snímku
            ys = [min(y, h - ph) for y in range(0, max(h - ph, 0) + krok, krok)]
            for i, y in enumerate(dict.fromkeys(ys)):
                k = f"{n:04d}{'LR'[s] if strany == 2 else 'P'}{i:02d}"
                klice.append(k)
                p = os.path.join(out, k + ".jpg")
                celkem += 1
                if not os.path.exists(p):
                    novych += 1
                    cmd += ["(", "mpr:s", "-crop", f"{sw}x{min(ph, h)}+{x0}+{max(y, 0)}", "+repage",
                            "-resize", f"{SIRKA}x", "-write", p, ")"]
        # Záznam před řezáním: přerušený běh dořízne příští spuštění (chybějící pásy pozná sito.py).
        z["snimky"][str(n)] = {"soubor": f, "sha256": otisky[n], "pasy": klice}
        uloz(zpath, z)
        if len(cmd) > 5:
            subprocess.run(cmd + ["null:"], check=True)
    print(f"{len(cisla)} snímků → {celkem} pásů v {out} (nově {novych}), kniha {kniha}")


if __name__ == "__main__":
    main()
