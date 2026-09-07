from dataclasses import dataclass, field


BEHAVIOR_LABELS = (
    "strangers_climbs",
    "strangers_linger",
    "strangers_peep_car",
    "strangers_pick_up_packages",
    "fall",
    "cat_come",
    "cat_out",
    "dog_come",
    "dog_out",
    "pool",
)
VIEW_TYPES = ("panorama", "closeup", "indoor")
POLARITIES = ("pos", "neg")
LIGHTING_VALUES = ("daytime", "night_full_color", "night_black_white")


@dataclass(frozen=True)
class ProjectMetadata:
    date: str
    camera: str
    view: str


@dataclass
class ClipRecord:
    source: str
    start_seconds: float
    end_seconds: float
    output: str
    behaviors: tuple[str, ...] = ()
    polarity: str = ""
    lighting: str = ""
    sequence: int = 0
    status: str = "queued"
    error: str = ""
    note: str = ""
    review_status: str = "pending"
    reviewer: str = ""
    reviewed_at: str = ""
    review_comment: str = ""
    rejection_reason: str = ""
    review_history: list[dict[str, str]] = field(default_factory=list)
