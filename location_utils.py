"""Keep only supplied geographic components, excluding missing-value markers."""
import re


def clean_location_parts(value):
    parts = []
    missing = {"na", "none", "null", "unknown", "unspecified", "notavailable",
               "notapplicable", "remote", "remotejob", "hybrid", "onsite", "tbd"}
    for part in str(value or "").split(","):
        part = " ".join(part.split()).strip()
        key = re.sub(r"[^a-z0-9]", "", part.casefold())
        if key and key not in missing:
            parts.append(part)
    return parts


def clean_location(value):
    return ", ".join(clean_location_parts(value))
