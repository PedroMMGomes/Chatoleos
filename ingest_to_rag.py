import json
import os
import requests
import time
import chromadb

# Attempt to import scraper functions. If scraper.py is not available,
# it will rely solely on an existing products_data.json.
try:
    import scraper 
    SCRAPER_AVAILABLE = True
except ImportError:
    SCRAPER_AVAILABLE = False
    print("Warning: scraper.py not found. Will rely on existing 'products_data.json'.")
    # Define a placeholder crawl_site if scraper is not available to avoid NameError
    def crawl_site(base_url, max_pages, max_products, progress_file):
        print(f"Scraper module not available. Cannot crawl {base_url}.")
        print(f"Please ensure 'products_data.json' exists or make 'scraper.py' available.")
        return []

# --- Configuration ---
PRODUCTS_FILE = "products_data.json"
CHROMA_DB_PATH = "chroma_db_store"
CHROMA_COLLECTION_NAME = "oleos_daterra_products"
OLLAMA_API_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL_NAME = "mxbai-embed-large"
SCRAPER_BASE_URL = 'https://oleosdaterra.com/'
SCRAPER_MAX_PAGES = 50  # Max non-product pages for scraper
SCRAPER_MAX_PRODUCTS = 200 # Max products for scraper

# --- Helper Functions ---
def run_scraper_if_needed(filename=PRODUCTS_FILE):
    """
    Checks if the product data file exists. If not, and if the scraper
    is available, runs the scraper to generate it.
    """
    if os.path.exists(filename):
        print(f"Found existing product data: {filename}")
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data and len(data) >= SCRAPER_MAX_PRODUCTS:
                    print(f"Product data file contains {len(data)} products, meeting or exceeding the target of {SCRAPER_MAX_PRODUCTS}. Scraping will be skipped.")
                    return True
                else:
                    print(f"Product data file contains {len(data)} products, less than the target of {SCRAPER_MAX_PRODUCTS}.")
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error reading existing product data file: {e}. Will attempt to rescrape.")
            # Fall through to scrape if file is corrupted or empty

    if not SCRAPER_AVAILABLE:
        print(f"Scraper module is not available and '{filename}' not found or insufficient. Cannot proceed.")
        return False

    print(f"'{filename}' not found or insufficient. Starting scraper for {SCRAPER_BASE_URL}...")
    try:
        # Ensure scraper.all_products_data and scraper.visited_urls are reset if scraper is re-run
        # This assumes 'scraper' module has these global variables.
        if SCRAPER_AVAILABLE:
            scraper.all_products_data = []
            scraper.visited_urls = set()
            # Check if the scraper's progress file exists to load it.
            # Assumes scraper has a constant like PROGRESS_OUTPUT_FILE or uses PRODUCTS_FILE for its own progress.
            # For this example, let's assume the scraper handles its own progress file loading internally
            # or we use the main PRODUCTS_FILE as its target.
            # If scraper.py uses its own progress file constant (e.g., scraper.PROGRESS_OUTPUT_FILE), use that.
            # This part might need adjustment based on exact scraper.py implementation details for progress.
            scraper_progress_file = getattr(scraper, 'PROGRESS_OUTPUT_FILE', PRODUCTS_FILE)
            if os.path.exists(scraper_progress_file):
                 scraper.load_progress(scraper_progress_file)

        print(f"Attempting to scrape up to {SCRAPER_MAX_PRODUCTS} products.")
        # Call the scraper's main crawling function
        scraper.crawl_site(
            base_url=SCRAPER_BASE_URL,
            max_pages=SCRAPER_MAX_PAGES,
            max_products=SCRAPER_MAX_PRODUCTS,
            progress_file=getattr(scraper, 'PROGRESS_OUTPUT_FILE', PRODUCTS_FILE) # Use scraper's specific progress file if defined
        )
        print("Scraping complete.")
        if not os.path.exists(filename) or os.path.getsize(filename) == 0:
            print(f"Error: Scraper ran but '{filename}' was not created or is empty.")
            return False
        return True
    except AttributeError as e:
        print(f"Scraper module is missing an expected attribute (e.g., all_products_data, visited_urls, load_progress, crawl_site): {e}")
        return False
    except Exception as e:
        print(f"An error occurred while running the scraper: {e}")
        return False

