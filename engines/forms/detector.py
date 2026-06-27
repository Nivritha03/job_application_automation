from playwright.sync_api import Page, Locator
from loguru import logger
from typing import Optional


class FieldGroup:
    """Represents a detected form field with its associated label and metadata."""
    def __init__(
        self,
        locator: Locator,
        label: str,
        field_type: str,
        name_attr: str = "",
        id_attr: str = "",
        placeholder: str = "",
        required: bool = False,
        options: list = None,
        aria_label: str = "",
        autocomplete: str = "",
    ):
        self.locator = locator
        self.label = label.strip().lower()
        self.label_raw = label.strip()
        self.field_type = field_type   # text, email, tel, file, select, textarea, radio, checkbox
        self.name_attr = name_attr
        self.id_attr = id_attr
        self.placeholder = placeholder
        self.required = required
        self.options = options or []
        self.aria_label = aria_label.strip().lower()
        self.autocomplete = autocomplete.strip().lower()

    def __repr__(self):
        return f"<FieldGroup label={self.label_raw!r} type={self.field_type}>"


class FormDetector:
    def __init__(self, page: Page):
        self.page = page

    def _get_label_for(self, locator: Locator, id_attr: str) -> str:
        """Attempt to find the label text for an input element via multiple strategies."""
        label_text = ""

        # Strategy 1: <label for="id">
        if id_attr:
            try:
                escaped = id_attr.replace("'", "\\'")
                label_loc = locator.page.locator(f"label[for='{escaped}']")
                if label_loc.count() > 0:
                    label_text = label_loc.first.inner_text().strip()
                    if label_text:
                        return label_text
            except Exception:
                pass

        # Strategy 2: ancestor <label> wrapping the input
        try:
            parent_label = locator.locator("xpath=ancestor::label")
            if parent_label.count() > 0:
                label_text = parent_label.first.inner_text().strip()
                if label_text:
                    return label_text
        except Exception:
            pass

        # Strategy 3: immediately preceding sibling <label>
        try:
            prev_label = locator.locator("xpath=preceding-sibling::label[1]")
            if prev_label.count() > 0:
                label_text = prev_label.first.inner_text().strip()
                if label_text:
                    return label_text
        except Exception:
            pass

        # Strategy 4: nearest parent container's first <label> or <span>/<div> with role
        try:
            container = locator.locator("xpath=ancestor::div[1]")
            if container.count() > 0:
                span = container.first.locator("label, span.label, span.field-label, div.label")
                if span.count() > 0:
                    label_text = span.first.inner_text().strip()
                    if label_text:
                        return label_text
        except Exception:
            pass

        return label_text

    def _get_select_options(self, locator: Locator) -> list:
        """Extract visible option texts from a <select> element."""
        try:
            options = locator.locator("option").all()
            texts = []
            for opt in options:
                t = opt.inner_text().strip()
                val = opt.get_attribute("value") or ""
                # Skip blank placeholders
                if t and val.lower() not in ("", "select", "please select", "-- select --"):
                    texts.append(t)
            return texts
        except Exception:
            return []

    def find_fields(self) -> list:
        """
        Returns a list of FieldGroup objects representing each detectable form field.
        Skips invisible, disabled, and irrelevant elements.
        """
        field_groups = []
        seen_ids = set()

        selectors = [
            "input:not([type='hidden']):not([type='submit']):not([type='reset'])"
            ":not([type='button']):not([type='image'])"
            ":not([aria-hidden='true'])",
            "textarea",
            "select",
        ]
        combined = ", ".join(selectors)

        try:
            all_locators = self.page.locator(combined).all()
        except Exception as e:
            logger.error(f"FormDetector: Failed to query form elements: {e}")
            return []

        for loc in all_locators:
            try:
                type_attr = (loc.get_attribute("type") or "text").lower()
                name_attr = (loc.get_attribute("name") or "").strip()
                id_attr   = (loc.get_attribute("id") or "").strip()
                placeholder = (loc.get_attribute("placeholder") or "").strip()
                tag_name  = loc.evaluate("el => el.tagName.toLowerCase()")
                required  = loc.get_attribute("required") is not None or \
                            loc.get_attribute("aria-required") == "true"

                # Determine field_type
                if tag_name == "textarea":
                    field_type = "textarea"
                elif tag_name == "select":
                    field_type = "select"
                elif type_attr == "file":
                    field_type = "file"
                elif type_attr in ("checkbox",):
                    field_type = "checkbox"
                elif type_attr in ("radio",):
                    field_type = "radio"
                elif type_attr in ("email",):
                    field_type = "email"
                elif type_attr in ("tel",):
                    field_type = "tel"
                elif type_attr in ("number",):
                    field_type = "number"
                elif type_attr in ("url",):
                    field_type = "url"
                else:
                    field_type = "text"

                # Skip aria-hidden inputs (React Select hidden inputs that intercept events)
                aria_hidden = loc.get_attribute("aria-hidden")
                if aria_hidden == "true":
                    continue

                # Skip tabindex=-1 text inputs (usually hidden-but-styled React inputs)
                tabindex = loc.get_attribute("tabindex")
                if tabindex == "-1" and field_type not in ("file", "radio", "checkbox"):
                    continue

                # Skip file inputs that are invisible but allow them for resume uploads
                if field_type != "file":
                    try:
                        if not loc.is_visible() or not loc.is_enabled():
                            continue
                    except Exception:
                        continue

                # Dedup by id
                dedup_key = id_attr or name_attr or placeholder
                if dedup_key and dedup_key in seen_ids:
                    continue
                if dedup_key:
                    seen_ids.add(dedup_key)

                # Skip GDPR / consent checkboxes — handled separately via auto-check
                if field_type == "checkbox" and (
                    "gdpr" in (id_attr + name_attr).lower()
                    or "consent" in (id_attr + name_attr).lower()
                ):
                    continue

                # Extract label
                label = self._get_label_for(loc, id_attr)

                aria_label_attr = (loc.get_attribute("aria-label") or "").strip()
                autocomplete_attr = (loc.get_attribute("autocomplete") or "").strip()

                # Fall back to placeholder / aria-label / name if no label found
                if not label:
                    label = (
                        aria_label_attr
                        or placeholder
                        or name_attr
                        or ""
                    ).strip()

                # Get options for select elements
                options = self._get_select_options(loc) if field_type == "select" else []

                # ── Pin the locator to a stable, id/name-based selector ────────
                # nth()-based locators shift when the DOM changes between detection
                # and filling (e.g. after previous fields are filled / React re-renders).
                # IMPORTANT: use [id='...'] attribute selector, NOT #id — CSS id
                # selectors cannot start with a digit (e.g. #430 is invalid).
                if id_attr:
                    pinned_loc = self.page.locator(f"[id='{id_attr}']")
                elif name_attr and field_type not in ("radio",):
                    pinned_loc = self.page.locator(
                        f"input[name='{name_attr}'], textarea[name='{name_attr}']"
                        f", select[name='{name_attr}']"
                    ).first
                else:
                    pinned_loc = loc  # fallback: keep original

                fg = FieldGroup(
                    locator=pinned_loc,
                    label=label,
                    field_type=field_type,
                    name_attr=name_attr,
                    id_attr=id_attr,
                    placeholder=placeholder,
                    required=required,
                    options=options,
                    aria_label=aria_label_attr,
                    autocomplete=autocomplete_attr,
                )
                field_groups.append(fg)

                logger.debug(
                    f"FormDetector: [{field_type:8s}] label={label!r:<40s} "
                    f"name={name_attr!r}  id={id_attr!r}"
                )

            except Exception as e:
                logger.debug(f"FormDetector: Skipping element — {e}")
                continue

        logger.info(f"FormDetector: Detected {len(field_groups)} form fields.")
        return field_groups
