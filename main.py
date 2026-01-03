# sanfoundry-scraper
# Copyright (C) 2026 Omsubhra Singha
# Distributed under the terms of the GNU General Public License v3

import os, re, time, base64, requests, uuid
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

app = FastAPI()

if not os.path.exists("static"): os.makedirs("static")
app.mount("/ui", StaticFiles(directory="static"), name="static")

# --- CORE UTILITIES ---

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|()]', "", name).replace(" ", "_")

def get_image_base64(url):
    """Downloads image and returns Base64 string to bake it directly into the PDF."""
    if not url: return ""
    if url.startswith("/"): url = "https://www.sanfoundry.com" + url
    
    clean_url = url.split('?')[0].split(',')[0].strip()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.sanfoundry.com/"
    }
    try:
        r = requests.get(clean_url, headers=headers, timeout=15)
        if r.status_code == 200:
            b64 = base64.b64encode(r.content).decode('utf-8')
            mime = r.headers.get('content-type', 'image/png')
            return f"data:{mime};base64,{b64}"
    except: pass
    return ""

def process_element(element, soup_context):
    """Handles classification (diagram vs math), link scrubbing, and sizing."""
    # 1. Handle Noscript
    for ns in element.find_all("noscript"):
        ns.replace_with(ns.decode_contents())

    # 2. Scrub Links (Unwrap <a> but keep text)
    for a in element.find_all("a"):
        a.unwrap()

    def classify_and_embed(img_tag, source_url):
        b64 = get_image_base64(source_url)
        if not b64: return None
        
        orig_w = int(img_tag.get('width', 0) or 0)
        orig_h = int(img_tag.get('height', 0) or 0)
        
        # YOUR SUCCESSFUL LOGIC: Scale up if likely a diagram
        is_diagram = (orig_w > 50 or orig_h > 40 or len(b64) > 5000)
        
        new_img = soup_context.new_tag("img", src=b64)
        new_img['class'] = "diagram" if is_diagram else "math-img"
        
        if is_diagram:
            # Force a readable minimum width for line drawings
            new_img['style'] = f"width: {max(orig_w, 350)}px; display:block; margin: 12px auto;"
        return new_img

    # Handle all images
    for img in element.find_all("img"):
        src = img.get("data-src") or img.get("src") or img.get("data-lazy-src")
        new_node = classify_and_embed(img, src)
        if new_node:
            img.replace_with(new_node)
        else:
            img.decompose()

    # Scrub raw URL strings
    raw_html = element.decode_contents()
    return re.sub(r'https?://\S+', '', raw_html)

# --- SCRAPER LOGIC ---

