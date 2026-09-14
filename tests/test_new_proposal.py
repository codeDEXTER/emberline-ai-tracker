"""`bin/new-proposal` -- every project creates proposals the same way (proposal 21, S-02).

The sponsor made the common-rules standard mandatory (proposal 21, A-01 and
A-02). The PhotoVault app's and engine's newest proposals had none of the
checked shape, and nothing existed to create one from. `new-proposal` writes
the page from templates/proposal.html and its ledger from
templates/ledger.json, then runs the two checkers on what it wrote. These
tests hold it to:

  * the next free number across every docs/proposals/NN-* entry, or an
    explicit --number that no entry already uses;
  * a slug made from the title, and a title that is empty, multi-line or
    carries control characters refused;
  * both files written, or neither -- including when a checker rejects the
    result after writing;
  * proposalcheck and tracker validate clean on the result, unedited;
  * never overwriting anything;
  * every template placeholder replaced, and the title escaped for HTML.

And, because a template can quietly defeat the checks it is meant to pass:
a page from the template that is flipped to accepted (or completed in part)
without recording the answers (or the exceptions) is still a violation.

Every test runs in a scratch git repository under a temp dir.

Run:  python3 -m unittest discover -s tests -p 'test_new_proposal.py' -v
"""
from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEW_PROPOSAL = ROOT / "bin" / "new-proposal"
PROPOSALCHECK = ROOT / "bin" / "proposalcheck"
TRACKER = ROOT / "bin" / "tracker"
TEMPLATE = ROOT / "templates" / "proposal.html"


def today_dates() -> set[str]:
    """The real clock's date, and tomorrow's in case a run crosses midnight."""
    now = datetime.date.today()
    return {now.isoformat(), (now + datetime.timedelta(days=1)).isoformat()}


