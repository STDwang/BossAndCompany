"""Optional, versioned project classification for Company_Workspace PROJECT.json.

This is an INDEPENDENT schema layered on top of the base schema_version: 2.
Adding a classification object never changes the base schema or the bound
skill_version, so existing checkouts and data files stay valid.

A classification is authored by an explicit coordinator from read-only GitHub
metadata. It records public/closed-source showcase status, fork origin,
activity tier and star/push facts used to rank projects. It never carries
paths, emails, workspace ids or private repository content.
"""
from datetime import datetime, timezone

CLASSIFICATION_VERSION = 1

SHOWCASE_VALUES = ("public-source", "source-private", "none")
ACTIVITY_TIERS = ("active", "recent", "dormant")
VISIBILITIES = ("public", "private")
DATA_SOURCES = ("gh-api-readonly", "coordinator-reviewed")

REQUIRED_KEYS = (
    "showcase", "is_fork", "activity_tier", "stars", "pushed_at",
    "visibility", "reviewed_at", "data_source",
)


def activity_tier_from_pushed_at(pushed_at, now=None):
    """Derive the activity tier from a pushed_at timestamp.

    active: pushed within 30 days; recent: within 365 days; dormant: older.
    """
    if pushed_at is None:
        return "dormant"
    if not isinstance(pushed_at, str):
        raise ValueError("pushed_at must be an ISO 8601 string or null")
    try:
        moment = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("pushed_at must be ISO 8601") from None
    if moment.tzinfo is None:
        raise ValueError("pushed_at must include a timezone")
    reference = now or datetime.now(timezone.utc)
    age = (reference - moment).days
    if age <= 30:
        return "active"
    if age <= 365:
        return "recent"
    return "dormant"


def validate_classification(value):
    if not isinstance(value, dict):
        raise ValueError("classification must be an object")
    missing = [key for key in REQUIRED_KEYS if key not in value]
    if missing:
        raise ValueError("classification missing keys: " + ", ".join(missing))
    extra = [key for key in value if key not in REQUIRED_KEYS]
    if extra:
        raise ValueError("classification has unknown keys: " + ", ".join(extra))
    if value["showcase"] not in SHOWCASE_VALUES:
        raise ValueError("invalid classification showcase")
    if not isinstance(value["is_fork"], bool):
        raise ValueError("classification is_fork must be boolean")
    if value["activity_tier"] not in ACTIVITY_TIERS:
        raise ValueError("invalid classification activity_tier")
    stars = value["stars"]
    if isinstance(stars, bool) or not isinstance(stars, int) or stars < 0:
        raise ValueError("classification stars must be a non-negative integer")
    if value["visibility"] not in VISIBILITIES:
        raise ValueError("invalid classification visibility")
    if value["data_source"] not in DATA_SOURCES:
        raise ValueError("invalid classification data_source")
    reviewed = value["reviewed_at"]
    if not isinstance(reviewed, str):
        raise ValueError("classification reviewed_at must be a date string")
    try:
        datetime.strptime(reviewed, "%Y-%m-%d")
    except ValueError:
        raise ValueError("classification reviewed_at must be YYYY-MM-DD") from None
    pushed = value["pushed_at"]
    if pushed is not None:
        if not isinstance(pushed, str):
            raise ValueError("classification pushed_at must be ISO 8601 or null")
        try:
            moment = datetime.fromisoformat(pushed.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("classification pushed_at must be ISO 8601") from None
        if moment.tzinfo is None:
            raise ValueError("classification pushed_at must include a timezone")
    if stars > 0 and value["visibility"] == "private":
        raise ValueError("private repository star count is not a public fact")
    return True


def attach(project_record, classification):
    """Return a copy of a PROJECT.json record with a validated classification.

    Unknown keys on the source record are preserved. An existing classification
    is replaced only by a validated one of the same version.
    """
    if not isinstance(project_record, dict):
        raise ValueError("project record must be an object")
    validate_classification(classification)
    result = dict(project_record)
    result["classification_version"] = CLASSIFICATION_VERSION
    result["classification"] = dict(classification)
    return result


def sort_key(project_record):
    """Rank key: stars descending, then pushed_at descending, then slug ascending.

    Records without a classification sort last. Accepts a bare classification
    or a full PROJECT.json record.
    """
    classification = project_record.get("classification", project_record) if isinstance(project_record, dict) else None
    if not isinstance(classification, dict) or "stars" not in classification:
        return (0, datetime.min.replace(tzinfo=timezone.utc).timestamp(), "")
    pushed = classification.get("pushed_at")
    moment = (datetime.fromisoformat(pushed.replace("Z", "+00:00"))
              if pushed else datetime.min.replace(tzinfo=timezone.utc))
    return (-classification["stars"], -moment.timestamp(), str(classification.get("visibility", "")))


def from_github(repo_data, showcase="none", reviewed_at=None, is_fork=False):
    """Build a classification from read-only GitHub repository metadata."""
    pushed = repo_data.get("pushed_at")
    private = bool(repo_data.get("private"))
    value = {
        "showcase": showcase,
        "is_fork": bool(repo_data.get("fork", is_fork)),
        "activity_tier": activity_tier_from_pushed_at(pushed),
        "stars": int(repo_data.get("stars") or 0) if not private else 0,
        "pushed_at": pushed,
        "visibility": "private" if private else "public",
        "reviewed_at": reviewed_at or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "data_source": "gh-api-readonly",
    }
    validate_classification(value)
    return value
