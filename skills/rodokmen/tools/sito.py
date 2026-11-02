#!/usr/bin/env python3
"""Síto Jev – kalibrace, prosetí a výběr pásů (postup: reference/sito_jev.md).

Jev (TypeSafe) je dostupný jen v OMP, v nástroji eval jako judge_batch. Proto je tohle modul pro eval;
z příkazové řádky jdou jen kroky bez modelu (stav, mřížka).

V OMP eval (Python), z kořene projektu:
  import importlib.util
  _s = importlib.util.spec_from_file_location("sito", "tools/sito.py")
  sito = importlib.util.module_from_spec(_s); _s.loader.exec_module(sito)
  await sito.kalibrace(judge_batch, PASY, [{"nazev": "znamy1", "strana": "0120L", "otazka": Q1}, …], popis=POPIS)
  await sito.proset(judge_batch, PASY, "novak_josef", Q, popis=POPIS, rozsah=(3, 260))
  sito.stav(PASY, "novak_josef");  sito.mrizka(PASY, "novak_josef")

Z příkazové řádky:
  sito.py stav <složka pásů> <hledání>                    (kód 1, když běh není úplný)
  sito.py mrizka <složka pásů> <hledání> [--prah 0.4] [--vyrez x0,x1]

Složka pásů vzniká nástrojem pasy.py --kniha (záznam pasy.json). Výsledky hledání: <složka>/jev_<hledání>.json,
kalibrace: <složka>/jev_kalibrace.json, mřížky: <složka>/mrizka_<hledání>/.
"""
import asyncio, glob, hashlib, inspect, json, os, re, shutil, subprocess, sys
for _s in (sys.stdout, sys.stderr):   # UTF-8 výstup i na Windows bez -X utf8 (cp1250 neumí třeba „→“)
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

JEV = "typesafe/jev-"   # verze se kontroluje předponou, konkrétní se ukládá a porovnává
PRAH = 0.4
STRANA = re.compile(r"^\d{4}[LRP]$")
PISMA = ["/System/Library/Fonts/Supplemental/Arial.ttf", r"C:\Windows\Fonts\arial.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf"]


class SitoChyba(Exception):
    """Síto nesmí pokračovat – výsledek by nebyl spolehlivý."""


def _uloz(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)   # atomicky: přerušení nenechá napůl zapsaný soubor


