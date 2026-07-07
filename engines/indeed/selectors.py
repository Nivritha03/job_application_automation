# Indeed selectors
# IndeedApply button has a specific class and ID — do not use generic "Apply" text.
APPLY_BTN = ".jobsearch-IndeedApplyButton-button, button#indeedApplyButton, button[class*='IndeedApply'], span:has-text('Easily apply') + button"
ALREADY_APPLIED = "button:has-text('Applied'), span:has-text('Applied'), div:has-text('You applied on')"
MODAL = "div.ia-Dialog, div.ia-Modal, div[role='dialog']"
NEXT_BTN = "button:has-text('Continue'), button:has-text('Next')"
SUBMIT_BTN = "button:has-text('Submit your application'), button:has-text('Submit Application'), button:has-text('Submit')"
EXTERNAL_APPLY_BTN = "button:has-text('Apply on company site'), button:has-text('Apply on Company Website'), a.jobalert-IndeedApplyLink"
