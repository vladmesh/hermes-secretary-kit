import importlib.util
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "brain-template/reindex.py"
spec = importlib.util.spec_from_file_location("reindex", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

HEADER = "# INDEX\n\nOne line per note. Section details: `<section>/_index.md`.\n"


class ReindexUnit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.addCleanup(setattr, m, "ROOT", m.ROOT)
        m.ROOT = self.root

    def run_reindex(self, *args):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = m.main(["--root", str(self.root), *args])
        return code, stdout.getvalue()

    def test_read_meta_frontmatter(self):
        note = self.root / "sample.md"
        note.write_text(
            "---\n name : 'Fictional café'\ndescription: \"Plan: meet at noon\"\n"
            "tags: [demo, lunch]\nupdated: 2026-02-03\ntype: fact\nignored line\n---\n# Not the description\n",
            encoding="utf-8")
        self.assertEqual(m.read_meta(note), {
            "name": "Fictional café", "description": "Plan: meet at noon", "tags": "[demo, lunch]",
            "updated": "2026-02-03", "type": "fact",
        })

    def test_read_meta_without_frontmatter_truncates_first_nonblank_line(self):
        note = self.root / "long-note.md"
        title = "A fictional heading " + "x" * 140
        note.write_text("\n  \n## " + title + "\nIgnored second line\n", encoding="utf-8")
        self.assertEqual(m.read_meta(note), {"name": "long-note", "description": title[:120]})

    def test_read_meta_partial_frontmatter_uses_missing_field_fallbacks(self):
        note = self.root / "partial.md"
        cases = [
            ("name: Named", "\n# Body title\n", {"name": "Named", "description": "Body title"}),
            ("description: Summary", "# Body title\n", {"name": "partial", "description": "Summary"}),
            ("type: fact", "# Body title\n", {"type": "fact", "name": "partial", "description": "Body title"}),
            ("", "\n \n", {"name": "partial", "description": ""}),
        ]
        for fields, body, expected in cases:
            with self.subTest(fields=fields):
                note.write_text("---\n" + fields + "\n---\n" + body, encoding="utf-8")
                self.assertEqual(m.read_meta(note), expected)

    def test_read_meta_unterminated_frontmatter_is_body(self):
        note = self.root / "unfinished.md"
        for text in ["---\nname: Not metadata\n", "---\nname: Not metadata\n---"]:
            with self.subTest(text=text):
                note.write_text(text, encoding="utf-8")
                self.assertEqual(m.read_meta(note), {"name": "unfinished", "description": "---"})

    def test_read_meta_empty_fields_are_not_missing_fields(self):
        note = self.root / "empty.md"
        note.write_text("---\nname: ''\ndescription: \"\"\n---\n# Body title\n", encoding="utf-8")
        self.assertEqual(m.read_meta(note), {"name": "", "description": ""})

    def test_read_meta_non_utf8_bytes_are_replaced(self):
        note = self.root / "bytes.md"
        cases = [
            (b"---\nname: Caf\xff\ndescription: bad \xfe byte\n---\nBody\n",
             {"name": "Caf\ufffd", "description": "bad \ufffd byte"}),
            (b"\n# Body \xff title\n", {"name": "bytes", "description": "Body \ufffd title"}),
        ]
        for content, expected in cases:
            with self.subTest(content=content):
                note.write_bytes(content)
                self.assertEqual(m.read_meta(note), expected)

    def test_sections_are_sorted_rendered_and_idempotent(self):
        sections = [
            ("facts", "tags: [demo, sample]\nupdated: 2026-02-03\n", " `[demo, sample]` (2026-02-03)"),
            ("people", "tags: [demo]\n", " `[demo]`"),
            ("projects", "updated: 2026-02-04\n", " (2026-02-04)"),
            ("journal", "tags: ''\nupdated: ''\n", ""),
        ]
        expected = {}
        for section, fields, suffix in sections:
            folder = self.root / section
            folder.mkdir()
            (folder / "z-last.md").write_text(
                "---\nname: Alpha\ndescription: Last by filename\n---\nBody\n", encoding="utf-8")
            (folder / "a-first.md").write_text(
                "---\nname: Zulu\ndescription: Café summary\n" + fields + "---\nBody\n", encoding="utf-8")
            expected[folder / "_index.md"] = (
                f"# {section}\n\n- [Zulu](a-first.md) - Café summary{suffix}\n"
                "- [Alpha](z-last.md) - Last by filename\n")
        expected[self.root / "INDEX.md"] = (
            HEADER + "\n- facts/a-first.md - Café summary\n- facts/z-last.md - Last by filename\n"
            "\n- people/a-first.md - Café summary\n- people/z-last.md - Last by filename\n"
            "\n- projects/a-first.md - Café summary\n- projects/z-last.md - Last by filename\n"
            "\n- journal/a-first.md - Café summary\n- journal/z-last.md - Last by filename\n")
        before = {p: p.read_bytes() for p in self.root.rglob("*.md")}
        self.assertEqual(m.build(), expected)
        self.assertEqual({p: p.read_bytes() for p in self.root.rglob("*.md")}, before)
        self.assertEqual(self.run_reindex(), (0, "indexed 8 notes in 4 sections\n"))
        for path, content in expected.items():
            self.assertEqual(path.read_bytes(), content.encode("utf-8"))
        first = {p: p.read_bytes() for p in self.root.rglob("*.md")}
        self.assertEqual(self.run_reindex(), (0, "indexed 8 notes in 4 sections\n"))
        self.assertEqual({p: p.read_bytes() for p in self.root.rglob("*.md")}, first)
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content)

    def test_missing_sections_are_not_created(self):
        self.assertEqual(m.build(), {self.root / "INDEX.md": HEADER})
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertEqual(self.run_reindex("--check"), (1, "stale: INDEX.md\n"))
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertEqual(self.run_reindex(), (0, "indexed 0 notes in 0 sections\n"))
        self.assertEqual((self.root / "INDEX.md").read_bytes(), HEADER.encode("utf-8"))
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["INDEX.md"])

    def test_empty_sections_get_empty_indexes(self):
        (self.root / "facts").mkdir()
        (self.root / "projects").mkdir()
        (self.root / "people").write_text("Not a directory\n", encoding="utf-8")
        expected = {
            self.root / "facts/_index.md": "# facts\n\n",
            self.root / "projects/_index.md": "# projects\n\n",
            self.root / "INDEX.md": HEADER,
        }
        self.assertEqual(m.build(), expected)
        self.assertEqual(self.run_reindex(), (0, "indexed 0 notes in 2 sections\n"))
        for path, content in expected.items():
            self.assertEqual(path.read_text(encoding="utf-8"), content)
        self.assertEqual((self.root / "people").read_text(encoding="utf-8"), "Not a directory\n")
        self.assertFalse((self.root / "journal").exists())
        self.assertEqual(self.run_reindex("--check"), (0, ""))

    def test_generated_indexes_and_non_notes_are_not_indexed(self):
        folder = self.root / "facts"
        folder.mkdir()
        sentinel = "---\nname: Not a note\ndescription: Must not appear\n---\n"
        (self.root / "INDEX.md").write_text(sentinel, encoding="utf-8")
        (folder / "_index.md").write_text(sentinel, encoding="utf-8")
        (self.root / "README.md").write_text(sentinel, encoding="utf-8")
        (folder / "ignored.txt").write_text(sentinel, encoding="utf-8")
        (folder / "nested").mkdir()
        (folder / "nested/hidden.md").write_text(sentinel, encoding="utf-8")
        (folder / "note.md").write_text(
            "---\nname: Sample\ndescription: A fictional note\n---\n", encoding="utf-8")
        self.assertEqual(m.build(), {
            folder / "_index.md": "# facts\n\n- [Sample](note.md) - A fictional note\n",
            self.root / "INDEX.md": HEADER + "\n- facts/note.md - A fictional note\n",
        })

    def test_check_reports_stale_indexes_without_writing(self):
        folder = self.root / "facts"
        folder.mkdir()
        (folder / "note.md").write_text(
            "---\nname: Sample\ndescription: Current description\n---\n", encoding="utf-8")
        (folder / "_index.md").write_bytes(b"old section\n")
        (self.root / "INDEX.md").write_bytes(b"old top\n")
        before = {p: p.read_bytes() for p in self.root.rglob("*.md")}
        self.assertEqual(self.run_reindex("--check"), (1, "stale: facts/_index.md\nstale: INDEX.md\n"))
        self.assertEqual({p: p.read_bytes() for p in self.root.rglob("*.md")}, before)
        self.assertEqual(self.run_reindex(), (0, "indexed 1 notes in 1 sections\n"))
        self.assertEqual((folder / "_index.md").read_bytes(),
                         b"# facts\n\n- [Sample](note.md) - Current description\n")
        self.assertEqual((self.root / "INDEX.md").read_bytes(),
                         (HEADER + "\n- facts/note.md - Current description\n").encode("utf-8"))
        rewritten = {p: p.read_bytes() for p in self.root.rglob("*.md")}
        self.assertEqual(self.run_reindex("--check"), (0, ""))
        self.assertEqual({p: p.read_bytes() for p in self.root.rglob("*.md")}, rewritten)


if __name__ == "__main__":
    unittest.main()
