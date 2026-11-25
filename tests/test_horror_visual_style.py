import unittest

from flows.image_content_generator.pipeline.prompt_base import constants


class TestHorrorVisualStyle(unittest.TestCase):
    def test_horror_visual_style_is_available(self):
        style = constants.STYLE_DESCRIPTIONS["horror_cinematic"]

        self.assertIn("Combined Horror", style)
        self.assertIn("photorealistic cinematic horror", style)
        self.assertIn("gratuitous gore", style)

    def test_horror_category_uses_horror_prompt_with_selected_style(self):
        template = constants.get_script_prompt_template(
            category="horror",
            style="stickman",
        )

        self.assertIs(template, constants.HORROR_SCRIPT_PROMPT)
        self.assertIn("STYLE-REFERENCE RULES", template)
        self.assertIn("STORY-TO-IMAGE FIDELITY", template)
        self.assertIn("12 to 16 scenes", template)

    def test_horror_visual_style_uses_horror_prompt_even_for_custom_category(self):
        template = constants.get_script_prompt_template(
            category="science",
            style="horror_cinematic",
        )

        self.assertIs(template, constants.HORROR_SCRIPT_PROMPT)

    def test_non_horror_projects_keep_existing_prompt(self):
        template = constants.get_script_prompt_template(
            category="finanzas",
            style="realistic",
        )

        self.assertIs(template, constants.FORM_SCRIPT_PROMPT)

    def test_horror_prompt_formats_all_context_fields(self):
        prompt = constants.HORROR_SCRIPT_PROMPT.format(
            idea="A voicemail arrives from tomorrow",
            category_desc="psychological horror",
            tone_desc="quiet dread",
            aspect_ratio="9:16",
            style_desc=constants.STYLE_DESCRIPTIONS["horror_cinematic"],
        )

        self.assertIn("A voicemail arrives from tomorrow", prompt)
        self.assertIn("9:16", prompt)
        self.assertIn("Direction D / Combined Horror", prompt)


if __name__ == "__main__":
    unittest.main()