def scrape_topic(page, url):
    """Processes a single MCQ page."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        # Click expand buttons
        page.evaluate('document.querySelectorAll(".collapseomatic").forEach(el => el.click())')
        time.sleep(2)
        
        soup = BeautifulSoup(page.content(), "lxml")
        title = soup.find("h1").text.strip() if soup.find("h1") else "Topic"
        content = soup.find("div", class_="entry-content")
        
        html = f"<h2 class='topic-header'>{title}</h2>"
        if content:
            for el in content.find_all(["p", "div", "table"], recursive=False):
                text = el.get_text(strip=True)
                if any(x in text for x in ["Enroll", "Certification", "advertisement"]): continue
                
                if re.match(r"^\d+\.", text):
                    html += f"<div class='question'>Q. {process_element(el, soup)}</div>"
                elif "collapseomatic_content" in el.get("class", []):
                    html += f"<div class='ans-block'>{process_element(el, soup)}</div>"
                elif re.search(r"^[a-d]\)\s", text):
                    html += f"<div class='option'>{process_element(el, soup)}</div>"
        return html, title
    except Exception as e:
        return f"<p style='color:red;'>Failed to scrape {url}: {str(e)}</p>", "Error"

@app.get("/", response_class=HTMLResponse)
async def home():
    with open("static/index.html", "r", encoding="utf-8") as f: return f.read()

@app.get("/convert")
def convert(url: str = Query(...)):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        final_html = ""
        filename = "Sanfoundry_Manual.pdf"

        try:
            if "#" in url: # LEVEL 2: CHAPTER
                base, fragment = url.split("#")
                page.goto(base, wait_until="domcontentloaded")
                soup = BeautifulSoup(page.content(), "lxml")
                subj_title = soup.find("h1").text.strip()
                
                target = soup.find(id=fragment) or soup.find("span", id=fragment)
                if not target: raise HTTPException(status_code=404, detail="Chapter not found")
                
                ch_title = target.get_text().strip()
                container = target.find_next(["table", "ul", "ol"])
                links = [a['href'] for a in container.find_all("a") if 'href' in a.attrs]
                
                for s_url in links:
                    h, _ = scrape_topic(page, s_url)
                    final_html += h
                filename = f"{subj_title}_{ch_title}.pdf"

            elif "1000-" in url: # LEVEL 1: SUBJECT
                page.goto(url, wait_until="domcontentloaded")
                soup = BeautifulSoup(page.content(), "lxml")
                subj_title = soup.find("h1").text.strip()
                content_div = soup.find("div", class_="entry-content")
                links = [a['href'] for a in content_div.find_all("a") if "sanfoundry.com" in a.get('href', '') and "#" not in a.get('href', '')]
                
                for s_url in links[:10]: # Limit for free-tier stability
                    h, _ = scrape_topic(page, s_url)
                    final_html += h
                filename = f"{subj_title}_Manual.pdf"

            else: # LEVEL 3: TOPIC
                h, topic_title = scrape_topic(page, url)
                final_html = h
                soup = BeautifulSoup(page.content(), "lxml")
                breadcrumb = soup.find("div", class_="breadcrumb")
                subj_name = breadcrumb.find_all("a")[-1].text.strip() if breadcrumb else "Sanfoundry"
                filename = f"{subj_name}_{topic_title}.pdf"

            # --- PROFESSIONAL CSS & RENDERING ---
            style = f"""<style>
                @page {{ margin: 10mm; }}
                body {{ font-family: 'Segoe UI', sans-serif; font-size: 8.5pt; line-height: 1.2; color: #111; }}
                .topic-header {{ color: #a00; border-bottom: 2px solid #a00; margin: 25px 0 10px 0; font-size: 11pt; page-break-before: always; }}
                .question {{ font-weight: bold; margin-top: 10px; font-size: 9pt; }}
                .ans-block {{ background: #f6fff6; border-left: 4px solid #27ae60; padding: 8px; margin: 5px 0; page-break-inside: avoid; }}
                .diagram {{ max-width: 95%; height: auto; border: 1px solid #ddd; padding: 5px; background: #fff; }}
                .math-img {{ height: 1.5em; vertical-align: middle; }}
                p, div {{ margin: 3px 0; }}
            </style>"""

            full_body = f"<html><head>{style}</head><body>{final_html}</body></html>"
            page.set_content(full_body)

            # YOUR SUCCESSFUL LOGIC: Force image paint via auto-scroll
            page.evaluate('''async () => {
                await new Promise((resolve) => {
                    let totalHeight = 0, distance = 500;
                    let timer = setInterval(() => {
                        window.scrollBy(0, distance);
                        totalHeight += distance;
                        if(totalHeight >= document.body.scrollHeight){
                            clearInterval(timer); resolve();
                        }
                    }, 100);
                });
            }''')
            time.sleep(3)

            output_path = f"{uuid.uuid4()}.pdf"
            page.pdf(path=output_path, format="A4", print_background=True)
            browser.close()
            
            return FileResponse(output_path, filename=sanitize_filename(filename))

        except Exception as e:
            browser.close()
            raise HTTPException(status_code=500, detail=str(e))
