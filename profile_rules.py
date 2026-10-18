"""Conservative, vocabulary-free extraction of visible profile text."""
import re
 
 
SECTION_NAMES = {
    "about": "about", "summary": "about", "experience": "experience",
    "education": "education", "skills": "skills", "top skills": "skills",
    "certifications": "certifications", "licenses & certifications": "certifications",
    "licenses and certifications": "certifications", "languages": "languages",
    "projects": "projects", "publications": "publications",
    "volunteer experience": "volunteer_experience", "volunteering": "volunteer_experience",
    "honors & awards": "honors_and_awards", "honors and awards": "honors_and_awards",
    "courses": "courses", "organizations": "organizations",
    "recommendations": "recommendations", "interests": "interests",
    "accomplishments": "accomplishments", "personal information": "personal_information",
    "contact info": "contact_information", "contact information": "contact_information",
    "activity": "activity", "featured": "featured",
    "people also viewed": "people_also_viewed",
    "people you may know": "people_you_may_know",
}

DATE_RANGE = re.compile(
    r"^(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+)?"
    r"\d{4}\s*[-\u2013\u2014]\s*(?:Present|"
    r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+)?\d{4})",
    re.I,
)
CITY_NAME = re.compile(
    r"(?=.{1,18}\Z)[^\W\d_][^\W\d_.'-]*"
    r"(?: [^\W\d_][^\W\d_.'-]*)*\Z",
    re.UNICODE,
)
DEGREE_NAME = re.compile(
    r"^(?:B(?:achelor)?\.?\s*(?:A|S|Comm|Com|Sc|Eng)?|"
    r"M(?:aster)?\.?\s*(?:A|S|B|BA|Sc|Eng)?|"
    r"Ph\.?\s*D|Associate|Doctorate)(?:\b|$)",
    re.I,
)
EMPLOYMENT_TYPE = re.compile(
    r"^(?P<company>.+?)\s*\u00b7\s*"
    r"(?:Full-time|Part-time|Self-employed|Freelance|Contract|Internship|"
    r"Apprenticeship|Seasonal)(?:\s+(?:Full-time|Part-time|Self-employed|"
    r"Freelance|Contract|Internship|Apprenticeship|Seasonal))*$",
    re.I,
)
EMPLOYMENT_DURATION = re.compile(
    r"^(?:Full-time|Part-time|Self-employed|Freelance|Contract|Internship|"
    r"Apprenticeship|Seasonal)\s*\u00b7\s*\d+\s*(?:yr|mo)",
    re.I,
)
SECTION_LABELS = {
    "position title": "title",
    "job title": "title",
    "company name": "company",
    "company": "company",
    "dates employed and duration": "duration",
    "dates employed": "duration",
    "position location": "location",
    "position summary": "description",
    "school": "school",
    "school name": "school",
    "degree": "degree",
    "degree name": "degree",
    "field of study": "field",
    "dates attended or expected graduation": "dates",
    "dates attended": "dates",
    "grade": "grade",
    "activities and societies": "activities",
}


def section_name(line):
    label = re.sub(r"\s*\(\d+\)\s*$", "", line).casefold()
    return SECTION_NAMES.get(label)


def is_valid_city_name(value):
    """A Ceipal city must contain 1-18 characters and use words, not digits."""
    return isinstance(value, str) and bool(CITY_NAME.fullmatch(value.strip()))


def is_valid_state_name(value):
    """Reject education credentials accidentally extracted as a state."""
    return (
        isinstance(value, str)
        and 0 < len(value.strip()) <= 40
        and not re.search(r"\d", value)
        and not DEGREE_NAME.match(value.strip())
    )
 
 
def extract_sections(lines):
    """Keep complete section text; never guess job or education boundaries."""
    blocks = {}
    current = "header"
    for line in lines:
        heading = section_name(line)
        if heading:
            current = heading
            blocks.setdefault(current, [])
        else:
            blocks.setdefault(current, []).append(line)
    return {key: "\n".join(value) for key, value in blocks.items()}


def _date_indexes(lines):
    indexes = []
    for index, line in enumerate(lines):
        lowered = line.casefold()
        if lowered.startswith(("dates employed", "dates attended")):
            indexes.append(index)
        elif DATE_RANGE.match(line) and not (
            index > 0
            and lines[index - 1].casefold().startswith(
                ("dates employed", "dates attended")
            )
        ):
            indexes.append(index)
    return indexes


