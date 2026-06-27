from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('https://job-boards.greenhouse.io/reddit/jobs/8013591')
    
    page.wait_for_timeout(2000)
    
    label_text = "What sexual orientation do you most closely identify with?"
    try:
        label_loc = page.locator(f"label:has-text('{label_text}')").first
        if label_loc.is_visible():
            container = page.locator("div", has=label_loc).last
            dropdown_trigger = container.locator("input, [class*='select'], [role='combobox']").first
            dropdown_trigger.scroll_into_view_if_needed()
            dropdown_trigger.click()
            page.wait_for_timeout(1000)
            
            # Print all list items or divs that have role='option' or contain text on the entire page
            print("--- ALL LI TEXTS ON PAGE ---")
            lis = page.locator("li").all()
            for li in lis:
                t = li.inner_text().strip()
                if t:
                    print(f"  li: '{t}'")
        else:
            print("Label not visible")
    except Exception as e:
        print('Error:', e)
        
    browser.close()
