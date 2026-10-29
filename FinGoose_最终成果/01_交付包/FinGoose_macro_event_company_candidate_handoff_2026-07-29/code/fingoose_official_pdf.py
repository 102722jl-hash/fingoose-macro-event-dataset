from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import pdfplumber
from pypdf import PdfReader


def normalize_text(value: str) -> str:
    return re.sub(r'\s+', ' ', value).strip()


def extract_pdf_pages(path: Path, *, source_id: str) -> list[dict[str, Any]]:
    '''Extract deterministic page-level evidence rows from an official PDF snapshot.'''
    if not source_id:
        raise ValueError('INVALID_SOURCE_ID')
    reader = PdfReader(str(path), strict=False)
    rows = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = normalize_text(page.extract_text() or '')
        rows.append(
            {
                'source_id': source_id,
                'page_number': page_number,
                'text': text,
                'text_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
                'source_locator': f'{path.as_posix()}:page={page_number}',
                'extraction_status': 'success' if text else 'empty',
                'extraction_engine': 'pypdf',
            }
        )
    return rows


def extract_pdf_pages_pdfplumber(
    path: Path,
    *,
    source_id: str,
) -> list[dict[str, Any]]:
    '''Extract page text with pdfplumber when embedded fonts defeat pypdf.'''
    if not source_id:
        raise ValueError('INVALID_SOURCE_ID')
    rows = []
    with pdfplumber.open(path) as document:
        for page_number, page in enumerate(document.pages, start=1):
            text = normalize_text(page.extract_text() or '')
            rows.append(
                {
                    'source_id': source_id,
                    'page_number': page_number,
                    'text': text,
                    'text_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
                    'source_locator': f'{path.as_posix()}:page={page_number}',
                    'extraction_status': 'success' if text else 'empty',
                    'extraction_engine': 'pdfplumber',
                }
            )
    return rows
