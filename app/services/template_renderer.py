from pathlib import Path


def render_template(template_path: str, context: dict) -> str:
    template = Path(template_path).read_text(encoding="utf-8")

    for key, value in context.items():
        placeholder = "{{" + key + "}}"
        template = template.replace(placeholder, str(value))

    return template