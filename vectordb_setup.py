import os 
import uuid
import time
import pdfplumber
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Distance, VectorParams
from langchain.text_splitter import RecursiveCharacterTextSplitter
from openai import OpenAI

# Load environment variables
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize Qdrant client
qdrant = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY"),
    timeout=60
)

# Generate OpenAI embeddings
def get_openai_embedding(text):
    response = client.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    return [item.embedding for item in response.data]

# Extract text from PDFs and split into chunks
def extract_text_from_pdf(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text.strip() + "\n"

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        length_function=len,
        is_separator_regex=False,
    )
    return text_splitter.split_text(text)

# Store text and embeddings in Qdrant
def load_pdfs_to_qdrant(pdf_directory, collection_name, batch_size=20, max_retries=3):
    # Create collection if not exists
    if not qdrant.collection_exists(collection_name):
        qdrant.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE)  # OpenAI embeddings size is 1536
        )
    
    pdf_files = [f for f in os.listdir(pdf_directory) if f.endswith('.pdf')]
    total_chunks_processed = 0
    
    for pdf_filename in pdf_files:
        pdf_path = os.path.join(pdf_directory, pdf_filename)
        text_chunks = extract_text_from_pdf(pdf_path)

        if text_chunks:
            try:
                embeddings = get_openai_embedding(text_chunks)
                points = []
                
                for chunk, embedding in zip(text_chunks, embeddings):
                    points.append(PointStruct(
                        id=str(uuid.uuid4()),
                        vector=embedding,
                        payload={"text": chunk, "source_file": pdf_filename, "document_path": pdf_path}
                    ))
                    
                    if len(points) >= batch_size:
                        for attempt in range(max_retries):
                            try:
                                qdrant.upsert(collection_name=collection_name, points=points)
                                total_chunks_processed += len(points)
                                print(f"Processed {len(points)} chunks from {pdf_filename}")
                                points = []
                                break
                            except Exception as e:
                                print(f"Attempt {attempt + 1} failed: {e}")
                                time.sleep(2 ** attempt)
                
                if points:
                    qdrant.upsert(collection_name=collection_name, points=points)
                    total_chunks_processed += len(points)

            except Exception as e:
                print(f"Error processing {pdf_filename}: {e}")
    
    print(f"Total chunks processed: {total_chunks_processed}")
    print(f"Total documents processed: {len(pdf_files)}")

# Run the script
if __name__ == "__main__":
    collection_name = "legal_documents_collection"
    pdf_directory = "./data"
    load_pdfs_to_qdrant(pdf_directory, collection_name)
