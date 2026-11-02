# Síto Jev – třídění knihy bez rejstříku (jen OMP)

**Jev** (TypeSafe, `typesafe/jev-<verze>`) je levný model, který na typovanou otázku nad obrázkem vrací pravděpodobnost
(„je na tomto výřezu křest, kde je otcem Jan Kufa?“). Je to **síto**: ukáže pásy, které stojí za přečtení. Čtení,
přepis a zápis do dat děláš ty nebo pomocník, jako u každé jiné knihy. V OMP je zabudovaný jako `judge_batch()`
v `eval`; nástroj `tools/sito.py` je modul pro `eval`, který ho volá a hlídá model, úplnost a kalibraci. V Claude Code
a Codexu knihu čti jako dosud (`nahledy.py`, pomocníci).

Síto vidí jen to, na co se ptáš: vedlejší nálezy (příbuzný o řádek vedle, svědek) přehlédne. Hodí se na velké cizí
knihy (nemocnice, ústavy, města), kde hledáš jednu osobu; farnost, kde žila celá rodina, raději čti pomocníkem.

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
2. Role `judge` = `typesafe/jev-…` (po přihlášení výchozí; nastavení `modelRoles.judge`). Bez přihlášení `judge`
   tiše použije náhradní chatový model (třeba Haiku) s nekalibrovanými čísly – `sito.py` takovou dávku zastaví.
3. `tools/pasy.py` se `--kniha` a `tools/sito.py` jsou od verze 0.7.4-xsigik; do projektu je přinese aktualizace
   projektu (`novy_projekt.py`, viz SKILL.md „Verze“), ne samotná aktualizace pluginu.

## Postup
1. **Rozvržení** – jeden snímek knihy si prohlédni dřív, než spočítáš cenu: kolik stran je na snímku, kde je
   sloupec se jménem, pořadí jméno/příjmení, kolik zápisů na stranu. Tiskopis, kde jeden zápis jde přes celou
   dvoustranu (knihy zemřelých kolem 1900–1920), má jméno jen vlevo: stahuj jen výřez levé strany. Cena ≈ počet
   snímků × počet pásů na snímek × 0,00013 $. Hotovo, až víš výřez (zlomky x0,y0,x1,y1) a `--strany`.
2. **Stažení a pásy.** Stahuj jen výřez (`portafontium.py snimek <kniha> <n> <soubor> x0,y0,x1,y1`,
   `ahmp_scan.py <XID> <n> <soubor> 1 x0,y0,x1,y1`; blokující badatelny viz `reference/portaly.md`), pak
   `python3 -I tools/pasy.py pracovni/<kniha>/pasy pracovni/<kniha>/s*.jpg --kniha <kniha> [--strany 1]`.
   Každá kniha má vlastní složku pásů; `pasy.py` si zapíše knihu, nastavení a otisk každého snímku (`pasy.json`)
   a jinou knihu nebo jiné nastavení do složky nepustí. Klíč `0065R01` = snímek 65, pravá strana (L/R, jedna
   strana P), pás 1 shora od 0. Složky ze 0.7.3 bez `pasy.json` nařež znovu do nové složky.
3. **Načtení nástroje** v `eval` (z kořene projektu; `importlib`, ať se nespustí příkazová řádka nástroje):
   ```python
   import importlib.util
   _s = importlib.util.spec_from_file_location("sito", "tools/sito.py")
   sito = importlib.util.module_from_spec(_s); _s.loader.exec_module(sito)
   PASY = "pracovni/<kniha>/pasy"
   POPIS = "Crop of a page of the <kniha> death register."   # posílá se ke každému pásu
   ```
4. **Otázka** podle oddílu „Jak se ptát“: jedna otázka typu `bool` na jedno hledání. Pro kalibraci stejná otázka
   se jménem známého zápisu.
5. **Kalibrace v téže knize** – 2–3 zápisy, které jsi sám přečetl na stránce této knihy, se stranou:
   ```python
   await sito.kalibrace(judge_batch, PASY, [{"nazev": "bauman", "strana": "0120L", "otazka": Q_bauman}, …],
                        popis=POPIS)
   ```
   Projde, když maximum pásů známé strany je aspoň 0,4 u každého zápisu; okolní strany jen vypíše (odhad falešných
   poplachů). Platí pro tuto složku pásů a tuto verzi Jevu. Neprojde-li, knihu čti jako dosud. Kalibrace ze
   sousedního svazku tuto knihu nekalibruje.
6. **Prosetí** v buňce `eval` bez časového limitu (`timeout: 0`):
   ```python
   s = await sito.proset(judge_batch, PASY, "<hledání>", Q, popis=POPIS, rozsah=(3, 260), vynechat=(…))
   ```
   `rozsah` = snímky, které má síto pokrýt; `vynechat` = desky a prázdné listy. Nástroj odmítne díru v rozsahu,
   jiný model než Jev, jinou verzi Jevu nebo jinou otázku než v uloženém hledání a knihu bez kalibrace
   (`bez_kalibrace=True` dovolí běh, výsledek zůstane „nekalibrováno“). Selhané pásy posílá znovu, dokud nemají skóre
   všechny; jinak skončí chybou. Výsledky ukládá průběžně do `PASY/jev_<hledání>.json`; přerušenou buňku spusť
   znovu – připojí rozběhnutou dávku a pošle jen chybějící pásy. Souběh 6 (při 16 selhalo ~25 % pásů).
   Hotovo, až `s["uplne"]` je True.
