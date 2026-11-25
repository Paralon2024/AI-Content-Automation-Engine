from flows.image_content_generator.pipeline.prompt_base import constants


def test_horror_visual_style_is_available():
    style = constants.STYLE_DESCRIPTIONS["horror_cinematic"]

    assert "Combined Horror" in style
    assert "photorealistic cinematic horror" in style
    assert "gratuitous gore" in style


def test_horror_category_uses_horror_prompt_with_selected_style():
    template = constants.get_script_prompt_template(
        category="horror",
        style="stickman",
    )

    assert template is constants.HORROR_SCRIPT_PROMPT
    assert "STYLE-REFERENCE RULES" in template
    assert "STORY-TO-IMAGE FIDELITY" in template
    assert "12 to 16 scenes" in template


def test_horror_visual_style_uses_horror_prompt_even_for_custom_category():
    template = constants.get_script_prompt_template(
        category="science",
        style="horror_cinematic",
    )

    assert template is constants.HORROR_SCRIPT_PROMPT


def test_non_horror_projects_keep_existing_prompt():
    template = constants.get_script_prompt_template(
        category="finanzas",
        style="realistic",
    )

    assert template is constants.FORM_SCRIPT_PROMPT


def test_horror_prompt_formats_all_context_fields():
    prompt = constants.HORROR_SCRIPT_PROMPT.format(
        idea="A voicemail arrives from tomorrow",
        category_desc="psychological horror",
        tone_desc="quiet dread",
        aspect_ratio="9:16",
        style_desc=constants.STYLE_DESCRIPTIONS["horror_cinematic"],
    )

    assert "A voicemail arrives from tomorrow" in prompt
    assert "9:16" in prompt
    assert "Direction D / Combined Horror" in prompt
