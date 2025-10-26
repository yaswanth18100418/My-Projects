import requests
from bs4 import BeautifulSoup
import time
import random
from datetime import datetime, timedelta
import pyodbc 

# --- Google Custom Search API ---
GOOGLE_API_KEY = "AIzaSyCEd6fg9r_m8KDNdrNQdGioa1fgAzMOb_s"
GOOGLE_SEARCH_ENGINE_ID = "444fa11ad31d74b0b"

# --- SQL Server DB Connection ---
def create_db_connection():
    """Create and return database connection"""
    try:
        connection_string = (
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=localhost\\SQLEXPRESS;"      # Change to your actual server name
            "DATABASE=WebScrapingDB;"            # Use your actual database
            "Trusted_Connection=yes;"            # Windows Authentication; use UID/PWD for SQL auth
        )
        conn = pyodbc.connect(connection_string)
        print("✅ Database connection successful")
        return conn
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None

def insert_to_database(conn, query, url, content):
    """Insert web search record into SQL Server database"""
    try:
        cursor = conn.cursor()
        sql = """
        INSERT INTO SearchResponses (user_query, source_link, content, timestamp)
        VALUES (?, ?, ?, ?)
        """
        timestamp = datetime.now()
        cursor.execute(sql, (query, url, content, timestamp))
        conn.commit()
        print(f"✅ Data inserted successfully for URL: {url}")
        return True
    except Exception as e:
        print(f"❌ Failed to insert data: {e}")
        return False

# --- Google Search & Scraping ---
def google_custom_search(query, num_results=5):
    """Perform an authenticated Google search using Custom Search API; return list of URLs"""
    base_url = "https://www.googleapis.com/customsearch/v1"
    urls = []
    max_per_request = 10
    for start in range(1, num_results + 1, max_per_request):
        params = {
            'key': GOOGLE_API_KEY,
            'cx': GOOGLE_SEARCH_ENGINE_ID,
            'q': query,
            'num': min(max_per_request, num_results - len(urls)),
            'start': start,
            'safe': 'active'
        }
        try:
            print(f"🔍 Fetching results {start}-{start + params['num'] - 1} for: {query}")
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            if 'items' in data:
                for item in data['items']:
                    link = item.get('link')
                    if link: urls.append(link)
            else:
                print("⚠️ No search results in this batch")
        except requests.exceptions.RequestException as e:
            print(f"❌ Google API request failed: {e}")
            break
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            break
        if len(urls) >= num_results: break
    print(f"✅ Found {len(urls)} total results")
    return urls

def extract_text_from_url(url):
    """Extract clean text content from a URL"""
    try:
        r = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header']): element.decompose()
        # Content-heavy tags
        tags = ["main", "article", "section", "p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote"]
        text_elements = soup.find_all(tags)
        text_content = []
        for element in text_elements:
            text = element.get_text(separator=" ", strip=True)
            if text and len(text) > 30: text_content.append(text)
        final_text = "\n".join(text_content).strip()
        return final_text if final_text else soup.get_text(separator=" ", strip=True)
    except Exception as e:
        return f"Error fetching {url}: {e}"

def perform_web_search(query, num_results=5, max_chars=10000, max_search_pool=5):
    """Perform web search and extract clean content from top N valid websites"""
    try:
        print(f"🔍 Searching for: {query}\n")
        time.sleep(random.uniform(2, 4))  # Delay
        date_sensitive_keywords = [
            'new', 'latest', 'recent', 'breaking', 'today', 'current', 'update', 'news'
        ]
        should_add_date_filter = any(keyword in query.lower() for keyword in date_sensitive_keywords)
        if should_add_date_filter:
            yesterday = datetime.now() - timedelta(days=1)
            date_filter = f" after:{yesterday.strftime('%Y-%m-%d')}"
            final_query = query + date_filter
            print(f"🔍 Date filter applied: {final_query}")
        else:
            final_query = query
            print(f"🔍 Standard search: {final_query}")

        search_results = google_custom_search(final_query, max_search_pool)
        if not search_results:
            return "No search results found.", []

        successful_extractions = []
        visited_urls = []
        MIN_WORD_COUNT = 200
        MIN_CHAR_COUNT = 1000
        for i, url in enumerate(search_results, 1):
            if len(successful_extractions) >= num_results:
                break
            print(f"\n📥 Fetching candidate {i}/{len(search_results)}: {url}")
            time.sleep(random.uniform(2, 4))
            content = extract_text_from_url(url)
            if not content or content.startswith("Error fetching"):
                print(f"⚠️ Skipped: Extraction failed from {url}")
                continue
            if any(bad in content.lower() for bad in [
                "captcha", "access denied", "403 forbidden", "404 not found",
                "please enable cookies", "cloudflare", "bot detection"
            ]):
                print(f"🚫 Skipped: Detected blocked/spam page from {url}")
                continue
            word_count = len(content.strip().split())
            char_count = len(content.strip())
            if word_count < MIN_WORD_COUNT or char_count < MIN_CHAR_COUNT:
                print(f"⚠️ Skipped: Insufficient content from {url} (Words: {word_count}, Chars: {char_count})")
                continue
            successful_extractions.append((url, content.strip()))
            visited_urls.append(url)
            print(f"✅ Success {len(successful_extractions)}/{num_results}: Added content from {url} (Words: {word_count})")

        if len(successful_extractions) == 0:
            return "Unable to extract sufficient content from any search results.", []
        if len(successful_extractions) < num_results:
            print(f"⚠️ Warning: Only found {len(successful_extractions)} websites with sufficient content (target was {num_results})")

        all_text = ""
        for url, content in successful_extractions:
            truncated_content = content[:max_chars] if len(content) > max_chars else content
            all_text += f"\n\n--- SOURCE: {url} ---\n{truncated_content}\n"
        print(f"\n✅ Successfully processed content from {len(successful_extractions)} websites")
        return all_text.strip(), visited_urls

    except Exception as e:
        print(f"❌ Error in web search: {str(e)}")
        return f"Search error: {str(e)}", []

# --- MAIN LOGIC ---
if __name__ == "__main__":
    conn = create_db_connection()
    if conn is None:
        print("❌ Cannot proceed without database connection")
        exit()
    query = input("🔍 Enter your search query: ")

    combined_text, urls = perform_web_search(query, num_results=1, max_chars=5000)
    if combined_text and not combined_text.startswith("Search error") and not combined_text.startswith("Unable to extract"):
        print("\n📄 Extracted Content:")
        print("=" * 80)
        print(combined_text)
        print("=" * 80)
        print("\n🔗 Sources:")
        for url in urls:
            print(f" - {url}")
            content = extract_text_from_url(url)
            if content and not content.startswith("Error fetching"):
                insert_to_database(conn, query, url, content[:5000])
    else:
        print(f"\n❌ {combined_text}")
    conn.close()
    print("\n✅ Database connection closed")
