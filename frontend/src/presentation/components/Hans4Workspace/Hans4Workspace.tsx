import { useEffect, useState } from 'react'

type Bible = {
  name: string
  identity: string
  wardrobe: string
  style_rules: string
  canonical_image_id: string
  style_reference_folder_id: string
}

const defaultBible: Bible = {
  name: '', identity: '', wardrobe: '',
  style_rules: '2D hand-inked horror comic, teal and indigo ink, amber practical lighting, vertical 9:16; no words, watermarks or logos.',
  canonical_image_id: '', style_reference_folder_id: '',
}
const blankScenes = ['', '', '', '']
const fieldNames: { key: keyof Bible; label: string; hint: string }[] = [
  { key: 'name', label: 'Protagonist name', hint: 'e.g. Elias' },
  { key: 'identity', label: 'Identity lock', hint: 'Age, face, hairstyle, skin tone, distinctive features' },
  { key: 'wardrobe', label: 'Wardrobe lock', hint: 'Exact jacket, cap, accessories, and colors' },
  { key: 'style_rules', label: 'Visual style lock', hint: 'Art style, lighting, palette, aspect ratio' },
  { key: 'canonical_image_id', label: 'Character reference image Drive ID', hint: 'ID only, not a public URL' },
  { key: 'style_reference_folder_id', label: 'Nine style-reference folder Drive ID', hint: 'ID only' },
]
const shell: React.CSSProperties = { display: 'grid', gap: 12, maxWidth: 820 }
const inputStyle: React.CSSProperties = {
  width: '100%', background: '#171727', color: '#ece9ff', border: '1px solid #3c3952',
  borderRadius: 8, padding: 10, font: 'inherit', boxSizing: 'border-box',
}
const buttonStyle: React.CSSProperties = {
  background: '#6456b6', border: 0, borderRadius: 8, color: 'white',
  padding: '10px 16px', cursor: 'pointer', fontWeight: 600,
}

export default function Hans4Workspace({ ideaId, onClose }: { ideaId: number; onClose: () => void }) {
  const [bible, setBible] = useState<Bible>(defaultBible)
  const [scenes, setScenes] = useState<string[]>(blankScenes)
  const [status, setStatus] = useState('Loading this idea’s character bible…')
  const [busy, setBusy] = useState(false)
  const [handoff, setHandoff] = useState('')
  const endpoint = `/api/hans4/ideas/${ideaId}`

  useEffect(() => {
    let active = true
    setHandoff('')
    setScenes(['', '', '', ''])
    fetch(`${endpoint}/character`)
      .then(async r => { if (!r.ok) throw new Error(await r.text()); return r.json() as Promise<Bible> })
      .then(data => { if (active) { setBible(data); setStatus('Character bible loaded (local storage).') } })
      .catch(e => { if (active) setStatus(`Unable to load character bible: ${String(e)}`) })
    return () => { active = false }
  }, [endpoint])

  async function save() {
    setBusy(true)
    try {
      const r = await fetch(`${endpoint}/character`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(bible),
      })
      if (!r.ok) throw new Error(await r.text())
      setStatus('Character bible saved locally. No media created.')
    } catch (e) { setStatus(`Save failed: ${String(e)}`) }
    finally { setBusy(false) }
  }

  async function preview() {
    setBusy(true)
    try {
      const r = await fetch(`${endpoint}/handoff`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenes: scenes.map((description, i) => ({ step: i + 1, description })) }),
      })
      if (!r.ok) throw new Error(await r.text())
      const result = await r.json()
      setHandoff(JSON.stringify(result, null, 2))
      setStatus('Four-scene n8n handoff prepared. Preview only; no workflow triggered.')
    } catch (e) { setStatus(`Handoff validation failed: ${String(e)}`) }
    finally { setBusy(false) }
  }

  return <section style={shell} aria-label="Hans4 horror character workspace">
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'center' }}>
      <div>
        <h2 style={{ margin: '0 0 4px' }}>Hans4 · Character Bible</h2>
        <p style={{ margin: 0, opacity: 0.75 }}>Idea #{ideaId} · Four 15-second scenes · Manual review</p>
      </div>
      <button type="button" style={buttonStyle} onClick={onClose}>Back to idea</button>
    </div>
    <p style={{ padding: 12, border: '1px solid #3c3952', borderRadius: 8, margin: 0 }}>
      This workspace saves a stable identity and prepares JSON inputs for the existing n8n image subworkflow.
      It does <strong>not</strong> generate images, trigger paid workflows, or publish videos.
    </p>
    {fieldNames.map(f => <label key={f.key} style={{ display: 'grid', gap: 5 }}>
      <span style={{ fontWeight: 600 }}>{f.label}</span>
      {(['identity', 'wardrobe', 'style_rules'] as string[]).includes(f.key) ?
        <textarea style={inputStyle} rows={3} placeholder={f.hint} value={bible[f.key]}
          onChange={e => setBible(prev => ({ ...prev, [f.key]: e.target.value }))} /> :
        <input style={inputStyle} placeholder={f.hint} value={bible[f.key]}
          onChange={e => setBible(prev => ({ ...prev, [f.key]: e.target.value }))} />}
    </label>)}
    <button type="button" style={{ ...buttonStyle, justifySelf: 'start' }} onClick={save} disabled={busy}>
      Save character bible
    </button>
    <h3 style={{ marginBottom: 0 }}>Scene image prompts</h3>
    {scenes.map((v, i) => <label key={i} style={{ display: 'grid', gap: 5 }}>
      <span>Scene {i + 1} — {['The Hook', 'The Escalation', 'The Chaos', 'The Conclusion'][i]}</span>
      <textarea style={inputStyle} rows={3} value={v}
        placeholder="Describe the scene, environment, character and camera angle (15 characters minimum)"
        onChange={e => setScenes(prev => prev.map((s, k) => k === i ? e.target.value : s))} />
    </label>)}
    <button type="button" style={{ ...buttonStyle, justifySelf: 'start' }} onClick={preview} disabled={busy}>
      Preview n8n image handoff
    </button>
    <p role="status" style={{ opacity: 0.8, margin: 0 }}>{status}</p>
    {handoff && <>
      <p style={{ marginBottom: 0 }}>Review the JSON before running n8n. Fill <code>folder_output_id</code> with the private Drive destination.</p>
      <textarea aria-label="n8n handoff JSON" readOnly style={{ ...inputStyle, fontFamily: 'monospace' }} rows={14} value={handoff} />
      <button type="button" style={{ ...buttonStyle, justifySelf: 'start' }}
        onClick={() => navigator.clipboard.writeText(handoff).then(() => setStatus('Handoff JSON copied.')).catch(() => setStatus('Clipboard unavailable; select the JSON above to copy.'))}>
        Copy handoff JSON
      </button>
    </>}
  </section>
}
