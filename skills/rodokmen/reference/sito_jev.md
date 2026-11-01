# Síto Jev – rychlé třídění knihy bez rejstříku (jen OMP)

**Jev** (TypeSafe, `typesafe/jev-1.14.0`) je levný model, který na typovanou otázku nad obrázkem vrací
pravděpodobnost („je na tomto výřezu křest, kde je otcem Jan Kufa?“). **Nic nečte ani nepřepisuje**, jen ukáže, které
strany přečíst. Nepřepíše zápis, nepřeloží ho a neodpoví na „jak se jmenuje otec?“. Podle vlastní dokumentace
([jaggedness](https://docs.typesafe.ai/go/jaggedness.md)) je slabý v počítání, porovnávání dat a víckrokových úvahách.

V OMP je zabudovaný jako `judge()` / `judge_batch()` v `eval`. **V Claude Code a Codexu tento krok přeskoč** a knihu
čti jako dosud (`nahledy.py`, pomocníci).

Ověřeno na jedné knize (N Jablunkov 1745–1769, ZA Opava, latinsky, 278 dvoustran bez rejstříku): celá kniha
za 0,38 $ a asi hodinu. Pásy s jeho skóre zachytily všech 30 známých stran se zápisem a jeden křest, který ruční
průchod přehlédl. Stejné čtení celé knihy Sonnetem by vyšlo asi na 7,6 $. S přečtením označených stran vychází
síto asi na 1,2 $.

## Kdy
- Kniha je **už stažená celá**, nebo ji stejně musíš číst celou (bez rejstříku, rejstřík neúplný).
  Kniha s rejstříkem → rejstřík.
- **Kvůli Jevu nikdy nestahuj celou knihu z badatelny**, která blokuje (ZA Opava po ~75 rychlých dotazech,
  SOA Litoměřice po ~100). Celé knihy raději z FamilySearch nebo z portálů bez blokování.
- Platí uživatel ze svého účtu TypeSafe (~0,0001 $ za pás, ~0,40 $ za knihu o 300 dvoustranách). Před prvním použitím
  mu řekni, co to stojí a že se snímky matriky pošlou do TypeSafe, a nech si to schválit.

## Nastavení (jednou) a kontrola
1. Uživatel se přihlásí v OMP: `/login typesafe`. Proměnná `TYPESAFE_API_KEY` funguje jen tehdy, když ji vidí proces,
   ze kterého se OMP spouští; klíč přidaný do `.zshrc` za běhu OMP nevidí.
2. Role `judge` = `typesafe/jev-1.14.0` (po přihlášení výchozí; nastavení `modelRoles.judge`).
3. **U každé dávky ověř** `b.status().get("model")`. Bez přihlášení `judge` **tiše** použije náhradní chatový model
   (třeba Haiku) – dražší, pomalejší a jeho čísla nejsou kalibrovaná. Tehdy `b.cancel()` a požádej o přihlášení.

## Postup
1. **Pásy.** Celé dvoustrany Jev nepřečte (skóre ~0,5 všude). Zmenšené snímky (`nahled`, `_q`, ~1000 px) stačí:
   `python3 -I tools/pasy.py pracovni/<svazek>/pasy pracovni/<svazek>/s*_q.jpg` (snímek s jednou stranou:
   `--strany 1`). Každá strana dá ~6 překrývajících se pásů, klíč `0065R01` = snímek 65, pravá strana, pás 1 (shora od 0).
2. **Otázka** podle oddílu „Jak se ptát“ níže. Ulož ji do `pracovni/<svazek>/jev_otazka.json`, ať jde výsledek zopakovat.
3. **Zkouška na známých zápisech** z této knihy: pásy 2–3 stran se zápisem, který už znáš, a několika stran s jinými
   nositeli příjmení (jiný otec, kmotr, matka rozená…). Když známé strany nemají maximum pásu aspoň 0,4, Jev na tuto knihu
   nestačí – čti ji jako dosud.
4. **Celá kniha** v `eval` – pošle jen pásy, které ještě nemají výsledek v `jev.json`:
   ```python
   import glob, json, os
   D = "pracovni/<svazek>/"
   Q = json.load(open(D + "jev_otazka.json"))
   pasy = {os.path.basename(p)[:-4]: p for p in sorted(glob.glob(D + "pasy/*.jpg"))}
   r = json.load(open(D + "jev.json")) if os.path.exists(D + "jev.json") else {}
   todo = {k: p for k, p in pasy.items() if k not in r}
   b = judge_batch({k: "Crop of a page of a baptism register, <fara> <roky>." for k in todo}, Q,
                   intent="síto Jev <svazek>", concurrency=4, retries=2, images={k: [p] for k, p in todo.items()})
   open(D + "jev_id.txt", "w").write(b.id)
   await b.drain(timeout=120)        # první výsledky
   print(b.status().get("model"))    # musí být typesafe/jev-…, jinak b.cancel()
   ```
   `concurrency=4` je nutné: při výchozích 32 souběžných dotazech s obrázky skončilo 271 z 276 timeoutem. Kniha
   o 3 300 pásech trvá asi hodinu – mezitím dělej jinou práci, na konec čekej nástrojem `wait` (ne blokujícím
   `drain()`). Po resetu kernelu `b = judge_batch.attach(open(D + "jev_id.txt").read())`; po restartu OMP dávka
   zanikne. Výsledky proto ukládej (po doběhnutí, při delší práci i průběžně):
   ```python
   r.update({k: a["otec"]["bool"] for k, a in b.results().items()})   # "otec" = id otázky v Q
   json.dump(r, open(D + "jev.json", "w"))
   print(len(r), "z", len(pasy), "chyby:", len(b.failed()))
   ```
   Pás s chybou neznamená „ne“. Dokud `len(r) < len(pasy)`, spusť první blok znovu – pošle jen chybějící pásy.
5. **Výběr** – práh **0,4** na maximum pásu na stranu:
   ```python
   PRAH = 0.4
   strana = {}
   for k, p in r.items():
       strana[k[:5]] = max(p, strana.get(k[:5], 0))   # "0065R"
   print(sorted(s for s, p in strana.items() if p >= PRAH))
   print(sorted(k for k, p in r.items() if p >= PRAH))   # pásy ke čtení
   ```
   Nejslabší známý zápis měl 0,53; falešný poplach stojí přečtení jednoho pásu, propad ztrátu zápisu. 0,4 je hodnota
   z jedné knihy – jestli platí i pro tuto, ukáže zkouška v kroku 3.
6. **Čtení.** Označené pásy ať přečte pomocník (`reference/zadani_pomocnika.md`, nejvýš ~50 pásů na běh) s malým
   kontextem, ne hlavní sezení s velkým kontextem – tahy hlavního sezení byly na celém pokusu nejdražší položka.
   Pás ukazuje, kde na straně hledat; kandidáta čti v plném rozlišení. Do dat jde jen to, co je přečteno na snímku
   (`SKILL.md`, Fáze 2, krok 5).
7. **Deník:** síto, otázka (soubor), práh, počet označených a přečtených stran. **Nepřítomnost zápisu Jev nikdy
   nedokládá** – „nenalezeno“ platí jen pro přečtené strany; u ostatních piš „Jev nic neoznačil“.

## Jak se ptát
- **Ptej se na roli, ne na jméno.** „Je na výřezu Kuffa?“ zachytí kmotry, matky i jiné rodiny. „Jak se jmenuje otec?“
  je generování, to Jev neumí.
- Otázka anglicky, typ `bool`. Úvod popíše stavbu zápisu v této knize (pořadí údajů, jak se píše otec, matka, kmotři),
  otázka se ptá na jeden úsudek. Logiku (práh, kombinace, datum, věk) dělá kód.
- `choice` (výběr z pevných možností) se hodí nanejvýš na řazení, ne jako hlavní síto – ztratil nejslabší známý zápis.
  Pořadí možností ovlivňuje odpověď.
- Ověřená otázka pro křty 18. století (jméno otce a vzory zápisů uprav podle hledání a knihy). Pro sňatky a úmrtí
  postav úvod stejně podle stavby zápisu; zatím nevyzkoušeno.
  ```json
  {"otec": {"type": "bool",
    "instructions": "The image is a crop of a page of an 18th-century Latin baptism register in old handwriting. Each entry: day, CHILD's first name (underlined, at line start), then the FATHER's first name in the genitive and his surname, then 'et' and the MOTHER (e.g. 'Anna Motykowa', 'Anna Kuffowa'), then place, then godparents after 'Lev:' (e.g. 'Paulus Podeschwa et Anna Joannis Kuffa uxor' = godmother Anna, wife of Jan Kufa). Is there an entry in which the FATHER of the baptised child is Joannes Kuffa (written 'Joannis Kuffa' right after the child's name)? The child's own name, the mother, and godparents do not count.",
    "criteria": {"true": "An entry reads '<child name> Joannis Kuffa et <mother>'.",
                 "false": "No entry has father Joannis Kuffa; Kuffa appears only as mother (Kuffowa), as godparent or godparent's husband, or not at all."}}}
  ```

## Měření (N Jablunkov 1745–1769)
| Pokus | Výsledek |
|---|---|
| Celé dvoustrany (1046 px), 278 snímků | nepoužitelné: skóre ~0,5 všude |
| Výřezy jednotlivých zápisů z plného rozlišení | pozitivní 0,74–0,96, negativní 0,06–0,20 |
| Pásy, celá kniha (3 336 pásů, 0,38 $, starší otázka „otec Joannis Kuffa“ bez popisu stavby zápisu) | práh 0,5: 30/30 známých stran, navíc 49/248 stran (112 pásů ke čtení) |
| Přečtení 26 nových stran ≥ 0,6 | 1 přehlédnutý křest, 2 pravé zápisy jiné rodiny, 23 falešných poplachů |
| Otázka na roli otce (výše) proti starší, 9 známých a 22 těžkých stran | práh 0,5: 9/9 a 7/22 falešných místo 14/22 |

Těžké strany byly vybrané podle chyb starší otázky a vzory v úvodu pocházejí z nich, takže pokles poplachů je zčásti
přizpůsobení zkoušce. Záměny rolí nezmizely (kmotra „Anna Joannis Kuffa uxor“ 0,61, dítě „Josephus Joannes Pauli
Kuffa“ 0,68). Otázka na roli s prahem 0,4 na celé knize zatím neběžela; označených pásů bude víc než 112.
