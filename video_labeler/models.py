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
REVIEW_STATUSES = ("pending", "approved", "needs_fix", "rejected")
REVIEW_STATUS_LABELS = {
    "pending": "待审核",
    "approved": "通过",
    "needs_fix": "需修正",
    "rejected": "剔除",
}
STRATUM_VALUES = ("easy_pos", "hard_pos", "easy_neg", "hard_neg", "pending_review")
STRATUM_LABELS = {
    "easy_pos": "简单正向",
    "hard_pos": "困难正向",
    "easy_neg": "简单负向",
    "hard_neg": "困难负向",
    "pending_review": "待复核",
}


@dataclass(frozen=True)
class ProjectMetadata:
    date: str
    camera: str
    view: str


@dataclass
class EventRecord:
    event_type: str = ""
    start_time_ms: int = 0
    end_time_ms: int = 0


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
    data_stratum: str = ""
    events: list[EventRecord] = field(default_factory=list)
