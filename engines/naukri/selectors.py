# Naukri selectors
# EXTERNAL_APPLY_BTN must NOT include generic "Apply" to avoid false external redirect detection.
# Real external links on Naukri say "Apply on company site" or redirect to a different domain.
APPLY_BTN = "button.apply-button, a.apply-button, button#apply-button, button.apply-btn, a.apply-btn"
ALREADY_APPLIED = "button:has-text('Applied'), span:has-text('Applied'), div:has-text('You have already applied')"
POPUP = "div.apply-modal, div[role='dialog']"
SUBMIT_POPUP = "button:has-text('Submit'), button:has-text('Confirm')"
EXTERNAL_APPLY_BTN = "button:has-text('Apply on company site'), button:has-text('Apply on Company Website'), a[href*='apply']:not([href*='naukri.com'])"