def _date_value(line, following):
    if DATE_RANGE.match(line):
        return line
    return following.strip() if following and DATE_RANGE.match(following.strip()) else ""


def _read_labeled_fields(lines, labels):
    values = {}
    for index, line in enumerate(lines):
        key = SECTION_LABELS.get(line.rstrip(":").strip().casefold())
        if key not in labels or index + 1 >= len(lines):
            continue

        if key in {"description", "activities"}:
            value_lines = []
            for value_line in lines[index + 1:]:
                if SECTION_LABELS.get(value_line.rstrip(":").strip().casefold()):
                    break
                value_lines.append(value_line.strip())
            value = "\n".join(value_lines)
        else:
            value = lines[index + 1].strip()
            if SECTION_LABELS.get(value.rstrip(":").strip().casefold()):
                continue
        if value:
            values[key] = value
    return values


def _clean_entry_lines(lines):
    return [
        line.strip()
        for line in lines
        if line.strip()
        and not re.fullmatch(r"(?:see more|show more|show all(?: \d+ .*)?)", line.strip(), re.I)
    ]


def parse_experience(text):
    """Extract distinct role, company, dates and description values."""
    lines = _clean_entry_lines(text.splitlines())
    date_indexes = _date_indexes(lines)
    if not date_indexes:
        return []

    entries = []
    start = 0
    for position, date_index in enumerate(date_indexes):
        end = date_index + 1
        if lines[date_index].casefold().startswith(("dates employed", "dates employed and duration")):
            date_value = _date_value(
                lines[date_index],
                lines[date_index + 1] if date_index + 1 < len(lines) else "",
            )
            if date_value:
                end += 1
        else:
            date_value = lines[date_index]

        boundary_end = (
            date_indexes[position + 1]
            if position + 1 < len(date_indexes)
            else len(lines)
        )
        section = lines[start:date_index]
        fields = _read_labeled_fields(
            section,
            {"title", "company", "location", "description"},
        )

        if not fields.get("title"):
            content = [
                line for line in section
                if SECTION_LABELS.get(line.rstrip(":").strip().casefold())
                not in {"title", "company", "location", "description"}
            ]
            if content:
                grouped_role = (
                    len(content) >= 3
                    and EMPLOYMENT_DURATION.match(content[-2])
                )
                match = EMPLOYMENT_TYPE.match(content[-1])
                if grouped_role:
                    fields["company"] = fields.get("company") or content[0]
                    fields["title"] = content[-1]
                elif match:
                    fields["company"] = fields.get("company") or match.group("company")
                    content.pop()
                elif len(content) >= 2:
                    fields["company"] = fields.get("company") or content.pop()
                if content and not fields.get("title"):
                    fields["title"] = content[-1]

        details_end = boundary_end
        if position + 1 < len(date_indexes):
            last_line = lines[boundary_end - 1] if boundary_end else ""
            prior_line = lines[boundary_end - 2] if boundary_end >= 2 else ""
            if EMPLOYMENT_TYPE.match(last_line):
                details_end = boundary_end - 2
            elif EMPLOYMENT_DURATION.match(prior_line):
                details_end = boundary_end - 3
            else:
                for index in range(end, boundary_end):
                    if SECTION_LABELS.get(lines[index].rstrip(":").strip().casefold()) in {
                        "title", "company"
                    }:
                        details_end = index
                        break
        details = lines[end:details_end]
        detail_fields = _read_labeled_fields(
            details,
            {"location", "description"},
        )
        fields["location"] = fields.get("location") or detail_fields.get("location", "")
        if detail_fields.get("description"):
            fields["description"] = detail_fields["description"]
        elif not fields.get("description"):
            consumed_values = {
                lines[index + 1].strip()
                for index, line in enumerate(details[:-1])
                if SECTION_LABELS.get(line.rstrip(":").strip().casefold())
                in {"location", "description"}
            }
            fields["description"] = "\n".join(
                line for line in details
                if SECTION_LABELS.get(line.rstrip(":").strip().casefold())
                not in {"location", "description"}
                and line not in consumed_values
            )

        entry = {
            "title": fields.get("title", ""),
            "company": fields.get("company", ""),
            "duration": date_value,
            "location": fields.get("location", ""),
            "description": fields.get("description", ""),
        }
        if any(entry.values()):
            entries.append(entry)
        start = end
    return entries


