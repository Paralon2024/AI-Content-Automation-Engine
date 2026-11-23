import { Idea, PipelineLevel } from '../../../tools/types'
import Uploader from '../../Uploader/Uploader'
import VideoSequence from '../components/previews/VideoSequence'
import { ActionRow, BtnSecondary } from '../StepWizard.styled'

interface Props {
  idea: Idea
  base: string
  level: PipelineLevel
  reupload: boolean
  onSetReupload: (v: boolean) => void
  onUploaded: () => void
}

export default function VideosStep({ idea, base, level, reupload, onSetReupload, onUploaded }: Props) {
  return (
    <>
      {(level === 1 || reupload) && (
        <Uploader
          ideaId={idea.id}
          endpoint="videos"
          accept=".mp4"
          label="Drag and drop videos here or click to select"
          hint="MP4 files only — sorted by filename"
          onUploaded={() => { onSetReupload(false); onUploaded() }}
        />
      )}
      {level >= 2 && !reupload && (
        <>
          <ActionRow>
            <BtnSecondary onClick={() => onSetReupload(true)}>↺ Re-upload videos</BtnSecondary>
          </ActionRow>
          <VideoSequence baseUrl={base} synced={false} />
        </>
      )}
    </>
  )
}
