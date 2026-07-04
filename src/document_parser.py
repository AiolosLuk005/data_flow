import docx
import fitz  # PyMuPDF
import pandas as pd
import os
import re

try:
    from pptx import Presentation
    PPTX_AVAILABLE = True
except ImportError:
    PPTX_AVAILABLE = False


def parse_docx(file_path):
    """Extract text from a .docx file."""
    doc = docx.Document(file_path)
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)

    # Also attempt to extract table content
    table_texts = []
    for table in doc.tables:
        for row in table.rows:
            row_data = [cell.text.strip() for cell in row.cells]
            table_texts.append(" | ".join(row_data))

    return "\n".join(full_text) + "\n\nTABLE DATA:\n" + "\n".join(table_texts)


def parse_pdf(file_path):
    """Extract text from a .pdf file."""
    doc = fitz.open(file_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text


def parse_txt(file_path):
    """Extract text from a .txt file."""
    encodings = ['utf-8', 'gbk', 'gb2312', 'utf-16', 'latin-1']
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError(f"Cannot decode text file with supported encodings: {file_path}")


def parse_xlsx(file_path):
    """Extract text from a .xlsx file by reading all sheets into text."""
    all_text = []
    xls = pd.ExcelFile(file_path, engine='openpyxl')
    for sheet_name in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
        all_text.append(f"--- Sheet: {sheet_name} ---")
        for _, row in df.iterrows():
            row_str = " | ".join([str(v) if pd.notna(v) else "" for v in row])
            all_text.append(row_str)
    return "\n".join(all_text)


def parse_md(file_path):
    """Extract text from a .md (Markdown) file."""
    encodings = ['utf-8', 'gbk', 'gb2312', 'utf-16', 'latin-1']
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError(f"Cannot decode markdown file with supported encodings: {file_path}")


def parse_csv(file_path):
    """Extract text from a .csv file in a structured format."""
    try:
        # Try reading with pandas for better format handling
        df = pd.read_csv(file_path, encoding='utf-8')
    except UnicodeDecodeError:
        # Fallback to GBK encoding for Chinese files
        df = pd.read_csv(file_path, encoding='gbk')
    
    # Convert to text format that LLM can understand
    all_text = []
    all_text.append("CSV Data:")
    all_text.append(" | ".join(df.columns.astype(str)))  # Header row
    all_text.append("-" * 50)
    
    for _, row in df.iterrows():
        row_str = " | ".join([str(v) if pd.notna(v) else "" for v in row])
        all_text.append(row_str)
    
    return "\n".join(all_text)


def parse_pptx(file_path):
    """Extract text from a .pptx (PowerPoint) file."""
    if not PPTX_AVAILABLE:
        raise ImportError(
            "PowerPoint 支持需要安装 python-pptx 库。\n"
            "请运行: pip install python-pptx"
        )
    
    prs = Presentation(file_path)
    all_text = []
    
    for slide_num, slide in enumerate(prs.slides, 1):
        all_text.append(f"\n--- Slide {slide_num} ---")
        
        # Extract text from all shapes in the slide
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text:
                all_text.append(shape.text)
            
            # Extract table content if present
            if shape.has_table:
                table = shape.table
                for row in table.rows:
                    row_data = [cell.text.strip() for cell in row.cells]
                    all_text.append(" | ".join(row_data))
    
    return "\n".join(all_text)


def get_document_content(file_path):
    """Route to the appropriate parser based on file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.docx':
        return parse_docx(file_path)
    elif ext == '.pdf':
        return parse_pdf(file_path)
    elif ext == '.txt':
        return parse_txt(file_path)
    elif ext in ('.xlsx', '.xls'):
        return parse_xlsx(file_path)
    elif ext == '.md':
        return parse_md(file_path)
    elif ext == '.csv':
        return parse_csv(file_path)
    elif ext in ('.pptx', '.ppt'):
        return parse_pptx(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def chunk_text(text: str, chunk_size: int = 1500, overlap: int = 300) -> list[str]:
    """
    Split document text into overlapping chunks for focused extraction.
    
    Strategy: Split by paragraphs first, then merge paragraphs into chunks
    of approximately chunk_size characters, with overlap between chunks
    to preserve context across boundaries.
    
    Args:
        text: Full document text.
        chunk_size: Target size of each chunk in characters.
        overlap: Number of overlapping characters between consecutive chunks.
    
    Returns:
        A list of text chunks.
    """
    if not text or len(text) <= chunk_size:
        return [text] if text else []
    
    # Split by paragraph (double newline or single newline)
    paragraphs = re.split(r'\n\s*\n|\n', text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]
    
    chunks = []
    current_chunk = ""
    
    for para in paragraphs:
        # If adding this paragraph exceeds chunk_size, commit current chunk
        if current_chunk and len(current_chunk) + len(para) + 1 > chunk_size:
            chunks.append(current_chunk)
            # Start new chunk with overlap from the end of the previous one
            if overlap > 0 and len(current_chunk) > overlap:
                current_chunk = current_chunk[-overlap:] + "\n" + para
            else:
                current_chunk = para
        else:
            current_chunk = (current_chunk + "\n" + para) if current_chunk else para
    
    # Don't forget the last chunk
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks


def search_relevant_chunks(chunks: list[str], headers: list[str], 
                           header_descriptions: dict = None,
                           top_k: int = 5) -> list[str]:
    """
    Find the most relevant chunks for the given headers using keyword scoring.
    
    Each chunk is scored by how many header-related keywords it contains.
    Returns the top_k most relevant chunks, concatenated with context markers.
    
    Args:
        chunks: List of text chunks from chunk_text().
        headers: List of header names to search for.
        header_descriptions: Optional descriptions to augment keyword search.
        top_k: Maximum number of chunks to return.
    
    Returns:
        List of the most relevant text chunks.
    """
    import re as _re
    
    # Build keyword set from headers and descriptions
    keywords = set()
    for h in headers:
        # Split header into individual Chinese words / terms
        # For Chinese: each 2-3 char segment is a keyword
        words = _re.findall(r'[\u4e00-\u9fff]{2,4}|[a-zA-Z]+|\d+', h)
        keywords.update(words)
    
    if header_descriptions:
        for desc in header_descriptions.values():
            if desc:
                words = _re.findall(r'[\u4e00-\u9fff]{2,4}|[a-zA-Z]+', desc)
                keywords.update(words)
    
    # Score each chunk
    scored_chunks = []
    for i, chunk in enumerate(chunks):
        score = 0
        for kw in keywords:
            score += chunk.count(kw)
        scored_chunks.append((score, i, chunk))
    
    if not chunks:
        return []
    
    first_chunk = chunks[0]
    
    # Sort the other chunks by score descending, taking top_k - 1 relevant ones
    other_scored_chunks = scored_chunks[1:]
    other_scored_chunks.sort(key=lambda x: x[0], reverse=True)
    top_others = other_scored_chunks[:(top_k - 1)]
    
    # Re-sort by original order to preserve document flow
    top_others.sort(key=lambda x: x[1])
    
    # Construct final list: start with the first chunk, then add other relevant chunks with score > 0
    result = [first_chunk]
    for _, _, chunk in top_others:
        if _ > 0:
            result.append(chunk)
            
    return result



if __name__ == "__main__":
    pass
