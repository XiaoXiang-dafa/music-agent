/** @type {any} */
const app = getApp()

const THEMES = [
  { bg: 'linear-gradient(180deg, #0d1b2a 0%, #0a0e14 40%, #080808 100%)', accent: '#07C160', shadow: 'rgba(7,193,96,0.3)' },
  { bg: 'linear-gradient(180deg, #1a0a0a 0%, #0e0a0a 40%, #080808 100%)', accent: '#FA5151', shadow: 'rgba(250,81,81,0.3)' },
  { bg: 'linear-gradient(180deg, #0a1628 0%, #0a0d14 40%, #080808 100%)', accent: '#3B82F6', shadow: 'rgba(59,130,246,0.3)' },
  { bg: 'linear-gradient(180deg, #1c1008 0%, #0e0c08 40%, #080808 100%)', accent: '#F97316', shadow: 'rgba(249,115,22,0.3)' },
  { bg: 'linear-gradient(180deg, #1a0a1c 0%, #0e0a0e 40%, #080808 100%)', accent: '#EC4899', shadow: 'rgba(236,72,153,0.3)' },
  { bg: 'linear-gradient(180deg, #081a18 0%, #0a0e0e 40%, #080808 100%)', accent: '#14B8A6', shadow: 'rgba(20,184,166,0.3)' },
  { bg: 'linear-gradient(180deg, #140a24 0%, #0e0a14 40%, #080808 100%)', accent: '#A855F7', shadow: 'rgba(168,85,247,0.3)' },
  { bg: 'linear-gradient(180deg, #1a1606 0%, #0e0c08 40%, #080808 100%)', accent: '#EAB308', shadow: 'rgba(234,179,8,0.3)' },
]

