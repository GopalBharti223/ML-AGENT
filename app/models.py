from typing import List, Optional

from pydantic import (
    BaseModel,
    Field,
    field_validator
)


class FactCheck(BaseModel):

    is_accurate: bool

    discrepancies: str = ""


class ScriptScene(BaseModel):

    scene_number: int = Field(
        ge=1
    )

    duration: float = Field(
        gt=0
    )

    narration: str = ""

    visual_description: str = ""

    text_overlay: str = ""

    chart_type: Optional[str] = None

    scene_purpose: Optional[str] = None

    visual_emphasis: Optional[str] = None

    highlight_countries: List[str] = Field(
        default_factory=list
    )

    important_year: Optional[int] = None

    important_value: Optional[float] = None

    pacing_hint: Optional[str] = None


class VideoScript(BaseModel):

    title: str

    topic: str

    category: str

    indicator_name: str

    total_duration: int = Field(
        ge=10,
        le=300
    )

    scenes: List[ScriptScene] = Field(
        min_length=3,
        max_length=10
    )

    fact_check: FactCheck

    source_name: str

    source_url: str

    chart_type: Optional[str] = None

    indicator_code: Optional[str] = ""

    # Retention feedback loop: hook style chosen at prompt
    # build time (script.py).  Flows into script.json and
    # video_history.hook_style via run.py's save_record.
    # Optional so older constructed scripts stay valid.
    hook_style: Optional[str] = None

    # ---------------------------------------------------------
    # VALIDATE SCENE NUMBERS
    # ---------------------------------------------------------

    @field_validator("scenes")
    @classmethod
    def validate_scene_numbers(cls, scenes):

        expected = list(
            range(
                1,
                len(scenes) + 1
            )
        )

        actual = [
            scene.scene_number
            for scene in scenes
        ]

        if actual != expected:

            raise ValueError(
                "Scene numbers must be sequential "
                "starting from 1."
            )

        return scenes
