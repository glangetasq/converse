from pathlib import Path
from string import Template


def get_prompt_template(path: Path, required_fields: list[str] | None = None) -> Template:
    required_fields = required_fields or []
    template = path.read_text(encoding="utf-8")
    prompt_template = Template(template)
    assert prompt_template.is_valid(), f"Invalid prompt template: {path}"

    expected_fields = set(required_fields)
    actual_fields = set(prompt_template.get_identifiers())
    missing_fields = expected_fields - actual_fields
    extra_fields = actual_fields - expected_fields

    assert not missing_fields, f"Missing prompt fields in {path}: {sorted(missing_fields)}"
    assert not extra_fields, f"Unexpected prompt fields in {path}: {sorted(extra_fields)}"
    return prompt_template
