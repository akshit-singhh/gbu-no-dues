from enum import Enum

class OverallApplicationStatus(str, Enum):
    Pending = "Pending"
    InProgress = "InProgress"
    Completed = "Completed"
    Rejected = "Rejected"
