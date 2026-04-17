from datetime import datetime


TERM_STRUCTURES = {
    "semester": {
        "label": "Semester",
        "terms": ["Semester 1", "Semester 2"],
        "calendar": {
            "Semester 1": "September to May",
            "Semester 2": "May to August",
        },
    },
    "trimester": {
        "label": "Trimester",
        "terms": ["Trimester 1", "Trimester 2", "Trimester 3"],
        "calendar": {
            "Trimester 1": "September to December",
            "Trimester 2": "January to April",
            "Trimester 3": "May to August",
        },
    },
}

MAX_UNITS_PER_TERM = 7


def get_default_academic_year(reference_date=None):
    reference_date = reference_date or datetime.utcnow()
    start_year = reference_date.year if reference_date.month >= 9 else reference_date.year - 1
    return f"{start_year}/{start_year + 1}"


def get_term_types():
    return [(key, value["label"]) for key, value in TERM_STRUCTURES.items()]


def get_term_choices(term_type=None):
    if term_type and term_type in TERM_STRUCTURES:
        return TERM_STRUCTURES[term_type]["terms"]

    choices = []
    for definition in TERM_STRUCTURES.values():
        choices.extend(definition["terms"])
    return choices


def get_term_calendar():
    rows = []
    for key, definition in TERM_STRUCTURES.items():
        rows.append(
            {
                "term_type": key,
                "label": definition["label"],
                "terms": [
                    {"name": term_name, "window": definition["calendar"][term_name]}
                    for term_name in definition["terms"]
                ],
            }
        )
    return rows


def normalize_term_type(term_type):
    value = (term_type or "").strip().lower()
    return value if value in TERM_STRUCTURES else ""


def validate_term_selection(term_type, term_name):
    normalized_type = normalize_term_type(term_type)
    if not normalized_type:
        return False

    return (term_name or "").strip() in TERM_STRUCTURES[normalized_type]["terms"]
