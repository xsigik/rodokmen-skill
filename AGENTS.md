# Správa repozitáře rodokmen-skill

Vydání nové verze: zvedni číslo ve třech místech najednou – `.claude-plugin/plugin.json` (`version`),
`skills/rodokmen/VERZE` (podle něj agent u uživatele pozná, že má aktualizovat projekt) a README na dvou místech – nahoře
„Aktuální verze forku: X.Y.Z-xsigik (D. M. RRRR, z původní A.B.C)“ a v požadavcích „Stav k D. M. RRRR (verze X.Y.Z-xsigik)“,
vždy s číslem verze i datem vydání. Verze tohoto forku mají příponu `-xsigik` (např. `0.7.5-xsigik`).
Do `CHANGELOG.md` přidej nahoru sekci `## X.Y.Z-xsigik – D. M. RRRR` (Nové / Opravy / Návody, krátké odrážky pro
uživatele, čísla issues forku jako `#21`). Po commitu a pushi vytvoř tag a vydání na GitHubu forku s textem té sekce:
`awk '/^## X.Y.Z-xsigik /{f=1;next} /^## /{f=0} f' CHANGELOG.md > /tmp/notes.md && gh release create vX.Y.Z-xsigik --repo xsigik/rodokmen-skill --target main --title "X.Y.Z-xsigik" --notes-file /tmp/notes.md`.
Mění-li se formát mezi `tools/` a `template/web/`, otestuj i aktualizaci projektu založeného předchozí verzí
(`novy_projekt.py` na stejnou složku, `npm install`, `npm run data`, `npm run build`).

Původní skill je `upstream` (sarsonj/rodokmen-skill). Jeho změny přebírej sloučením `upstream/main` do `main`; kde má
upstream stejnou funkčnost jako fork, přednost má řešení upstreamu. Tento soubor nahrazuje upstreamový `CLAUDE.md`
(Claude Code čte i `AGENTS.md`) – nová pravidla z `CLAUDE.md` upstreamu přenes sem.

Skill se vyvíjí a zkouší v Claude Code. Jde použít i v Codexu a OMP (Oh My Pi), které ho instalují ze stejného
`.claude-plugin/marketplace.json` – ten proto nepřesouvej. Když měníš pokyny vázané na aplikaci (nástroje, příkazy,
restart), uprav i stávající zmínky o Codexu a OMP, ať si neodporují. V Codexu ani OMP je ověřovat nemusíš.
