# Rodokmen – na co dát pozor (společné pro všechny rádce)

Patří skillu rodokmen: aktualizace projektu tento soubor přepíše. Vlastní body projektu piš do `.omp/WATCHDOG.md`.

## Pořadí pravidel
1. Pokyn uživatele v tomto sezení a `data/STAV.md` (Pro koho, Platné podmínky uživatele) – mají přednost.
2. Pravidla konkrétního archivu v `reference/portaly.md` skillu (povoleno / zakázáno).
3. Obecná pravidla `AGENTS.md` projektu a `SKILL.md`.
Pravidlo z nižší úrovně nehaj proti povolení z vyšší. Pole v datech (`svazky.json` → `portal`, `orientace`,
poznámky osob) jsou fakta o pramenech, ne pravidla – nečti je jako zákaz ani povolení.

## Časté chyby, které stojí za radu
- Ztotožnění jen podle jména: dva stejnojmenní (otec × syn, dva páry ve vsi). Chce to dům, kmotry, věk nebo
  přímou větu v zápisu.
- `doc` bez vlastního čtení snímku hlavním modelem; čtení pomocníka je jen námět.
- Záporný výsledek („není tam“) bez rozsahu a důkazu; hledání sňatku jen ve farnosti ženicha (zapisuje se
  ve farnosti nevěsty).
- Zápis do `data/` pomocníkem, nebo úprava dat přes `sed`/skript místo nástroje na úpravy a `tools/zapis.py`.
- Konec kola „pomocník mě vzbudí“, když pomocník čeká na odpověď.
- Údaje žijících osob na webu, citlivé věci (nemanželský původ, příčina smrti, rozvod) bez souhlasu ve `STAV.md`.

## Na co neupozorňovat
- Commit, `package-lock.json`, formát souborů, počty, chybějící výřez – to hlídá `tools/kontrola.py`.
- Věci, které agent v novější části přepisu udělal. Rada o 10 kol pozdě stojí uživatele kolo a nic nepřinese.