def parse_education(text):
    """Extract each school as its own education entry."""
    lines = _clean_entry_lines(text.splitlines())
    date_indexes = _date_indexes(lines)
    if not date_indexes:
        return []

    entries = []
    start = 0
    for date_index in date_indexes:
        section = lines[start:date_index]
        fields = _read_labeled_fields(
            section,
            {"school", "degree", "field", "grade", "activities"},
        )
        content = [
            line for line in section
            if SECTION_LABELS.get(line.rstrip(":").strip().casefold())
            not in {"school", "degree", "field", "grade", "activities"}
        ]
        if not fields.get("school") and content:
            fields["school"] = content[0]
        if not fields.get("degree") and len(content) > 1:
            fields["degree"] = content[1]
        date_line = lines[date_index]
        following = lines[date_index + 1] if date_index + 1 < len(lines) else ""
        dates = _date_value(date_line, following)

        entry = {
            "school": fields.get("school", ""),
            "degree": " · ".join(
                value for value in (fields.get("degree", ""), fields.get("field", ""))
                if value
            ),
            "dates": dates,
            "score": fields.get("grade", ""),
            "extra": fields.get("activities", ""),
        }
        if any(entry.values()):
            entries.append(entry)
        start = date_index + 1
        if lines[date_index].casefold().startswith("dates attended"):
            start += 1
    return entries


def parse_certifications(text):
    """Separate certification names, issuers, dates and credential details."""
    lines = _clean_entry_lines(text.splitlines())
    entries = []
    current = {}

    def save_current():
        if current.get("name") or current.get("issuer"):
            entries.append(dict(current))
        current.clear()

    for line in lines:
        lowered = line.casefold()
        if lowered.startswith(("issued by:", "issuing organization:")):
            current["issuer"] = line.split(":", 1)[1].strip()
        elif re.match(r"^issued(?:\s+date)?\s*:?\s*.+$", line, re.I):
            current["issued"] = re.sub(
                r"^issued(?:\s+date)?\s*:?\s*", "", line, flags=re.I
            )
        elif DATE_RANGE.fullmatch(line):
            current["issued"] = line
        elif lowered.startswith("credential id"):
            current["credential_id"] = line.split(":", 1)[-1].strip()
        elif lowered.startswith("credential url"):
            current["credential_url"] = line.split(":", 1)[-1].strip()
        elif lowered == "show credential":
            continue
        elif lowered in {"licenses & certifications", "certifications"}:
            continue
        elif not current.get("name"):
            current["name"] = line
        elif not current.get("issuer"):
            current["issuer"] = line
        else:
            save_current()
            current["name"] = line
    save_current()
    return entries


