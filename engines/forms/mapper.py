import re
from loguru import logger
from engines.forms.detector import FieldGroup


# ── Profile field matching rules ──────────────────────────────────────────────
# Each rule: (field_key, [keyword fragments to match in label/name/placeholder])
# Evaluated in order — first match wins.
PROFILE_FIELD_RULES = [
    ("resume",      ["resume", "cv", "curriculum vitae", "upload resume", "attach resume"]),
    ("email",       ["email", "e-mail", "electronic mail"]),
    ("phone",       ["phone", "mobile", "telephone", "cell", "tel"]),
    ("first_name",  ["first name", "firstname", "given name"]),
    ("last_name",   ["last name", "lastname", "surname", "family name"]),
    ("name",        ["full name", "fullname", "your name", "legal name"]),
    ("linkedin",    ["linkedin"]),
    ("github",      ["github"]),
    ("portfolio",   ["portfolio", "personal website", "personal site"]),
    ("website",     ["website", "web site", "url", "personal url"]),
    ("location",    ["location", "city", "city, state", "current location"]),
    ("cover_letter",["cover letter", "coverletter", "cover note", "message to hiring"]),
    ("current_salary", ["current salary", "current compensation", "current ctc"]),
    ("expected_salary",["expected salary", "desired salary", "expected compensation",
                        "expected ctc", "salary expectations"]),
    ("degree",      ["degree"]),
    ("discipline",  ["discipline", "major", "field of study"]),
    ("school",      ["school", "university", "college"]),
    ("country",     ["country"]),
]

# ── Question type detection ───────────────────────────────────────────────────
# Keywords whose presence in a question label hint that this is a Q&A field,
# not a standard profile field.
QUESTION_HINT_KEYWORDS = [
    "authorized", "sponsorship", "sponsor", "visa", "citizen",
    "veteran", "disability", "disabled", "felony", "relocate",
    "why do you", "why are you", "why would you", "how did you",
    "tell us", "describe", "years of experience", "notice period",
    "start date", "available", "preferred", "pronoun",
    "gender", "race", "ethnicity", "education level",
    "privacy", "policy", "consent", "agree",
    "how many years", "what is your", "are you",
]


def _indicators(fg: FieldGroup) -> str:
    """Combine all text signals for a field into one searchable string."""
    return " ".join(filter(None, [
        fg.label,
        fg.name_attr.lower().replace("_", " ").replace("-", " "),
        fg.id_attr.lower().replace("_", " ").replace("-", " "),
        fg.placeholder.lower(),
    ]))


def _is_question(fg: FieldGroup, indicators: str) -> bool:
    """Heuristic: is this a Q&A question rather than a profile field?"""
    # Textareas are almost always question/essay fields unless they're cover letters
    if fg.field_type == "textarea" and "cover" not in indicators:
        return True
    # Selects with many options are likely dropdowns/questions
    if fg.field_type == "select" and len(fg.options) >= 2:
        return True
    # Keyword presence
    if any(kw in indicators for kw in QUESTION_HINT_KEYWORDS):
        return True
    # Label phrasing heuristic: question-like sentence structure
    label = fg.label
    if label.endswith("?") or label.startswith("are ") or label.startswith("do ") \
            or label.startswith("have ") or label.startswith("will ") \
            or label.startswith("how ") or label.startswith("what ") \
            or label.startswith("please ") or label.startswith("describe "):
        return True
    return False


class FormMapper:
    """
    Maps a list of FieldGroup objects into two dicts:
      - profile_fields: {field_key: FieldGroup}  — standard fields like email, phone, resume
      - questions:      {label_text: FieldGroup}  — Q&A fields routed to QuestionHandler
    """

    def _score_field(self, fg: FieldGroup, keywords: list[str]) -> int:
        score = 0
        def normalize(val: str) -> str:
            return val.lower().replace("_", " ").replace("-", " ")

        label = normalize(fg.label)
        placeholder = normalize(fg.placeholder)
        aria_label = normalize(fg.aria_label)
        name_attr = normalize(fg.name_attr)
        id_attr = normalize(fg.id_attr)
        autocomplete = normalize(fg.autocomplete)

        # Check keyword presence in attributes with scoring weights
        if any(kw in autocomplete for kw in keywords):
            score += 10
        if any(kw in placeholder for kw in keywords):
            score += 10
        if any(kw in name_attr for kw in keywords):
            score += 9
        if any(kw in label for kw in keywords):
            score += 8
        if any(kw in aria_label for kw in keywords):
            score += 8
        if any(kw in id_attr for kw in keywords):
            score += 7

        return score

    def map_fields(self, field_groups: list) -> tuple[dict, dict]:
        """
        Maps a list of FieldGroup objects into profile_fields and questions using
        attribute scoring weights, resolving conflicts by highest confidence.
        """
        profile_fields: dict[str, FieldGroup] = {}
        questions: dict[str, FieldGroup] = {}

        # Temporary list to store candidate profile mappings
        candidates = []  # items: (fg, best_key, score)
        unmapped_fgs = []

        for fg in field_groups:
            # ── 1. Resume is always a profile field ──────────────────────────
            if fg.field_type == "file":
                profile_fields["resume"] = fg
                logger.debug(f"FormMapper: [profile ] resume ← {fg.label_raw!r}")
                continue

            # Calculate scores for each profile field
            scores = {field_key: self._score_field(fg, keywords) for field_key, keywords in PROFILE_FIELD_RULES}
            best_key, best_score = max(scores.items(), key=lambda x: x[1])

            # Minimum score threshold is 7 (equivalent to at least one ID attr match)
            if best_score >= 7:
                candidates.append((fg, best_key, best_score))
            else:
                unmapped_fgs.append(fg)

        # Resolve conflicts (multiple fields mapping to the same profile field key)
        # Group candidates by key
        by_key: dict[str, list] = {}
        for fg, key, score in candidates:
            by_key.setdefault(key, []).append((fg, score))

        for key, fgs_with_scores in by_key.items():
            # Pick highest score
            fgs_with_scores.sort(key=lambda x: x[1], reverse=True)
            winner_fg, winner_score = fgs_with_scores[0]
            profile_fields[key] = winner_fg
            logger.debug(
                f"FormMapper: [profile ] {key:<20s} ← label={winner_fg.label_raw!r} (Score: {winner_score})"
            )

            # Move losers to unmapped list to see if they fit questions
            for loser_fg, loser_score in fgs_with_scores[1:]:
                unmapped_fgs.append(loser_fg)

        # Classify remaining fields as questions or log as unmapped
        for fg in unmapped_fgs:
            indicators = _indicators(fg)
            if _is_question(fg, indicators):
                key = fg.label_raw or fg.name_attr or fg.placeholder or f"field_{id(fg)}"
                questions[key] = fg
                logger.debug(
                    f"FormMapper: [question] {key!r:<40s} type={fg.field_type}"
                )
            else:
                logger.debug(
                    f"FormMapper: [unmapped] label={fg.label_raw!r}  "
                    f"name={fg.name_attr!r}  id={fg.id_attr!r}  type={fg.field_type}"
                )

        logger.info(
            f"FormMapper: {len(profile_fields)} profile fields, "
            f"{len(questions)} questions detected."
        )
        return profile_fields, questions
