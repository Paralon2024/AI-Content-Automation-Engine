import { useState, useCallback, useRef, useEffect } from 'react'
import { MusicNode } from '../../tools/types'
import { api } from '../../tools/api'
import {
  Root, Header, HeaderTitle, TrackCount, UploadBtn,
  Tree, FolderRow, FileRow, FileName, SelectedBadge, ActionBtn, FolderCount,
  DropZone, DropIcon, Player, PlayerName, PlayPauseBtn, Progress, TimeLabel, DragOverlay,
} from './MusicLibrary.styled'

function countFiles(nodes: MusicNode[]): number {
  return nodes.reduce((acc, n) => acc + (n.type === 'file' ? 1 : countFiles(n.children)), 0)
}

function formatTime(s: number) {
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${sec.toString().padStart(2, '0')}`
}

function TreeNode({
  node, depth, selected, previewing, onSelect, onPreview, onDelete,
}: {
  node: MusicNode
  depth: number
  selected: string
  previewing: string
  onSelect: (path: string) => void
  onPreview: (path: string) => void
  onDelete: (path: string, isDir: boolean) => void
}) {
  const [open, setOpen] = useState(true)

  if (node.type === 'dir') {
    const count = countFiles(node.children)
    return (
      <>
        <FolderRow $depth={depth} onClick={() => setOpen(o => !o)}>
          <span style={{ fontSize: 10 }}>{open ? '▾' : '▸'}</span>
          <span>📁</span>
          <span style={{ flex: 1, color: 'inherit' }}>{node.name}</span>
          <FolderCount>{count} {count === 1 ? 'track' : 'tracks'}</FolderCount>
          <ActionBtn
            className="del"
            title="Delete folder"
            onClick={e => { e.stopPropagation(); onDelete(node.path, true) }}
          >✕</ActionBtn>
        </FolderRow>
        {open && node.children.map(child => (
          <TreeNode
            key={child.path} node={child} depth={depth + 1}
            selected={selected} previewing={previewing}
            onSelect={onSelect} onPreview={onPreview}
            onDelete={onDelete}
          />
        ))}
      </>
    )
  }

  const isSelected = selected === node.path
  const isPreviewing = previewing === node.path

  return (
    <FileRow
      $depth={depth} $selected={isSelected} $previewing={isPreviewing}
      onClick={() => onSelect(isSelected ? '' : node.path)}
    >
      <span style={{ fontSize: 13 }}>♫</span>
      <FileName title={node.name}>{node.name}</FileName>
      {isSelected && <SelectedBadge>✓ selected</SelectedBadge>}
      <div className="actions" style={{ display: 'flex', gap: 2 }}>
        <ActionBtn
          title={isPreviewing ? 'Stop' : 'Preview'}
          onClick={e => { e.stopPropagation(); onPreview(isPreviewing ? '' : node.path) }}
        >
          {isPreviewing ? '■' : '▶'}
        </ActionBtn>
        <ActionBtn
          title="Delete"
          onClick={e => { e.stopPropagation(); onDelete(node.path, false) }}
        >✕</ActionBtn>
      </div>
    </FileRow>
  )
}

interface Props {
  selected: string
  onSelect: (path: string) => void
  volume?: number
}

export default function MusicLibrary({ selected, onSelect, volume = 1 }: Props) {
  const uploadRef = useRef<HTMLInputElement>(null)
  const audioRef = useRef<HTMLAudioElement>(null)

  const [nodes, setNodes] = useState<MusicNode[]>([])
  const [uploading, setUploading] = useState(false)
  const [dragging, setDragging] = useState(0)
  const [previewing, setPreviewing] = useState('')
  const [playing, setPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [libraryError, setLibraryError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setNodes(await api.music.list())
  }, [])

  useEffect(() => {
    refresh().catch(error => {
      setLibraryError(error instanceof Error ? error.message : 'Could not load the music library.')
    })
  }, [refresh])

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return
    if (!previewing) { audio.pause(); audio.src = ''; setPlaying(false); return }
    audio.src = api.music.streamUrl(previewing)
    audio.volume = Math.max(0, Math.min(1, volume))
    audio.play().then(() => setPlaying(true)).catch(() => {
      setLibraryError('Could not preview this audio track.')
    })
  }, [previewing])

  useEffect(() => {
    if (audioRef.current) audioRef.current.volume = Math.max(0, Math.min(1, volume))
  }, [volume])

  const uploadFiles = useCallback(async (files: File[]) => {
    if (!files.length) return
    setUploading(true)
    setLibraryError(null)
    try {
      await api.music.upload(files)
      await refresh()
    } catch (error) {
      setLibraryError(error instanceof Error ? error.message : 'Music upload failed.')
    } finally {
      setUploading(false)
    }
  }, [refresh])

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    uploadFiles(Array.from(e.target.files ?? []))
    e.target.value = ''
  }, [uploadFiles])

  const handleDragEnter = (e: React.DragEvent) => { e.preventDefault(); setDragging(d => d + 1) }
  const handleDragLeave = () => setDragging(d => Math.max(0, d - 1))
  const handleDragOver = (e: React.DragEvent) => e.preventDefault()
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(0)
    const files = Array.from(e.dataTransfer.files).filter(
      f => f.type.startsWith('audio/') || /\.(mp3|wav|ogg|aac|m4a|flac)$/i.test(f.name)
    )
    uploadFiles(files)
  }

  const handleDelete = useCallback(async (path: string, isDir: boolean) => {
    const label = isDir ? `the folder "${path}" and its contents` : `"${path}"`
    if (!confirm(`Delete ${label}?`)) return
    setLibraryError(null)
    try {
      await api.music.delete(path)
      const isWithinDeletedFolder = (value: string) =>
        value === path || (isDir && value.startsWith(`${path}/`))
      if (isWithinDeletedFolder(selected)) onSelect('')
      if (isWithinDeletedFolder(previewing)) setPreviewing('')
      await refresh()
    } catch (error) {
      setLibraryError(error instanceof Error ? error.message : 'Could not delete the selected item.')
    }
  }, [selected, previewing, onSelect, refresh])

  const totalTracks = countFiles(nodes)

  return (
    <Root
      $dragging={dragging > 0}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      <audio
        ref={audioRef}
        onTimeUpdate={() => setCurrentTime(audioRef.current?.currentTime ?? 0)}
        onDurationChange={() => setDuration(audioRef.current?.duration ?? 0)}
        onEnded={() => setPlaying(false)}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
      />

      <Header>
        <HeaderTitle>🎵 Music Library</HeaderTitle>
        {totalTracks > 0 && <TrackCount>{totalTracks} {totalTracks === 1 ? 'track' : 'tracks'}</TrackCount>}
        <UploadBtn onClick={() => uploadRef.current?.click()} disabled={uploading}>
          {uploading ? '⏳ Uploading…' : '↑ Upload tracks'}
        </UploadBtn>
        <input
          ref={uploadRef}
          type="file"
          accept="audio/*,.mp3,.wav,.ogg,.aac,.m4a,.flac"
          multiple
          style={{ display: 'none' }}
          onChange={handleFileInput}
        />
      </Header>

      {libraryError && (
        <p role="alert" aria-live="polite" style={{ color: '#ef4444', fontSize: 12, margin: '8px 12px' }}>
          {libraryError}
        </p>
      )}

      {nodes.length > 0 && (
        <Tree>
          {nodes.map(node => (
            <TreeNode
              key={node.path} node={node} depth={0}
              selected={selected} previewing={previewing}
              onSelect={onSelect} onPreview={setPreviewing}
              onDelete={handleDelete}
            />
          ))}
        </Tree>
      )}

      <DropZone $active={dragging > 0} $uploading={uploading}>
        <DropIcon>{uploading ? '⏳' : dragging > 0 ? '🎵' : '☁'}</DropIcon>
        <span>
          {uploading ? 'Uploading…'
          : dragging > 0 ? 'Drop files here'
          : nodes.length === 0 ? 'Drag audio tracks here\nor click to select'
          : 'Drop more tracks here or click to select'}
        </span>
        <input
          type="file"
          accept="audio/*,.mp3,.wav,.ogg,.aac,.m4a,.flac"
          multiple
          onChange={handleFileInput}
        />
      </DropZone>

      {previewing && (
        <Player>
          <PlayPauseBtn onClick={() => {
            if (playing) audioRef.current?.pause()
            else audioRef.current?.play()
          }}>
            {playing ? '❚❚' : '▶'}
          </PlayPauseBtn>
          <PlayerName title={previewing}>{previewing.split('/').pop()}</PlayerName>
          <Progress
            type="range" min={0} max={duration || 1} step={0.1} value={currentTime}
            onChange={e => { if (audioRef.current) audioRef.current.currentTime = Number(e.target.value) }}
          />
          <TimeLabel>{formatTime(currentTime)}</TimeLabel>
          <ActionBtn onClick={() => setPreviewing('')} title="Close">✕</ActionBtn>
        </Player>
      )}

      {dragging > 0 && (
        <DragOverlay>
          <span style={{ fontSize: 32 }}>🎵</span>
          <span>Drop to upload</span>
        </DragOverlay>
      )}
    </Root>
  )
}
