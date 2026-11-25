# Cinematic Horror Shorts — Direction D (Combined Horror)

This visual preset adapts the reusable style-reference principles from the public [hans-n8n terror-story workflow](https://github.com/hans1801/hans-n8n/tree/main/workflows/videos-terror-story) and its [image style-reference workflow](https://github.com/hans1801/hans-n8n/tree/main/workflows/videos-style-reference) to this engine's existing structured script pipeline.

## Visual identity

- Grounded, photorealistic cinematic horror with restrained surreal / graphic accents.
- Desaturated charcoal and blue-green shadows, cold moonlight, sickly amber practical lights, and rare restrained crimson accents.
- Deep but readable shadows, motivated lighting, negative space, volumetric haze, tactile surfaces, fine film grain, controlled halation, and cinematic depth.
- Atmosphere and implication over gratuitous gore; no default reliance on jump scares.
- Vertical 9:16 composition with the story clue readable on a phone screen.

## Continuity rules

Treat the selected style as a visual bible across all scenes. Keep recurring characters, wardrobe, props, locations, geography, lens character, lighting logic, and color grade consistent. The scene image must depict the exact event in its narration. A named object or clue should be the visual focal point when it drives the narration.

If a generation provider receives reference images, they are used only to guide palette, lighting, contrast, texture, atmosphere, grain, and detail. Do not copy their subjects, characters, poses, objects, framing, camera angles, layouts, or recognizable compositions. Each generated scene remains an original composition.

## Motion direction

Animate each scene as a restrained continuation of its still image: slow push-ins, subtle handheld drift, small human reactions, environmental movement, drifting dust, or motivated light changes. Avoid random camera shake, morphing, identity drift, teleporting subjects, and effects that contradict the narration.

## Narrative shape

The horror prompt uses a continuous creepypasta arc: hook, anomaly, false safety, escalation, and a final reveal caused by the original premise. It retains the engine's existing 12–16-scene structured script contract and roughly 60-second short-form target; it does not import the source workflow's four-scene schema or its n8n / Google Drive / ElevenLabs execution dependencies.

## Scope

This is a prompt and UI preset integration. It does not automatically download reference images, invoke n8n, call an external image/video provider, or publish content. Provider-side reference-image injection can be implemented separately once a supported image-generation path is selected.