def load_product_data(filename=PRODUCTS_FILE):
    """Loads product data from the specified JSON file."""
    print(f"Loading products from {filename}...")
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            products = json.load(f)
        print(f"Loaded {len(products)} products.")
        return products
    except FileNotFoundError:
        print(f"Error: Product data file '{filename}' not found.")
        return []
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from '{filename}'. File might be corrupted.")
        return []
    except Exception as e:
        print(f"An unexpected error occurred while loading product data: {e}")
        return []

def process_product_text(product):
    """
    Concatenates relevant text fields from a product object into a single string.
    """
    text_parts = []
    
    title = product.get("title", "")
    if title != "N/A":
        text_parts.append(f"Nome: {title}")

    description = product.get("description", "")
    if description != "N/A":
        text_parts.append(f"Descrição: {description}")

    category = product.get("category", "")
    if category != "N/A":
        text_parts.append(f"Categoria: {category}")

    sku = product.get("sku", "")
    if sku != "N/A":
        text_parts.append(f"SKU: {sku}")
    
    price = product.get("price", "")
    if price != "N/A":
        text_parts.append(f"Preço: {str(price)}") # Ensure price is string

    extra_info = product.get("extra_info", {})
    if extra_info:
        extra_info_parts = []
        for key, value in extra_info.items():
            if value and value != "N/A": # Ensure value is not empty or N/A
                 extra_info_parts.append(f"{key}: {value}")
        if extra_info_parts:
            text_parts.append("Informações Adicionais: " + "; ".join(extra_info_parts))
            
    # Fallback: if no other text, use the URL
    if not text_parts and "url" in product:
        text_parts.append(f"URL: {product['url']}")

    return "\n".join(part for part in text_parts if part)

