/** @type {any} */
const app = getApp()

Component({
  data: {
    show: false,
    playQueue: [],
    queueIndex: -1,
    queueLength: 0,
    modeIcon: '🔁',
  },

  timer: null,

  lifetimes: {
    attached() {
      this._pageVisible = true
      this.timer = setInterval(() => {
        if (app.globalData._showQueue && this._pageVisible) {
          app.globalData._showQueue = false
          this._syncQueue(true)
        }
      }, 300)
    },
    detached() {
      if (this.timer) clearInterval(this.timer)
    },
  },

  pageLifetimes: {
    show() { this._pageVisible = true },
    hide() { this._pageVisible = false; this._unlockPageScroll() },
  },

  methods: {
    // 反转队列：最新播放的在最上面
    _syncQueue(shouldShow) {
      const q = app.globalData.playQueue
      const len = q.length
      const displayQueue = [...q].reverse()
      const displayIndex = len > 0 ? len - 1 - app.globalData.queueIndex : -1
      this.setData({
        show: shouldShow,
        playQueue: displayQueue,
        queueIndex: displayIndex,
        queueLength: len,
        modeIcon: app.globalData.modeIcons[app.globalData.playMode],
      })
      if (shouldShow) this._lockPageScroll()
    },
    // 将展示索引映射回原始索引
    _realIdx(displayIdx) {
      return app.globalData.playQueue.length - 1 - displayIdx
    },
    show() { this._syncQueue(true) },
    hide() {
      this.setData({ show: false })
      this._unlockPageScroll()
    },

    // 锁定/解锁当前页面滚动
    _lockPageScroll() {
      try {
        const pages = getCurrentPages()
        if (pages.length > 0) pages[pages.length - 1].setData({ _scrollLock: true })
      } catch (e) {}
    },
    _unlockPageScroll() {
      try {
        const pages = getCurrentPages()
        if (pages.length > 0) pages[pages.length - 1].setData({ _scrollLock: false })
      } catch (e) {}
    },

    playFromQueue(e) {
      const displayIdx = e.currentTarget.dataset.index
      // 如果点击的是正在播放的歌曲，不重新播放
      if (displayIdx === this.data.queueIndex) return
      const realIdx = this._realIdx(displayIdx)
      app.playFromQueue(realIdx)
      setTimeout(() => this._syncQueue(false), 300)
    },

    removeFromQueue(e) {
      const realIdx = this._realIdx(e.currentTarget.dataset.index)
      const queue = app.globalData.playQueue
      if (realIdx < 0 || realIdx >= queue.length) return
      if (queue.length === 1 && realIdx === app.globalData.queueIndex && app.globalData.isPlaying) {
        wx.showToast({ title: '歌曲正在播放哦～', icon: 'none' })
        return
      }
      queue.splice(realIdx, 1)
      if (realIdx <= app.globalData.queueIndex && app.globalData.queueIndex > 0) {
        app.globalData.queueIndex--
      }
      if (queue.length === 0) {
        app.globalData.queueIndex = -1
        app.globalData.currentSong = null
      }
      this._syncQueue(false)
    },

    clearQueue() {
      const queue = app.globalData.playQueue
      if (queue.length === 1 && app.globalData.queueIndex === 0 && app.globalData.isPlaying) {
        wx.showToast({ title: '歌曲正在播放哦～', icon: 'none' })
        return
      }
      app.clearQueue()
      this.setData({ playQueue: [], queueIndex: -1, queueLength: 0, show: false })
    },

    preventScroll() {},

    cycleMode() {
      const mode = app.cycleMode()
      this.setData({ modeIcon: app.globalData.modeIcons[mode] })
    },

    // ★ 封面加载失败时替换为默认占位图（真机兼容兜底）
    onCoverError(e) {
      const idx = e.currentTarget.dataset.index
      if (idx !== undefined) {
        this.setData({ ['playQueue[' + idx + '].cover']: '/images/default-cover.png' })
      }
    },
  },
})
