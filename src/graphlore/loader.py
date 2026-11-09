"""Load text, Markdown and (with the optional ``pdf`` extra) PDF documents."""

from __future__ import annotations

from pathlib import Path

from graphlore.models import Document

TEXT_SUFFIXES = {".txt", ".md"}


def _read(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("install the 'pdf' extra to read PDF files") from exc
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    return path.read_text(encoding="utf-8")


def load_documents(path: Path | str) -> list[Document]:
    """Load one file, or every supported file below a directory in sorted order.

    Document ids are paths relative to the input, without the suffix, so they are stable
    across machines.
    """
    root = Path(path)
    if not root.exists():
        raise FileNotFoundError(f"{root} does not exist")
    if root.is_file():
        files, base = [root], root.parent
    else:
        supported = TEXT_SUFFIXES | {".pdf"}
        files = sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in supported)
        base = root
    if not files:
        raise ValueError(f"no .txt, .md or .pdf documents found under {root}")
    documents: list[Document] = []
    seen: set[str] = set()
    for file in files:
        text = _read(file).strip()
        if not text:
            continue
        doc_id = file.relative_to(base).with_suffix("").as_posix()
        if doc_id in seen:
            raise ValueError(f"two documents would share the id {doc_id!r}; rename one of them")
        seen.add(doc_id)
        documents.append(Document(doc_id, text))
    if not documents:
        raise ValueError(f"all documents under {root} are empty")
    return documents
