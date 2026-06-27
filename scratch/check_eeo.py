from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('https://job-boards.greenhouse.io/reddit/jobs/8013591')
    
    page.wait_for_timeout(2000)
    
    # We want to find the elements for Transgender and Sexual Orientation
    # and print their surrounding HTML structure.
    for term in ["transgender", "sexual orientation"]:
        print(f"\n--- INSPECTION FOR: {term} ---")
        try:
            label_loc = page.locator(f"label:has-text('{term}')").first
            if label_loc.is_visible():
                print("Label HTML:", label_loc.evaluate("el => el.outerHTML"))
                # Find sibling or parent div
                parent = label_loc.locator("xpath=..")
                print("Parent HTML:", parent.evaluate("el => el.outerHTML")[:500])
                
                # Find inputs/comboboxes
                inputs = parent.locator("input").all()
                for i, inp in enumerate(inputs):
                    print(f"  Input[{i}] HTML:", inp.evaluate("el => el.outerHTML"))
                    
                # Let's try to click the input's grandparent and see if options menu appears in the page
                if inputs:
                    inp = inputs[0]
                    gp = inp.locator("xpath=../..")
                    print("Grandparent HTML:", gp.evaluate("el => el.outerHTML")[:500])
                    print("Clicking grandparent...")
                    gp.click()
                    page.wait_for_timeout(1000)
                    
                    # Dump any visible menus
                    menus = page.locator("[class*='menu']").all()
                    print(f"Open menus found after click: {len(menus)}")
                    for m_idx, m in enumerate(menus):
                        print(f"  Menu[{m_idx}] innerText:", m.inner_text().strip().split("\n"))
                    # Close menu
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(500)
            else:
                print("Label not found / not visible")
        except Exception as e:
            print("Error:", e)
            
    browser.close()
