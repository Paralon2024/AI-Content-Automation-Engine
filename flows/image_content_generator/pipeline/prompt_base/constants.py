# flake8: noqa: E501

# ====================================================================================
# FORM-BASED GENERATION
# ====================================================================================

STYLE_DESCRIPTIONS: dict[str, str] = {
    "stickman": "Dynamic hand-drawn 2D webcomic sketch style, thick expressive black ink outlines, vibrant minimalist color palette for highlights, clean shading, white background with glowing accents.",
    "realistic": "Photorealistic cinematic style, high-detail rendering, natural dramatic lighting, professional photography quality, sharp focus, rich cinematic color grading.",
    "anime": "Japanese anime style, bold clean outlines, vibrant saturated colors, expressive character designs, dynamic composition, cel-shading with smooth gradients.",
    "watercolor": "Soft watercolor painting style, loose expressive brushstrokes, translucent overlapping color washes, gentle pastel palette, visible paper texture, dreamy and artistic feel.",
    "flat": "Clean modern flat design style, geometric simplified shapes, bold solid colors, minimal shadows, simple iconographic characters, professional and contemporary look.",
}

TONE_DESCRIPTIONS: dict[str, str] = {
    "motivacional": "motivational and energetic, with urgency and conviction that inspires immediate action",
    "educativo": "educational and clear, with precise explanations and concrete examples, using the tone of an expert mentor",
    "dramatico": "dramatic and tense, with suspenseful storytelling, unexpected twists, and strong emotional impact",
    "entretenimiento": "entertaining and dynamic, with a fast pace, surprising moments, and continuous engagement",
    "inspiracional": "inspirational and emotional, with stories of overcoming challenges, universal values, and a powerful message",
}

CATEGORY_DESCRIPTIONS: dict[str, str] = {
    "finanzas": "personal finance — money, investing, saving, and financial freedom",
    "horror": "psychological horror — suspense, fears, unexplained phenomena, and disturbing stories",
    "motivacion": "personal growth — growth mindset, discipline, and achieving goals",
    "historia": "historical events — fascinating people and events that changed the world",
    "ciencia": "science and technology — discoveries, innovation, and fascinating facts about the universe",
}

FORM_SCRIPT_PROMPT: str = """# 🎬 SHORT-FORM VIDEO SCRIPT GENERATOR

## CREATION CONTEXT
**Core idea:** {idea}
**Category:** {category_desc}
**Narrative tone:** {tone_desc}
**Video format:** {aspect_ratio}

## VISUAL STYLE (REQUIRED FOR EVERY image_prompt)
Use EXACTLY this style in the `style` field of every scene:
`{style_desc}`
Use EXACTLY this aspect_ratio in the `aspect_ratio` field of every scene:
`{aspect_ratio}`

## REQUIRED SCRIPT STRUCTURE
1. **Act 1 — Hook [Scenes 1–4]:** Stop the scroll within the first 3 seconds. Open with a compelling version of the core idea.
2. **Act 2 — Development [Scenes 5–10]:** Develop the idea with valuable information, facts, or engaging storytelling.
3. **Act 3 — Closing [Scene 11 to the end]:** Deliver a powerful conclusion with a call to action or memorable final reflection.

## REQUIRED RULES

### NARRATION
- Use short, direct sentences with pacing that matches the requested tone.
- The `narration` field must always be written in **ENGLISH**.
- Use no more than one narration sentence per scene.

### IMAGE AND VIDEO
- Write `image_prompt` fields (subjects, environment, lighting, composition, and style) in **ENGLISH**.
- Write `video_prompt` fields (motion, camera_movement, transition, and duration_hint) in **ENGLISH**.
- The `image_prompt` must visually illustrate the narration.
- Images must show coherent narrative progression.

### STRUCTURE
- Include **12 to 16 scenes**.
- Number scenes sequentially, starting at 1.
"""

# ====================================================================================
# JSON SCHEMAS
# ====================================================================================


CHUNK_INSTRUCTIONS: str = """
---
## 🎬 CONTINUITY INSTRUCTIONS (SCENE MODULE)
You are currently generating one section of the complete script.

**SCENE RANGE:** You MUST generate exactly the scenes from **{start_scene} through {end_scene}**.

**PREVIOUS STORY CONTEXT:**
{context}

**CONTINUITY RULE:** Ensure the transition from the last known scene to the new scene ({start_scene}) is smooth and logical, while preserving the same cinematic atmosphere. Do not repeat scenes; continue the story and keep the numbering sequential.
---
"""

# ====================================================================================
# CORE PROMPTS
# ====================================================================================

AUDIO_PROMPT: str = """Narrate the following script with a clear, expressive, and engaging voice. Adapt the delivery to the content: increase intensity for dramatic material, maintain a steady and confident pace for educational material, and convey energy and conviction for motivational material. Read the text exactly as written, without omitting or adding anything:

{audio_text}"""

ALIGNMENT_PROMPT: str = """# 🧠 MASTER PROMPT — AUDIO AND TEXT ALIGNMENT

You are an expert in audio-to-text alignment. Your task is to identify the exact start and end times for each script scene based on the Whisper transcription data.

---

## 🔹 WHISPER DATA (WITH TIMESTAMPS)
{whisper_data}

---

## 📝 ORIGINAL SCRIPT (SCENES)
{scenes_data}

---

## 📋 INSTRUCTIONS (CRITICAL)
1. Return exactly {expected_count} scenes in the JSON.
2. For each scene, identify its start time (`start_time`) and end time (`end_time`) in the audio.
3. Scene 1 usually starts at 0.000 seconds.
4. The end of one scene must match the start of the next scene.
5. Be precise. Ignore minor wording differences between the script and the audio.
6. Respond exclusively in JSON format.

## 📦 OUTPUT FORMAT (JSON)
Respond exclusively using the following JSON schema:
```json
{{
  "alignments": [
    {{
      "scene_number": 1,
      "start_time": 0.000,
      "end_time": 5.452
    }},
    ...
  ]
}}
```
"""
