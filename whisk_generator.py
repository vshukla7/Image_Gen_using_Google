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
        data = prompt_queue.get()
        if data == "EXIT":
            break
            
        prompt, aspect_ratio = data
            
        print(f"\n[Worker] Processing prompt: '{prompt}' (Ratio: {aspect_ratio})")
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
                # 1. Navigate to Google Flow (formerly Whisk)
                print("[Worker] Navigating to AI Generator (Flow)...")
                page.goto("https://labs.google/fx/tools/flow", wait_until="networkidle") 
                
                # Check for "Get started with Flow" modal
                try:
                    get_started_btn = page.locator("button:has-text('Get started with Flow')")
                    if get_started_btn.is_visible(timeout=5000):
                        print("[Worker] Clicking 'Get started with Flow' modal...")
                        get_started_btn.click()
                        page.wait_for_timeout(1000)
                except:
                    pass

                # --- NEW PROJECT FLOW ---
                print("[Worker] Creating a new project...")
                new_project_selector = "button:has-text('New project'), button:has(i:text('add'))"
                try:
                    page.wait_for_selector(new_project_selector, timeout=10000)
                    page.click(new_project_selector)
                    page.wait_for_timeout(2000)
                except Exception as e:
                    print(f"[Worker] Warning: Failed to find 'New project' button. Checking DOM...")
                    # Fallback: find any button with 'New' or 'add'
                    btns = page.locator("button").all()
                    found = False
                    for b in btns:
                        txt = b.inner_text().lower()
                        if "new project" in txt or ("add" in txt and len(txt) < 15):
                            b.click()
                            found = True
                            break
                    if not found:
                        print("[Worker] Could not find 'New project' button. Proceeding with current page.")
                
                # Check for login redirect after project creation attempt
                if "signin" in page.url or "accounts.google.com" in page.url:
                    print("\n[!] Google Login Required! Launching window for manual login...")
                    context.close()
                    
                    # Launch a temporary non-headless window for login
                    with p.chromium.launch_persistent_context(
                        user_data_dir=user_data_dir,
                        headless=False,
                        args=["--disable-blink-features=AutomationControlled"]
                    ) as login_context:
                        login_page = login_context.pages[0] if login_context.pages else login_context.new_page()
                        login_page.goto("https://labs.google/fx/tools/whisk/project")
                        print("[!] PLEASE LOGIN NOW. Waiting 30 seconds for manual login...")
                        login_page.wait_for_timeout(30000) # Wait for user to finish login
                    
                    print("[!] Login session closed. Relaunching in headless mode to continue...")
                    # Re-launch the persistent headless context
                    context = p.chromium.launch_persistent_context(
                        user_data_dir=user_data_dir,
                        headless=True,
                        args=["--disable-blink-features=AutomationControlled"]
                    )
                    page = context.pages[0] if context.pages else context.new_page()
                    page.goto("https://labs.google/fx/tools/flow", wait_until="networkidle")
                
                # 2. Wait for the prompt input box and fill it
                # Flow uses a content-editable div with role="textbox"
                input_selector = 'div[role="textbox"]'
                print("[Worker] Waiting for input field...")
                
                page.wait_for_selector(input_selector, state="visible", timeout=15000)
                page.click(input_selector)
                page.keyboard.type(prompt)
                
                # Attempt to set Aspect Ratio
                try:
                    # Click the current model/ratio button (usually has an icon like crop_16_9 or similar)
                    aspect_ratio_btn = page.locator("button:has(i:text('crop_')), button:has(i:text('aspect_ratio'))").first
                    if aspect_ratio_btn.is_visible(timeout=3000):
                        print("[Worker] Opening Aspect Ratio/Model menu...")
                        aspect_ratio_btn.click()
                        page.wait_for_timeout(800)
                        
                        # Map to Flow's internal ratio triggers
                        ratio_map = {
                            "carousel": "SQUARE",
                            "1:1": "SQUARE",
                            "landscape": "LANDSCAPE",
                            "16:9": "LANDSCAPE",
                            "portrait": "PORTRAIT",
                            "9:16": "PORTRAIT",
                            "4:3": "LANDSCAPE_4_3",
                            "3:4": "PORTRAIT_3_4"
                        }
                        target_key = ratio_map.get(aspect_ratio.lower(), "SQUARE")
                        
                        print(f"[Worker] Selecting {target_key} format option...")
                        format_btn = page.locator(f"button[id*='-trigger-{target_key}']")
                        if format_btn.is_visible(timeout=2000):
                            format_btn.click()
                            print(f"[Worker] Successfully set aspect ratio key to {target_key}")
                        else:
                            print(f"[Worker] Could not find option for {target_key}")
                        
                        page.keyboard.press("Escape")
                except Exception as e:
                    print(f"[Worker] Warning: Failed to set aspect ratio - {e}")
                    
                # 3. Click Generate button
                # Flow uses an arrow_forward icon. We'll try multiple selectors and Enter key.
                print("[Worker] Clicking Generate...")
                try:
                    # Try clicking the button with the arrow icon
                    generate_btn = page.locator("button:has-text('arrow_forward'), button:has(i:text('arrow_forward')), button[aria-label*='reate']").first
                    if generate_btn.is_visible():
                        generate_btn.click()
                    else:
                        print("[Worker] Generate button not visible, pressing Enter instead...")
                        page.keyboard.press("Enter")
                except Exception as e:
                    print(f"[Worker] Click failed, trying Enter key: {e}")
                    page.keyboard.press("Enter")
                
                # Wait for generation to finish. 
                # Flow shows a card with a percentage while generating.
                # We wait for the percentage to disappear or the image to be stable.
                print("[Worker] Waiting for image generation to complete...")
                try:
                    # Wait for a div that represents the image card to have an img tag
                    # We target any button-like container that holds an image
                    page.wait_for_selector("div[role='button'] img, img.sc-", state="visible", timeout=90000)
                except Exception as e:
                    print(f"[Worker] Timeout waiting for images to generate: {e}")
                    
                print("[Worker] Generation seems done. Waiting 3 seconds for UI to settle...")
                page.wait_for_timeout(3000)
                
                # 5. Download the First Image
                # Find the first image card
                image_card = page.locator("div[role='button']:has(img)").first
                
                if image_card.is_visible():
                    print("[Worker] Found image card. Opening options menu...")
                    image_card.hover()
                    page.wait_for_timeout(500)
                    
                    # Click the 'more_vert' menu button on the card
                    menu_btn = image_card.locator("button:has(i:text('more_vert'))").first
                    if menu_btn.is_visible():
                        menu_btn.click()
                        page.wait_for_timeout(800)
                        
                        # Click the Download option in the main menu
                        download_opt = page.locator("div[role='menuitem']:has-text('Download'), button:has-text('Download')").first
                        if download_opt.is_visible():
                            print("[Worker] Clicking Download (opening resolution menu)...")
                            download_opt.click()
                            page.wait_for_timeout(1000)
                            
                            # Flow now shows a RESOLUTION menu (1K, 2K, etc.)
                            # We'll target the "1K" or "Original size" option
                            resolution_opt = page.locator("div:has-text('1K'), div:has-text('Original size'), button:has-text('1K')").first
                            if resolution_opt.is_visible():
                                print("[Worker] Selecting 1K resolution...")
                                
                                safe_prompt = "".join(x for x in prompt[:15] if x.isalnum())
                                filename = os.path.join(DOWNLOAD_DIR, f"{safe_prompt}_{int(time.time())}.png")
                                
                                with page.expect_download(timeout=30000) as download_info:
                                    resolution_opt.click()
                                    
                                download = download_info.value
                                download.save_as(filename)
                                print(f"[Worker] Successfully downloaded image: {filename}")
                            else:
                                print("[Worker] Could not find '1K' resolution option.")
                            
                            # Optional: Archive (Delete) the image from the project
                            # Re-open menu if it closed
                            page.wait_for_timeout(500)
                            if not page.locator("div[role='menuitem']:has-text('Archive')").is_visible():
                                image_card.hover()
                                menu_btn.click()
                                page.wait_for_timeout(800)
                                
                            archive_opt = page.locator("div[role='menuitem']:has-text('Archive'), button:has-text('Archive')").first
                            if archive_opt.is_visible():
                                print("[Worker] Archiving (deleting) image from project...")
                                archive_opt.click()
                                page.wait_for_timeout(1000)
                        else:
                            print("[Worker] Could not find 'Download' option in menu.")
                    else:
                        print("[Worker] Could not find 'more_vert' menu on image card.")
                else:
                    print("[Worker] Failed to find the generated image card.")

                # --- PROJECT DELETION FLOW ---
                print("[Worker] Deleting project to clean up...")
                try:
                    # Navigate back to dashboard
                    page.goto("https://labs.google/fx/tools/flow", wait_until="networkidle")
                    page.wait_for_timeout(2000)
                    
                    # Find the most recent project card and click delete
                    # Usually the first card is the newest one
                    project_card = page.locator("div[role='button']").first
                    if project_card.is_visible():
                        # Look for delete icon on the card
                        card_delete_btn = project_card.locator("button:has(i:text('delete'))").first
                        if card_delete_btn.is_visible():
                            card_delete_btn.click()
                            page.wait_for_timeout(1000)
                            
                            confirm_modal_btn = page.locator("button:has-text('Delete Project')").first
                            if confirm_modal_btn.is_visible():
                                confirm_modal_btn.click()
                                print("[Worker] Project deleted successfully.")
                except Exception as e:
                    print(f"[Worker] Could not delete project: {e}")

            except Exception as e:
                print(f"[Worker] Error processing prompt: {e}")
                
                # Take a diagnostic screenshot on failure
                try:
                    error_img = f"error_debug_{int(time.time())}.png"
                    page.screenshot(path=error_img)
                    print(f"[Worker] Diagnostic screenshot saved to {error_img}")
                except:
                    pass

                print("[Worker] Check if the site requires login or if the CSS selectors have changed.")
                # Fallback: Print DOM summary if error occurs
                try:
                    print("[Worker] DOM Check: Identifying buttons on page...")
                    btns = page.locator("button").all()
                    for i, b in enumerate(btns[:10]):
                        txt = b.inner_text().strip().replace('\n', ' ')
                        print(f"  - Button {i}: {txt}")
                except:
                    pass
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
            user_prompt = input("\nEnter your image prompt: ")
            
            if user_prompt.lower() == 'exit':
                print("Sending exit signal to worker...")
                prompt_queue.put("EXIT")
                break
                
            if user_prompt.strip():
                # Ask for aspect ratio optionally
                ratio_input = input("Enter aspect ratio (Press Enter for 'Carousel'): ").strip()
                if not ratio_input:
                    ratio_input = "Carousel"
                    
                prompt_queue.put((user_prompt, ratio_input))
            
    except KeyboardInterrupt:
        print("\nKeyboard interrupt detected. Exiting...")
        prompt_queue.put("EXIT")
        
    print("Waiting for worker process to finish...")
    worker.join()
    print("Done.")
