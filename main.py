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

# --- IMAGE & ELEMENT LOGIC ---

def get_image_base64(url):
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
            return f"data:{r.headers.get('content-type', 'image/png')};base64,{b64}"
    except: pass
    return ""

def process_element(element, soup_context):
    for ns in element.find_all("noscript"):
        ns.replace_with(ns.decode_contents())
    for a in element.find_all("a"): a.unwrap()
    
    def classify_and_embed(img_tag, source_url):
        b64 = get_image_base64(source_url)
        if not b64: return None
        orig_w = int(img_tag.get('width', 0) or 0)
        orig_h = int(img_tag.get('height', 0) or 0)
        is_diagram = (orig_w > 50 or orig_h > 40 or len(b64) > 5000)
        new_img = soup_context.new_tag("img", src=b64)
        new_img['class'] = "diagram" if is_diagram else "math-img"
        if is_diagram:
            new_img['style'] = f"width: {max(orig_w, 350)}px; display:block; margin: 12px auto;"
        return new_img

    for img in element.find_all("img"):
        src = img.get("data-src") or img.get("src") or img.get("data-lazy-src")
        new_node = classify_and_embed(img, src)
        if new_node: img.replace_with(new_node)
        else: img.decompose()

    for btn in element.find_all(class_=re.compile("collapseomatic")): btn.decompose()
    return re.sub(r'https?://\S+', '', element.decode_contents())

# --- SCRAPER ---

def scrape_topic(page, url):
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
                    raw_expl = el.decode_contents().split("Explanation:")[-1] if "Explanation:" in el.decode_contents() else el.decode_contents()
                    html += f"""<div class='ans-block'>
                                <span class='ans-label'>Ans: {ans_match.group(1) if ans_match else '?'}</span> | 
                                <span class='expl'><strong>Explanation:</strong> {process_element(BeautifulSoup(raw_expl, 'lxml'), soup)}</span>
                                </div>"""
                elif re.search(r"^[a-d]\)\s", text) or (len(text) < 100 and "a)" in text):
                    html += f"<div class='option'>{process_element(el, soup)}</div>"
        return html
    except: return ""

@app.get("/")
async def home():
    with open("static/index.html", "r", encoding="utf-8") as f: return HTMLResponse(f.read())

@app.get("/convert")
def convert(url: str = Query(...)):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Use a real user-agent to prevent bot-detection 404s
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        page = context.new_page()
        final_html = ""

        try:
            if "#" in url:
                base, fragment = url.split("#")
                page.goto(base, wait_until="networkidle", timeout=60000)
                
                # STABILIZATION: Force full page load by scrolling
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2)
                
                soup = BeautifulSoup(page.content(), "lxml")
                # DEEP SEARCH: 1. By exact ID, 2. By ID partial match, 3. By text content
                target = soup.find(id=fragment) or soup.find(id=re.compile(fragment))
                if not target:
                    clean_text = fragment.replace("-", " ").lower()
                    target = soup.find(lambda t: t.name in ["h2", "h3"] and clean_text in t.text.lower())
                
                if not target: raise HTTPException(status_code=404, detail="Chapter header not found.")
                
                container = target.find_next(["table", "ul", "ol"])
                links = [a['href'] for a in container.find_all("a") if 'href' in a.attrs]
                for s_url in links: final_html += scrape_topic(page, s_url)
                filename = f"Chapter_{fragment}.pdf"
            else:
                final_html = scrape_topic(page, url)
                filename = "Export.pdf"

            style = "<style>@page{margin:10mm;}body{font-family:sans-serif;font-size:8.5pt;line-height:1.2;}.topic-header{color:#a00;border-bottom:1.5px solid #a00;page-break-before:always;}.ans-block{background:#f6fff6;border-left:4px solid #27ae60;padding:8px;page-break-inside:avoid;}.diagram{max-width:95%;display:block;margin:12px auto;}</style>"
            page.set_content(f"<html><head>{style}</head><body>{final_html}</body></html>")
            
            # Final scroll for PDF rendering
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(3)
            
            output_path = f"{uuid.uuid4()}.pdf"
            page.pdf(path=output_path, format="A4", print_background=True)
            return FileResponse(output_path, filename=re.sub(r'[\\/*?:"<>|()]', "", filename).replace(" ", "_"))
        finally:
            browser.close()
