import { useState, useEffect, useRef } from 'react'
import { PipelineLevel } from '../../../tools/types'
import Terminal from '../components/Terminal/Terminal'
import VideoPlayer from '../components/previews/VideoPlayer'
import MusicLibrary from '../../MusicLibrary/MusicLibrary'
import { ActionRow, BtnPrimary, BtnSecondary } from '../StepWizard.styled'
import { JobStep } from '../../../tools/hooks/useJobStep'
import { TwoCol, Left, VolumeRow, VolumeLabel, VolumeSlider, VolumePct, MusicHint } from './ProductionStep.styled'
import type { MusicOpts } from '../hooks/useStepWizard'

interface Props {
  base: string
  level: PipelineLevel
  subsStep: JobStep
  assembleStep: JobStep
  onSubs: (opts: MusicOpts) => void
  onAssemble: (opts: MusicOpts) => void
}

export default function ProductionStep({ base, level, subsStep, assembleStep, onSubs, onAssemble }: Props) {
  const [selectedPath, setSelectedPath] = useState('')
  const [volume, setVolume] = useState(18)

  const anyRunning = !!(subsStep.jobId || assembleStep.jobId)

  const [videoVersion, setVideoVersion] = useState(0)
  const wasRunning = useRef(false)
  useEffect(() => {
    if (wasRunning.current && !anyRunning) setVideoVersion(v => v + 1)
    wasRunning.current = anyRunning
  })

  const videoSrc = level >= 7
    ? `${base}/video`
    : level >= 5
      ? `${base}/editions/subtitled_video.mp4`
      : `${base}/editions/raw_video.mp4`

  const videoLabel = level >= 7
    ? 'Video final'
    : level >= 5
      ? 'Video with subtitles'
      : 'Assembled video (no subtitles)'

  if (anyRunning) {
    return (
      <>
        {subsStep.jobId    && <Terminal logs={subsStep.logs}    running />}
        {assembleStep.jobId && <Terminal logs={assembleStep.logs} running />}
      </>
    )
  }

  return (
    <TwoCol>
      <Left>
        <MusicLibrary selected={selectedPath} onSelect={setSelectedPath} volume={volume / 100} />

        <VolumeRow>
          <VolumeLabel>Volume</VolumeLabel>
          <VolumeSlider
            type="range" min={0} max={100} value={volume}
            onChange={e => setVolume(Number(e.target.value))}
          />
          <VolumePct>{volume}%</VolumePct>
        </VolumeRow>

        {level === 4 && (
          <ActionRow>
            <BtnPrimary
              onClick={() => onSubs({ musicPath: selectedPath, bgVolume: volume / 100 })}
              disabled={!selectedPath}
            >
              Add music and generate subtitles
            </BtnPrimary>
            {!selectedPath && (
              <MusicHint>Select a music track to continue.</MusicHint>
            )}
          </ActionRow>
        )}


        {(level === 5 || level === 6) && (
          <ActionRow>
            <BtnPrimary
              onClick={() => onAssemble({ musicPath: selectedPath, bgVolume: volume / 100 })}
              disabled={!selectedPath}
            >
              {level === 5 ? 'Resume: add music and finalize video' : 'Resume: finalize video'}
            </BtnPrimary>
            {!selectedPath && (
              <MusicHint>Select a music track to resume production.</MusicHint>
            )}
          </ActionRow>
        )}

        {level === 7 && (
          <ActionRow>
            <BtnSecondary
              onClick={() => onSubs({ musicPath: selectedPath, bgVolume: volume / 100 })}
              disabled={!selectedPath}
            >
              ↺ Regenerate
            </BtnSecondary>
            {!selectedPath && (
              <MusicHint>Select a music track to regenerate.</MusicHint>
            )}
          </ActionRow>
        )}
      </Left>

      <VideoPlayer src={`${videoSrc}?v=${videoVersion}`} label={videoLabel} />
    </TwoCol>
  )
}
