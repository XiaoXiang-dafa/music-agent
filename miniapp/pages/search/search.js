/** @type {any} */
const app = getApp()

Page({
  data: {
    keyword: '',
    songs: [],
    suggestions: [],     // ★ 实时联想
    loading: false,
    searched: false,
    currentSong: null,
    isPlaying: false,
    searchHistory: [],
    showHistory: true,
    _scrollLock: false,
    source: 'qq',        // ★ 音源: 'qq' | 'netease'
    sourceLabel: 'QQ音乐',
  },

  suggestTimer: null,  // ★ 防抖

  onLoad() {
    this.updatePlayerState()
    setInterval(() => this.updatePlayerState(), 500)
    this._loadHistory()
  },

  onShow() {
    this.updatePlayerState()
    this._loadHistory()
  },

  _loadHistory() {
    this.setData({ searchHistory: app.globalData.searchHistory })
  },

  updatePlayerState() {
    this.setData({
      currentSong: app.globalData.currentSong,
      isPlaying: app.globalData.isPlaying,
    })
  },

  // ★ 清空搜索输入
  clearInput() {
    this.setData({ keyword: '', suggestions: [], searched: false, showHistory: true })
  },

  // ★ 收起联想下拉
  dismissSuggest() {
    this.setData({ suggestions: [] })
  },

  // ★ 输入时 300ms 防抖实时联想
  onInput(e) {
    const kw = e.detail.value
    this.setData({ keyword: kw })

    if (this.suggestTimer) clearTimeout(this.suggestTimer)

    if (!kw.trim()) {
      this.setData({ suggestions: [], searched: false, showHistory: true })
      return
    }

    this.suggestTimer = setTimeout(() => {
      const endpoint = this.data.source === 'netease' ? '/api/search/netease' : '/api/search'
      app.request(endpoint + '?q=' + encodeURIComponent(kw.trim()) + '&limit=6').then(res => {
        // cover 已是 HTTPS CDN URL，直接使用，不代理
        const sug = (res.songs || []).slice(0, 6).map(s => ({ ...s, source: this.data.source }))
        this.setData({ suggestions: sug })
      }).catch(() => {})
    }, 300)
  },

  // 点联想条目
  tapSuggest(e) {
    const { id, name, artist } = e.currentTarget.dataset
    const kw = name + (artist ? ' ' + artist : '')
    this.setData({ keyword: kw, suggestions: [] })
    this._doSearch(kw)
  },

  // ★ 切换音源
  switchSource(e) {
    const src = e.currentTarget.dataset.source
    if (src === this.data.source) return
    this.setData({ source: src, sourceLabel: src === 'netease' ? '网易云' : 'QQ音乐', songs: [], suggestions: [], searched: false, showHistory: true })
  },

  tapHistory(e) {
    const kw = e.currentTarget.dataset.kw
    this.setData({ keyword: kw })
    this._doSearch(kw)
  },

  clearHistory() {
    wx.showModal({
      title: '清除搜索历史',
      success: (res) => {
        if (res.confirm) {
          app.clearSearchHistory()
          this.setData({ searchHistory: [] })
        }
      },
    })
  },

  doSearch() {
    const kw = this.data.keyword.trim()
    if (!kw) return
    this._doSearch(kw)
  },

  _doSearch(kw) {
    if (!kw) return
    this.setData({ loading: true, searched: true, songs: [], suggestions: [], showHistory: false })

    app.addSearchKeyword(kw)
    this._loadHistory()

    const endpoint = this.data.source === 'netease' ? '/api/search/netease' : '/api/search'
    app.request(endpoint + '?q=' + encodeURIComponent(kw)).then(res => {
      // cover 已是 HTTPS CDN URL（https://y.gtimg.cn/...），真机直接加载
      const songs = (res.songs || []).map(s => ({ ...s, source: this.data.source }))
      this.setData({ songs, loading: false })
      if (songs.length === 0) {
        wx.showToast({ title: '没有找到相关歌曲', icon: 'none' })
      }
    }).catch(() => {
      wx.showToast({ title: '搜索失败', icon: 'none' })
      this.setData({ loading: false })
    })
  },

  playSong(e) {
    const { id, name, artist, cover, source } = e.currentTarget.dataset
    wx.showLoading({ title: '加载中' })
    const urlEndpoint = source === 'netease' ? '/api/song/url/netease' : '/api/song/url'
    app.request(urlEndpoint + '?id=' + id).then(urlRes => {
      wx.hideLoading()
      const url = urlRes.url || ''
      if (!url) { wx.showToast({ title: '暂无版权', icon: 'none' }); return }
      const song = { id, name, artist, url, cover: cover || '', source: source || 'qq' }
      const queue = app.globalData.playQueue
      if (!queue.find(s => s.id === id)) queue.push({ id, name, artist, cover: cover || '', source: source || 'qq' })
      app.globalData.queueIndex = queue.findIndex(s => s.id === id)
      app.playSong(song)
      this.updatePlayerState()
      wx.navigateTo({ url: '/pages/player/player' })
    }).catch(() => { wx.hideLoading(); wx.showToast({ title: '加载失败', icon: 'none' }) })
  },

  addToQueue(e) {
    const { id, name, artist, cover, source } = e.currentTarget.dataset
    app.addToQueue([{ id, name, artist, cover: cover || '', source: source || 'qq' }])
  },

  goPlayer() {
    if (app.globalData.currentSong) wx.navigateTo({ url: '/pages/player/player' })
  },

  togglePlay() { app.togglePlay(); this.updatePlayerState() },

  // ★ 封面加载失败时替换为默认占位图（真机兼容兜底）
  onCoverError(e) {
    const idx = e.currentTarget.dataset.index
    if (idx !== undefined && this.data.songs[idx]) {
      this.setData({ ['songs[' + idx + '].cover']: '/images/default-cover.png' })
    }
  },
})
