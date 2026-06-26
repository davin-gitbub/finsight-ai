"""FinSight AI — 离线文档入库脚本

用法：
    python ingest.py path/to/doc.pdf          # 单个文件
    python ingest.py path/to/directory/        # 批量目录
    python ingest.py path/to/doc.pdf --recreate   # 重建集合
"""

import os
import sys
import re
import argparse

import fitz

from config import settings
from rag import get_embedding, get_chroma_client, get_chroma_collection


def extract_text_from_pdf(filepath: str) -> list[dict]:
    """使用 PyMuPDF 解析 PDF，返回段落列表。"""
    doc = fitz.open(filepath)
    paragraphs = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("blocks")
        # Combine blocks on the same page into natural paragraphs
        combined = ""
        for block in blocks:
            text = block[4].strip()
            if not text:
                continue
            # If block is very short, it's likely a title/heading
            if len(text) < 20 and combined:
                paragraphs.append(
                    {"page": page_num + 1, "text": combined, "section": _detect_section(combined)}
                )
                combined = text
            elif combined and not combined.endswith(("\n", "。")):
                combined += text
            else:
                if combined:
                    paragraphs.append(
                        {"page": page_num + 1, "text": combined, "section": _detect_section(combined)}
                    )
                combined = text
        if combined:
            paragraphs.append(
                {"page": page_num + 1, "text": combined, "section": _detect_section(combined)}
            )

    doc.close()
    return paragraphs


def _detect_section(text: str) -> str:
    """简单检测章节标题"""
    lines = text.strip().split("\n")
    for line in lines[:3]:
        line = line.strip()
        if re.match(r"^第[一二三四五六七八九十百千]+[章节条]", line):
            return line[:30]
        if re.match(r"^[0-9]+(\.[0-9]+)*\s+", line):
            return line[:30]
        if re.match(r"^[一二三四五六七八九十]、", line):
            return line[:30]
    return ""


def chunk_document(paragraphs: list[dict], source: str) -> list[dict]:
    """递归切块：短段落合并，长段落拆分。"""
    chunks = []
    buffer = ""
    buffer_pages = set()
    chunk_index = 0

    for para in paragraphs:
        if len(para["text"]) > settings.chunk_max_chars:
            if buffer:
                chunks.append(
                    {
                        "text": buffer.strip(),
                        "source": source,
                        "page": min(buffer_pages),
                        "section": "",
                        "chunk_index": chunk_index,
                    }
                )
                chunk_index += 1
                buffer = ""
                buffer_pages = set()
            chunks.extend(_split_long_paragraph(para, source, chunk_index))
            chunk_index = len(chunks)
            continue

        if buffer and len(buffer) + len(para["text"]) > settings.chunk_max_chars:
            chunks.append(
                {
                    "text": buffer.strip(),
                    "source": source,
                    "page": min(buffer_pages),
                    "section": "",
                    "chunk_index": chunk_index,
                }
            )
            chunk_index += 1
            buffer = ""
            buffer_pages = set()

        buffer += para["text"] + "\n"
        buffer_pages.add(para["page"])

    if buffer:
        chunks.append(
            {
                "text": buffer.strip(),
                "source": source,
                "page": min(buffer_pages),
                "section": "",
                "chunk_index": chunk_index,
            }
        )

    return chunks


def _split_long_paragraph(para: dict, source: str, start_index: int) -> list[dict]:
    """按句子拆分超长段落"""
    sentences = re.split(r"(?<=[。！？\n])", para["text"])
    chunks = []
    buffer = ""
    idx = start_index

    for sent in sentences:
        if not sent.strip():
            continue
        if buffer and len(buffer) + len(sent) > settings.chunk_max_chars:
            chunks.append(
                {
                    "text": buffer.strip(),
                    "source": source,
                    "page": para["page"],
                    "section": para.get("section", ""),
                    "chunk_index": idx,
                }
            )
            idx += 1
            buffer = sent
        else:
            buffer += sent

    if buffer:
        chunks.append(
            {
                "text": buffer.strip(),
                "source": source,
                "page": para["page"],
                "section": para.get("section", ""),
                "chunk_index": idx,
            }
        )

    return chunks


def process_file(filepath: str, collection) -> int:
    """处理单个 PDF 文件，返回入库块数"""
    filename = os.path.basename(filepath)
    print(f"  Processing: {filename}")

    paragraphs = extract_text_from_pdf(filepath)
    print(f"  Extracted {len(paragraphs)} paragraphs")

    chunks = chunk_document(paragraphs, filename)
    print(f"  Generated {len(chunks)} chunks")

    ids = []
    embeddings = []
    documents = []
    metadatas = []

    for chunk in chunks:
        chunk_id = f"{filename}_{chunk['page']}_{chunk['chunk_index']}"
        ids.append(chunk_id)
        documents.append(chunk["text"])
        metadatas.append(
            {
                "source": chunk["source"],
                "page": chunk["page"],
                "chunk_index": chunk["chunk_index"],
                "total_chunks": len(chunks),
                "section": chunk.get("section", ""),
                "char_count": len(chunk["text"]),
            }
        )

    print(f"  Computing embeddings ({len(chunks)} chunks)...")
    for i, text in enumerate(documents):
        emb = get_embedding(text)
        embeddings.append(emb)
        if (i + 1) % 10 == 0:
            print(f"    {i + 1}/{len(chunks)}")

    collection.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
    print(f"  Done: {len(chunks)} chunks indexed")
    return len(chunks)


def main():
    parser = argparse.ArgumentParser(description="FinSight AI 文档入库工具")
    parser.add_argument("path", help="PDF 文件路径或目录路径")
    parser.add_argument("--recreate", action="store_true", help="重建 Chroma 集合")
    args = parser.parse_args()

    collection = get_chroma_collection()

    if args.recreate:
        print("Recreating collection...")
        client = get_chroma_client()
        client.delete_collection(settings.chroma_collection)
        collection = get_chroma_collection()

    if os.path.isfile(args.path):
        files = [args.path]
    elif os.path.isdir(args.path):
        files = [
            os.path.join(args.path, f)
            for f in os.listdir(args.path)
            if f.lower().endswith(".pdf")
        ]
    else:
        print(f"Error: {args.path} not found")
        sys.exit(1)

    total = 0
    for fp in files:
        try:
            total += process_file(fp, collection)
        except Exception as e:
            print(f"  Error processing {fp}: {e}")

    print(f"\nTotal: {total} chunks indexed from {len(files)} files")


if __name__ == "__main__":
    main()
