from custom_components.motis.config_flows.errors.InvalidCredentialFormat import InvalidCredentialFormat

prefixes_by_field: dict[str, tuple[str, ...]] = {
    "url": ("url=",)
}

def sanitize_credential(field: str, value: str) -> str:
    """Ensure credentials do not contain whitespace noise or known prefixes."""
    cleaned = value.strip()
    if not cleaned or cleaned != value:
        raise InvalidCredentialFormat

    for prefix in prefixes_by_field.get(field, ()):
        if cleaned.lower().startswith(prefix.lower()):
            raise InvalidCredentialFormat

    return cleaned
