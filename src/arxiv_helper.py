import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
import sys

# ── Add parent dir to path so imports work ───────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from ingestion import ingest_single_pdf, PAPERS_DIR
from vectorstore import get_vectorstore

def clean_filename(title: str) -> str:
    """Clean a string to be a safe filename."""
    title = re.sub(r'[^\w\s-]', '', title)
    title = re.sub(r'[-\s]+', '_', title).strip('_')
    return title[:60]

def extract_search_term(query: str) -> str:
    """Strip question fluff so arXiv keyword search works better."""
    q = query.strip()
    for phrase in (
        "what is", "what are", "how does", "how do", "explain", "tell me about",
        "describe", "summarize", "summary of", "paper on", "research on",
    ):
        q = re.sub(re.escape(phrase), "", q, flags=re.IGNORECASE)
    q = re.sub(r"[^\w\s\-]", " ", q)
    q = re.sub(r"\s+", " ", q).strip()
    return (q[:120] or query[:120]).strip()


def should_auto_fetch_arxiv(query: str, documents: list, vs) -> bool:
    """Decide if we should auto-download a paper from arXiv."""
    original = query.strip()
    if not original:
        return False

    if re.search(r"\b\d{4}\.\d{4,5}(?:v\d+)?\b", original):
        return True

    fetch_keywords = (
        "download paper", "fetch paper", "get paper", "find paper",
        "arxiv", "not in database", "don't have", "do not have",
    )
    if any(kw in original.lower() for kw in fetch_keywords):
        return True

    if vs.count() == 0:
        return True

    if not documents:
        return True

    max_score = max((d.get("score", 0.0) for d in documents), default=0.0)
    if max_score < 0.38:
        return True

    # Topic mentioned but no indexed paper filename looks related
    papers = vs.list_papers()
    if papers:
        q_tokens = {t for t in re.findall(r"[a-z]{4,}", original.lower())}
        paper_blob = " ".join(p.lower().replace(".pdf", "").replace("_", " ") for p in papers)
        overlap = sum(1 for t in q_tokens if t in paper_blob)
        if len(q_tokens) >= 2 and overlap == 0:
            return True

    return False


def download_and_ingest_arxiv(search_term: str) -> str:
    """
    Search arXiv by ID or keywords, download the top matching PDF,
    ingest its content into ChromaDB, and return a summary string.
    """
    search_term = search_term.strip()
    
    # 1. Determine if search term is an arXiv ID
    is_id = re.match(r'^\d{4}\.\d{4,5}(?:v\d+)?$', search_term)
    
    if is_id:
        url = f"http://export.arxiv.org/api/query?id_list={search_term}"
    else:
        encoded_term = urllib.parse.quote(search_term)
        url = f"http://export.arxiv.org/api/query?search_query=all:{encoded_term}&max_results=1"
        
    print(f"[arxiv_helper] Querying arXiv API: {url}")
    
    try:
        # Fetch search results
        response = urllib.request.urlopen(url)
        xml_data = response.read()
    except Exception as e:
        raise RuntimeError(f"Failed to query arXiv API: {e}")
        
    # 2. Parse XML
    try:
        root = ET.fromstring(xml_data)
    except Exception as e:
        raise RuntimeError(f"Failed to parse arXiv XML response: {e}")
        
    # XML Namespace handling
    ns = {
        'atom': 'http://www.w3.org/2005/Atom',
        'opensearch': 'http://a9.com/-/spec/opensearch/1.1/',
        'arxiv': 'http://arxiv.org/schemas/atom'
    }
    
    entries = root.findall('atom:entry', ns)
    if not entries:
        return f"No papers found on arXiv matching '{search_term}'."
        
    entry = entries[0]
    
    # Check if it's a dummy entry (e.g. invalid ID)
    title_el = entry.find('atom:title', ns)
    if title_el is None or title_el.text.strip() == "Error" or "information not found" in (entry.find('atom:summary', ns).text or "").lower():
        return f"Paper '{search_term}' not found on arXiv."
        
    title = title_el.text.replace('\n', ' ').strip()
    
    # Extract PDF link
    pdf_url = None
    for link in entry.findall('atom:link', ns):
        if link.attrib.get('title') == 'pdf':
            pdf_url = link.attrib.get('href')
            break
        elif link.attrib.get('type') == 'application/pdf':
            pdf_url = link.attrib.get('href')
            break
            
    if not pdf_url:
        # Fallback construction of PDF url from ID
        id_url = entry.find('atom:id', ns).text
        paper_id = id_url.split('/abs/')[-1].split('v')[0]
        pdf_url = f"https://arxiv.org/pdf/{paper_id}.pdf"
        
    # Make sure PDF url is https
    if pdf_url.startswith('http://'):
        pdf_url = 'https://' + pdf_url[7:]
        
    # 3. Download the PDF
    PAPERS_DIR.mkdir(parents=True, exist_ok=True)
    filename = clean_filename(title) + ".pdf"
    download_path = PAPERS_DIR / filename
    
    # Prevent downloading if it already exists in the folder
    if download_path.exists():
        print(f"[arxiv_helper] Paper '{title}' already exists locally as {filename}.")
    else:
        print(f"[arxiv_helper] Downloading PDF from: {pdf_url} -> {download_path}")
        try:
            # ArXiv sometimes blocks requests without a User-Agent header, so we use a Request object
            req = urllib.request.Request(
                pdf_url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req) as response_pdf:
                with open(download_path, 'wb') as f:
                    f.write(response_pdf.read())
        except Exception as e:
            raise RuntimeError(f"Failed to download PDF from {pdf_url}: {e}")
            
    # 4. Ingest PDF
    print(f"[arxiv_helper] Ingesting downloaded PDF: {filename}")
    try:
        vs = get_vectorstore()
        chunks, embeddings = ingest_single_pdf(download_path)
        if not chunks:
            return f"Downloaded paper '{title}' but failed to extract text."
            
        added = vs.add_documents(chunks, embeddings)
        return f"Successfully downloaded and ingested '{title}' ({added} chunks added)."
    except Exception as e:
        raise RuntimeError(f"Failed to ingest downloaded paper '{title}': {e}")

if __name__ == "__main__":
    # Test downloader
    import sys
    test_query = " ".join(sys.argv[1:]) or "1706.03762"
    print(download_and_ingest_arxiv(test_query))
