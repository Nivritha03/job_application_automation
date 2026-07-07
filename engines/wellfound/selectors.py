# Wellfound selectors
# Apply buttons on Wellfound say "Apply" or "I'm interested" — class-based is more reliable.
APPLY_BTN = "button[class*='applyButton'], a[class*='applyButton'], button:has-text('Quick Apply'), button:has-text(\"I'm interested\")"
ALREADY_APPLIED = "button:has-text('Applied'), span:has-text('Applied'), div:has-text('applied to')"
NOTE_BOX = "textarea[name='note'], textarea[placeholder*='pitch'], textarea[placeholder*='note'], textarea[placeholder*='cover']"
SUBMIT_MODAL = "button:has-text('Send Application'), button:has-text('Submit Application'), button:has-text('Confirm')"
EXTERNAL_APPLY_BTN = "button:has-text('Apply on company site'), button:has-text('Apply on Company Website'), a[href*='greenhouse.io'], a[href*='lever.co'], a[href*='ashbyhq.com']"