def _otisk(*data):
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _cti(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _zaznam(pasy):
    p = os.path.join(pasy, "pasy.json")
    if not os.path.exists(p):
        raise SitoChyba(f"{pasy}: chybí pasy.json – nařež pásy nástrojem pasy.py s --kniha (každá kniha vlastní složka).")
    return _cti(p)


def _nastaveni(z):
    """Otisk knihy a nastavení pásů – kalibrace platí jen pro ně."""
    return _otisk(z["kniha"], z["nastaveni"])


def _pasy_snimku(pasy, z, cisla):
    """{klíč pásu: cesta} pro dané snímky; chybějící soubor pásu je chyba."""
    out = {}
    for n in cisla:
        for k in z["snimky"][str(n)]["pasy"]:
            p = os.path.join(pasy, k + ".jpg")
            if not os.path.exists(p):
                raise SitoChyba(f"{p} chybí – spusť pasy.py znovu na snímek {n}.")
            out[k] = p
    return out


def _snimky_rozsahu(z, rozsah, vynechat):
    od, do = rozsah
    cisla = [n for n in range(od, do + 1) if n not in set(vynechat)]
    chybi = [n for n in cisla if str(n) not in z["snimky"]]
    return cisla, chybi


def _otazka(otazka):
    if not (isinstance(otazka, dict) and len(otazka) == 1):
        raise SitoChyba("Otázka musí být právě jedna: {id: {\"type\": \"bool\", …}}.")
    qid, q = next(iter(otazka.items()))
    if not (isinstance(q, dict) and q.get("type") == "bool"):
        raise SitoChyba(f"Otázka „{qid}“ musí mít typ bool (síto počítá s pravděpodobností ano).")
    return qid


def _p(answers, qid):
    try:
        p = answers[qid]["bool"]
    except (KeyError, TypeError):
        return None
    return float(p) if isinstance(p, (int, float)) and not isinstance(p, bool) else None


async def _vysledek(x):
    return await x if inspect.isawaitable(x) else x


PRERUSENI = (asyncio.CancelledError, KeyboardInterrupt)   # přerušená buňka: dávka běží dál, proset ji příště připojí


async def _dobeh(b, qid, over_model, prijmi):
    """Čeká na dávku až do konce (drain se může vrátit předčasně). Skóre předá až po ověření modelu.
    Po skončení dávky bere všechny odpovědi z results() – drain je po konci už vrátit nemusí."""
    cekajici, model = {}, None
    try:
        while True:
            for k, item in await b.drain(timeout=30):
                if getattr(item, "ok", False):
                    p = _p(item.answers, qid)
                    if p is not None:
                        cekajici[k] = p
            st = b.status()
            if st.get("model") and not model:
                model = st["model"]
                over_model(model)
            if not st.get("running"):
                for k, a in (b.results() or {}).items():
                    p = _p(a, qid)
                    if p is not None:
                        cekajici[k] = p
                if not model:
                    model = b.status().get("model")
                    if not model:
                        raise SitoChyba("Dávka nevrátila model – nejde ověřit, že běžel Jev. Výsledek nepoužívej.")
                    over_model(model)
                if cekajici:
                    prijmi(cekajici)
                return model
            if model and cekajici:
                prijmi(cekajici)
                cekajici = {}
    except PRERUSENI:
        raise
    except BaseException:   # špatný model nebo mrtvá dávka: zastavit, ať dál neplatíš
        try:
            b.cancel()
        except Exception:
            pass
        raise


def _model_jev(m):
    if not str(m).startswith(JEV):
        raise SitoChyba(f"Dávka běží na modelu {m}, ne na Jevu ({JEV}…). Přihlas se v OMP (/login typesafe), "
                        "nebo knihu přečti pomocníkem. Výsledek nepoužívej.")


async def _kola(judge_batch, cesty, otazka, qid, popis, skore, *, intent, concurrency, kola, over_model,
                po_prijeti=lambda: None, nova_davka=lambda bid: None, hotova_davka=lambda bid: None):
    """Posílá pásy bez skóre, dokud je nemají všechny, nejvýš `kola`-krát. Vrátí model."""
    model = None

    def prijmi(nove):
        skore.update({k: p for k, p in nove.items() if k in cesty})
        po_prijeti()

    for _ in range(kola):
        chybi = {k: p for k, p in cesty.items() if k not in skore}
        if not chybi:
            break
        b = judge_batch({k: popis for k in chybi}, otazka, intent=intent, concurrency=concurrency, retries=2,
                        images={k: [p] for k, p in chybi.items()})
        nova_davka(b.id)
        try:
            model = await _dobeh(b, qid, over_model, prijmi) or model
        except PRERUSENI:
            raise
        except BaseException:
            hotova_davka(b.id)   # zastavená dávka se nepřipojuje; její pásy příště pošle nová dávka
            raise
        hotova_davka(b.id)
    chybi = sorted(k for k in cesty if k not in skore)
    if chybi:
        raise SitoChyba(f"{len(chybi)} pásů nemá ani po {kola} kolech skóre (např. {', '.join(chybi[:5])}). "
                        "Spusť znovu; do té doby výsledek nehlas.")
    return model


async def kalibrace(judge_batch, pasy, zname, *, popis, okoli=4, prah=PRAH, concurrency=6, kola=5):
    """Zkouška na známých zápisech z TÉŽE knihy. zname = [{"nazev", "strana": "0120L", "otazka"}].
    Projde, když maximum pásů známé strany ≥ prah u každého známého zápisu. Uloží jev_kalibrace.json."""
    z = _zaznam(pasy)
    if not zname:
        raise SitoChyba("Kalibrace potřebuje aspoň jeden známý zápis z této knihy (doporučeno 2–3).")
    for zn in zname:
        if not STRANA.match(str(zn.get("strana", ""))):
            raise SitoChyba(f"{zn.get('nazev')}: strana se zadává jako snímek + strana, např. „0120L“ nebo „0120P“.")
        if str(int(zn["strana"][:4])) not in z["snimky"]:
            raise SitoChyba(f"{zn['nazev']}: snímek {int(zn['strana'][:4])} ve složce {pasy} není.")
        _otazka(zn["otazka"])
    stav_modelu = {}

    def over(m):
        _model_jev(m)
        if stav_modelu.setdefault("model", m) != m:
            raise SitoChyba(f"Model se během kalibrace změnil ({stav_modelu['model']} → {m}).")

    vysl = []
    for zn in zname:
        n = int(zn["strana"][:4])
        cisla = [c for c in range(n - okoli, n + okoli + 1) if str(c) in z["snimky"]]
        cesty = _pasy_snimku(pasy, z, cisla)
        skore = {}
        await _kola(judge_batch, cesty, zn["otazka"], _otazka(zn["otazka"]), popis, skore,
                    intent=f"kalibrace {zn['nazev']}", concurrency=concurrency, kola=kola, over_model=over)
        strany = {}
        for k, p in skore.items():
            strany[k[:5]] = max(p, strany.get(k[:5], 0.0))
        if zn["strana"] not in strany:
            raise SitoChyba(f"{zn['nazev']}: strana {zn['strana']} nemá pásy (jiné --strany?).")
        ostatni = sorted(((round(p, 2), s) for s, p in strany.items() if s != zn["strana"]), reverse=True)
        vysl.append({"nazev": zn["nazev"], "strana": zn["strana"], "otazka": zn["otazka"],
                     "znama": round(strany[zn["strana"]], 3), "ostatni_max": ostatni[:5], "skore": skore})
    model = stav_modelu["model"]
    prosla = all(v["znama"] >= prah for v in vysl)
    path = os.path.join(pasy, "jev_kalibrace.json")
    d = _cti(path) if os.path.exists(path) else {}
    d[model] = {"nastaveni": _nastaveni(z), "popis": _otisk(popis), "kniha": z["kniha"], "prah": prah,
                "prosla": prosla, "zname": vysl}
    _uloz(path, d)
    return {"model": model, "prosla": prosla, "prah": prah,
            "zname": [{k: v[k] for k in ("nazev", "strana", "znama", "ostatni_max")} for v in vysl]}


def _kalibrace_ok(pasy, z, model, popis):
    path = os.path.join(pasy, "jev_kalibrace.json")
    e = (_cti(path) if os.path.exists(path) else {}).get(model)
    return bool(e and e["prosla"] and e["nastaveni"] == _nastaveni(z) and e.get("popis") == _otisk(popis))


def _cesta(pasy, hledani):
    if not re.match(r"^[\w-]+$", hledani):
        raise SitoChyba(f"Název hledání „{hledani}“: jen písmena, číslice, _ a -.")
    return os.path.join(pasy, f"jev_{hledani}.json")


async def proset(judge_batch, pasy, hledani, otazka, *, popis, rozsah, vynechat=(), concurrency=6, kola=5,
                 bez_kalibrace=False):
    """Proseje všechny pásy snímků v rozsahu (mimo vynechat). Vyžaduje úspěšnou kalibraci téže verze Jevu
    a téhož nastavení pásů; bez_kalibrace=True výsledek trvale označí „nekalibrováno“."""
    qid = _otazka(otazka)
    z = _zaznam(pasy)
    cisla, chybi = _snimky_rozsahu(z, rozsah, vynechat)
    if chybi:
        raise SitoChyba(f"V rozsahu {rozsah[0]}–{rozsah[1]} chybí pásy snímků {chybi[:10]}{' …' if len(chybi) > 10 else ''}. "
                        "Stáhni a nařež je, nebo je uveď ve vynechat (desky, prázdné listy).")
    cesty = _pasy_snimku(pasy, z, cisla)
    otisk = _otisk(otazka, popis, _nastaveni(z), sorted(set(vynechat)), list(rozsah),
                   [z["snimky"][str(n)]["sha256"] for n in cisla])
    path = _cesta(pasy, hledani)
    if os.path.exists(path):
        d = _cti(path)
        if "skore" not in d or "otisk" not in d:
            raise SitoChyba(f"{path} je ve starém formátu (verze 0.7.3) – jen ke čtení. Nové hledání pojmenuj jinak.")
        if d["otisk"] != otisk:
            raise SitoChyba(f"{path} vznikl s jinou otázkou, popisem, rozsahem nebo pásy. Výsledky nejde míchat – "
                            "nové hledání pojmenuj jinak.")
    else:
        d = {"kniha": z["kniha"], "hledani": hledani, "otazka": otazka, "popis": popis, "otisk": otisk,
             "rozsah": list(rozsah), "vynechat": sorted(set(vynechat)), "model": None, "kalibrace": None,
             "davky": [], "hotove_davky": [], "skore": {}}
    skore = d["skore"]

    def over(m):
        _model_jev(m)
        if d["model"] and d["model"] != m:
            raise SitoChyba(f"{path} je z modelu {d['model']}, teď běží {m}. Výsledky dvou verzí nemíchej – "
                            "nová kalibrace a nové hledání pod jiným názvem.")
        if not bez_kalibrace and d["kalibrace"] != m:
            if not _kalibrace_ok(pasy, z, m, popis):
                raise SitoChyba(f"Pro {m}, tyto pásy a tento popis chybí úspěšná kalibrace (sito.kalibrace na známých "
                                "zápisech z téže knihy, se stejným popisem). Bez ní jen bez_kalibrace=True a výsledek "
                                "je „nekalibrováno“.")
            d["kalibrace"] = m
        d["model"] = m

    def ulozit():
        _uloz(path, d)

    def nova(bid):
        d["davky"].append(bid)
        ulozit()

    def hotova(bid):
        d["hotove_davky"].append(bid)
        ulozit()

    ulozit()
    # Po resetu kernelu: nejdřív dočerpat rozběhnutou dávku.
    def prijmi(nove):
        skore.update({k: p for k, p in nove.items() if k in cesty})
        ulozit()

    for bid in [x for x in d["davky"] if x not in d["hotove_davky"]]:
        try:
            b = await _vysledek(judge_batch.attach(bid))
            await _dobeh(b, qid, over, prijmi)
        except PRERUSENI:
            raise
        except SitoChyba:
            hotova(bid)   # důvod (model, kalibrace) platí i pro novou dávku – ohlásit
            raise
        except Exception:
            hotova(bid)   # dávka už neexistuje nebo skončila chybou; její pásy bez skóre pošle nová dávka
            continue
        hotova(bid)
    await _kola(judge_batch, cesty, otazka, qid, popis, skore, intent=f"síto {hledani}", concurrency=concurrency,
                kola=kola, over_model=over, po_prijeti=ulozit, nova_davka=nova, hotova_davka=hotova)
    ulozit()
    return stav(pasy, hledani)


def stav(pasy, hledani, prah=PRAH):
    """Souhrn hledání pro deník; „uplne“ jen když má skóre každý pás rozsahu."""
    path = _cesta(pasy, hledani)
    if not os.path.exists(path):
        raise SitoChyba(f"{path} neexistuje.")
    d = _cti(path)
    if "skore" not in d or "otisk" not in d:
        return {"hledani": hledani, "stary_format": True, "uplne": False, "se_skore": len(d)}
    z = _zaznam(pasy)
    cisla, chybi_snimky = _snimky_rozsahu(z, d["rozsah"], d["vynechat"])
    ocek = [k for n in cisla if str(n) in z["snimky"] for k in z["snimky"][str(n)]["pasy"]]
    skore = d["skore"]
    chybi = [k for k in ocek if k not in skore]
    strany = {}
    for k in ocek:
        if k in skore:
            strany[k[:5]] = max(skore[k], strany.get(k[:5], 0.0))
    return {"kniha": d["kniha"], "hledani": hledani, "model": d["model"],
            "kalibrace": d["kalibrace"] or "nekalibrováno", "rozsah": d["rozsah"], "vynechat": d["vynechat"],
            "ocekavano": len(ocek), "se_skore": len(ocek) - len(chybi), "chybi_pasu": len(chybi),
            "chybi_snimky": chybi_snimky, "uplne": bool(ocek) and not chybi and not chybi_snimky,
            "prah": prah, "stran_nad_prahem": sum(p >= prah for p in strany.values()),
            "pasu_nad_prahem": sum(skore[k] >= prah for k in ocek if k in skore)}


def vyber(pasy, hledani, prah=PRAH):
    """Strany a pásy nad prahem. Neúplný běh odmítne – nedá se číst jako negativní výsledek."""
    s = stav(pasy, hledani, prah)
    if not s["uplne"]:
        raise SitoChyba(f"Hledání {hledani} není úplné ({s.get('se_skore')} z {s.get('ocekavano', '?')} pásů) – "
                        "nejdřív sito.proset.")
    d = _cti(_cesta(pasy, hledani))
    sk = d["skore"]
    p = sorted(k for k, v in sk.items() if v >= prah)
    return {"strany": sorted({k[:5] for k in p}), "pasy": p}


def _magick():
    m = (shutil.which("magick") or next(iter(sorted(glob.glob(r"C:\Program Files\ImageMagick*\magick.exe"))), None)
         or (os.name != "nt" and shutil.which("convert")))
    if not m:
        raise SitoChyba("Chybí ImageMagick (příkaz magick).")
    return m


def mrizka(pasy, hledani, prah=PRAH, vyrez=None):
    """Obrázky 2 × 5 označených pásů s popiskem; k pásu 00 (záhlaví, první zápis useknutý) přidá pás 01.
    vyrez=(x0, x1) = jen část šířky pásu (zlomky), např. (0.5, 1) pro sloupec jména vpravo."""
    v = vyber(pasy, hledani, prah)
    z = _zaznam(pasy)
    vse = {k for s in z["snimky"].values() for k in s["pasy"]}
    dilky = []
    for k in v["pasy"]:
        dilky.append(k)
        if k.endswith("00") and k[:-2] + "01" in vse:
            dilky.append(k[:-2] + "01")
    dilky = list(dict.fromkeys(dilky))
    out = os.path.join(pasy, f"mrizka_{hledani}")
    os.makedirs(out, exist_ok=True)
    for f in glob.glob(os.path.join(out, "*.jpg")):
        os.remove(f)
    M = _magick()
    pismo = next((f for f in PISMA if os.path.exists(f)), None)
    soubory = []
    for i in range(0, len(dilky), 10):
        radky = []
        for j in range(i, min(i + 10, len(dilky)), 2):
            radek = ["("]
            for k in dilky[j:j + 2]:
                radek += ["(", os.path.join(pasy, k + ".jpg")]
                if vyrez:   # pásy mají pevnou šířku z pasy.json
                    sirka = z["nastaveni"]["sirka"]
                    x0, x1 = round(vyrez[0] * sirka), round(vyrez[1] * sirka)
                    radek += ["-gravity", "northwest", "-crop", f"{x1 - x0}x100000+{x0}+0", "+repage"]
                radek += ["-resize", "760x", "-background", "white", "-gravity", "north", "-splice", "0x26"]
                radek += (["-font", pismo] if pismo else []) + ["-pointsize", "20", "-annotate", "+0+2", k,
                                                                 "-bordercolor", "white", "-border", "4", ")"]
            radky += radek + ["-gravity", "northwest", "+append", ")"]
        f = os.path.join(out, f"{i // 10 + 1:02d}.jpg")
        subprocess.run([M, *radky, "-background", "white", "-append", f], check=True, capture_output=True)
        soubory.append(f)
    return soubory


def main():
    a = sys.argv[1:]
    try:
        if len(a) >= 3 and a[0] == "stav":
            s = stav(a[1], a[2])
            for k, v in s.items():
                print(f"{k}: {v}")
            sys.exit(0 if s["uplne"] else 1)
        if len(a) >= 3 and a[0] == "mrizka":
            prah, vyrez, args = PRAH, None, iter(a[3:])
            for x in args:
                if x == "--prah":
                    prah = float(next(args))
                elif x == "--vyrez":
                    vyrez = tuple(float(v) for v in next(args).split(","))
            for f in mrizka(a[1], a[2], prah, vyrez):
                print(f)
            return
    except SitoChyba as e:
        sys.exit(str(e))
    sys.exit(__doc__)


if __name__ == "__main__":
    main()
