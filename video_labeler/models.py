from dataclasses import dataclass


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
VIEW_TYPES = ("panorama", "closeup")
POLARITIES = ("pos", "neg")
LIGHTING_VALUES = ("daytime", "night_full_color", "night_black_white")


@dataclass(frozen=True)
class ProjectMetadata:
    date: str
    camera: str
    view: str
