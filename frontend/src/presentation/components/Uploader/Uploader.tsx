import { useState, useRef } from 'react'
import {
  UploaderRoot, DropZone, DropHint, DropIcon, DropLabel, DropSmall,
  FileList, FileItem, SceneNum, FileName, FileSize, RemoveBtn, AddMoreBtn, UploadBtn,
} from './Uploader.styled'

interface UploaderProps {
  ideaId: number
  endpoint?: string
  accept?: string
  label?: string
  hint?: string
  onUploaded: () => void
}

export default function Uploader({
  ideaId,
  endpoint = 'videos',
  accept = '.mp4',
  label,
  hint,
  onUploaded,
}: UploaderProps) {
  const [files, setFiles] = useState<File[]>([])
  const [uploading, setUploading] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const acceptedExts = accept.split(',').map(e => e.trim().replace('.', ''))

  function addFiles(incoming: FileList | null) {
    if (!incoming) return
    setUploadError(null)
    const filtered = Array.from(incoming).filter(f =>
      acceptedExts.some(ext => f.name.toLowerCase().endsWith(`.${ext}`))
    )
    setFiles(prev => {
      const names = new Set(prev.map(f => f.name))
      return [...prev, ...filtered.filter(f => !names.has(f.name))]
    })
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragging(false)
    addFiles(e.dataTransfer.files)
  }

  function removeFile(name: string) {
    setFiles(prev => prev.filter(f => f.name !== name))
  }

  async function handleUpload() {
    if (!files.length) return
    setUploading(true)
    const sorted = [...files].sort((a, b) => a.name.localeCompare(b.name))
    const form = new FormData()
    sorted.forEach(f => form.append('files', f))
    setUploadError(null)
    try {
      const response = await fetch(`/api/ideas/${ideaId}/${endpoint}`, { method: 'POST', body: form })
      const payload = await response.json().catch(() => ({})) as { detail?: unknown }
      if (!response.ok) {
        const detail = typeof payload.detail === 'string'
          ? payload.detail
          : `Upload failed (HTTP ${response.status})`
        throw new Error(detail)
      }
      setFiles([])
      onUploaded()
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : 'Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  const sorted = [...files].sort((a, b) => a.name.localeCompare(b.name))

  return (
    <UploaderRoot>
      <DropZone
        $dragging={dragging}
        $hasFiles={files.length > 0}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => !files.length && inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={accept}
          style={{ display: 'none' }}
          onChange={e => addFiles(e.target.files)}
        />

        {files.length === 0 ? (
          <DropHint>
            <DropIcon>🎬</DropIcon>
            <DropLabel>{label ?? 'Drag and drop files here or click to select'}</DropLabel>
            <DropSmall>{hint ?? `Files: ${accept} — sorted by filename`}</DropSmall>
          </DropHint>
        ) : (
          <FileList onClick={e => e.stopPropagation()}>
            {sorted.map((f, i) => (
              <FileItem key={f.name}>
                <SceneNum>Scene {i + 1}</SceneNum>
                <FileName>{f.name}</FileName>
                <FileSize>{(f.size / 1e6).toFixed(1)} MB</FileSize>
                <RemoveBtn onClick={() => removeFile(f.name)}>×</RemoveBtn>
              </FileItem>
            ))}
            <AddMoreBtn onClick={() => inputRef.current?.click()}>+ Add more</AddMoreBtn>
          </FileList>
        )}
      </DropZone>

      {uploadError && (
        <p role="alert" style={{ color: '#ef4444', margin: '8px 0 0' }}>{uploadError}</p>
      )}

      {files.length > 0 && (
        <UploadBtn onClick={handleUpload} disabled={uploading}>
          {uploading ? 'Uploading...' : `Upload ${files.length} file${files.length !== 1 ? 's' : ''}`}
        </UploadBtn>
      )}
    </UploaderRoot>
  )
}
