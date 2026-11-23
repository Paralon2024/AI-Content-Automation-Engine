# Hans4 Studio (draft integration)

This optional feature adds a **local character bible and image-scene handoff** to the existing
Content Engine web dashboard. It does not replace or modify existing video workflows.

## Local setup

Run the repository's existing Docker Compose stack and open the web dashboard on
`http://localhost:5678`. Create or select an idea in the sidebar, then click
**Hans4 Studio** in the header.

Fill in:
- Protagonist name and detailed stable physical identity.
- Exact wardrobe and the consistent visual style (9:16).
- Google Drive file ID for the approved canonical protagonist image.
- Google Drive folder ID containing the nine approved style references.

Click **Save character bible**. Data is saved under
`flows/image_content_generator/out_short/ideas/idea_XXXXXX/hans4_character.json`
in the existing local project volume. It is not written to n8n, GitHub or Google Drive.

Write descriptions for four scenes, in order: Hook, Escalation, Chaos, Conclusion.
Click **Preview n8n image handoff** and copy the JSON. Supply a private output
Drive folder ID before using those inputs with the existing n8n image subworkflow.

### Existing n8n image subworkflow compatibility

Tested against **YT - Image Style Reference - Gemini**
(workflow ID `INg7VydBBxMD8DlT`) input fields:

`image_prompt`, `folder_reference_id`, `filename_output`,
`folder_output_id`, `character_image_id`, `character_bible`.

The handoff is an **export** for manual review, not a webhook or remote execution.
The canonical protagonist reference is applied to scenes 2–4 when populated;
scene 1 establishes the canonical identity. Review generated images for mismatches
before approving media creation.

### Security / rollout restrictions

The upstream application is currently a **local development app without authentication**.
Do not expose ports 5678 or 8000 to the public internet; the existing compose file
binds them to `127.0.0.1` for a reason. Do not paste API tokens in bible fields.

No new n8n workflows are activated. No media-generation, rendering, paid endpoints or
YouTube publishing is triggered by this dashboard. Port 10000 and the running
`hans4-worker.service` stay unchanged.

### What this does *not* yet implement

This is phase 1 of an integration. It does not yet provide an authenticated
n8n API proxy, automatic history/duplicate checks, images generated via Chrome Flow,
automatic multi-step story processing or a one-click render. These will require
separate authenticated service design and testing.