7. **Výběr a čtení.** `python3 -I tools/sito.py mrizka PASY <hledání> [--vyrez 0.5,1]` udělá obrázky 2 × 5 pásů nad
   prahem 0,4 s popiskem; `--vyrez` = jen sloupec jména. K pásu 00 přidá pás 01: pás 00 nese záhlaví tiskopisu
   (častý falešný poplach ~0,5) a první zápis je v něm useknutý. Mřížky čti ty nebo pomocník
   (`reference/zadani_pomocnika.md`); kandidáta ověř v plném rozlišení. Do dat jde jen to, co je přečteno na snímku
   (`SKILL.md`, Fáze 2, krok 5). Hotovo, až má každý označený pás výsledek: zápis, nebo nic.
8. **Deník a zpráva rodině.** `python3 -I tools/sito.py stav PASY <hledání>` vypíše model, kalibraci, pokrytí
   a počty nad prahem (kód 1 = neúplné). Do deníku: kniha, rozsah, hledání, otázka, práh, kalibrace (zápisy a jejich
   skóre), počet označených a přečtených pásů. U přečtených stran „nenalezeno“; u ostatních **„síto nic
   neoznačilo“** s uvedením, ve kterých knihách prošla kalibrace – nepřítomnost zápisu síto nedokládá.

## Jak se ptát
- **Ptej se na roli** (otec, matka, kmotr). Otázka na výskyt jména označí i kmotry, matky a jiné rodiny.
- Typ `bool`, anglicky. Jev volí jen ano/ne nebo z pevných možností, jméno sám nenapíše. Výběr z možností (`choice`)
  ve zkoušce ztratil nejslabší známý zápis, proto síto stavěj na `bool`.
- Úvod otázky popíše stavbu zápisu v této knize (pořadí údajů, jak se píše otec, matka, kmotři), otázka se ptá
  na jeden úsudek. Logiku (práh, kombinace, datum, věk) dělá kód – v počítání a porovnávání dat je Jev slabý
  ([jaggedness](https://docs.typesafe.ai/go/jaggedness.md)).
- Vzor pro křty 18. století; jméno otce i vzory zápisů v úvodu nahraď podle hledání a knihy.
  ```json
  {"otec": {"type": "bool",
    "instructions": "The image is a crop of a page of an 18th-century Latin baptism register in old handwriting. Each entry: day, CHILD's first name (underlined, at line start), then the FATHER's first name in the genitive and his surname, then 'et' and the MOTHER (e.g. 'Anna Motykowa', 'Anna Kuffowa'), then place, then godparents after 'Lev:' (e.g. 'Paulus Podeschwa et Anna Joannis Kuffa uxor' = godmother Anna, wife of Jan Kufa). Is there an entry in which the FATHER of the baptised child is Joannes Kuffa (written 'Joannis Kuffa' right after the child's name)? The child's own name, the mother, and godparents do not count.",
    "criteria": {"true": "An entry reads '<child name> Joannis Kuffa et <mother>'.",
                 "false": "No entry has father Joannis Kuffa; Kuffa appears only as mother (Kuffowa), as godparent or godparent's husband, or not at all."}}}
  ```
- Vzor pro knihy zemřelých s tiskopisem přes dvoustranu (pásy jen z levé strany); pořadí jméno/příjmení podle
  knihy (Všeobecná nemocnice „Příjmení Jméno“, Bohnice „Jméno Příjmení“ podtržené):
  ```json
  {"zem": {"type": "bool",
    "instructions": "The image is a horizontal crop of the left page of a death register (1911-1922) of the General Hospital in Prague, handwritten mostly in Czech. Columns from left: entry number; day and month of death and burial; place of death (often ditto marks); then the column 'Zemřelý' with the DECEASED person's surname FIRST, then first name, then status/occupation and residence (e.g. 'Bauman Julie, žena bednáře v Dolní Počernici č. 160'). Is there an entry in which the DECEASED person is Josef Novák (written roughly 'Novák Josef' at the start of the 'Zemřelý' column)? A spouse or parent with that name does not count.",
    "criteria": {"true": "An entry's deceased-person column begins with 'Novák Josef' or a close spelling.",
                 "false": "No entry's deceased person is Josef Novák."}}}
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

## Měření 2 (knihy zemřelých 1912–1922: PF Dobřany, AHMP Všeobecná nemocnice Z8–Z11, Bohnice Z2–Z3)
| Pokus | Výsledek |
|---|---|
| 1 670 snímků, jen levá strana, ~11 000 pásů vč. kalibrací | ≈ 1,4–1,8 $; 4 860 pásů za 88 min při souběhu 10 |
| Kalibrace v téže knize, 3 známé zápisy na knihu (6 knih) | známé strany 0,76–0,98, okolní strany nejvýš 0,22–0,68 |
| Práh 0,4 | 108 označených pásů (~1 %), všechny přečteny, všechny falešné (hledaný zápis nebyl nalezen) |
| Souběh | 16 → ~25 % pásů selhalo, 10 → 6 z 4 860, 6 → 0 |

Většinu poplachů v Z9 dělaly pásy 00 se záhlavím tiskopisu. Dobřany byly kalibrované jen v sousedních svazcích –
ty výsledky platí jako „nekalibrováno“. Podrobnosti: issue #21.
