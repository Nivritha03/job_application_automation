from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('https://job-boards.greenhouse.io/reddit/jobs/8013591')
    
    page.wait_for_timeout(2000)
    
    # Check degree dropdown
    try:
        deg = page.locator("[id='degree--0']").first
        deg.scroll_into_view_if_needed()
        deg.click()
        page.wait_for_timeout(1000)
        # We can find the open menu list
        menu = page.locator("[class*='menu']").first
        if menu.is_visible():
            print("Degree options:", menu.inner_text().split("\n"))
        else:
            print("Degree menu not visible")
        page.keyboard.press("Escape")
    except Exception as e:
        print("Error degree:", e)
        
    # Check discipline dropdown
    try:
        disc = page.locator("[id='discipline--0']").first
        disc.scroll_into_view_if_needed()
        disc.click()
        page.wait_for_timeout(1000)
        menu = page.locator("[class*='menu']").first
        if menu.is_visible():
            print("Discipline options:", menu.inner_text().split("\n"))
        else:
            print("Discipline menu not visible")
        page.keyboard.press("Escape")
    except Exception as e:
        print("Error discipline:", e)
        
    browser.close()