Page({
  data: {
    statusBarHeight: 0,
    song: {}, isPlaying: false, isFavorite: false,
    currentTimeText: '00:00', durationText: '00:00', progress: 0,
    lyricLines: [],
    currentLyric: -1,
    currentLyricText: '',     // 单行歌词文本
    showQueue: false,         // 播放队列弹窗
    playQueue: [],            // 队列数据
    playMode: 0, modeIcon: '🔁',
    queueIndex: -1, queueLength: 0,
    touchStartX: 0, touchStartY: 0,
    _scrollLock: false,
    themeBg: THEMES[0].bg, themeAccent: THEMES[0].accent, themeShadow: THEMES[0].shadow,
    waveBars: [],
  },

  timer: null,
  _rawLyrics: [],
  _lastSongId: 0,

  onLoad() {
    this.setData({ statusBarHeight: wx.getSystemInfoSync().statusBarHeight })
    const bars = []
    for (let i = 0; i < 22; i++) bars.push({ height: 8, active: false })
    this.setData({ waveBars: bars })

    this._applyTheme()
    this.updateState()
    this.startTimer()
  },

  onUnload() {
    if (this.timer) clearInterval(this.timer)
  },

  onShow() {
    this._applyTheme()
    this.updateState()
  },

  _applyTheme() {
    const song = app.globalData.currentSong
    if (!song || !song.id) {
      const t = THEMES[0]
      this.setData({ themeBg: t.bg, themeAccent: t.accent, themeShadow: t.shadow })
      return
    }
    const coverUrl = song.cover || ''
    if (coverUrl) {
      app.request('/api/cover/color?url=' + encodeURIComponent(coverUrl)).then(res => {
        if (res.color) {
          const { r, g, b } = res.color
          const bg = `linear-gradient(180deg, rgba(${r},${g},${b},0.35) 0%, rgba(${Math.floor(r*0.55)},${Math.floor(g*0.55)},${Math.floor(b*0.55)},0.15) 40%, #080808 100%)`
          this.setData({ themeBg: bg })
        } else {
          this._fallbackTheme(song.id)
        }
      }).catch(() => this._fallbackTheme(song.id))
    } else {
      this._fallbackTheme(song.id)
    }
  },

  _fallbackTheme(songId) {
    const idx = songId ? (typeof songId === 'string' ? songId.length : songId) % THEMES.length : 0
    const t = THEMES[idx]
    this.setData({ themeBg: t.bg, themeAccent: t.accent, themeShadow: t.shadow })
  },

  startTimer() {
    this.timer = setInterval(() => {
      const bgAudio = app.bgAudio
      if (!bgAudio) return
      const ct = bgAudio.currentTime || 0
      const dur = bgAudio.duration || (app.globalData.currentSong?.duration || 0) / 1000 || 1
      const pct = dur > 0 ? (ct / dur) * 100 : 0
      const song = app.globalData.currentSong || {}

      if (song.id && song.id !== this._lastSongId) {
        this._lastSongId = song.id
        this._applyTheme()
        this.loadLyric(song.id)
      }

      let curLyric = -1
      for (let i = 0; i < this._rawLyrics.length; i++) {
        if (this._rawLyrics[i].time <= ct) curLyric = i
        else break
      }

      // 单行歌词：取当前行文本
      const lyricText = (curLyric >= 0 && this._rawLyrics[curLyric])
        ? this._rawLyrics[curLyric].text : ''

      // 声波
      const waveBars = this.data.waveBars
      if (app.globalData.isPlaying) {
        for (let i = 0; i < waveBars.length; i++) {
          const h = 10 + Math.random() * 70
          waveBars[i] = { height: h, active: h > 40 }
        }
      } else if (waveBars.length > 0) {
        for (let i = 0; i < waveBars.length; i++) {
          waveBars[i] = { height: 8, active: false }
        }
      }

      this.setData({
        currentTimeText: app.fmtTime(ct), durationText: app.fmtTime(dur), progress: pct,
        isPlaying: app.globalData.isPlaying, song: song,
        currentLyric: curLyric, currentLyricText: lyricText,
        playMode: app.globalData.playMode, modeIcon: app.globalData.modeIcons[app.globalData.playMode],
        queueIndex: app.globalData.queueIndex, queueLength: app.globalData.playQueue.length,
        isFavorite: app.isFavorite(app.globalData.currentSong?.id),
        playQueue: app.globalData.playQueue,
        waveBars: waveBars,
      })
    }, 250)
  },

  // ===== 播放队列 =====
  showQueue() {
    app.globalData._showQueue = true
  },

  updateState() {
    const song = app.globalData.currentSong || {}
    this.setData({
      song, isPlaying: app.globalData.isPlaying, isFavorite: app.isFavorite(song.id),
      playMode: app.globalData.playMode, modeIcon: app.globalData.modeIcons[app.globalData.playMode],
      queueIndex: app.globalData.queueIndex, queueLength: app.globalData.playQueue.length,
    })
    if (song.id && song.id !== this._lastSongId) {
      this._lastSongId = song.id
      this.loadLyric(song.id)
    }
  },

  loadLyric(songId) {
    this.setData({ currentLyric: -1, currentLyricText: '' })
    this._rawLyrics = []

    const song = app.globalData.currentSong || {}
    const source = song.source || 'qq'
    const lyricEndpoint = source === 'netease' ? '/api/lyric/netease' : '/api/lyric'

    app.request(lyricEndpoint + '?id=' + songId).then(res => {
      const lrcText = (res && (res.lyric || (res.lrc && res.lrc.lyric))) || ''
      const raw = this.parseLrc(lrcText)
      this._rawLyrics = raw
      this.setData({ lyricLines: raw })
    }).catch(() => {
      this._rawLyrics = []
      this.setData({ lyricLines: [] })
    })
  },

  parseLrc(lrc) {
    if (!lrc || typeof lrc !== 'string') return []
    const lines = []
    let offset = 0
    const timeRe = /\[(\d+):(\d+(?:\.\d+)?)\](.*)/
    for (let raw of lrc.split('\n')) {
      raw = raw.replace(/\r$/, '')
      const offMatch = raw.match(/\[offset:\s*([+-]?\d+)\s*\]/i)
      if (offMatch) { offset = parseInt(offMatch[1]) / 1000; continue }
      const m = raw.match(timeRe)
      if (!m) continue
      const time = parseInt(m[1]) * 60 + parseFloat(m[2]) + offset
      const text = m[3].trim()
      if (!text) continue
      lines.push({ time: Math.max(0, time), text })
    }
    lines.sort((a, b) => a.time - b.time)
    const deduped = []
    for (const l of lines) {
      if (deduped.length === 0 || deduped[deduped.length - 1].time !== l.time) {
        deduped.push(l)
      }
    }
    return deduped
  },

  togglePlay() { app.togglePlay() },
  onSeek(e) {
    const dur = app.bgAudio.duration || (app.globalData.currentSong?.duration || 0) / 1000
    if (dur > 0) app.seek((e.detail.value / 100) * dur)
  },
  prev() { app.playPrev(); this._applyTheme(); this._lastSongId = 0 },
  next() { app.playNext(); this._applyTheme(); this._lastSongId = 0 },
  cycleMode() {
    const mode = app.cycleMode()
    this.setData({ playMode: mode, modeIcon: app.globalData.modeIcons[mode] })
  },
  toggleFavorite() {
    const song = app.globalData.currentSong
    if (!song || !song.id) return
    app.toggleFavorite(song)
    this.setData({ isFavorite: app.isFavorite(song.id) })
  },
  onTouchStart(e) {
    this.setData({ touchStartX: e.touches[0].clientX, touchStartY: e.touches[0].clientY })
  },
  onTouchEnd(e) {
    const dx = e.changedTouches[0].clientX - this.data.touchStartX
    const dy = e.changedTouches[0].clientY - this.data.touchStartY
    if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 2) {
      if (dx < 0) { app.playNext(); this._applyTheme(); this._lastSongId = 0 }
      else { app.playPrev(); this._applyTheme(); this._lastSongId = 0 }
      wx.showToast({ title: dx < 0 ? '下一首' : '上一首', icon: 'none', duration: 800 })
    }
  },
  goBack() { wx.navigateBack() },

  // ★ 封面加载失败时替换为默认占位图（真机兼容兜底）
  onCoverError() {
    const song = this.data.song || {}
    this.setData({ 'song.cover': '/images/default-cover.png' })
  },
})
