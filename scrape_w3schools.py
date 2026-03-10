import requests
from bs4 import BeautifulSoup
import time
import urllib.parse
import os

base_url = "https://www.w3schools.com/python/"
start_url = "https://www.w3schools.com/python/default.asp"

def get_links():
    response = requests.get(start_url)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # The sidebar menu usually has id "leftmenuinnerinner"
    menu_div = soup.find('div', id='leftmenuinnerinner')
    if not menu_div:
        print("Could not find sidebar menu.")
        return []
        
    links = []
    seen_urls = set()
    
    for a in menu_div.find_all('a'):
        href = a.get('href')
        if href and not href.startswith('http') and not href.startswith('javascript'):
            full_url = urllib.parse.urljoin(base_url, href)
            # only keep python pages (all python pages generally under /python/ and end with asp)
            if '.asp' in full_url:
                 if full_url not in seen_urls:
                    seen_urls.add(full_url)
                    links.append({'title': a.text.strip(), 'url': full_url})
                    
    return links

def scrape_page(url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        main_div = soup.find('div', id='main')
        if not main_div:
            return ""
            
        content = []
        for element in main_div.find_all(['h1', 'h2', 'h3', 'p', 'li', 'div']):
            # Skip advertisement elements or other non-content divs early
            if element.name == 'div' and not any(cls in ['w3-example', 'w3-code'] for cls in element.get('class', [])):
                continue

            if element.name in ['h1', 'h2', 'h3']:
                content.append(f"\n\n{'#' * int(element.name[1])} {element.text.strip()}")
            elif element.name == 'p':
                # filter out next/prev button texts
                text = element.text.strip()
                if text and text not in ["❯", "❮", "Next ❯", "❮ Previous", "❮ Prev"]:
                    content.append(text)
            elif element.name == 'li':
                content.append(f"- {element.text.strip()}")
            elif element.name == 'div' and 'w3-example' in element.get('class', []):
                code_div = element.find('div', class_='w3-code')
                if code_div:
                    # Clean the code text roughly
                    code_text = code_div.text.replace('xa0', ' ').strip()
                    content.append(f"\nExample Code:\n```python\n{code_text}\n```\n")
                    
        return "\n".join(content)
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return ""

def main():
    print("Fetching links from the sidebar...")
    links = get_links()
    print(f"Found {len(links)} links. Starting to scrape...")
    
    output_file = 'w3schools_python_full_course.txt'
    
    with open(output_file, 'w', encoding='utf-8') as f:
        # Title
        f.write("# W3Schools Python Tutorial Complete Text\n")
        f.write(f"Source: {base_url}\n\n")
        
        for i, link in enumerate(links):
            print(f"Scraping [{i+1}/{len(links)}]: {link['title']}")
            f.write(f"\n\n{'='*50}\nSection: {link['title']}\n{'='*50}\n")
            
            page_content = scrape_page(link['url'])
            # Since `find_all` extracts things sequentially, some things might be duplicated if 
            # nested. My simple logic avoids most nesting but it's a basic scrape.
            f.write(page_content)
            f.write("\n")
            
            # Sleep slightly to be respectful
            time.sleep(0.2)
            
    print(f"\nScraping completed! All text saved to: {os.path.abspath(output_file)}")

if __name__ == '__main__':
    main()
