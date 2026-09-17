import { useEffect, useRef } from 'react'

export interface Song {
  name: string
  artist: string
  url: string
}

/** 音频播放器：收到 Agent 的 play_song 结果后自动播放。 */
export default function Player({ song }: { song: Song | null }) {
  const ref = useRef<HTMLAudioElement>(null)

  useEffect(() => {
    if (song && ref.current) {
      ref.current.load()
      ref.current.play().catch(() => {})
    }
  }, [song])

  if (!song) return null

  return (
    <div className="player">
      <div className="player-info">
        <span className="player-icon">▶️</span>
        <div>
          <div className="player-song">{song.name}</div>
          <div className="player-artist">{song.artist || '未知歌手'}</div>
        </div>
      </div>
      <audio ref={ref} controls autoPlay className="player-audio" src={song.url} />
    </div>
  )
}
