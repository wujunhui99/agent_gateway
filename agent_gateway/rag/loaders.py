from __future__ import annotations

import csv
import json
import os
from typing import List

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document


def load_documents(file_path: str, filename: str) -> List[Document]:
    ext = os.path.splitext(filename)[1].lower()
    if ext in {".txt", ".md"}:
        loader = TextLoader(file_path, autodetect_encoding=True)
        return loader.load()
    if ext == ".pdf":
        loader = PyPDFLoader(file_path)
        return loader.load()
    if ext == ".json":
        with open(file_path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        return [
            Document(
                page_content=json.dumps(data, ensure_ascii=False, indent=2),
                metadata={"source": filename, "type": "json"},
            )
        ]
    if ext == ".csv":
        with open(file_path, newline="", encoding="utf-8") as fp:
            reader = csv.reader(fp)
            rows = list(reader)
        header = rows[0] if rows else []
        lines = ["\t".join(header)]
        for row in rows[1:]:
            lines.append("\t".join(row))
        content = "\n".join(lines)
        return [
            Document(
                page_content=content,
                metadata={"source": filename, "type": "csv"},
            )
        ]

    # fallback: treat as raw text
    with open(file_path, "r", encoding="utf-8", errors="ignore") as fp:
        content = fp.read()
    return [
        Document(
            page_content=content,
            metadata={"source": filename, "type": ext or "unknown"},
        )
    ]


__all__ = ["load_documents"]