def build_profile(raw):
    sections = raw.get("public_sections", [])
    if not isinstance(sections, list) or not all(isinstance(s, str) for s in sections):
        raise ValueError("public_sections must be a list of strings")
    lines = [line.strip() for section in sections for line in section.splitlines() if line.strip()]
    if not lines:
        raise ValueError("No profile text available")
    if any(re.search(r"^sign in to linkedin(?: talent solutions)?$", line, re.I) for line in lines):
        raise ValueError("LinkedIn login page received instead of profile text")
    name = raw.get("name") or lines[0]
    if re.search(r"sign in|join linkedin|search results", name, re.I):
        raise ValueError("Profile identity unavailable")
    parts = name.split()
    result = {"first_name": " ".join(parts[:-1]) if len(parts) > 1 else name,
              "last_name": parts[-1] if len(parts) > 1 else None,
              "city": None, "state": None, "country": None, "job_title": None,
              "skills": [], "certifications": [], "extraction_method": "rules"}
    # Only the profile header can supply personal location, never job addresses.
    header = []
    for line in lines:
        if section_name(line):
            break
        header.append(line)
    for line in header:
        for segment in re.split(r"\s*[·•]\s*", line):
            location = segment.split("Contact Info")[0].strip()
            fields = [part.strip() for part in location.split(",")]
            if len(fields) != 3 or not all(fields):
                continue
            if any(x in location for x in ("|", "&")):
                continue
            # A school or award segment ("..., Global Campus (Cum Laude, 2009)")
            # also splits into three parts; a real location has no digits or notes.
            if any(re.search(r"[()\[\]\d]", field) for field in fields):
                continue
            if not is_valid_city_name(fields[0]) or not is_valid_state_name(fields[1]):
                continue
            result["city"], result["state"], result["country"] = fields
            break
        if result["city"]:
            break
    for index, line in enumerate(lines[:-1]):
        if line.casefold() == "position title":
            result["job_title"] = lines[index + 1]
            break
 
    seen = set()
    def add(skill, evidence, source):
        skill = skill.strip(" \t•,;:.")
        if not skill or len(skill) > 100 or len(skill.split()) > 12:
            return
        if "…" in skill or "..." in skill:
            return
        key = skill.casefold()
        if key not in seen:
            result["skills"].append({"skill": skill, "basis": "explicit",
                                     "source": source, "evidence": evidence})
            seen.add(key)
 
    in_skills = False
    for line in lines:
        if re.fullmatch(r"(?:Top\s+)?Skills(?:\s*\(\d+\))?", line, re.I):
            in_skills = True
            continue
        if in_skills:
            if section_name(line) or re.match(r"^Show (?:all|more)\b", line, re.I):
                in_skills = False
            elif (
                not re.search(r"endorse|^\d+$|see more|used at|associated with", line, re.I)
                and "\u00b7" not in line
                and not line.casefold().endswith(("company", "organization"))
            ):
                add(line, line, "skills")

    for skill in raw.get("skill_mentions", []):
        if isinstance(skill, dict) and skill.get("skill"):
            add(
                str(skill["skill"]),
                str(skill.get("evidence") or skill["skill"]),
                "skills",
            )
 
    # Language cues select arbitrary skill phrases, without a skill-name dictionary.
    cue = re.compile(r"\b(?:speciali[sz]ing in|expertise in|proficient in|skilled in|focusing on|work across)\s+(.+)", re.I)
    section_kind = "summary"
    for line in lines:
        heading = section_name(line)
        if heading:
            section_kind = {"about": "summary", "experience": "experience"}.get(heading, "other")
        if line.casefold() == "experience":
            section_kind = "experience"
        if re.match(r"^(Education|Skills|Accomplishments|Certifications|Interests|Personal Information)\b", line, re.I):
            section_kind = "other"
        if line.casefold() in ("about", "summary"):
            section_kind = "summary"
        if section_kind == "other":
            continue
        match = cue.search(line)
        if match:
            topics = re.split(r"[.!?](?:\s|$)|…|\.{3}|\bsee more\b", match.group(1), maxsplit=1)[0]
            for topic in re.split(r",\s*(?:and\s+)?|;|\s+and\s+|\s+&\s+", topics):
                add(topic, line, section_kind)
 
    sections = extract_sections(lines)
    result["name"] = name
    result["sections"] = sections
    result["raw_text"] = "\n".join(lines)
    result["about"] = sections.get("about", "")
    # Keep the complete sections above while exposing parsed entries separately.
    for field in set(SECTION_NAMES.values()) - {"about", "skills"}:
        text = sections.get(field, "")
        if field == "experience":
            result[field] = parse_experience(text) or ([text] if text else [])
        elif field == "education":
            result[field] = parse_education(text) or ([text] if text else [])
        elif field == "certifications":
            result[field] = parse_certifications(text) or ([text] if text else [])
        else:
            result[field] = [text] if text else []

    employer_names = {
        entry.get("company", "").strip().casefold()
        for entry in result.get("experience", [])
        if isinstance(entry, dict) and entry.get("company")
    }
    result["skills"] = [
        skill for skill in result["skills"]
        if skill["skill"].casefold() not in employer_names
    ]

    summary = [sections.get("header") or name]
    for field, text in sections.items():
        if text and field not in {"people_also_viewed", "people_you_may_know", "header"}:
            summary.append(f"{field.replace('_', ' ').title()}\n{text}")
    result["full_summary"] = "\n\n".join(summary)
    return result