# Síto Jev – třídění knihy bez rejstříku (jen OMP)

**Jev** (TypeSafe, `typesafe/jev-1.14.0`) je levný model, který na typovanou otázku nad obrázkem vrací pravděpodobnost
(„je na tomto výřezu křest, kde je otcem Jan Kufa?“). Je to **síto**: ukáže pásy, které stojí za přečtení. Čtení,
přepis a zápis do dat děláš ty nebo pomocník, jako u každé jiné knihy. V OMP je zabudovaný jako `judge()` /
`judge_batch()` v `eval`; v Claude Code a Codexu knihu čti jako dosud (`nahledy.py`, pomocníci).

## Kdy
- Kniha bez použitelného rejstříku (nebo dlouhý rozsah let v ní), kterou bys stejně četl celou. Kniha s rejstříkem
  → rejstřík.
- Síto stahování nepřidává: prosej jen snímky, které bys stáhl i pro čtení – celou knihu jen tehdy, když bys ji četl
  celou. Stahuj jako dosud podle `reference/portaly.md` (ZA Opava a SOA Litoměřice blokují rychlé dotazy, snímky ber
  nástrojem `soal_zoomify.py`).
- Platí uživatel ze svého účtu TypeSafe: ~0,0001 $ za pás, ~0,40 $ za knihu o 300 dvoustranách; s přečtením
  označených pásů ~1,2 $ proti ~7,6 $ za čtení celé knihy Sonnetem. Před prvním použitím mu to řekni i to, že se
  snímky matriky pošlou do TypeSafe, a nech si to schválit.

## Nastavení (jednou)
1. Uživatel se přihlásí v OMP: `/login typesafe`. Proměnná `TYPESAFE_API_KEY` funguje jen tehdy, když ji vidí proces,
   ze kterého se OMP spouští; klíč přidaný do `.zshrc` za běhu OMP nevidí.
2. Role `judge` = `typesafe/jev-1.14.0` (po přihlášení výchozí; nastavení `modelRoles.judge`).
   Bez přihlášení `judge` **tiše** použije náhradní chatový model (třeba Haiku) – dražší, pomalejší a s nekalibrovanými
   čísly. Proto kontrola modelu v kroku 4.

## Postup
1. **Pásy** ze zmenšených snímků (`nahled`, `_q`, ~1000 px):
   `python3 -I tools/pasy.py pracovni/<svazek>/pasy pracovni/<svazek>/s*_q.jpg` (snímek s jednou stranou:
   `--strany 1`). Každá strana dá ~6 překrývajících se pásů, klíč `0065R01` = snímek 65, pravá strana, pás 1 (shora od 0).
2. **Otázka** podle oddílu „Jak se ptát“. Každé hledání v knize má vlastní krátký název (`otec_jan_kufa`) a vlastní
   soubory; otázku ulož do `pracovni/<svazek>/jev_<hledání>_otazka.json`, ať jde výsledek zopakovat.
3. **Zkouška na známých zápisech** z této knihy: pásy 2–3 stran se zápisem, který už znáš, a několika stran s jinými
   nositeli příjmení (jiný otec, kmotr, matka rozená…). Pokračuj, jen když každá známá strana má maximum pásu
   aspoň 0,4; jinak knihu čti jako dosud.
4. **Celá kniha** v `eval` – pošle jen pásy, které ještě nemají výsledek v `jev_<hledání>.json`:
   ```python
   import glob, json, os
   D, H = "pracovni/<svazek>/", "<hledání>"
   Q = json.load(open(D + f"jev_{H}_otazka.json"))
   pasy = {os.path.basename(p)[:-4]: p for p in sorted(glob.glob(D + "pasy/*.jpg"))}
   r = json.load(open(D + f"jev_{H}.json")) if os.path.exists(D + f"jev_{H}.json") else {}
   todo = {k: p for k, p in pasy.items() if k not in r}
   b = judge_batch({k: "Crop of a page of a baptism register, <fara> <roky>." for k in todo}, Q,
                   intent="síto Jev <svazek>", concurrency=4, retries=2, images={k: [p] for k, p in todo.items()})
   open(D + f"jev_{H}_id.txt", "w").write(b.id)
   await b.drain(timeout=120)        # první výsledky
   print(b.status().get("model"))    # musí být typesafe/jev-…, jinak b.cancel() a přihlášení (Nastavení)
   ```
   `concurrency=4`: při výchozích 32 souběžných dotazech s obrázky skončilo 271 z 276 timeoutem. Kniha o 3 300
   pásech trvá asi hodinu – mezitím dělej jinou práci a na konec čekej nástrojem `wait`. Po resetu kernelu
   `b = judge_batch.attach(open(D + f"jev_{H}_id.txt").read())`; restart OMP dávku zruší, proto výsledky ukládej
   (po doběhnutí, při delší práci i průběžně):
   ```python
   r.update({k: a["otec"]["bool"] for k, a in b.results().items()})   # "otec" = id otázky v Q
   json.dump(r, open(D + f"jev_{H}.json", "w"))
   print(len(r), "z", len(pasy), "chyby:", len(b.failed()))
   ```
   Hotovo, až `len(r) == len(pasy)`. Pás s chybou nemá výsledek – spusť první blok znovu, pošle jen chybějící pásy.
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
   z jedné knihy – jestli platí i pro tuto, ukázala zkouška v kroku 3.
