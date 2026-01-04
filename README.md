# 🌐 Sanfoundry Scraper (Web-Based)

**"Deployable, Classifiable, and Scalable Data Extraction."**

This is the fully containerized, web-app version of the Sanfoundry Scraper. While the **PC-Based Pro** version is built for local precision, this version is designed for cloud deployment, featuring an integrated web interface and automated link classification.

### 🚀 Live Preview

The app is currently hosted on Render: **[scraper4sanfoundry.qzz.io](https://www.google.com/search?q=http://scraper4sanfoundry.qzz.io)**

> **⚠️ Performance Note:** Due to the resource constraints of free-tier hosting, the service may occasionally time out or fail to process large batches. For mission-critical tasks, I recommend running the Docker container locally or supporting our hardware fund below.

---

### ✨ Key Features

* **Dockerized Architecture:** Fully portable and ready to deploy on any cloud provider or local server.
* **Link Classification:** Automatically detects the structure of the provided Sanfoundry URL and applies the appropriate scraping methodology.
* **Web Dashboard:** A simple, intuitive interface to paste URLs and monitor scraping progress in real-time.
* **Complete Logic:** Inherits the core engine's ability to handle math symbols and embedded images.

---

### 🛠️ Local Deployment (Docker)

If you have Docker installed on your system (e.g., Windows 11), you can bypass cloud limits by running the app locally:

1. **Clone the repo:**
```bash
git clone https://github.com/omsusi/sanfoundry-scraper.git
cd sanfoundry-scraper

```


2. **Build the image:**
```bash
docker build -t sanfoundry-web-scraper .

```


3. **Run the container:**
```bash
docker run -p 8080:8080 sanfoundry-web-scraper

```


4. Access the app at `http://localhost:8080`.

---

### 🌱 Support the Project: Hardware & Hosting Fund

Maintaining a reliable, 24/7 web service requires consistent computing power. Currently, free hosting resources are stretched thin, leading to service instability.

**My Goal:** I am raising **₹8,000** to purchase a **Raspberry Pi** to serve as a dedicated, low-power computing server. This hardware will allow me to:

* Keep the service **"always awake"** without cloud timeouts.
* Provide a stable environment for users who cannot run heavy scripts on their own machines.
* Offer faster processing for bulk MCQ and image extraction.

**How to contribute:**
If this tool has saved you hours of study time, please consider a small donation to help reach this milestone.

👉 **[Support the Goal on Buy Me a Coffee](https://buymeacoffee.com/omsusi)**

---

### 💼 Professional Services

**Custom Scraping & Managed Execution**
If you have specific requirements beyond this tool, I offer professional commissions:

* **Custom Scraper Development:** Tailored solutions for any platform.
* **Data-as-a-Service:** I handle the compute and delivery for high-volume datasets.
* **Enterprise Formatting:** Custom PDF/Excel styling for institutional use.

📫 **Inquiries:** [LinkedIn](https://linkedin.com/in/omsubhra-singha-30447a254) | [Email](mailto:omsubhrasingha21@gmail.com)

---
