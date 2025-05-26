import requests
from bs4 import BeautifulSoup
import time
import json
import re
import random
import os
from urllib.parse import urljoin, urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor

def get_soup(url):
    """Obtém o BeautifulSoup de uma URL com headers para simular um navegador."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"Erro ao acessar {url}: {e}")
        return None

def is_same_domain(url, base_url):
    """Verifica se a URL está no mesmo domínio que a base_url."""
    parsed_url = urlparse(url)
    parsed_base = urlparse(base_url)
    return parsed_url.netloc == parsed_base.netloc or not parsed_url.netloc

def clean_url(url):
    """Remove fragmentos, queries e outros parâmetros para normalizar URLs."""
    parsed = urlparse(url)
    
    # Remove fragment (#content, #tab-description, etc)
    cleaned = parsed._replace(fragment='')
    
    # Remove parâmetros específicos que não mudam o produto
    if parsed.query:
        query_params = parse_qs(parsed.query)
        # Remove parâmetros comuns que não alteram o conteúdo do produto
        params_to_remove = ['add-to-cart', 'add_to_wishlist', 'add-to-compare']
        for param in params_to_remove:
            if param in query_params:
                del query_params[param]
        
        # Reconstrói a query sem os parâmetros removidos
        new_query = '&'.join([f"{k}={v[0]}" for k, v in query_params.items()])
        cleaned = cleaned._replace(query=new_query)
    
    return cleaned.geturl()

def normalize_product_url(url):
    """Normaliza URLs de produtos para evitar duplicatas."""
    # Remove fragmentos e parâmetros desnecessários
    clean = clean_url(url)
    
    # Remove barras finais extras
    while clean.endswith('/'):
        clean = clean[:-1]
    
    # Adiciona uma única barra no final para padronizar
    if not clean.endswith('/'):
        clean += '/'
    
    return clean

def find_all_links(soup, base_url):
    """Encontra todos os links na página."""
    links = []
    if not soup:
        return links
    
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        full_url = urljoin(base_url, href)
        
        # Apenas links do mesmo domínio
        if is_same_domain(href, base_url):
            links.append(full_url)
    
    return links

def find_category_links(soup, base_url):
    """Encontra links para categorias de produtos."""
    category_links = []
    
    # Padrões comuns para menus de categorias
    category_containers = [
        soup.select('.product-categories'),
        soup.select('.woocommerce-loop-category__title'),
        soup.select('.menu-item-object-product_cat a'),
        soup.select('li.cat-item a'),
        soup.select('.widget_product_categories a')
    ]
    
    for container in category_containers:
        for item in container:
            if hasattr(item, 'href'):  # Se o próprio item for um link
                href = item['href']
                full_url = urljoin(base_url, href)
                category_links.append(full_url)
            else:  # Se o item contém links
                for link in item.find_all('a', href=True):
                    href = link['href']
                    full_url = urljoin(base_url, href)
                    category_links.append(full_url)
    
    # Procura por links que contenham "categoria" ou "category" na URL
    for link in find_all_links(soup, base_url):
        if 'categoria' in link or 'category' in link:
            category_links.append(link)
    
    return list(set(category_links))  # Remove duplicatas

def find_pagination_links(soup, base_url):
    """Encontra links de paginação."""
    pagination_links = []
    
    # Padrões comuns para paginação
    pagination_containers = [
        soup.select('.woocommerce-pagination a'),
        soup.select('.pagination a'),
        soup.select('a.page-numbers')
    ]
    
    for container in pagination_containers:
        for link in container:
            if 'href' in link.attrs:
                href = link['href']
                full_url = urljoin(base_url, href)
                pagination_links.append(full_url)
    
    return list(set(pagination_links))  # Remove duplicatas

def is_product_page(url, soup):
    """Tenta identificar se uma página é de produto."""
    if not soup:
        return False
        
    # Padrões comuns em URLs de produto
    url_patterns = ['/produto/', '/product/', '/shop/', '/p/']
    
    # Elementos comuns em páginas de produto
    product_elements = [
        soup.find('div', class_=re.compile(r'product|produto', re.I)),
        soup.find('span', class_=re.compile(r'price|preco', re.I)),
        soup.find('button', class_=re.compile(r'add-to-cart|comprar|carrinho', re.I)),
        soup.find('div', {'id': re.compile(r'product|produto', re.I)}),
        soup.find('form', {'class': re.compile(r'cart', re.I)}),
        soup.select_one('.woocommerce-product-gallery'),
        soup.select_one('.single-product')
    ]
    
    # Verificar URL
    if any(pattern in url for pattern in url_patterns):
        return True
    
    # Verificar elementos da página
    if any(element is not None for element in product_elements):
        return True
        
    return False

def extract_product_info(url, soup):
    """Extrai informações de um produto."""
    if not soup:
        return None
    
    # Título do produto
    title = ""
    title_candidates = [
        soup.find('h1'),
        soup.find('h1', class_=re.compile(r'product-title|produto|woocommerce-products-header__title', re.I)),
        soup.find('h2', class_=re.compile(r'product-title|produto', re.I)),
        soup.select_one('.product_title')
    ]
    
    for candidate in title_candidates:
        if candidate and candidate.text.strip():
            title = candidate.text.strip()
            break
    
    # Extrair preço
    price = ""
    price_candidates = [
        soup.select_one('.woocommerce-Price-amount'),
        soup.select_one('.price'),
        soup.find('span', class_=re.compile(r'price|preco', re.I)),
        soup.find('div', class_=re.compile(r'price|preco', re.I))
    ]
    
    for candidate in price_candidates:
        if candidate and candidate.text.strip():
            price = candidate.text.strip().replace('\n', ' ').replace('\t', ' ')
            # Remove espaços múltiplos
            price = re.sub(' +', ' ', price)
            break
    
    # Extrair descrição
    description = ""
    desc_candidates = [
        soup.select_one('.woocommerce-product-details__short-description'),
        soup.select_one('.description'),
        soup.select_one('#tab-description'),
        soup.find('div', {'id': 'tab-description'}),
        soup.find('div', class_=re.compile(r'description|descricao|detalhes', re.I))
    ]
    
    for candidate in desc_candidates:
        if candidate and candidate.text.strip():
            description = candidate.text.strip().replace('\n', ' ').replace('\t', ' ')
            # Remove espaços múltiplos
            description = re.sub(' +', ' ', description)
            break
    
    # Extrair categoria do produto
    category = ""
    cat_candidates = [
        soup.select_one('.product-categories'),
        soup.select_one('.posted_in')
    ]
    
    for candidate in cat_candidates:
        if candidate and candidate.text.strip():
            category = candidate.text.strip().replace('\n', ' ').replace('\t', ' ')
            if 'Categoria:' in category:
                category = category.split('Categoria:')[1].strip()
            break
    
    # Extrair SKU ou código do produto
    sku = ""
    sku_candidates = [
        soup.select_one('.sku'),
        soup.find('span', class_=re.compile(r'sku', re.I))
    ]
    
    for candidate in sku_candidates:
        if candidate and candidate.text.strip():
            sku = candidate.text.strip()
            break
    
    # Extrair disponibilidade
    in_stock = "Desconhecido"
    stock_candidates = [
        soup.select_one('.stock'),
        soup.find('p', class_=re.compile(r'stock|disponib', re.I))
    ]
    
    for candidate in stock_candidates:
        if candidate and candidate.text.strip():
            in_stock = candidate.text.strip()
            break
    
    # Extrair imagens
    images = []
    img_containers = [
        soup.select('.woocommerce-product-gallery__image'),
        soup.select('.product-images img')
    ]
    
    for container in img_containers:
        for img_div in container:
            img = img_div.find('img')
            if img:
                src = img.get('src') or img.get('data-src') or img.get('data-lazy-src', '')
                if src:
                    full_img_url = urljoin(url, src)
                    images.append(full_img_url)
    
    # Se não encontrou imagens nos containers específicos, tenta buscar diretamente
    if not images:
        img_tags = soup.find_all('img', src=True)
        for img in img_tags:
            src = img.get('src', img.get('data-src', ''))
            if src and ('product' in src.lower() or 'produto' in src.lower() or 'upload' in src.lower()):
                full_img_url = urljoin(url, src)
                images.append(full_img_url)
    
    # Extrair características adicionais
    extra_info = {}
    info_containers = [
        soup.select('.woocommerce-product-attributes'),
        soup.select('.product_meta'),
        soup.find('table', class_=re.compile(r'attr|feature|spec|detail', re.I))
    ]
    
    for container in info_containers:
        if not container:
            continue
            
        if isinstance(container, list):
            for item in container:
                rows = item.find_all(['tr', 'div'])
                for row in rows:
                    th = row.find('th')
                    td = row.find('td')
                    if th and td:
                        key = th.text.strip().replace(':', '')
                        value = td.text.strip()
                        extra_info[key] = value
        else:
            rows = container.find_all(['tr', 'div'])
            for row in rows:
                th = row.find('th')
                td = row.find('td')
                if th and td:
                    key = th.text.strip().replace(':', '')
                    value = td.text.strip()
                    extra_info[key] = value
    
    # Busca por pares de termos comuns como "Peso:" e o valor seguinte
    for element in soup.find_all(['p', 'div', 'span']):
        text = element.text.strip()
        if ':' in text and len(text) < 100:  # Evita textos muito longos
            try:
                key, value = text.split(':', 1)
                if len(key) < 30:  # Chaves não devem ser muito longas
                    extra_info[key.strip()] = value.strip()
            except:
                pass
    
    # Seções de conteúdo
    content_html = ""
    tabs = soup.select('.woocommerce-tabs')
    if tabs:
        for tab in tabs:
            content_html += str(tab)
            
    # Criar o dicionário de informações do produto
    product_info = {
        "url": url,
        "title": title,
        "price": price,
        "description": description,
        "category": category,
        "sku": sku,
        "availability": in_stock,
        "images": images[:10],  # Limitar a 10 imagens
        "extra_info": extra_info
    }
    
    return product_info

def find_product_links(soup, base_url):
    """Encontra links diretos para produtos na página."""
    product_links = []
    
    # Padrões comuns para links de produtos
    product_containers = [
        soup.select('.products .product a'),
        soup.select('.woocommerce-loop-product__title a'),
        soup.select('.product-title a'),
        soup.select('.product_list_widget a')
    ]
    
    for container in product_containers:
        for link in container:
            if 'href' in link.attrs:
                href = link['href']
                full_url = urljoin(base_url, href)
                product_links.append(full_url)
    
    # Procura por links que contenham "produto" ou "product" na URL
    for link in find_all_links(soup, base_url):
        if '/produto/' in link or '/product/' in link:
            product_links.append(link)
    
    return list(set(product_links))  # Remove duplicatas

def crawl_site(start_url, max_pages=100, max_products=200, save_interval=20):
    """Realiza crawling no site para encontrar páginas de produtos."""
    visited = set()
    to_visit = [start_url]
    products = {}  # Dicionário para armazenar produtos por URL normalizada
    pages_visited = 0
    base_domain = urlparse(start_url).netloc
    
    # Adiciona URLs de categorias para explorar primeiro
    soup = get_soup(start_url)
    if soup:
        category_links = find_category_links(soup, start_url)
        for link in category_links:
            if link not in to_visit:
                to_visit.append(link)
                print(f"Adicionada categoria: {link}")
    
    print(f"Iniciando crawling a partir de {start_url}")
    print(f"Encontradas {len(to_visit)} URLs para visitar inicialmente")
    
    # Arquivo para salvar o progresso
    temp_file = 'temp_products.json'
    
    try:
        while to_visit and pages_visited < max_pages and (max_products is None or len(products) < max_products):
            current_url = to_visit.pop(0)
            
            # Normaliza a URL para verificação
            normalized_url = clean_url(current_url)
            
            # Ignora URLs já visitadas ou de outros domínios
            if normalized_url in visited or urlparse(current_url).netloc != base_domain:
                continue
            
            visited.add(normalized_url)
            pages_visited += 1
            
            if pages_visited % 5 == 0:
                print(f"Páginas visitadas: {pages_visited}, produtos únicos encontrados: {len(products)}, URLs a visitar: {len(to_visit)}")
            
            # Adiciona um delay para não sobrecarregar o servidor
            time.sleep(random.uniform(0.5, 1.5))
            
            # Obtém a soup da página
            soup = get_soup(current_url)
            if not soup:
                continue
            
            # Verifica se é uma página de produto
            if is_product_page(current_url, soup):
                print(f"Encontrou página de produto: {current_url}")
                
                # Extrai informações do produto
                product_info = extract_product_info(current_url, soup)
                
                if product_info and product_info["title"]:
                    # Usa URL normalizada como chave para evitar duplicatas
                    product_key = normalize_product_url(current_url)
                    
                    # Se já temos este produto mas a nova versão tem mais informação, a atualizamos
                    if product_key in products:
                        existing = products[product_key]
                        # Se a nova versão tem mais informações de descrição
                        if (not existing["description"] and product_info["description"]) or \
                        (len(product_info["description"]) > len(existing["description"]) and len(existing["description"]) < 100):
                            products[product_key] = product_info
                            print(f"Atualizando produto: {product_info['title']} (mais informações)")
                    else:
                        products[product_key] = product_info
                        print(f"Produto extraído: {product_info['title']}")
                        
                        # Salva o progresso a cada X produtos novos
                        if len(products) % save_interval == 0:
                            save_progress(products, temp_file)
            
            # Encontra links de produtos na página atual
            product_links = find_product_links(soup, current_url)
            for link in product_links:
                if normalize_product_url(link) not in visited and link not in to_visit:
                    to_visit.insert(0, link)  # Insere no início para priorizar
            
            # Encontra links de paginação
            pagination_links = find_pagination_links(soup, current_url)
            for link in pagination_links:
                if clean_url(link) not in visited and link not in to_visit:
                    to_visit.insert(1, link)  # Insere logo após os links de produtos
            
            # Encontra mais links para visitar
            new_links = find_all_links(soup, current_url)
            
            # Adiciona novos links para visitar
            for link in new_links:
                # Verificamos a URL normalizada para evitar duplicatas
                if clean_url(link) not in visited and link not in to_visit:
                    to_visit.append(link)
                    
            # Prioriza links que parecem ser de produto
            to_visit.sort(key=lambda x: 1 if '/produto/' in x or '/product/' in x else 
                                        (2 if '/categoria' in x or '/category' in x else 3))
    
    except KeyboardInterrupt:
        print("\nCrawling interrompido pelo usuário.")
    except Exception as e:
        print(f"\nErro durante o crawling: {e}")
    finally:
        # Converte o dicionário para lista de produtos
        product_list = list(products.values())
        
        # Remove o arquivo temporário se existir
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass
        
        print(f"Crawling finalizado. Visitadas {pages_visited} páginas, encontrados {len(product_list)} produtos únicos.")
        return product_list

def save_progress(products, filename):
    """Salva o progresso atual em um arquivo temporário."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(list(products.values()), f, ensure_ascii=False, indent=4)
        print(f"Progresso salvo: {len(products)} produtos no arquivo {filename}")
    except Exception as e:
        print(f"Erro ao salvar progresso: {e}")

def scrape_with_threads(urls, max_workers=5):
    """Executa o scraping em paralelo usando threads."""
    products = {}
    
    def process_url(url):
        soup = get_soup(url)
        if soup and is_product_page(url, soup):
            product_info = extract_product_info(url, soup)
            if product_info and product_info["title"]:
                return normalize_product_url(url), product_info
        return None, None
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(process_url, urls))
    
    # Filtra resultados None e adiciona ao dicionário
    for key, product in results:
        if key and product:
            products[key] = product
    
    return list(products.values())

if __name__ == "__main__":
    base_url = "https://oleosdaterra.com/"
    
    # Crawling do site
    products = crawl_site(base_url, max_pages=200, max_products=200, save_interval=10)
    
    # Salva os dados em um arquivo JSON
    with open('products_data.json', 'w', encoding='utf-8') as f:
        json.dump(products, f, ensure_ascii=False, indent=4)
    
    print(f"Scraping concluído. {len(products)} produtos extraídos e salvos em products_data.json") 