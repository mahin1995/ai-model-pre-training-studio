from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, model_validator

PositiveNumber = Annotated[float, Field(gt=0, allow_inf_nan=False, strict=True)]
NonnegativeNumber = Annotated[float, Field(ge=0, allow_inf_nan=False, strict=True)]
PositiveInt = Annotated[StrictInt, Field(gt=0)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Hardware(Model):
    location: Literal["local", "cloud"] | None = None
    status: Literal["unknown", "entered"] = "unknown"
    gpuModel: StrictStr = ""
    gpuCount: PositiveInt | None = None
    vramPerGpuGb: PositiveNumber | None = None
    ramGb: PositiveNumber | None = None
    freeDiskGb: PositiveNumber | None = None


class Budget(Model):
    maxHours: PositiveNumber | None = None
    maxCost: NonnegativeNumber | None = None
    currency: Literal["USD", "BDT", "EUR", "GBP"] = "USD"


class Source(Model):
    id: Annotated[StrictStr, Field(min_length=1)]
    name: StrictStr = ""
    reference: StrictStr = ""
    language: StrictStr = ""
    permissionNote: StrictStr = ""
    permission: Literal["confirmed", "needs-review", "unknown"] = "unknown"


class SuccessCriteria(Model):
    qualityNotes: StrictStr = ""
    heldOutLoss: NonnegativeNumber | None = None
    perplexity: PositiveNumber | None = None
    maxLatencyMs: PositiveNumber | None = None
    maxMemoryGb: PositiveNumber | None = None


class Project(Model):
    id: UUID
    name: Annotated[StrictStr, Field(max_length=200)] = ""
    description: StrictStr = ""
    task: Literal["completion", "chatbot", "domain-assistant"] | None = None
    language: Literal["bn", "en", "mixed"] | None = None
    objective: StrictStr = ""
    hardware: Hardware = Field(default_factory=Hardware)
    budget: Budget = Field(default_factory=Budget)
    hasExistingData: StrictBool | None = None
    sources: list[Source] = Field(default_factory=list)
    successCriteria: SuccessCriteria = Field(default_factory=SuccessCriteria)
    status: Literal["draft", "scope-ready"] = "draft"
    updatedAt: StrictStr = ""
    revision: Annotated[StrictInt, Field(ge=0)] = 0

    @model_validator(mode="after")
    def require_ready_scope(self):
        if len({s.id for s in self.sources}) != len(self.sources):
            raise ValueError("Each data source must have a unique ID.")
        if self.status == "scope-ready":
            hardware = self.hardware
            complete = (
                self.name.strip() and self.task and self.language and self.objective.strip()
                and hardware.status == "entered" and hardware.location and hardware.gpuModel.strip()
                and hardware.gpuCount and hardware.vramPerGpuGb and hardware.ramGb and hardware.freeDiskGb
                and self.budget.maxHours is not None
                and (hardware.location != "cloud" or self.budget.maxCost is not None)
                and self.hasExistingData is not None and self.sources
                and all(s.name.strip() and s.reference.strip() and s.language.strip() and s.permissionNote.strip()
                        and s.permission == "confirmed" for s in self.sources)
                and self.successCriteria.qualityNotes.strip()
            )
            if not complete:
                raise ValueError("Complete all scope requirements and source permissions before marking scope ready.")
        return self
