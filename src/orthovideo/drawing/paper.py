PAPER_SIZES_MM = {
    "A4": (210.0, 297.0),
    "A3": (297.0, 420.0),
    "A2": (420.0, 594.0),
    "A1": (594.0, 841.0),
    "A0": (841.0, 1189.0),
}


def get_paper_size(
    format_name: str,
    orientation: str,
) -> tuple[float, float]:

    name = format_name.upper()

    if name not in PAPER_SIZES_MM:
        raise ValueError(
            f"Formato foglio non supportato: {format_name}"
        )

    width, height = PAPER_SIZES_MM[name]

    orientation = orientation.lower()

    if orientation == "portrait":
        return (
            min(width, height),
            max(width, height),
        )

    if orientation == "landscape":
        return (
            max(width, height),
            min(width, height),
        )

    raise ValueError(
        "orientation deve essere "
        "'portrait' oppure 'landscape'."
    )