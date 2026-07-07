# Glassdoor selectors
# Glassdoor Easy Apply button is clearly labeled — use data-test and class selectors.
APPLY_BTN = "button[data-test='easy-apply-button'], button:has-text('Easy Apply'), button.easy-apply, [class*='EasyApplyButton']"
ALREADY_APPLIED = "button:has-text('Applied'), span:has-text('Applied'), div:has-text('You applied')"
MODAL = ".modal-content, div[role='dialog']"
SUBMIT_MODAL = "button:has-text('Submit Application'), button:has-text('Continue'), button:has-text('Confirm')"
EXTERNAL_APPLY_BTN = "button:has-text('Apply on company site'), button:has-text('Apply on Company Website'), a[data-test='job-apply-external']"
