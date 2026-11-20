"""
Template & Personalization Service.

Responsible for discovering templates in templates/, extracting placeholder tokens,
validating inputs, and personalizing both subject line and email body.
"""

import re
from pathlib import Path
from typing import Dict, Any, Tuple, List
from src.email_automation.config import settings


# Matches placeholders enclosed in braces, e.g. {name}, {company}
PLACEHOLDER_REGEX = re.compile(r"\{([a-zA-Z0-9_]+)\}")


class PersonalizationError(Exception):
    """Raised when required template placeholders cannot be resolved."""
    pass


class TemplateService:
    """Manages file-based email templates and rendering."""

    def __init__(self, templates_dir: Path = settings.TEMPLATES_DIR):
        self.templates_dir = templates_dir
        self.templates_dir.mkdir(parents=True, exist_ok=True)

    def list_templates(self) -> List[Dict[str, Any]]:
        """Scans the templates directory and returns metadata for all available templates."""
        templates = []
        for file_path in sorted(self.templates_dir.glob("*.txt")):
            content = file_path.read_text(encoding="utf-8")
            subject, body = self.parse_raw_content(content)
            placeholders = self.extract_placeholders(f"{subject}\n{body}")
            templates.append({
                "name": file_path.name,
                "file_path": str(file_path),
                "default_subject": subject,
                "body_preview": body[:140] + ("..." if len(body) > 140 else ""),
                "placeholders": sorted(list(placeholders))
            })
        return templates

    def get_template(self, template_name: str) -> Tuple[str, str]:
        """
        Loads and parses a template file by name.
        Returns:
            Tuple[subject, body]
        """
        # Sanitize against path traversal
        clean_name = Path(template_name).name
        file_path = self.templates_dir / clean_name
        if not file_path.exists():
            raise FileNotFoundError(f"Template '{template_name}' not found in {self.templates_dir}")
        content = file_path.read_text(encoding="utf-8")
        return self.parse_raw_content(content)

    @staticmethod
    def parse_raw_content(content: str) -> Tuple[str, str]:
        """
        Splits raw template content into subject and body.
        If the first line starts with 'Subject:', extracts it as subject.
        """
        lines = content.strip().splitlines()
        subject = "Notification"
        body_lines = []

        if lines and lines[0].lower().startswith("subject:"):
            subject = lines[0].split(":", 1)[1].strip()
            body_lines = lines[1:]
        else:
            body_lines = lines

        body = "\n".join(body_lines).strip()
        return subject, body

    @staticmethod
    def extract_placeholders(text: str) -> set:
        """Finds all placeholder variable names enclosed in curly braces {variable}."""
        return set(PLACEHOLDER_REGEX.findall(text))

    @classmethod
    def render(cls, template_text: str, context: Dict[str, Any], strict: bool = True) -> str:
        """
        Substitutes variables into template_text.
        If strict is True, raises PersonalizationError for any unsupplied placeholder.
        """
        placeholders = cls.extract_placeholders(template_text)
        missing = [p for p in placeholders if p not in context or context[p] is None]
        
        if strict and missing:
            raise PersonalizationError(
                f"Missing required fields for template placeholders: {', '.join(sorted(missing))}"
            )

        # Safe formatting with fallback for empty/missing non-strict values
        safe_context = {k: ("" if v is None else str(v)) for k, v in context.items()}
        try:
            return template_text.format_map(safe_context)
        except KeyError as e:
            raise PersonalizationError(f"Missing placeholder in context: {e}")

    @classmethod
    def personalize_email(
        cls,
        subject_template: str,
        body_template: str,
        contact_data: Dict[str, Any],
        strict: bool = True
    ) -> Tuple[str, str]:
        """
        Personalizes both the subject line and email body using contact field values.
        Returns (personalized_subject, personalized_body).
        """
        personalized_subject = cls.render(subject_template, contact_data, strict=strict)
        personalized_body = cls.render(body_template, contact_data, strict=strict)
        return personalized_subject, personalized_body
