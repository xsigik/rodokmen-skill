import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SKILL = Path(__file__).resolve().parents[1] / "skills" / "rodokmen"
_spec = importlib.util.spec_from_file_location("sito", SKILL / "tools" / "sito.py")
sito = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sito)
MAGICK = shutil.which("magick") or shutil.which("convert")
JEV = "typesafe/jev-1.14.0"
Q = {"zem": {"type": "bool", "instructions": "Is the deceased person X?"}}


class Item:
    def __init__(self, ok, answers=None):
        self.ok, self.answers = ok, answers


class Batch:
    """Stand-in for an OMP judge batch: drain returns a few items at a time and may return early;
    a cancelled run raises on drain; results() holds every settled answer."""

    def __init__(self, bid, items, model, interrupt=False, tail_only_in_results=False):
        self.id, self._items, self.model, self.cancelled = bid, list(items), model, False
        self._interrupt, self._tail, self._settled = interrupt, tail_only_in_results, []

    async def drain(self, timeout=None):
        if self.cancelled:
            raise RuntimeError("run cancelled")
        if self._interrupt:
            self._interrupt = False
            raise asyncio.CancelledError()
        out = self._items[:2]
        if self._tail:   # everything settles at once, drain hands out only the first items
            self._settled += self._items
            self._items = []
        else:
            self._settled += out
            self._items = self._items[2:]
        return out

    def status(self):
        return {"id": self.id, "running": bool(self._items) and not self.cancelled, "model": self.model}

    def results(self):
        return {k: it.answers for k, it in self._settled if it.ok}

    def cancel(self):
        self.cancelled = True


class Judge:
    """Stand-in for judge_batch. score(key) gives P(yes); fail[key] = how many rounds the band fails first."""

    def __init__(self, score=lambda k: 0.1, model=JEV, fail=None, interrupt_first=False, tail_first=False):
        self.score, self.model, self.fail = score, model, dict(fail or {})
        self.calls, self.batches = [], {}
        self.interrupt_first, self.tail_first = interrupt_first, tail_first

    def __call__(self, states, questions, *, intent, concurrency, retries, images):
        self.calls.append(sorted(states))
        qid = next(iter(questions))
        items = []
        for k in sorted(states):
            if self.fail.get(k, 0) > 0:
                self.fail[k] -= 1
                items.append((k, Item(False)))
            else:
                items.append((k, Item(True, {qid: {"bool": self.score(k)}})))
        first = len(self.calls) == 1
        b = Batch(f"b{len(self.calls)}", items, self.model, interrupt=self.interrupt_first and first,
                  tail_only_in_results=self.tail_first and first)
        self.batches[b.id] = b
        return b

    def attach(self, bid):
        return self.batches[bid]


class SitoTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pasy = str(Path(self.tmp.name) / "pasy")
        self.make_bands(range(1, 6))

    def make_bands(self, snimky, sides="LR", bands=3, kniha="test_kniha"):
        Path(self.pasy).mkdir(exist_ok=True)
        z = {"kniha": kniha, "nastaveni": {"strany": len(sides), "sirka": 1569, "vyska": 600, "krok": 420},
             "snimky": {}}
        for n in snimky:
            keys = [f"{n:04d}{s}{i:02d}" for s in sides for i in range(bands)]
            for k in keys:
                (Path(self.pasy) / f"{k}.jpg").write_bytes(b"x")
            z["snimky"][str(n)] = {"soubor": f"s{n:03d}.jpg", "sha256": hashlib.sha256(str(n).encode()).hexdigest(),
                                   "pasy": keys}
        (Path(self.pasy) / "pasy.json").write_text(json.dumps(z), encoding="utf-8")

    async def calibrate(self, judge, strana="0003L"):
        return await sito.kalibrace(judge, self.pasy, [{"nazev": "znamy", "strana": strana, "otazka": Q}],
                                    popis="page")

    async def test_non_jev_model_is_rejected_and_batch_cancelled(self):
        judge = Judge(model="anthropic/claude-haiku-5-5")
        with self.assertRaisesRegex(sito.SitoChyba, "ne na Jevu"):
            await sito.proset(judge, self.pasy, "h", Q, popis="page", rozsah=(1, 5), bez_kalibrace=True)
        self.assertTrue(judge.batches["b1"].cancelled)
        self.assertEqual(json.loads((Path(self.pasy) / "jev_h.json").read_text())["skore"], {})

    async def test_failed_bands_are_resent_until_every_band_has_a_score(self):
        judge = Judge(fail={"0002L01": 1, "0004R02": 2})
        s = await sito.proset(judge, self.pasy, "h", Q, popis="page", rozsah=(1, 5), bez_kalibrace=True)
        self.assertTrue(s["uplne"])
        self.assertEqual(s["se_skore"], 30)
        self.assertEqual(judge.calls[1], ["0002L01", "0004R02"])
        self.assertEqual(judge.calls[2], ["0004R02"])

    async def test_band_without_score_after_all_rounds_blocks_the_result(self):
        judge = Judge(fail={"0002L01": 99})
        with self.assertRaisesRegex(sito.SitoChyba, "1 pásů nemá"):
            await sito.proset(judge, self.pasy, "h", Q, popis="page", rozsah=(1, 5), kola=3, bez_kalibrace=True)
        self.assertFalse(sito.stav(self.pasy, "h")["uplne"])
        with self.assertRaisesRegex(sito.SitoChyba, "není úplné"):
            sito.vyber(self.pasy, "h")

    async def test_gap_in_range_is_rejected_before_any_band_is_sent(self):
        judge = Judge()
        with self.assertRaisesRegex(sito.SitoChyba, r"chybí pásy snímků \[6, 7\]"):
            await sito.proset(judge, self.pasy, "h", Q, popis="page", rozsah=(1, 7), bez_kalibrace=True)
        self.assertEqual(judge.calls, [])
        s = await sito.proset(judge, self.pasy, "h2", Q, popis="page", rozsah=(1, 7), vynechat=(6, 7),
                              bez_kalibrace=True)
        self.assertTrue(s["uplne"])

    async def test_resume_with_a_different_question_is_rejected(self):
        await sito.proset(Judge(), self.pasy, "h", Q, popis="page", rozsah=(1, 5), bez_kalibrace=True)
        other = {"zem": {"type": "bool", "instructions": "Is the deceased person Y?"}}
        with self.assertRaisesRegex(sito.SitoChyba, "jinou otázkou"):
            await sito.proset(Judge(), self.pasy, "h", other, popis="page", rozsah=(1, 5), bez_kalibrace=True)

    async def test_scores_from_two_jev_versions_are_not_mixed(self):
        with self.assertRaises(sito.SitoChyba):
            await sito.proset(Judge(fail={"0001L00": 9}), self.pasy, "h", Q, popis="page", rozsah=(1, 5), kola=1,
                              bez_kalibrace=True)
        with self.assertRaisesRegex(sito.SitoChyba, "dvou verzí"):
            await sito.proset(Judge(model="typesafe/jev-1.15.0"), self.pasy, "h", Q, popis="page", rozsah=(1, 5),
                              bez_kalibrace=True)

    async def test_results_from_old_version_are_read_only(self):
        (Path(self.pasy) / "jev_h.json").write_text(json.dumps({"0001L00": 0.2}), encoding="utf-8")
        with self.assertRaisesRegex(sito.SitoChyba, "starém formátu"):
            await sito.proset(Judge(), self.pasy, "h", Q, popis="page", rozsah=(1, 5), bez_kalibrace=True)
        self.assertTrue(sito.stav(self.pasy, "h")["stary_format"])

    async def test_calibration_counts_only_the_known_page(self):
        opposite_high = Judge(score=lambda k: 0.95 if k.startswith("0003R") else 0.1)
        r = await self.calibrate(opposite_high)
        self.assertFalse(r["prosla"])
        with self.assertRaisesRegex(sito.SitoChyba, "chybí úspěšná kalibrace"):
            await sito.proset(Judge(), self.pasy, "h", Q, popis="page", rozsah=(1, 5))

        known_high = Judge(score=lambda k: 0.95 if k.startswith("0003L") else 0.1)
        r = await self.calibrate(known_high)
        self.assertTrue(r["prosla"])
        self.assertEqual(r["zname"][0]["znama"], 0.95)
        s = await sito.proset(Judge(), self.pasy, "h", Q, popis="page", rozsah=(1, 5))
        self.assertEqual(s["kalibrace"], JEV)

    async def test_calibration_from_another_jev_version_does_not_count(self):
        await self.calibrate(Judge(score=lambda k: 0.95))
        with self.assertRaisesRegex(sito.SitoChyba, "chybí úspěšná kalibrace"):
            await sito.proset(Judge(model="typesafe/jev-1.15.0"), self.pasy, "h", Q, popis="page", rozsah=(1, 5))

    async def test_run_without_calibration_stays_marked(self):
        s = await sito.proset(Judge(), self.pasy, "h", Q, popis="page", rozsah=(1, 5), bez_kalibrace=True)
        self.assertEqual(s["kalibrace"], "nekalibrováno")

    async def test_interrupted_run_reattaches_the_running_batch(self):
        judge = Judge(interrupt_first=True)
        with self.assertRaises(asyncio.CancelledError):
            await sito.proset(judge, self.pasy, "h", Q, popis="page", rozsah=(1, 5), bez_kalibrace=True)
        self.assertFalse(judge.batches["b1"].cancelled)
        s = await sito.proset(judge, self.pasy, "h", Q, popis="page", rozsah=(1, 5), bez_kalibrace=True)
        self.assertTrue(s["uplne"])
        self.assertEqual(len(judge.calls), 1)   # nothing re-sent: the attached batch delivered every band

    async def test_answers_settled_after_the_last_drain_are_kept(self):
        judge = Judge(tail_first=True)
        s = await sito.proset(judge, self.pasy, "h", Q, popis="page", rozsah=(1, 5), bez_kalibrace=True)
        self.assertTrue(s["uplne"])
        self.assertEqual(len(judge.calls), 1)

    async def test_search_finishes_once_jev_is_available(self):
        judge = Judge(model="anthropic/claude-haiku-5-5")
        with self.assertRaisesRegex(sito.SitoChyba, "ne na Jevu"):
            await sito.proset(judge, self.pasy, "h", Q, popis="page", rozsah=(1, 5), bez_kalibrace=True)
        judge.model = JEV   # the user logged in to TypeSafe
        s = await sito.proset(judge, self.pasy, "h", Q, popis="page", rozsah=(1, 5), bez_kalibrace=True)
        self.assertTrue(s["uplne"])
        self.assertEqual(s["model"], JEV)

    async def test_dead_batch_is_abandoned_on_resume(self):
        judge = Judge(interrupt_first=True)
        with self.assertRaises(asyncio.CancelledError):
            await sito.proset(judge, self.pasy, "h", Q, popis="page", rozsah=(1, 5), bez_kalibrace=True)
        judge.batches["b1"].cancel()   # the run died while nobody was waiting
        s = await sito.proset(judge, self.pasy, "h", Q, popis="page", rozsah=(1, 5), bez_kalibrace=True)
        self.assertTrue(s["uplne"])
        self.assertEqual(len(judge.calls), 2)

    async def test_calibration_with_another_description_does_not_count(self):
        await self.calibrate(Judge(score=lambda k: 0.95))
        with self.assertRaisesRegex(sito.SitoChyba, "chybí úspěšná kalibrace"):
            await sito.proset(Judge(), self.pasy, "h", Q, popis="other book", rozsah=(1, 5))

    async def test_batch_that_returns_nothing_and_no_model_is_rejected(self):
        judge = Judge(model=None, fail={f"{n:04d}{s}{i:02d}": 9 for n in range(1, 6) for s in "LR" for i in range(3)})
        with self.assertRaisesRegex(sito.SitoChyba, "nevrátila model"):
            await sito.proset(judge, self.pasy, "h", Q, popis="page", rozsah=(1, 5), bez_kalibrace=True)

    async def test_question_must_be_a_single_bool(self):
        two = {"a": Q["zem"], "b": Q["zem"]}
        with self.assertRaisesRegex(sito.SitoChyba, "právě jedna"):
            await sito.proset(Judge(), self.pasy, "h", two, popis="page", rozsah=(1, 5), bez_kalibrace=True)

    async def test_cli_status_fails_for_incomplete_run(self):
        with self.assertRaises(sito.SitoChyba):
            await sito.proset(Judge(fail={"0001L00": 9}), self.pasy, "h", Q, popis="page", rozsah=(1, 5), kola=1,
                              bez_kalibrace=True)
        r = subprocess.run([sys.executable, "-I", str(SKILL / "tools/sito.py"), "stav", self.pasy, "h"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, r.stdout)
        await sito.proset(Judge(), self.pasy, "h", Q, popis="page", rozsah=(1, 5), bez_kalibrace=True)
        r = subprocess.run([sys.executable, "-I", str(SKILL / "tools/sito.py"), "stav", self.pasy, "h"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    @unittest.skipUnless(MAGICK, "ImageMagick chybí")
    async def test_grid_shows_header_band_together_with_the_next_band(self):
        self.make_bands([1], sides="L", bands=2)
        for k in ("0001L00", "0001L01"):
            subprocess.run([MAGICK, "-size", "1569x600", "xc:white", str(Path(self.pasy) / f"{k}.jpg")], check=True)
        await sito.proset(Judge(score=lambda k: 0.9 if k == "0001L00" else 0.1), self.pasy, "h", Q, popis="page",
                          rozsah=(1, 1), bez_kalibrace=True)
        files = sito.mrizka(self.pasy, "h")
        self.assertEqual(len(files), 1)
        w = int(subprocess.run([MAGICK, files[0], "-format", "%w", "info:"], capture_output=True, text=True,
                               check=True).stdout)
        self.assertGreater(w, 1500)   # two tiles side by side: band 00 and its continuation 01


@unittest.skipUnless(MAGICK, "ImageMagick chybí")
class PasyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.out = self.dir / "pasy"

    def image(self, name, color):
        p = self.dir / name
        p.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([MAGICK, "-size", "1000x700", f"xc:{color}", str(p)], check=True)
        return str(p)

    def pasy(self, *args):
        return subprocess.run([sys.executable, "-I", str(SKILL / "tools/pasy.py"), str(self.out), *args],
                              capture_output=True, text=True)

    def test_second_book_into_the_same_folder_is_rejected_without_writing(self):
        self.assertEqual(self.pasy(self.image("a/s001.jpg", "white"), "--kniha", "kniha_a").returncode, 0)
        before = sorted(p.name for p in self.out.iterdir())
        r = self.pasy(self.image("b/s002.jpg", "gray"), "--kniha", "kniha_b")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("kniha_a", r.stderr)
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), before)

    def test_same_book_can_be_extended_and_rerun(self):
        a = self.image("s001.jpg", "white")
        self.assertEqual(self.pasy(a, "--kniha", "k").returncode, 0)
        r = self.pasy(a, self.image("s002.jpg", "white"), "--kniha", "k")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("2 snímků", r.stdout)
        z = json.loads((self.out / "pasy.json").read_text())
        self.assertEqual(sorted(z["snimky"]), ["1", "2"])
        self.assertTrue(all((self.out / f"{k}.jpg").exists() for s in z["snimky"].values() for k in s["pasy"]))

    def test_other_settings_in_the_same_folder_are_rejected(self):
        a = self.image("s001.jpg", "white")
        self.assertEqual(self.pasy(a, "--kniha", "k").returncode, 0)
        r = self.pasy(a, "--kniha", "k", "--strany", "1")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("nastavením", r.stderr)

    def test_same_scan_number_with_different_content_is_rejected(self):
        self.assertEqual(self.pasy(self.image("a/s001.jpg", "white"), "--kniha", "k").returncode, 0)
        r = self.pasy(self.image("b/s001.jpg", "gray"), "--kniha", "k")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("jiného obsahu", r.stderr)

    def test_folder_with_bands_but_no_record_is_rejected(self):
        self.out.mkdir()
        (self.out / "0001L00.jpg").write_bytes(b"x")
        r = self.pasy(self.image("s001.jpg", "white"), "--kniha", "k")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("bez záznamu", r.stderr)

    def test_book_name_is_required(self):
        r = self.pasy(self.image("s001.jpg", "white"))
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(self.out.exists())


if __name__ == "__main__":
    unittest.main()
