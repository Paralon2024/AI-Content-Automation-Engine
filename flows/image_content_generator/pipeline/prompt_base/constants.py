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
    "horror_cinematic": (
        "Direction D — Combined Horror: premium photorealistic cinematic horror blended with "
        "restrained surreal and graphic-novel accents. Tactile real-world textures, oppressive "
        "negative space, unsettling silhouettes, subtle visual distortions, deep layered shadows, "
        "volumetric haze, practical motivated lighting, desaturated charcoal and blue-green "
        "shadows, cold moonlight, sickly amber practical highlights, and rare restrained crimson "
        "accents. Fine film grain, controlled halation, anamorphic depth, high contrast without "
        "crushing important details. Terrifying through atmosphere, composition and implication, "
        "never through gratuitous gore."
    ),
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
    "horror": "psychological and supernatural horror — suspense, dread, uncanny events, isolation, and disturbing reveals",
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

HORROR_SCRIPT_PROMPT: str = """# 🎬 CINEMATIC HORROR SHORTS — STORY AND VISUAL GENERATOR

## CREATION CONTEXT
**Core idea:** {idea}
**Category:** {category_desc}
**Narrative tone:** {tone_desc}
**Video format:** {aspect_ratio}
**Global visual direction:** {style_desc}

## VISUAL BIBLE — APPLY TO EVERY SCENE
Treat the global visual direction as a locked visual bible, not a loose suggestion.
- Repeat the exact same visual identity in the `style` field of every scene.
- Keep the protagonist's face, age range, hair, build, wardrobe, and defining details consistent. If the protagonist is not visible, preserve the identity of recurring props and locations.
- Keep geography, room layout, time of night, weather, lens character, contrast, film grain, and color grade coherent between adjacent scenes.
- Use a consistent cinematic horror language: motivated practical light, deep but readable shadows, layered darkness, atmospheric haze, tactile surfaces, restrained highlights, and deliberate negative space.
- Direction D / Combined Horror means grounded cinematic realism with subtle surreal or graphic accents. Do not turn the whole image into cartoon, anime, fantasy concept art, or generic neon cyberpunk.
- Frame for vertical `{aspect_ratio}`; keep the important subject and story clue readable on a phone screen.
- No captions, lettering, logos, watermarks, UI overlays, or random decorative symbols inside generated images.

## STYLE-REFERENCE RULES
If style-reference images are supplied by the image-generation provider, use them ONLY to guide the shared art direction: palette, lighting, contrast, texture, atmosphere, grain, and level of detail.
Do NOT copy a reference image's character, subject, object, pose, camera angle, framing, layout, or recognizable composition. Every scene must be an original composition that depicts this story's actual events.
Do not claim that reference images were supplied when none are available.

## STORY DESIGN — CREEPYPASTA / CINEMATIC HORROR
Build one continuous, believable short horror story from the core idea. The audience should feel that the event could happen to them.
Use a clear escalating arc across the scenes:
1. **The Hook:** a mundane, relatable detail becomes subtly wrong in the first moments.
2. **The Anomaly:** introduce a specific visual or audible clue that cannot be comfortably explained.
3. **False Safety:** offer a plausible explanation or apparent resolution; let tension briefly breathe.
4. **The Escalation:** reveal evidence that the explanation is incomplete or impossible.
5. **The Final Reveal:** deliver a disturbing consequence directly caused by the original premise. The ending must reframe earlier details and feel inevitable in hindsight.

The final reveal must be a consequence of the core idea, never a random monster, unrelated jump scare, moral lesson, or vague philosophical statement. Keep exposition minimal and let images, sound cues, and concrete details carry the dread.

## NARRATION AND PACING
- Write in natural, intimate, believable English, as if recounting something that really happened.
- Use concise lines, one narration sentence per scene; avoid purple prose and long explanations.
- Create a strong opening hook immediately. Escalate tension scene by scene and reserve the strongest information for the final reveal.
- Include **12 to 16 scenes** for a roughly 60-second short. Number scenes sequentially from 1.
- Every scene must advance the story or deepen the audience's understanding; do not pad with interchangeable atmosphere shots.

## IMAGE PROMPT — STORY-TO-IMAGE FIDELITY
- The image must depict the exact moment described by that scene's narration, not a loosely related horror image.
- Priority: **narrated event → story-relevant object or presence → protagonist reaction (only when useful)**.
- If narration mentions a phone, doorway, mirror, chair, window, photograph, shadow, or other specific clue, make that clue visually legible and central to the composition.
- The protagonist may be shown directly, as a partial figure, as a silhouette, from behind, or remain off-camera when the object is the stronger focal point.
- Never invent a creature, weapon, injury, symbol, or supernatural event that the narration does not establish.
- Describe subject, action, environment, lighting, composition, and the exact visual style in concrete production-ready English.

## VIDEO PROMPT — CONTROLLED CINEMATIC MOTION
- Animate the still image as a short, physically plausible continuation of the exact scene.
- Specify subject motion, subtle acting, environmental motion, camera movement, and transition.
- Favor restrained motion: slow push-ins, creeping lateral tracks, slight handheld drift, a delayed head turn, curtain movement, flickering practical light, drifting dust, or a shadow changing by a small amount.
- Use sudden movement only when the story earns it. Avoid random shaking, constant zooming, morphing faces, melting architecture, flicker artifacts, teleporting subjects, or changing wardrobe/identity.
- Preserve the composition and visual identity of the source image throughout the clip.

## QUALITY CHECK BEFORE RETURNING
1. Does every image depict its narration literally and clearly?
2. Does the same protagonist, key prop, and location remain consistent wherever they recur?
3. Does the visual language remain coherent across all scenes?
4. Are style references used only for aesthetic guidance, never copied as scene content?
5. Does the final reveal follow directly from the premise and reinterpret earlier clues?
6. Does every video prompt describe controlled motion that can plausibly animate its image?

If any answer is NO, revise the script before returning it. Return only data matching the required JSON schema.
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

AUDIO_PROMPT: str = """{audio_text}"""

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
