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
    """Prevents HTTP header crashes by removing illegal characters."""
    return re.sub(r'[\\/*?:"<>|()]', "", name).replace(" ", "_")

def get_image_base64(url):
    """Downloads image and returns Base64 string for offline PDF viewing."""
    if not url: return ""
    if url.startswith("/"): url = "https://www.sanfoundry.com" + url
    
    clean_url = url.split('?')[0].split(',')[0].strip()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
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
    """Your successful PC logic: handles math vs diagrams and scrubs links."""
    for ns in element.find_all("noscript"):
        ns.replace_with(ns.decode_contents())

    # Scrub blue links (Unwrap keeps the text but removes the clickable <a>)
    for a in element.find_all("a"):
        a.unwrap()

    def classify_and_embed(img_tag, source_url):
        b64 = get_image_base64(source_url)
        if not b64: return None
        
        orig_w = int(img_tag.get('width', 0) or 0)
        orig_h = int(img_tag.get('height', 0) or 0)
        
        # Scale up diagrams vs keeping math symbols small
        is_diagram = (orig_w > 50 or orig_h > 40 or len(b64) > 5000)
        
        new_img = soup_context.new_tag("img", src=b64)
        new_img['class'] = "diagram" if is_diagram else "math-img"
        
        if is_diagram:
            new_img['style'] = f"width: {max(orig_w, 350)}px; display:block; margin: 12px auto;"
        return new_img

    # Process all image sources
    for img in element.find_all("img"):
        src = img.get("data-src") or img.get("src") or img.get("data-lazy-src")
        new_node = classify_and_embed(img, src)
        if new_node:
            img.replace_with(new_node)
        else:
            img.decompose()

    for btn in element.find_all(class_=re.compile("collapseomatic")):
        btn.decompose()

    # Scrub raw URL strings from text
    raw_html = element.decode_contents()
    return re.sub(r'https?://\S+', '', raw_html)

# --- SCRAPER LOGIC ---

def scrape_topic(page, url):
    """Processes a single topic page using your Answer/Explanation logic."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.evaluate('document.querySelectorAll(".collapseomatic").forEach(el => el.click())')
        time.sleep(2)
        
        soup = BeautifulSoup(page.content(), "lxml")
        title = soup.find("h1").text.strip() if soup.find("h1") else "Topic"
        content = soup.find("div", class_="entry-content")
        
        html = f"<h2 class='topic-header'>{title}</h2>"
        if content:
            for el in content.find_all(["p", "div", "center", "table"], recursive=False):
                text = el.get_text(strip=True)
                if any(x in text for x in ["Enroll", "Certification", "advertisement"]): continue
                
                if re.match(r"^\d+\.", text):
                    html += f"<div class='question'>Q. {process_element(el, soup)}</div>"
                elif "collapseomatic_content" in el.get("class", []):
                    ans_match = re.search(r"Answer:\s*([a-d])", text)
                    ans_letter = ans_match.group(1) if ans_match else "?"
                    raw_expl = el.decode_contents().split("Explanation:")[-1] if "Explanation:" in el.decode_contents() else el.decode_contents()
                    expl_container = BeautifulSoup(f"<div>{raw_expl}</div>", "lxml")
                    html += f"""<div class='ans-block'>
                                <span class='ans-label'>Ans: {ans_letter}</span> | 
                                <span class='expl'><strong>Explanation:</strong> {process_element(expl_container, soup)}</span>
                                </div>"""
                elif re.search(r"^[a-d]\)\s", text) or (len(text) < 100 and "a)" in text):
                    html += f"<div class='option'>{process_element(el, soup)}</div>"
        return html, title
    except: return "", "Error"

@app.get("/", response_class=HTMLResponse)
async def home():
    with open("static/index.html", "r", encoding="utf-8") as f: return f.read()

@app.get("/convert")
def convert(url: str = Query(...)):
    # Headless must be True for Render/Docker
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        final_html = ""

        try:
            if "#" in url:
                base, fragment = url.split("#")
                page.goto(base, wait_until="networkidle")
                
                # Render-specific fix for 404: Scroll to fragment to force lazy-load
                page.evaluate(f"document.getElementById('{fragment}')?.scrollIntoView()")
                time.sleep(2)
                
                soup = BeautifulSoup(page.content(), "lxml")
                target = soup.find(id=fragment) or soup.find(lambda t: t.name=="h2" and fragment in t.get('id', ''))
                
                if not target:
                    # Fallback for dynamic IDs: match header text
                    clean_frag = fragment.replace("-", " ").lower()
                    target = soup.find(lambda t: t.name=="h2" and clean_frag in t.text.lower())

                if not target: raise HTTPException(status_code=404, detail="Chapter header not found.")
                
                ch_title = target.get_text().strip()
                container = target.find_next(["table", "ul", "ol"])
                links = [a['href'] for a in container.find_all("a") if 'href' in a.attrs]
                
                for s_url in links:
                    h, _ = scrape_topic(page, s_url)
                    final_html += h
                filename = f"Chapter_{ch_title}.pdf"

            else:
                h, title = scrape_topic(page, url)
                final_html = h
                # Hierarchy Naming: Subject_Topic
                soup = BeautifulSoup(page.content(), "lxml")
                breadcrumb = soup.find("div", class_="breadcrumb")
                subj_name = breadcrumb.find_all("a")[-1].text.strip() if breadcrumb else "Sanfoundry"
                filename = f"{subj_name}_{title}.pdf"

            # --- YOUR SUCCESSFUL PDF STYLING ---
            style = """<style>
                @page { margin: 10mm; }
                body { font-family: 'Segoe UI', Tahoma, sans-serif; font-size: 8.5pt; line-height: 1.15; color: #111; }
                .topic-header { color: #a00; border-bottom: 1.5px solid #a00; margin: 15px 0 5px 0; font-size: 10.5pt; font-weight: bold; text-transform: uppercase; page-break-before: always; }
                .question { font-weight: bold; display: block; margin-top: 10px; font-size: 9.2pt; }
                .ans-block { margin-top: 4px; padding: 5px 12px; background: #f6fff6; border-left: 4px solid #27ae60; page-break-inside: avoid; }
                .ans-label { color: #27ae60; font-weight: bold; }
                .diagram { max-width: 95%; height: auto; display: block; margin: 12px auto; border: 1px solid #ddd; padding: 8px; background: #fff; }
                .math-img { display: inline-block; height: 1.6em; vertical-align: middle; }
            </style>"""

            page.set_content(f"<html><head>{style}</head><body>{final_html}</body></html>")
            
            # Auto-scroll to ensure images are fully decoded before PDF capture
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