class Scratch(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve() / "project"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.proposals = self.root / "docs" / "proposals"

    def tearDown(self):
        self._tmp.cleanup()

    def run_new(self, *args, project: Path | None = None, cwd: Path | None = None):
        argv = [sys.executable, str(NEW_PROPOSAL)]
        if project is not False:
            argv += ["--project", str(project or self.root)]
        return subprocess.run(argv + list(args), capture_output=True, text=True,
                              check=False, cwd=str(cwd or self.root))

    def seed(self, name: str, text: str = "") -> Path:
        self.proposals.mkdir(parents=True, exist_ok=True)
        p = self.proposals / name
        p.write_text(text)
        return p

    def listing(self) -> list[str]:
        return sorted(p.name for p in self.proposals.iterdir()) if self.proposals.exists() else []

    def assert_ok(self, r):
        self.assertEqual(r.returncode, 0, f"exit {r.returncode}\nstdout:\n{r.stdout}\nstderr:\n{r.stderr}")


class TestNumbering(Scratch):
    def test_first_proposal_in_an_empty_project_is_01(self):
        r = self.run_new("Warm-up for everyone")
        self.assert_ok(r)
        self.assertEqual(self.listing(), ["01-warm-up-for-everyone.html", "01-warm-up-for-everyone.json"])

    def test_next_number_is_one_above_every_numbered_entry(self):
        self.seed("03-proposal-a.html")
        self.seed("12-data.sidecar.json", "{}")      # not a ledger, still a number in use
        self.seed("07-b.json", "{}")
        (self.proposals / "09-assets").mkdir()         # a directory holds its number too
        self.seed("README.md")
        r = self.run_new("Next one")
        self.assert_ok(r)
        self.assertTrue((self.proposals / "13-next-one.html").is_file(), self.listing())
        self.assertTrue((self.proposals / "13-next-one.json").is_file(), self.listing())

    def test_explicit_number_is_used_and_zero_padded(self):
        self.seed("03-proposal-a.html")
        r = self.run_new("--number", "5", "Explicit")
        self.assert_ok(r)
        self.assertIn("05-explicit.html", self.listing())
        self.assertIn("05-explicit.json", self.listing())
        page = (self.proposals / "05-explicit.html").read_text()
        self.assertIn('<meta name="proposal-id" content="05">', page)
        self.assertEqual(json.loads((self.proposals / "05-explicit.json").read_text())["proposal"], 5)

    def test_explicit_number_three_digits(self):
        r = self.run_new("--number", "120", "Big")
        self.assert_ok(r)
        self.assertIn("120-big.html", self.listing())

    def test_explicit_number_already_used_is_refused_naming_the_file(self):
        self.seed("05-something-else.json", '{"keep": true}')
        before = self.listing()
        for spelled in ("5", "05", "005"):
            with self.subTest(number=spelled):
                r = self.run_new("--number", spelled, "Collides")
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn("05-something-else.json", r.stdout + r.stderr)
                self.assertEqual(self.listing(), before)
        self.assertEqual((self.proposals / "05-something-else.json").read_text(), '{"keep": true}')

    def test_bad_numbers_are_refused(self):
        for bad in ("0", "-3", "abc", "4.5", ""):
            with self.subTest(number=bad):
                r = self.run_new("--number", bad, "Fine title")
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn("--number", r.stderr)
                self.assertEqual(self.listing(), [])


class TestTitles(Scratch):
    def test_slug_is_lowercase_ascii_hyphens(self):
        cases = {
            "The Standard: Is Mandatory!": "the-standard-is-mandatory",
            "Café résumé, déjà vu": "cafe-resume-deja-vu",
            "  spaced   out  ": "spaced-out",
            "v2.0 -- the_sequel": "v2-0-the-sequel",
        }
        for n, (title, slug) in enumerate(cases.items(), start=1):
            with self.subTest(title=title):
                r = self.run_new("--number", str(n), title)
                self.assert_ok(r)
                self.assertIn(f"{n:02d}-{slug}.html", self.listing())

    def test_bad_titles_are_refused_and_write_nothing(self):
        bad = {
            "empty": "",
            "whitespace only": "   ",
            "multi-line": "first line\nsecond line",
            "carriage return": "title\rinjected",
            "tab": "a\tb",
            "escape sequence": "red \x1b[31mtitle",
            "C1 control": "a\x85b",
            "unicode line separator": "a\u2028b",
            "unicode paragraph separator": "a\u2029b",
            "no ascii to slug": "日本語",
        }
        for label, title in bad.items():
            with self.subTest(label):
                r = self.run_new(title)
                self.assertEqual(r.returncode, 1, f"{label}: {r.stdout}{r.stderr}")
                self.assertIn("title", (r.stdout + r.stderr).lower())
                self.assertEqual(self.listing(), [], label)
                # Nothing at all created, not even the directory.
                self.assertFalse((self.root / "docs").exists(), label)


class TestWritten(Scratch):
    def make(self, title="The standard is mandatory", *extra):
        r = self.run_new(*extra, title)
        self.assert_ok(r)
        html = next(self.proposals.glob("*.html"))
        ledger = next(self.proposals.glob("*.json"))
        return r, html, ledger

    def test_both_files_written_and_both_paths_printed_with_next_step(self):
        r, html, ledger = self.make()
        self.assertEqual(html.name, "01-the-standard-is-mandatory.html")
        self.assertEqual(ledger.name, "01-the-standard-is-mandatory.json")
        self.assertIn(str(html), r.stdout)
        self.assertIn(str(ledger), r.stdout)
        self.assertIn("fill the page", r.stdout.lower())
        self.assertIn("items", r.stdout.lower())

    def test_proposalcheck_and_tracker_validate_clean_on_the_result(self):
        _, _, ledger = self.make()
        pc = subprocess.run([sys.executable, str(PROPOSALCHECK), "--project", str(self.root)],
                            capture_output=True, text=True, check=False)
        self.assertEqual(pc.returncode, 0, pc.stdout + pc.stderr)
        self.assertIn("1 asked decisions", pc.stdout)
        tv = subprocess.run([sys.executable, str(TRACKER), "validate", str(ledger)],
                            capture_output=True, text=True, check=False)
        self.assertEqual(tv.returncode, 0, tv.stdout + tv.stderr)
        self.assertIn("well-formed", tv.stdout)

    def test_page_carries_the_checked_shape(self):
        _, html, _ = self.make()
        page = html.read_text()
        self.assertIn('<meta name="proposal-status" content="proposed">', page)
        self.assertIn('<meta name="proposal-id" content="01">', page)
        self.assertIn('<meta name="common-rules-template" content="proposal/21">', page)
        self.assertRegex(page, r'<ol class="decisions">\s*<li')
        self.assertIn("<title>01 · proposed · The standard is mandatory</title>", page)
        self.assertIsNone(re.search(r'<meta name="proposal-part-of"', page))
        self.assertIsNone(re.search(r'<meta name="proposal-decided"', page))
        self.assertTrue(any(d in page for d in today_dates()), "page carries today's date")

    def test_ledger_is_the_minimal_contract(self):
        _, _, ledger = self.make()
        data = json.loads(ledger.read_text())
        self.assertEqual(data["proposal"], 1)
        self.assertEqual(data["title"], "The standard is mandatory")
        self.assertEqual(data["status"], "proposed")
        self.assertIn(data["updated"], today_dates())
        self.assertEqual(data["items"], [])
        self.assertIn("tiers", data)

    def test_every_placeholder_replaced_in_both_files(self):
        _, html, ledger = self.make()
        self.assertNotRegex(html.read_text(), r"\{\{")
        self.assertNotRegex(ledger.read_text(), r"\{\{")

    def test_template_placeholders_are_exactly_the_three(self):
        found = set(re.findall(r"\{\{(.*?)\}\}", TEMPLATE.read_text()))
        self.assertEqual(found, {"NUMBER", "TITLE", "DATE"})

    def test_title_is_escaped_in_html_and_not_reexpanded(self):
        title = 'Tags <b>&amp; "quotes" {{DATE}}'
        r = self.run_new(title)
        self.assert_ok(r)
        html = next(self.proposals.glob("*.html")).read_text()
        self.assertNotIn(title, html)
        self.assertIn("Tags &lt;b&gt;&amp;amp; &quot;quotes&quot; {{DATE}}", html)
        data = json.loads(next(self.proposals.glob("*.json")).read_text())
        self.assertEqual(data["title"], title)

    def test_template_meta_is_in_the_template_itself(self):
        self.assertIn('<meta name="common-rules-template" content="proposal/21">', TEMPLATE.read_text())

    def test_new_proposal_is_executable(self):
        self.assertTrue(os.access(NEW_PROPOSAL, os.X_OK))


class TestNoOverwrite(Scratch):
    def test_same_title_twice_takes_the_next_number(self):
        self.assert_ok(self.run_new("Same"))
        first = (self.proposals / "01-same.html").read_text()
        self.assert_ok(self.run_new("Same"))
        self.assertEqual(self.listing(), ["01-same.html", "01-same.json", "02-same.html", "02-same.json"])
        self.assertEqual((self.proposals / "01-same.html").read_text(), first)

    def test_existing_page_is_never_overwritten(self):
        self.assert_ok(self.run_new("Same"))
        page = self.proposals / "01-same.html"
        page.write_text("hand edited")
        r = self.run_new("--number", "1", "Same")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(page.read_text(), "hand edited")


class TestAllOrNothing(Scratch):
    def test_a_checker_rejecting_the_result_leaves_nothing_behind(self):
        # A document with no NN- filename that already claims proposal-id 01:
        # the number looks free by filename, but proposalcheck reports a
        # collision once the new page exists.
        self.seed("draft.html",
                  '<meta name="proposal-id" content="01">\n'
                  '<meta name="proposal-status" content="proposed">\n<h1>draft</h1>')
        r = self.run_new("Collides by id")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("proposalcheck", r.stdout + r.stderr)
        self.assertEqual(self.listing(), ["draft.html"])

    def test_a_violation_elsewhere_does_not_block(self):
        # A pre-existing lead with a typo'd status, dated after the floor: a
        # violation that is not new-proposal's to fix or to be blocked by.
        self.seed("02-old.html",
                  '<meta name="proposal-id" content="02">\n'
                  '<meta name="proposal-status" content="superseded-by 1">\n'
                  '<meta name="proposal-decided" content="2026-09-01">\n<h1>old</h1>')
        r = self.run_new("Unrelated")
        self.assert_ok(r)
        self.assertIn("03-unrelated.html", self.listing())


class TestProject(Scratch):
    def test_project_is_the_git_top_of_dir(self):
        sub = self.root / "src" / "deep"
        sub.mkdir(parents=True)
        r = self.run_new("From below", project=sub)
        self.assert_ok(r)
        self.assertTrue((self.root / "docs" / "proposals" / "01-from-below.html").is_file())
        self.assertFalse((sub / "docs").exists())

    def test_default_project_is_cwd(self):
        sub = self.root / "src"
        sub.mkdir()
        r = self.run_new("From cwd", project=False, cwd=sub)
        self.assert_ok(r)
        self.assertTrue((self.root / "docs" / "proposals" / "01-from-cwd.html").is_file())

    def test_not_a_git_repository_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.run_new("Nowhere", project=Path(tmp))
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("not inside a git repository", r.stderr)
            self.assertEqual(list(Path(tmp).iterdir()), [])


class TestTemplateDoesNotDefeatTheChecks(Scratch):
    """The page must not pre-satisfy the rules it exists to meet: an answers
    block or an exceptions block baked into the template would let every
    future proposal reach accepted with nothing recorded."""

    def flip(self, status: str) -> subprocess.CompletedProcess:
        self.assert_ok(self.run_new("Flip me"))
        page = self.proposals / "01-flip-me.html"
        text = page.read_text().replace(
            '<meta name="proposal-status" content="proposed">',
            f'<meta name="proposal-status" content="{status}">\n'
            '<meta name="proposal-decided" content="2026-09-14">')
        page.write_text(text)
        return subprocess.run([sys.executable, str(PROPOSALCHECK), "--project", str(self.root)],
                              capture_output=True, text=True, check=False)

    def test_accepted_without_answers_is_a_violation(self):
        r = self.flip("accepted")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("records no answers", r.stdout)

    def test_completed_in_part_without_exceptions_is_a_violation(self):
        r = self.flip("completed in part")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("exceptions", r.stdout)


if __name__ == "__main__":
    unittest.main()
