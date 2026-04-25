import multiprocessing
import os
import time
import playwright
from playwright.sync_api import sync_playwright

DOWNLOAD_DIR = "downloaded_images"

def worker_process(prompt_queue):
    # Create the download directory if it doesn't exist
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    
    # Use a persistent user data directory so logins are saved between runs
    user_data_dir = os.path.join(os.getcwd(), "playwright_profile")
    
    while True:
        prompt = prompt_queue.get()
        if prompt == "EXIT":
            break
            
        print(f"\n[Worker] Processing prompt: '{prompt}'")
        print("[Worker] Launching headless browser...")
        
        with sync_playwright() as p:
            # Use a persistent context to keep cookies/logins
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )
            page = context.pages[0] if context.pages else context.new_page()
            
            try:
                # 1. Navigate to Whisk/ImageFX target site
                print("[Worker] Navigating to AI Generator...")
                page.goto("https://labs.google/fx/tools/whisk/project", wait_until="networkidle") 
                
                # Check for login redirect
                if "signin" in page.url or "accounts.google.com" in page.url:
                    print("\n[!] ERROR: Google Login Required!")
                    print("[!] Please change 'headless=True' to 'headless=False' on line 18 in whisk_generator.py")
                    print("[!] Run the script once, log in manually to your Google Account, then switch back to headless=True.")
                    break
                
                # 2. Wait for the prompt input box and fill it
                # ImageFX sometimes uses contenteditable div or a specific textarea
                input_selector = "div[contenteditable='true'], textarea:not(.g-recaptcha-response)"
                print("[Worker] Waiting for input field...")
                
                # We wait for it to be visible. If it fails, maybe a popup is blocking it.
                page.wait_for_selector(input_selector, state="visible", timeout=15000)
                page.fill(input_selector, prompt)
                
                # Attempt to set Aspect Ratio to Carousel if available on the input bar
                carousel_btn = page.locator("button:has-text('Carousel'), button[aria-label*='Carousel'], button[title*='Carousel'], div:has-text('Carousel')").last
                try:
                    if carousel_btn.is_visible(timeout=2000):
                        print("[Worker] Selecting Carousel format option...")
                        carousel_btn.click()
                except:
                    pass
                    
                # 3. Click Generate button
                generate_btn_selector = "button[aria-label='Submit prompt'], button:has-text('Generate')"
                print("[Worker] Clicking Generate...")
                page.click(generate_btn_selector)
                
                print("[Worker] Waiting for image generation to complete...")
                
                # 4. Wait for generation to finish
                # Usually the generate button is disabled while generating.
                # Let's wait a moment, then wait for the button to be enabled again (or just wait if it doesn't disable)
                page.wait_for_timeout(2000)
                
                # Smart wait: wait until generate button is no longer disabled/spinning, max 30s
                try:
                    # Depending on DOM, button might be disabled
                    page.wait_for_function(f"() => !document.querySelector(`{generate_btn_selector}`).disabled", timeout=30000)
                except:
                    pass
                
                print("[Worker] Generation seems done. Waiting 10 seconds before downloading as requested...")
                page.wait_for_timeout(10000)
                
                # 5. Hover, Download, and Delete the First Image
                print("[Worker] Hovering over the first generated image...")
                
                # Find the generated images. Profile pics and logos are usually small.
                # We will find the first image on the page that is larger than 100x100 pixels.
                all_images = page.locator("img, [role='img']")
                first_image = None
                
                for i in range(all_images.count()):
                    img = all_images.nth(i)
                    box = img.bounding_box()
                    if box and box["width"] > 100 and box["height"] > 100:
                        first_image = img
                        break
                
                if first_image is not None:
                    first_image.hover()
                    page.wait_for_timeout(1000) # Wait for animation/buttons to appear
                    
                    # Look for the download button that appears
                    download_btn = page.locator("button[aria-label*='ownload'], button[title*='ownload'], button:has-text('Download')").first
                    
                    if download_btn.is_visible():
                        print("[Worker] Found download button, clicking...")
                        
                        safe_prompt = "".join(x for x in prompt[:15] if x.isalnum())
                        filename = os.path.join(DOWNLOAD_DIR, f"{safe_prompt}_{int(time.time())}.png")
                        
                        # Intercept the actual browser download
                        with page.expect_download(timeout=30000) as download_info:
                            download_btn.click()
                            
                        download = download_info.value
                        download.save_as(filename)
                        print(f"[Worker] Successfully downloaded actual image: {filename}")
                        
                        # Now click the Delete button to clean up
                        delete_btn = page.locator("button[aria-label*='elete'], button[title*='elete'], button:has-text('Delete')").first
                        if delete_btn.is_visible():
                            print("[Worker] Clicking delete button to remove the generated image...")
                            delete_btn.click()
                            page.wait_for_timeout(1000)
                            
                            # Handle potential confirmation dialog
                            confirm_btn = page.locator("button:has-text('Confirm'), button:has-text('Yes'), button:has-text('Delete')").last
                            if confirm_btn.is_visible():
                                confirm_btn.click()
                            print("[Worker] Image deleted from history.")
                            
                    else:
                        print("[Worker] Failed to find the Download button after hovering.")
                        # Fallback to screenshot
                        safe_prompt = "".join(x for x in prompt[:15] if x.isalnum())
                        filename = os.path.join(DOWNLOAD_DIR, f"{safe_prompt}_{int(time.time())}.png")
                        first_image.screenshot(path=filename)
                        print(f"[Worker] Fallback: Saved screenshot of the image to {filename}")
                else:
                    print("[Worker] Failed to find the generated image area.")

            except Exception as e:
                print(f"[Worker] Error processing prompt: {e}")
                print("[Worker] Check if the site requires login or if the CSS selectors have changed.")
            finally:
                print("[Worker] Closing browser for this prompt.")
                context.close()

if __name__ == "__main__":
    # Ensure Playwright is installed
    try:
        import playwright
    except ImportError:
        print("Playwright is not installed. Please run: pip install playwright && playwright install")
        exit(1)

    # Use a Queue to send prompts from the main process (Terminal) to the Worker process
    prompt_queue = multiprocessing.Queue()
    
    # Start worker process
    worker = multiprocessing.Process(target=worker_process, args=(prompt_queue,))
    worker.start()
    
    print("\n=== Terminal AI Image Generator (Headless Playwright) ===")
    print(f"Images will be saved to: {os.path.abspath(DOWNLOAD_DIR)}")
    print("Type 'exit' to quit.\n")
    
    try:
        while True:
            # Get prompt from user via terminal
            user_prompt = input("Enter your image prompt: ")
            
            if user_prompt.lower() == 'exit':
                print("Sending exit signal to worker...")
                prompt_queue.put("EXIT")
                break
            
            if user_prompt.strip():
                prompt_queue.put(user_prompt)
            
    except KeyboardInterrupt:
        print("\nKeyboard interrupt detected. Exiting...")
        prompt_queue.put("EXIT")
        
    print("Waiting for worker process to finish...")
    worker.join()
    print("Done.")
