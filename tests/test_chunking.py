import io
import unittest

from docx import Document

from app.chunking import (
    recursive_split_text,
    chunk_txt,
    chunk_csv,
    chunk_docx,
)


class ChunkingTests(unittest.TestCase):
    def test_recursive_chunks_respect_size(self):
        text = ("Paragraph one has several words. " * 80) + "\n\n" + ("Paragraph two. " * 80)
        chunks = recursive_split_text(text, chunk_size=180, overlap=30)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 180 for chunk in chunks))

    def test_txt_metadata_is_attached(self):
        result = chunk_txt(("hello world. " * 100).encode(), "notes.txt", 100, 10)
        self.assertTrue(result)
        self.assertEqual(result[0]["metadata"]["file_type"], "txt")
        self.assertIn("chunk_part", result[0]["metadata"])

    def test_csv_repeats_header_for_every_row_group(self):
        csv_bytes = ("name,team\n" + "".join(f"user{i},team{i}\n" for i in range(5))).encode()
        chunks = chunk_csv(csv_bytes, "people.csv", rows_per_chunk=2)
        self.assertEqual(len(chunks), 3)
        self.assertTrue(all(chunk["content"].splitlines()[0] == "name,team" for chunk in chunks))
        self.assertEqual(chunks[1]["metadata"]["row_start"], 3)

    def test_docx_preserves_heading_path(self):
        document = Document()
        document.add_heading("Chapter 1", level=1)
        document.add_heading("Introduction", level=2)
        document.add_paragraph("This is the introduction.")
        buffer = io.BytesIO()
        document.save(buffer)
        chunks = chunk_docx(buffer.getvalue(), "guide.docx")
        self.assertEqual(chunks[0]["metadata"]["heading"], "Introduction")
        self.assertEqual(chunks[0]["metadata"]["heading_path"], ["Chapter 1", "Introduction"])


if __name__ == "__main__":
    unittest.main()
