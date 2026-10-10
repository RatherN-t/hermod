"""Tools the LLM can call. Each maps to a DB write, so the log is structured, not prose."""

TOOL_SPECS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "log_dose",
            "description": "Record what the patient said about a scheduled dose.",
            "parameters": {
                "type": "object",
                "properties": {
                    "medication": {"type": "string"},
                    "status": {"type": "string", "enum": ["taken", "late", "missed", "extra"]},
                    "when": {"type": "string", "description": "ISO time or 'this morning' etc."},
                    "note": {"type": "string"},
                },
                "required": ["medication", "status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "flag_issue",
            "description": "Raise something the doctor should review.",
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["missed_doses", "extra_dose", "side_effect", "stopped_early",
                                 "question_for_doctor"],
                    },
                    "severity": {"type": "string", "enum": ["info", "warning", "urgent"]},
                    "summary": {"type": "string"},
                },
                "required": ["kind", "severity", "summary"],
            },
        },
    },
]


def execute_tool(name: str, args: dict, patient_id: int) -> dict:
    raise NotImplementedError
