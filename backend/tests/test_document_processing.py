import io

from docx import Document

from app.services.document_processing import CHUNK_OVERLAP, CHUNK_SIZE, process_document


def test_text_files_are_chunked_and_preserve_content() -> None:
    text = "A study note about photosynthesis. " * 120

    processed = process_document("notes.txt", text.encode())

    assert processed.status == "ready"
    assert len(processed.chunks) > 1
    assert all(page is None for page, _ in processed.chunks)
    assert all(len(chunk) <= CHUNK_SIZE for _, chunk in processed.chunks)
    assert processed.chunks[0][1][-CHUNK_OVERLAP:] in processed.chunks[1][1]


def test_docx_paragraphs_are_extracted() -> None:
    output = io.BytesIO()
    document = Document()
    document.add_paragraph("Newton's laws describe motion and force.")
    document.save(output)

    processed = process_document("lesson.docx", output.getvalue())

    assert processed.status == "ready"
    assert "motion and force" in processed.chunks[0][1]


def test_audio_files_are_marked_unsupported_for_text_extraction() -> None:
    processed = process_document("lecture.mp3", b"ID3 audio bytes")

    assert processed.status == "unsupported"
    assert processed.chunks == ()
