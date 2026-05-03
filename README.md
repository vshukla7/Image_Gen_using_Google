# Terminal AI Image Generator (Headless Playwright)

A Python-based terminal automation script that connects directly to Google Labs ImageFX/Whisk to generate, download, and manage AI images completely in the background via the command line.

## 🚀 Features

- **Terminal-Based Workflow:** No need to interact with a browser UI. Type your prompt in the terminal, and the script does the rest.
- **Headless Browser Execution:** Uses Microsoft Playwright to run a hidden Chrome environment in the background.
- **Smart Aspect Ratio Selection:** Automatically attempts to set the format to "Carousel" (16:9 landscape) before generation.
- **Intelligent Element Detection:** Ignores small UI elements like Google Profile pictures and only targets the actual generated high-resolution images by analyzing bounding box dimensions (>100x100px).
- **Auto-Download & Cleanup:** Automatically hovers to reveal the download button, intercepts the high-quality file, saves it to `downloaded_images/`, and subsequently deletes the image from the site history to keep your workspace clean.
- **Persistent Sessions:** Saves your Google Account cookies so you only have to log in once.

## 🛠️ Installation & Setup

1. **Install Python Dependencies:**
   Ensure you have `playwright` installed via pip:
   ```bash
   pip install playwright
   ```

2. **Install Playwright Browsers:**
   Download the required headless browser binaries:
   ```bash
   playwright install chromium
   ```

3. **First-Time Login Setup:**
   - Open `whisk_generator.py` in a text editor.
   - On line 20, change `headless=True` to `headless=False`.
   - Run the script: `python whisk_generator.py`
   - The browser window will open. **Log in to your Google Account** and accept any terms if prompted.
   - Close the script.
   - Change `headless=False` back to `headless=True`.

## 🎮 Usage

Simply run the script in your terminal:
```bash
python whisk_generator.py
```
- Enter your desired image prompt and hit **Enter**.
- The script will launch a background worker, connect to the site, generate your image, download it, and automatically clear it from the history.
- Type `exit` to stop the script.

## ⚠️ Disclaimer

**For Testing and Personal Use Only.**

This script was created for educational purposes, workflow automation testing, and personal convenience. It relies on standard browser automation tools (Playwright) to interface with public UI elements. 

- This project is **not** affiliated with, endorsed by, or sponsored by Google or Google Labs.
- Users are solely responsible for ensuring their use of this script complies with the **Terms of Service** of the target website (Google Labs / ImageFX).
- This tool is designed to automate personal tasks and should **not** be used for spam, abuse, scraping at scale, or circumventing any platform security mechanisms.
- The author does not promote or condone the abuse of AI generation services. Please use this tool responsibly.
