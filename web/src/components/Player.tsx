import { useEffect, useRef } from 'react'

export interface Song {
  name: string
  artist: string
  url: string
  cover?: string
  source?: string
}

export default function Player({ song }: { song: Song | null }) {
  const audioRef = useRef<HTMLAudioElement>(null)

  useEffect(() => {
    if (!song || !audioRef.current) return
    audioRef.current.load()
    audioRef.current.play().catch(() => {
      // 浏览器可能阻止自动播放，原生播放键仍可正常使用。
    })
  }, [song])

  return (
    <div className={song ? 'player has-song' : 'player'}>
      <div className="record-stage" aria-hidden="true">
        <div className="record">
          <div className="record-ring ring-one" />
          <div className="record-ring ring-two" />
          <div className="record-label">
            {song?.cover ? <img src={song.cover} alt="" /> : null}
          </div>
        </div>
        <div className="tonearm"><i /></div>
      </div>

      <div className="track-copy">
        <p className="track-status">{song ? '正在播放' : '等待点歌'}</p>
        <h2>{song?.name ?? '把此刻交给音乐'}</h2>
        <p>{song?.artist || '说出一首歌，或描述你的心情'}</p>
      </div>

      {song ? (
        <audio
          ref={audioRef}
          className="native-player"
          controls
          preload="metadata"
          src={song.url}
          aria-label={`播放 ${song.name} - ${song.artist || '未知歌手'}`}
        />
      ) : (
        <div className="player-placeholder" aria-hidden="true">
          <span /><span /><span /><span /><span />
        </div>
      )}
    </div>
  )
}
