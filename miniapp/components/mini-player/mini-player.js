/** @type {any} */
const app = getApp()

Component({
  data: {
    song: null,
    isPlaying: false,
    isFavorite: false,
    progress: 0,
  },

  timer: null,

  lifetimes: {
    attached() {
      this.update()
      this.timer = setInterval(() => this.update(), 500)
    },
    detached() {
      if (this.timer) clearInterval(this.timer)
    },
  },

  pageLifetimes: {
    show() { this.update() },
  },

  methods: {
    update() {
      const bgAudio = app.bgAudio
      const ct = bgAudio ? (bgAudio.currentTime || 0) : 0
      const dur = bgAudio ? (bgAudio.duration || (app.globalData.currentSong?.duration || 0) / 1000 || 1) : 1
      const pct = dur > 0 ? (ct / dur) * 100 : 0
      const songId = app.globalData.currentSong?.id

      this.setData({
        song: app.globalData.currentSong,
        isPlaying: app.globalData.isPlaying,
        isFavorite: app.isFavorite(songId),
        progress: Math.min(pct, 100),
      })
    },

    goPlayer() {
      if (app.globalData.currentSong) {
        wx.navigateTo({ url: '/pages/player/player' })
      }
    },

    goQueue() {
      app.globalData._showQueue = true
    },

    togglePlay() {
      app.togglePlay()
      this.update()
    },

    prev() {
      app.playPrev()
      this.update()
    },

    next() {
      app.playNext()
      this.update()
    },

    toggleFav() {
      const song = app.globalData.currentSong
      if (!song || !song.id) return
      app.toggleFavorite(song)
      this.setData({ isFavorite: app.isFavorite(song.id) })
    },

    // ★ 封面加载失败时替换为默认占位图（真机兼容兜底）
    onCoverError() {
      this.setData({ 'song.cover': '/images/default-cover.png' })
    },
  },
})
