# Zadání pro pomocníka (subagenta)

Pomocník nemá kontext projektu – zná jen zadání. Šablona vznikla z kol, kde obecné zadání (12 osob, obecná pravidla)
končilo po 1–2 nálezech a pomocníka bylo nutné několikrát posílat „pokračuj“. Vyplň všechny části v `<…>`.

## Než zadání napíšeš (dělá hlavní model)
- **Malá dávka:** 4–6 osob na pomocníka, jedna fara / jedna kniha / jeden archiv. Víc pomocníků nad jedním portálem
  ho přetíží – rozlož je mezi archivy.
- **Orientaci v knize udělej sám:** najdi knihu, rejstřík a přepočet snímek ↔ folio (pagina), ověř ho na jednom
  snímku a pomocníkovi dej **uzavřený seznam snímků**. Výchozí bod je pole `orientace` svazku v `data/svazky.json`;
  co ověříš nově, doplň tam (svazek nejdřív zapiš nástrojem `… svazek`, ten vypíše klíč). Pomocník, který hledá,
  kde kniha začíná, spotřebuje většinu běhu na orientaci. Pozor: „fol.“ v rejstříku bývá pagina.
- **Kontrolní zápis:** vyber jeden zápis ze stejné knihy, který už máš doložený (osoba, datum, snímek). Pomocník ho
  musí najít jako první – tím ověříš, že čte správnou knihu a že mu snímky jdou.
- **Model:** levnější pracovní model pomocníka (Claude Code: Sonnet; Codex a OMP viz `SKILL.md`, „Pomocníci“), ne ten
  nejlevnější. Nejlevnější model (Haiku) na listování knihou nestačí (v rejstříku řádky najde, v knize se ztratí
  v číslování listů); použij ho nejvýš na rejstřík. Kurent 18. a 1. poloviny 19. století a vybledlé snímky čte levnější
  model nespolehlivě – takovou knihu čti sám, nebo pomocníkovi dej přesný snímek. ARON a Porta fontium zvládá dobře.
- **Nejvýš ~50 snímků na jeden běh.** Při stovkách obrázků pomocník část z nich přestane vidět („media removed“)
  a bez tabulky stavu snímků by to nepoznal. Delší knihu rozděl do dalších zadání.

## Šablona (zkopíruj a vyplň)

```
Jsi pomocník při hledání předků v matrikách. Tvoje role je JEN NAJÍT zápisy; přepis a ověření dělá hlavní model.

PROJEKT: <absolutní cesta ke kořeni projektu>
VÝSTUP:  <absolutní cesta>/pracovni/pom_<větev>/vysledek.md   (piš jen sem)
NÁSTROJ: <např. python3 -I tools/portafontium.py snimek <kniha> <snímek> <soubor> – spouštěj z kořene projektu>
         <technické pasti z reference/matriky.md: macOS zsh / Windows python -I -X utf8, magick>
         <kniha bez rejstříku: procházej ji přes python3 -I tools/nahledy.py <pf|ebad|trebon> <kniha> <od> <do> [výřez sloupců],
          zápis čti přes python3 -I tools/overit.py>

KNIHA: <archiv, signatura, druh (N/O/Z), roky, odkaz>
SNÍMKY: <uzavřený seznam nebo rozsah, např. 28–41>; přepočet: <snímek ≈ (folio + 1)/2 − 5>
        orientace: <oddíly, rejstřík – z pole orientace svazku>
ROZPOČET: nejvýš <N ≤ 50> stažených snímků; v plném rozlišení jen ty, kde je kandidát.

KONTROLNÍ ZÁPIS (najdi nejdřív): <jméno, datum, dům> na snímku <n>.
  Když ho nenajdeš, zastav se a napiš proč – bez něj tvé „nenalezeno“ u ostatních osob neplatí.

HLEDEJ (projdi VŠECHNY):
1. <jméno, druh zápisu, očekávaný rok ± rozpětí, dům, rodiče/manžel – co víme>
2. …

PRAVIDLA:
- Obrázek ke čtení zmenši na nejvýš 2000 px (větší se nezobrazí a „četl“ bys naslepo); na kandidáta si udělej výřez
  v plném rozlišení.
- Nikdy nepiš údaj, který jsi na snímku neviděl. Nejisté čtení označ (?), nečitelné […].
- 7ber/7bris = září, 8ber = říjen, 9ber = listopad, Xber = prosinec (ne 7. a 8. měsíc).
- Když se ti obrázek nezobrazí (prázdný, „media removed“), zastav se a napiš, u kterého snímku.
- Po KAŽDÉ osobě hned připiš výsledek do výstupního souboru (můžeš skončit předčasně – co je zapsané, neztratí se).
- Každý snímek stahuj jednou; nad jedním archivem běží jen jedno stahování. Odpověď 503 / timeout =
  přestaň s tímto archivem a napiš to.

FORMÁT VÝSLEDKU (pro každou osobu):
- osoba: <číslo / jméno ze zadání>
- výsledek: nalezeno / nenalezeno / nejisté
- snímek, souřadnice zápisu (zlomky 0–1: x0,y0,x1,y1), soubor výřezu, ze kterého jsi četl
- jen ztotožňující údaje: datum, dům, jméno, věk, jména rodičů / manžela
- u „nenalezeno“: které snímky jsi prošel
- vedlejší nálezy: zjevně související výskyty (stejný dům, vzácné příjmení rodu) se snímkem

STAV KAŽDÉHO SNÍMKU na konci: číslo – rok a první jméno, které na něm skutečně čteš / nečitelné / nepodařilo se stáhnout.

HOTOVO, až má každá osoba ze seznamu výsledek a každý snímek stav.
```

## Po návratu pomocníka
- Kontrolní zápis nenalezen nebo chybí stav snímků → výsledek ber jako neúplný, „nenalezeno“ neplatí.
- Každý nález ověř sám na snímku (`tools/overit.py`, viz `SKILL.md`, „Pomocníci“), teprve pak ho zapiš do dat jako `doc`.
- Rozliš „zápis doložen“ a „vazba na rodinu doložena“: shoda jména z rejstříku je kandidát, ne doklad.
- Prošlý rozsah (i bez nálezu) zapiš do deníku, ať se stejné snímky neprocházejí znovu.
- Co stav snímků prozradil o rozvržení knihy (kde začíná rok, obec, rejstřík), ověř a doplň do `orientace` svazku.
