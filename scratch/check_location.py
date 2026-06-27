from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('https://job-boards.greenhouse.io/reddit/jobs/8013591')
    
    page.wait_for_timeout(2000)
    
    # Locate location input
    loc = page.locator("[id='candidate-location']").first
    loc.scroll_into_view_if_needed()
    loc.click()
    loc.type("Hyderabad, Telangana", delay=100)
    page.wait_for_timeout(2000)
    
    # Use our selector
    selector = (
        "[class*='menu'] li[role='option'], [class*='menu'] [class*='option'], "
        "[class*='listbox'] li[role='option'], [class*='listbox'] [class*='option']"
    )
    opts = page.locator(selector).all()
    print("Found options count:", len(opts))
    for i, opt in enumerate(opts):
        print(f"  opt[{i}]: text='{opt.inner_text().strip()}' visible={opt.is_visible()}")
        
    browser.close()
