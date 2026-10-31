import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SKILL = Path(__file__).resolve().parents[1] / "skills" / "rodokmen"


class DataChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        subprocess.run([sys.executable, "-I", str(SKILL / "tools/novy_projekt.py"), str(self.project)],
                       check=True, capture_output=True, text=True)
        self.people = {
            1: dict(n="Adam Zkouška", y="* 2000", st="unk"),
            2: dict(n="Jan Nový", y="1800–1860", st="unk"),
            3: dict(n="matka neuvedena", st="unk"),
            4: dict(n="Jan Nový", y="1800–1860", st="unk"),
            8: dict(n="Josef Nový", y="† 1831", st="unk"),
            10: dict(n="František Marek", st="unk"),
            21: dict(n="Marie Marková", y="1823–1890", st="unk"),
            42: dict(n="Marie Marková", y="1823–1890", st="unk"),
        }
        self.save_people()
        self.save_json("web.json", {"prihlaseni": {"otevreny": True}})

    def save_people(self, hypotheses=None):
        (self.project / "data/osoby.py").write_text(
            f"P = {self.people!r}\nSAME = {{42: 21}}\nLINES = {{8: ('Noví', '')}}\n"
            f"SIDE = []\nISSUES = []\nHYPOTEZY = {hypotheses or []!r}\n", encoding="utf-8")

    def save_json(self, name, value):
        (self.project / "data" / name).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def run_tool(self, name, *args):
        return subprocess.run([sys.executable, "-I", str(self.project / "tools" / name), *args],
                              cwd=self.project, capture_output=True, text=True)

    def test_epidemic_hints_require_an_exact_death(self):
        facts = {
            "Přesné datum": "† 12. 5. 1831 v Holicích",
            "Přesný rok": "† 1831, Holice",
            "Před": "† před 1831", "Po": "† po 1831", "Mezi": "† mezi 1831 a 1843",
            "Rozmezí": "† 1831–1843", "Rozmezí s mezerami": "† 1831 – 1843",
            "Přibližně": "† asi 1831", "Nejistě": "† 1831?", "Volba": "† 1831 nebo 1832",
            "Neplatné datum": "† 31. 2. 1831",
        }
        self.people = {k: dict(n=name, f=[fact], st="unk") for k, (name, fact) in enumerate(facts.items(), 1)}
        self.save_people()
        # SAME is irrelevant to these hints; avoid excluding an input case.
        with (self.project / "data/osoby.py").open("a", encoding="utf-8") as f:
            f.write("SAME = {}\n")
        result = self.run_tool("napady.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        hints = [line for line in result.stdout.splitlines() if "cholera?" in line]
        self.assertEqual(len(hints), 2, result.stdout)
        self.assertTrue(any("Přesné datum" in line for line in hints))
        self.assertTrue(any("Přesný rok" in line for line in hints))

    def test_checker_finds_stale_person_links_without_export(self):
        (self.project / "data/zajimavosti.md").write_text(
            "[Marie](/osoba/marie-markova-1824/) a [Marie](/osoba/marie-markova-1823/)", encoding="utf-8")
        result = self.run_tool("kontrola.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("/osoba/marie-markova-1824/", result.stdout)
        self.assertNotIn("/osoba/marie-markova-1823/", result.stdout)
        self.assertFalse((self.project / "web/src/data/site.json").exists())

    def test_relationship_degree_is_a_warning_and_accepts_alias_generations(self):
        (self.project / "data/pribeh.md").write_text(
            "prapraprababička [Marie](/osoba/marie-markova-1823/)\n\n"
            "praprababička [Marie](/osoba/marie-markova-1823/)\n\n"
            "prababička [Marie](/osoba/marie-markova-1823/)", encoding="utf-8")
        result = self.run_tool("kontrola.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("prababička", result.stdout)
        # 21 and its alias 42 describe two legitimate degrees for the same URL.
        self.assertNotIn("„prapraprababička“", result.stdout)
        self.assertNotIn("„praprababička“", result.stdout)

    def test_degree_for_21_without_alias_rejects_one_extra_pra(self):
        with (self.project / "data/osoby.py").open("a", encoding="utf-8") as f:
            f.write("SAME = {}\n")
        (self.project / "data/pribeh.md").write_text(
            "prapraprababička [Marie](/osoba/marie-markova-1823/)\n\n"
            "praprababička [Marie](/osoba/marie-markova-1823/)\n\n"
            "dědeček [Jan](/osoba/jan-novy-1800-4/)", encoding="utf-8")
        result = self.run_tool("kontrola.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("„prapraprababička“", result.stdout)
        self.assertNotIn("„praprababička“", result.stdout)
        self.assertNotIn("„dědeček“", result.stdout)
        self.assertIn("pribeh.md", result.stdout)

    def test_dry_check_uses_exporter_routes_and_does_not_write(self):
        (self.project / "data/pribeh.md").write_text(
            "[jeden](/osoba/jan-novy-1800/) [druhý](/osoba/jan-novy-1800-4/) "
            "[úmrtí](/osoba/josef-novy/) [rod](/rod/novi/) [rodina](/rodina/jan-novy-1800-rodina/) "
            "[neznámá](/osoba/matka-neuvedena/)", encoding="utf-8")
        before = {str(p.relative_to(self.project)): p.read_bytes() for p in self.project.rglob('*') if p.is_file()}
        result = self.run_tool("export_web.py", "--kontrola-odkazu")
        self.assertEqual(result.returncode, 0, result.stderr)
        warnings = json.loads(result.stdout)
        self.assertEqual(len(warnings), 1, warnings)
        self.assertIn("/osoba/matka-neuvedena/", warnings[0])
        after = {str(p.relative_to(self.project)): p.read_bytes() for p in self.project.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        exported = self.run_tool("export_web.py")
        self.assertEqual(exported.returncode, 0, exported.stderr)
        site = json.loads((self.project / "web/src/data/site.json").read_text())
        self.assertIn("jan-novy-1800-4", site["people"])
        self.assertNotIn("josef-novy-1831", site["people"])
        self.assertIn("jan-novy-1800-rodina", site["families"])
        self.assertIn("novi", site["lines"])

    def test_check_covers_public_config_hypotheses_and_ignores_comments(self):
        self.save_json("web.json", {"prihlaseni": {"otevreny": True}, "uvod": {"odstavce": ["[chybí](/osoba/konfigurace/)"]}})
        self.save_people([dict(rod=8, nadpis="Hypotéza", text="[chybí](/osoba/hypoteza/)", polozky=[])])
        (self.project / "data/zajimavosti.md").write_text("<!-- [poznámka](/osoba/soukroma/) -->", encoding="utf-8")
        result = self.run_tool("kontrola.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("/osoba/konfigurace/", result.stdout)
        self.assertIn("/osoba/hypoteza/", result.stdout)
        self.assertNotIn("/osoba/soukroma/", result.stdout)


if __name__ == "__main__":
    unittest.main()
