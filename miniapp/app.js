App({
  globalData: {
    // 后端地址
    apiBase: 'http://127.0.0.1:5050',
    userId: '',          // ★ 唯一用户标识，每个用户独立会话
    currentSong: null,
    isPlaying: false,

    // 播放队列
    playQueue: [],
    queueIndex: -1,

    // 播放模式: 0=列表循环, 1=单曲循环, 2=随机
    playMode: 0,
    modeLabels: ['列表循环', '单曲循环', '随机播放'],
    modeIcons: ['🔁', '🔂', '🔀'],

    // 收藏 & 历史（本地存储）
    favorites: [],
    playHistory: [],
    searchHistory: [],
  },

  onLaunch() {
    // ★ 生成/加载唯一用户 ID（每个用户独立会话 & 角色）
    let userId = wx.getStorageSync('userId')
    if (!userId) {
      userId = 'u_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8)
      wx.setStorageSync('userId', userId)
    }
    this.globalData.userId = userId

    // ★ BackgroundAudioManager — 支持后台播放 + 锁屏控制
    this.bgAudio = wx.getBackgroundAudioManager()

    // 加载本地存储
    this._loadStorage()

    // 后台音频事件
    this.bgAudio.onPlay(() => {
      this.globalData.isPlaying = true
    })
    this.bgAudio.onPause(() => {
      this.globalData.isPlaying = false
    })
    this.bgAudio.onStop(() => {
      this.globalData.isPlaying = false
    })
    this.bgAudio.onEnded(() => {
      this.globalData.isPlaying = false
      this.playNext() // 自动切下一首
    })
    this.bgAudio.onError((err) => {
      console.error('Audio error:', err)
      wx.showToast({ title: '播放失败', icon: 'none' })
      this.globalData.isPlaying = false
    })

    // 系统控制中心上一首/下一首
    this.bgAudio.onPrev(() => { this.playPrev() })
    this.bgAudio.onNext(() => { this.playNext() })
  },

  // ===== 本地存储 =====
  _loadStorage() {
    try {
      const fav = wx.getStorageSync('favorites')
      if (fav) this.globalData.favorites = JSON.parse(fav)
      const hist = wx.getStorageSync('playHistory')
      if (hist) this.globalData.playHistory = JSON.parse(hist)
      const sh = wx.getStorageSync('searchHistory')
      if (sh) this.globalData.searchHistory = JSON.parse(sh)
    } catch (e) { /* ignore */ }
  },

  _saveFavorites() {
    wx.setStorageSync('favorites', JSON.stringify(this.globalData.favorites))
  },

  _saveHistory() {
    wx.setStorageSync('playHistory', JSON.stringify(this.globalData.playHistory.slice(0, 100)))
  },

  _saveSearchHistory() {
    wx.setStorageSync('searchHistory', JSON.stringify(this.globalData.searchHistory.slice(0, 20)))
  },

  // ===== 网络请求 =====
  request(url, method = 'GET', data = {}) {
    // ★ 所有请求自动带上用户 ID，后端按 session 隔离会话和角色
    data.session = this.globalData.userId
    let done = false
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        if (!done) { done = true; reject(new Error('请求超时')) }
      }, 15000)
      wx.request({
        url: this.globalData.apiBase + url,
        method, data, timeout: 15000,
        header: { 'content-type': 'application/json' },
        success: (res) => {
          if (done) return
          done = true; clearTimeout(timer)
          if (res.statusCode === 200) resolve(res.data)
          else reject(new Error('status ' + res.statusCode))
        },
        fail: (err) => {
          if (done) return
          done = true; clearTimeout(timer)
          reject(err)
        },
      })
    })
  },

  // ===== 封面 URL 工具 =====
  // ★ 所有封面最终都必须走 HTTPS CDN，不能走 HTTP 代理（真机不允许 HTTP 图片）
  //   CDN 域名: y.gtimg.cn，需在微信公众平台 → 开发管理 → 服务器域名
  //   → downloadFile合法域名 中添加 "https://y.gtimg.cn"

  // ★ 安全封面 URL：自动清理旧代理 URL、非 HTTPS URL（一律用 CDN 重建）
  safeCdnCover(coverUrl, songId) {
    if (!coverUrl) return songId ? this.coverUrl(songId) : '/images/default-cover.png'
    if (coverUrl.startsWith('https://')) return coverUrl
    // 非 HTTPS（含旧代理 /api/cover）一律用 CDN 重建
    return songId ? this.coverUrl(songId) : '/images/default-cover.png'
  },

  // ★ 根据 songId (QQ音乐 mid) 直接拼接 CDN 封面 URL
  //   格式: https://y.gtimg.cn/music/photo_new/T002R300x300M000{mid}.jpg
  coverUrl(songId) {
    if (!songId) return '/images/default-cover.png'
    return 'https://y.gtimg.cn/music/photo_new/T002R300x300M000' + songId + '.jpg'
  },

  playSong(song) {
    if (!song || !song.url) {
      wx.showToast({ title: '暂无播放链接', icon: 'none' })
      return
    }
    // ★ 封面强制走 HTTPS CDN，防止缓存中的旧 HTTP 代理 URL 导致超时
    song.cover = this.safeCdnCover(song.cover, song.id)
    this.bgAudio.title = song.name || '未知歌曲'
    this.bgAudio.epname = song.artist || ''
    this.bgAudio.singer = song.artist || ''
    this.bgAudio.coverImgUrl = song.cover
    this.bgAudio.src = song.url

    this.globalData.currentSong = song
    this._addHistory(song)
  },

  playFromQueue(index) {
    const queue = this.globalData.playQueue
    if (queue.length === 0) return
    if (index < 0 || index >= queue.length) return

    const song = queue[index]
    this.globalData.queueIndex = index

    wx.showLoading({ title: '加载中' })
    const source = song.source || 'qq'
    const urlEndpoint = source === 'netease' ? '/api/song/url/netease' : '/api/song/url'
    this.request(urlEndpoint + '?id=' + song.id).then(res => {
      wx.hideLoading()
      if (!res.url) {
        wx.showToast({ title: '暂无版权', icon: 'none' })
        return
      }
      song.url = res.url
      // ★ 直接使用网易云 CDN URL，不需要代理
      if (!song.cover) {
        song.cover = this.coverUrl(song.id)
      }
      this.playSong(song)
    }).catch(() => {
      wx.hideLoading()
      wx.showToast({ title: '加载失败', icon: 'none' })
    })
  },

  addToQueue(songs) {
    if (!Array.isArray(songs)) songs = [songs]
    this.globalData.playQueue.push(...songs)
    wx.showToast({ title: `已添加到队列`, icon: 'success' })
  },

  clearQueue() {
    this.globalData.playQueue = []
    this.globalData.queueIndex = -1
  },

  playNext() {
    const queue = this.globalData.playQueue
    if (queue.length === 0) return

    let next
    switch (this.globalData.playMode) {
      case 0: // 列表循环
        next = (this.globalData.queueIndex + 1) % queue.length
        break
      case 1: // 单曲循环
        next = this.globalData.queueIndex
        break
      case 2: // 随机
        next = Math.floor(Math.random() * queue.length)
        break
    }
    this.playFromQueue(next)
  },

  playPrev() {
    const queue = this.globalData.playQueue
    if (queue.length === 0) return

    let prev
    if (this.globalData.playMode === 2) {
      prev = Math.floor(Math.random() * queue.length)
    } else {
      prev = this.globalData.queueIndex - 1
      if (prev < 0) prev = queue.length - 1
    }
    this.playFromQueue(prev)
  },

  cycleMode() {
    this.globalData.playMode = (this.globalData.playMode + 1) % 3
    const labels = this.globalData.modeLabels
    wx.showToast({ title: labels[this.globalData.playMode], icon: 'none' })
    return this.globalData.playMode
  },

  togglePlay() {
    if (this.globalData.isPlaying) {
      this.bgAudio.pause()
    } else if (this.bgAudio.src) {
      this.bgAudio.play()
    }
  },

  seek(pos) {
    if (this.bgAudio.src) this.bgAudio.seek(pos)
  },

  // ===== 收藏 =====
  toggleFavorite(song) {
    if (!song || !song.id) return
    const fav = this.globalData.favorites
    const idx = fav.findIndex(s => s.id === song.id)
    if (idx >= 0) {
      fav.splice(idx, 1)
      wx.showToast({ title: '已取消收藏', icon: 'none' })
    } else {
      fav.unshift({
        id: song.id, name: song.name, artist: song.artist,
        cover: this.safeCdnCover(song.cover, song.id), time: Date.now(),
      })
      wx.showToast({ title: '已收藏', icon: 'none' })
    }
    this._saveFavorites()
  },

  isFavorite(songId) {
    return this.globalData.favorites.some(s => s.id === songId)
  },

  removeFavorite(songId) {
    const fav = this.globalData.favorites
    const idx = fav.findIndex(s => s.id === songId)
    if (idx >= 0) {
      fav.splice(idx, 1)
      this._saveFavorites()
    }
  },

  // ===== 播放历史 =====
  _addHistory(song) {
    if (!song || !song.id) return
    const hist = this.globalData.playHistory
    const idx = hist.findIndex(s => s.id === song.id)
    if (idx >= 0) hist.splice(idx, 1)
    hist.unshift({
      id: song.id, name: song.name, artist: song.artist,
      cover: this.safeCdnCover(song.cover, song.id), time: Date.now(),
    })
    if (hist.length > 100) hist.pop()
    this._saveHistory()
  },

  // ===== 搜索历史 =====
  addSearchKeyword(kw) {
    if (!kw || !kw.trim()) return
    kw = kw.trim()
    const sh = this.globalData.searchHistory
    const idx = sh.indexOf(kw)
    if (idx >= 0) sh.splice(idx, 1)
    sh.unshift(kw)
    if (sh.length > 20) sh.pop()
    this._saveSearchHistory()
  },

  clearSearchHistory() {
    this.globalData.searchHistory = []
    this._saveSearchHistory()
  },

  // ===== 工具 =====
  fmtTime(sec) {
    if (!sec || isNaN(sec)) return '00:00'
    const m = Math.floor(sec / 60)
    const s = Math.floor(sec % 60)
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  },
})