6. **Čtení.** Označené pásy čte pomocník s malým kontextem (`reference/zadani_pomocnika.md`, nejvýš ~50 pásů na běh)
   – vyjde levněji než hlavní sezení, jehož tahy byly na pokusu nejdražší položka. Pás ukazuje, kde na straně hledat;
   kandidáta čti v plném rozlišení. Do dat jde jen to, co je přečteno na snímku (`SKILL.md`, Fáze 2, krok 5).
   Hotovo, až má každý označený pás výsledek: zápis, nebo nic.
7. **Deník:** síto, název hledání a otázka (soubor), práh, počet označených a přečtených stran. „Nenalezeno“ piš
   jen u přečtených stran; u ostatních „síto nic neoznačilo“ – nepřítomnost zápisu síto nedokládá.

## Jak se ptát
- **Ptej se na roli** (otec, matka, kmotr). Otázka na výskyt jména označí i kmotry, matky a jiné rodiny.
- Typ `bool`, anglicky. Jev volí jen ano/ne nebo z pevných možností, jméno sám nenapíše. Výběr z možností (`choice`)
  ve zkoušce ztratil nejslabší známý zápis, proto síto stavěj na `bool`.
- Úvod otázky popíše stavbu zápisu v této knize (pořadí údajů, jak se píše otec, matka, kmotři), otázka se ptá
  na jeden úsudek. Logiku (práh, kombinace, datum, věk) dělá kód – v počítání a porovnávání dat je Jev slabý
  ([jaggedness](https://docs.typesafe.ai/go/jaggedness.md)).
- Vzor pro křty 18. století; jméno otce i vzory zápisů v úvodu nahraď podle hledání a knihy. Pro sňatky a úmrtí
  postav úvod stejně podle stavby zápisu (zatím nevyzkoušeno).
  ```json
  {"otec": {"type": "bool",
    "instructions": "The image is a crop of a page of an 18th-century Latin baptism register in old handwriting. Each entry: day, CHILD's first name (underlined, at line start), then the FATHER's first name in the genitive and his surname, then 'et' and the MOTHER (e.g. 'Anna Motykowa', 'Anna Kuffowa'), then place, then godparents after 'Lev:' (e.g. 'Paulus Podeschwa et Anna Joannis Kuffa uxor' = godmother Anna, wife of Jan Kufa). Is there an entry in which the FATHER of the baptised child is Joannes Kuffa (written 'Joannis Kuffa' right after the child's name)? The child's own name, the mother, and godparents do not count.",
    "criteria": {"true": "An entry reads '<child name> Joannis Kuffa et <mother>'.",
                 "false": "No entry has father Joannis Kuffa; Kuffa appears only as mother (Kuffowa), as godparent or godparent's husband, or not at all."}}}
  ```

## Měření (N Jablunkov 1745–1769, ZA Opava, latinsky, 278 dvoustran bez rejstříku)
| Pokus | Výsledek |
|---|---|
| Celé dvoustrany (1046 px), 278 snímků | nepoužitelné: skóre ~0,5 všude |
| Výřezy jednotlivých zápisů z plného rozlišení | pozitivní 0,74–0,96, negativní 0,06–0,20 |
| Pásy, celá kniha (3 336 pásů, 0,38 $, asi hodina, starší otázka „otec Joannis Kuffa“ bez popisu stavby zápisu) | práh 0,5: 30/30 známých stran, navíc 49/248 stran (112 pásů ke čtení) |
| Přečtení 26 nových stran ≥ 0,6 | 1 přehlédnutý křest, 2 pravé zápisy jiné rodiny, 23 falešných poplachů |
| Otázka na roli otce (výše) proti starší, 9 známých a 22 těžkých stran | práh 0,5: 9/9 a 7/22 falešných místo 14/22 |

Těžké strany byly vybrané podle chyb starší otázky a vzory v úvodu pocházejí z nich, takže pokles poplachů je zčásti
přizpůsobení zkoušce. Záměny rolí nezmizely (kmotra „Anna Joannis Kuffa uxor“ 0,61, dítě „Josephus Joannes Pauli
Kuffa“ 0,68). Otázka na roli s prahem 0,4 na celé knize zatím neběžela; označených pásů bude víc než 112.
