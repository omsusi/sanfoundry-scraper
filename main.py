# sanfoundry-scraper
# Copyright (C) 2026 Omsubhra Singha
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

import os, re, time, base64, requests, uuid
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

app = FastAPI()

if not os.path.exists("static"): os.makedirs("static")
app.mount("/ui", StaticFiles(directory="static"), name="static")

# --- YOUR IMAGE LOGIC ---
def get_image_base64(url):
    if not url: return ""
    if url.startswith("/"): url = "https://www.sanfoundry.com" + url
    try:
        r = requests.get(url.split('?')[0], timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            return f"data:{r.headers.get('content-type', 'image/png')};base64,{base64.b64encode(r.content).decode('utf-8')}"
    except: pass
    return ""

def process_element(element, soup_context):
    for ns in element.find_all("noscript"):
        ns.replace_with(ns.decode_contents())

    def classify_and_embed(img_tag, source_url):
        b64 = get_image_base64(source_url)
        if not b64: return None
        orig_w = int(img_tag.get('width', 0) or 0)
        orig_h = int(img_tag.get('height', 0) or 0)
        is_diagram = (orig_w > 50 or orig_h > 40 or len(b64) > 5000)
        new_img = soup_context.new_tag("img", src=b64)
        new_img['class'] = "diagram" if is_diagram else "math-img"
        if is_diagram: new_img['style'] = f"width: {max(orig_w, 350)}px;"
        return new_img

    for img in element.find_all("img"):
        src = img.get("data-src") or img.get("src") or img.get("data-lazy-src")
        new_node = classify_and_embed(img, src)
        if new_node: img.replace_with(new_node)
        else: img.decompose()

    for btn in element.find_all(class_=re.compile("collapseomatic")):
        btn.decompose()
    return element.decode_contents()

# --- SCRAPER CORE ---
def scrape_page(page, url):
    page.goto(url, wait_until="domcontentloaded")
    page.evaluate('document.querySelectorAll(".collapseomatic").forEach(el => el.click())')
    time.sleep(1)
    
    soup = BeautifulSoup(page.content(), "lxml")
    title = soup.find("h1").text.strip() if soup.find("h1") else "Topic"
    content = soup.find("div", class_="entry-content")
    
    html = f"<h2 class='topic-header'>{title}</h2>"
    for el in content.find_all(["p", "div"], recursive=False):
        text = el.get_text(strip=True)
        if any(x in text for x in ["Enroll", "Certification", "advertisement"]): continue
        if re.match(r"^\d+\.", text):
            html += f"<div class='question'>Q. {process_element(el, soup)}</div>"
        elif "collapseomatic_content" in el.get("class", []):
            html += f"<div class='ans-block'>{process_element(el, soup)}</div>"
        elif re.search(r"^[a-d]\)\s", text):
            html += f"<div class='option'>{process_element(el, soup)}</div>"
    return html, title

@app.get("/", response_class=HTMLResponse)
async def home():
    with open("static/index.html", "r") as f: return f.read()

@app.get("/convert")
def smart_convert(url: str = Query(...)):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        final_html = ""
        filename = "Sanfoundry_Export.pdf"

        # ROUTER LOGIC
        if "#" in url: # LEVEL 2: Chapter Anchor
            base, fragment = url.split("#")
            page.goto(base, wait_until="domcontentloaded")
            soup = BeautifulSoup(page.content(), "lxml")
            subj_title = soup.find("h1").text.strip()
            target = soup.find(id=fragment) or soup.find("span", id=fragment)
            ch_title = target.get_text() if target else "Chapter"
            
            subtopics = [a['href'] for a in target.find_next(["table", "ul"]).find_all("a")]
            for s_url in subtopics:
                h, _ = scrape_page(page, s_url)
                final_html += h
            filename = f"{subj_title}_{ch_title}.pdf"

        elif "1000-" in url: # LEVEL 1: Subject Index
            page.goto(url, wait_until="domcontentloaded")
            soup = BeautifulSoup(page.content(), "lxml")
            subj_title = soup.find("h1").text.strip()
            # Grabbing all subtopic links from the table
            subtopics = [a['href'] for a in soup.find("div", class_="entry-content").find_all("a") if "sanfoundry.com" in a.get('href', '') and "#" not in a.get('href', '')]
            # Limiting to 10 for free-tier stability, remove [:10] for full
            for s_url in subtopics[:10]: 
                h, _ = scrape_page(page, s_url)
                final_html += h
            filename = f"{subj_title}_Complete_Manual.pdf"

        else: # LEVEL 3: Sub-topic Page
            h, title = scrape_page(page, url)
            final_html = h
            filename = f"{title}.pdf"

        # RENDER PDF
        style = """<style>
            @page { margin: 10mm; }
            body { font-family: 'Segoe UI', sans-serif; font-size: 8.5pt; line-height: 1.2; }
            .topic-header { color: #a00; border-bottom: 2px solid #a00; margin: 30px 0 10px 0; page-break-before: always; }
            .question { font-weight: bold; margin-top: 10px; }
            .ans-block { background: #f6fff6; border-left: 4px solid #27ae60; padding: 8px; margin: 5px 0; }
            .diagram { max-width: 95%; height: auto; display: block; margin: 10px auto; border: 1px solid #ddd; padding: 5px; }
        </style>"""
        
        output_path = f"{uuid.uuid4()}.pdf"
        page.set_content(f"<html><head>{style}</head><body>{final_html}</body></html>")
        page.pdf(path=output_path, format="A4", print_background=True)
        browser.close()
        
        return FileResponse(output_path, filename=filename.replace(" ", "_"))