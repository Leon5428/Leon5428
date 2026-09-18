"""Run from the repository root: python -m unittest discover -s WebCode/tests -v."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import build


class BuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pandoc = build.find_pandoc(build.ROOT)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix=".build-test-", dir=build.ROOT)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(build.ROOT / "WebCode/templates", self.root / "WebCode/templates")
        shutil.copytree(build.ROOT / "WebCode/css", self.root / "WebCode/css")
        shutil.copytree(build.ROOT / "WebCode/assets", self.root / "WebCode/assets")

    def subject(self, name="M01-Test", *, order=1, chapters=None):
        directory = self.root / "Math" / name
        directory.mkdir(parents=True)
        if chapters is None:
            chapters = [{"file": "00-first.tex", "title": "First", "order": 1}]
        meta = {"title": name, "order": order, "chapters": chapters}
        (directory / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        for chapter in chapters:
            (directory / chapter["file"]).write_text(r"\section{Introduction} A paragraph.", encoding="utf-8")
        return directory

    def run_build(self, **kwargs):
        return build.build(self.root, pandoc=self.pandoc, **kwargs)

    def hashes(self):
        return {p.relative_to(self.root / "Output").as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (self.root / "Output").rglob("*") if p.is_file()}

    def test_metadata_order_navigation_and_determinism(self):
        # Both array order and filename numbering intentionally differ from display order.
        self.subject(chapters=[{"file": "00-first.tex", "title": "Later", "order": 20},
                               {"file": "01-second.tex", "title": "Earlier & <safe>", "order": 10}])
        self.subject("M02-Single", order=0)
        count, warnings = self.run_build()
        self.assertEqual((count, warnings), (3, []))
        page = (self.root / "Output/Math/M01-Test/01-second.html").read_text(encoding="utf-8")
        tree = page.split('<nav class="content-tree"', 1)[1].split('</nav>', 1)[0]
        self.assertLess(tree.index("M02-Single"), tree.index("M01-Test"))
        self.assertLess(tree.index("Earlier &amp; &lt;safe&gt;"), tree.index("Later"))
        self.assertIn('class="subject-link"', tree)
        self.assertIn('class="subject-group current-subject" name="subjects" open', tree)
        self.assertEqual(tree.count('<details'), 1)
        self.assertNotIn('chapter-count', tree)
        self.assertNotIn('category-heading', tree)
        self.assertIn('aria-current="page"', tree)
        self.assertIn('next-article', page)
        self.assertNotIn('previous-article', page)
        self.assertIn('href="../../index.html"', page)
        before = self.hashes()
        self.run_build()
        self.assertEqual(before, self.hashes())

    def test_real_latex_math_lists_tables_images_and_refs(self):
        subject = self.subject()
        (subject / "figure").mkdir()
        (subject / "figure/diagram.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>', encoding="utf-8")
        (subject / "00-first.tex").write_text(r"""