def get_embedding(text: str, ollama_api_url: str = OLLAMA_API_URL, model_name: str = EMBEDDING_MODEL_NAME):
    """
    Generates an embedding for the given text using the Ollama API.
    Retries on failure.
    """
    if not text or not text.strip():
        print("Warning: Attempted to get embedding for empty text. Skipping.")
        return None

    max_retries = 3
    retry_delay = 5  # seconds
    for attempt in range(max_retries):
        try:
            response = requests.post(
                ollama_api_url,
                json={"model": model_name, "prompt": text},
                timeout=60  # Increased timeout for potentially long embeddings
            )
            response.raise_for_status()  # Raise an exception for bad status codes
            return response.json().get("embedding")
        except requests.exceptions.RequestException as e:
            print(f"Error calling Ollama API (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print("Max retries reached. Failed to get embedding.")
                return None
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON response from Ollama API: {e}. Response: {response.text[:200]}") # Log part of response
            return None # Don't retry on JSON decode error, likely server issue or bad response
    return None

# --- Main Ingestion Logic ---
def ingest_products_to_chromadb(products):
    """
    Generates embeddings for products and stores them in ChromaDB.
    """
    if not products:
        print("No products to ingest.")
        return

    print(f"Initializing ChromaDB client at {CHROMA_DB_PATH}...")
    try:
        client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    except Exception as e:
        print(f"Error initializing ChromaDB client: {e}")
        print("Please ensure ChromaDB is installed and configured correctly.")
        print("Try: pip install chromadb")
        return

    print(f"Getting or creating ChromaDB collection: {CHROMA_COLLECTION_NAME}...")
    try:
        # Check if collection exists to decide on clearing
        existing_collections = [col.name for col in client.list_collections()]
        if CHROMA_COLLECTION_NAME in existing_collections:
            print(f"Collection '{CHROMA_COLLECTION_NAME}' already exists. Clearing it for re-population.")
            client.delete_collection(name=CHROMA_COLLECTION_NAME)
        
        collection = client.create_collection(
            name=CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"} # Optional: specify distance function
        )
        print(f"Collection '{CHROMA_COLLECTION_NAME}' ready.")
    except Exception as e:
        print(f"Error creating/getting ChromaDB collection: {e}")
        # Attempt to get collection if creation failed (e.g., race condition or already exists issue not caught)
        try:
            collection = client.get_collection(name=CHROMA_COLLECTION_NAME)
            print(f"Successfully got existing collection '{CHROMA_COLLECTION_NAME}' after initial error.")
        except Exception as e_get:
            print(f"Critical error: Could not create or get collection '{CHROMA_COLLECTION_NAME}': {e_get}")
            return

    print("Generating embeddings and ingesting to ChromaDB...")
    processed_count = 0
    batch_size = 50 # Process in batches. Adjust if needed, smaller batches use less memory at once.
    product_batches = [products[i:i + batch_size] for i in range(0, len(products), batch_size)]

    for batch_num, product_batch in enumerate(product_batches):
        print(f"Processing batch {batch_num + 1}/{len(product_batches)}...")
        
        embeddings_batch = []
        documents_batch = []
        metadatas_batch = []
        ids_batch = []

        for product in product_batch:
            product_url = product.get("url")
            if not product_url:
                print(f"Skipping product without URL: {product.get('title', 'Unknown Title')}")
                continue

            product_text = process_product_text(product)
            if not product_text:
                print(f"Skipping product with no processable text: {product_url}")
                continue

            print(f"Generating embedding for: {product.get('title', product_url)[:50]}...")
            embedding = get_embedding(product_text)

            if embedding:
                embeddings_batch.append(embedding)
                documents_batch.append(product_text)
                metadatas_batch.append({
                    "url": product_url,
                    "title": product.get("title", "N/A"),
                    "price": str(product.get("price", "N/A")), # Ensure price is string for metadata
                    "category": product.get("category", "N/A"),
                    "image_url": product.get("images", [None])[0] if product.get("images") else None # First image
                })
                ids_batch.append(product_url) # Use URL as ID
            else:
                print(f"Failed to generate embedding for product: {product_url}. Skipping.")
        
        if ids_batch: # If any successful embeddings in batch
            try:
                print(f"Adding batch of {len(ids_batch)} items to ChromaDB...")
                collection.add(
                    embeddings=embeddings_batch,
                    documents=documents_batch,
                    metadatas=metadatas_batch,
                    ids=ids_batch
                )
                processed_count += len(ids_batch)
                print(f"Successfully added batch to ChromaDB. Total processed: {processed_count}")
            except Exception as e:
                print(f"Error adding batch to ChromaDB: {e}")
                # Optionally, add more detailed error logging here, e.g., which IDs failed
        
        # Small delay to avoid overwhelming Ollama or DB, especially if running locally
        time.sleep(1) 

    print(f"Ingestion complete. Processed and stored {processed_count} products in ChromaDB.")
    print(f"ChromaDB data should be stored in the '{CHROMA_DB_PATH}' directory.")
    
    # Verify count in collection
    try:
        count = collection.count()
        print(f"Verification: Collection '{CHROMA_COLLECTION_NAME}' now contains {count} items.")
    except Exception as e:
        print(f"Error verifying collection count: {e}")

# --- Main Execution ---
if __name__ == "__main__":
    print("Starting RAG ingestion process...")

    # Step 1: Ensure product data is available (scrape if needed)
    if not run_scraper_if_needed(PRODUCTS_FILE):
        print("Could not obtain product data. Exiting.")
        exit(1) # Exit if no data

    # Step 2: Load product data
    products = load_product_data(PRODUCTS_FILE)
    if not products:
        print("No products loaded. Exiting.")
        exit(1) # Exit if no data after loading attempt

    # Step 3: Generate embeddings and ingest into ChromaDB
    ingest_products_to_chromadb(products)

    print("RAG ingestion process finished.")

    