\documentclass{article}
\usepackage{amsmath,graphicx,hyperref}
\newcommand{\RR}{\mathbb{R}}
\begin{document}
\section{Background}\label{sec:bg}
Text with \textbf{bold} and inline $x\in\RR$.
\[ A=\begin{pmatrix}1 & 2\\3 & 4\end{pmatrix},\quad \int_0^1 x^2\,dx=\frac13. \]
\subsection{Details}
\begin{itemize}\item First\item Second\end{itemize}
\begin{enumerate}\item Step one\item Step two\end{enumerate}
\begin{tabular}{cc}A & B \\ 1 & 2\end{tabular}
\begin{verbatim}
print("<hello>")
\end{verbatim}
\begin{figure}\includegraphics{figure/diagram.svg}\caption{Diagram}\end{figure}
\hyperref[sec:bg]{Back to background}
\end{document}
""", encoding="utf-8")
        self.run_build(strict=True)
        page = (self.root / "Output/Math/M01-Test/00-first.html").read_text(encoding="utf-8")
        for expected in ['class="math inline"', 'class="math display"', '\\mathbb{R}',
                         '<h2 id="section-1"', '<h3 id="section-2"', '<ul>', '<ol>', '<table>',
                         '<pre>', 'figure/diagram.svg', 'href="#section-1"', build.MATHJAX_URL]:
            self.assertIn(expected, page)
        self.assertTrue((self.root / "Output/Math/M01-Test/figure/diagram.svg").is_file())

    def test_strict_mode_preserves_output_on_missing_metadata_and_empty_body(self):
        subject = self.subject()
        self.run_build()
        before = self.hashes()
        (subject / "00-first.tex").write_text(r"\documentclass{article}", encoding="utf-8")
        other = self.root / "Math/M02-Unconfigured"
        other.mkdir()
        (other / "00-first.tex").write_text("Draft", encoding="utf-8")
        with self.assertRaisesRegex(build.BuildError, "Strict build stopped"):
            self.run_build(strict=True)
        self.assertEqual(before, self.hashes())
        count, warnings = self.run_build()
        self.assertEqual(count, 1)
        self.assertEqual(len(warnings), 2)

    def test_invalid_metadata_and_traversal_are_errors(self):
        subject = self.subject()
        meta_path = subject / "meta.json"
        original = json.loads(meta_path.read_text())
        for bad_order in [True, "1", 1.5]:
            with self.subTest(order=bad_order):
                bad = dict(original, order=bad_order)
                meta_path.write_text(json.dumps(bad))
                with self.assertRaisesRegex(build.BuildError, "order"):
                    build.discover(self.root, [])
        bad = dict(original, chapters=[{"file": "../outside.tex", "title": "Bad", "order": 1}])
        meta_path.write_text(json.dumps(bad))
        with self.assertRaises(build.BuildError):
            build.discover(self.root, [])
        meta_path.write_text('{"title":')
        with self.assertRaisesRegex(build.BuildError, "invalid JSON"):
            build.discover(self.root, [])

    def test_duplicate_orders_missing_source_and_raw_tex(self):
        subject = self.subject(chapters=[{"file": "00-first.tex", "title": "One", "order": 1},
                                         {"file": "01-second.tex", "title": "Two", "order": 1}])
        with self.assertRaisesRegex(build.BuildError, "duplicate"):
            build.discover(self.root, [])
        meta_path = subject / "meta.json"
        meta = json.loads(meta_path.read_text())
        meta["chapters"][1]["order"] = 2
        meta_path.write_text(json.dumps(meta))
        (subject / "01-second.tex").unlink()
        with self.assertRaisesRegex(build.BuildError, "does not exist"):
            build.discover(self.root, [])
        (subject / "01-second.tex").write_text(r"\unsupportedcommand{Content}")
        with self.assertRaises(build.BuildError):
            self.run_build()
        self.assertFalse((self.root / "Output").exists())

    def test_stale_generated_files_removed_unrelated_files_preserved(self):
        subject = self.subject(chapters=[{"file": "00-first.tex", "title": "One", "order": 1},
                                         {"file": "01-second.tex", "title": "Two", "order": 2}])
        self.run_build()
        marker = self.root / "Output/keep.txt"
        marker.write_text("User-owned")
        meta_path = subject / "meta.json"
        meta = json.loads(meta_path.read_text())
        meta["chapters"].pop()
        meta_path.write_text(json.dumps(meta))
        self.run_build()
        self.assertFalse((self.root / "Output/Math/M01-Test/01-second.html").exists())
        self.assertEqual(marker.read_text(), "User-owned")

    def test_existing_unmanaged_output_is_not_overwritten(self):
        self.subject()
        output = self.root / "Output"
        output.mkdir()
        (output / "index.html").write_text("User page")
        with self.assertRaisesRegex(build.BuildError, "not owned"):
            self.run_build()
        self.assertEqual((output / "index.html").read_text(), "User page")

    @unittest.skipUnless(os.name == "nt", "Windows ACL regression")
    def test_published_files_inherit_output_directory_permissions(self):
        self.subject()
        self.run_build()
        # Cover both the first publication and replacing existing files.
        self.run_build()
        paths = [self.root / "Output/index.html", self.root / "Output" / build.MANIFEST]
        for path in paths:
            with self.subTest(path=path.name):
                script = "$acl = Get-Acl -LiteralPath $env:LEONBLOG_ACL_TEST; $acl.AreAccessRulesProtected"
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", script],
                    env=dict(os.environ, LEONBLOG_ACL_TEST=str(path)),
                    capture_output=True, text=True, check=True,
                )
                self.assertEqual(result.stdout.strip(), "False")
        self.assertEqual(list((self.root / "Output").rglob(".build-*.tmp")), [])

    def test_missing_asset_or_template_token_leaves_output_unchanged(self):
        subject = self.subject()
        self.run_build()
        before = self.hashes()
        (subject / "00-first.tex").write_text(r"\includegraphics{figure/missing.png}")
        with self.assertRaisesRegex(build.BuildError, "missing referenced resource"):
            self.run_build()
        self.assertEqual(before, self.hashes())
        with self.assertRaisesRegex(build.BuildError, "unknown placeholder"):
            build.render("{{ typo }}", {})

    def test_check_does_not_publish_and_validates_anchors(self):
        self.subject()
        self.run_build(check=True)
        self.assertFalse((self.root / "Output").exists())
        self.run_build()
        path = self.root / "Output/index.html"
        path.write_text(path.read_text(encoding="utf-8") + '<a href="#missing">broken</a>', encoding="utf-8")
        with self.assertRaisesRegex(build.BuildError, "missing anchor"):
            build.validate_output(self.root / "Output")


if __name__ == "__main__":
    unittest.main()
