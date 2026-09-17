/** @type {any} */
const app = getApp()

Page({
  data: {
    favorites: [],
    playHistory: [],
    currentTab: 'fav', // 'fav' | 'history'
    isEmpty: true,
    _scrollLock: false,
  },

  onLoad() {
    this.loadData()
  },

  onShow() {
    this.loadData()
  },

  loadData() {
    // ★ 用 safeCdnCover 自动清理旧代理 URL，防止缓存中的 HTTP/IP 地址导致超时
    const favs = (app.globalData.favorites || []).map(s => ({ ...s, cover: app.safeCdnCover(s.cover, s.id) }))
    const hist = (app.globalData.playHistory || []).map(s => ({ ...s, cover: app.safeCdnCover(s.cover, s.id) }))
    this.setData({
      favorites: favs,
      playHistory: hist,
      isEmpty: (this.data.currentTab === 'fav' ? favs : hist).length === 0,
    })
  },

  switchTab(e) {
    const tab = e.currentTarget.dataset.tab
    this.setData({ currentTab: tab }, () => this.loadData())
  },

  // 播放
  playSong(e) {
    const { id, name, artist, cover } = e.currentTarget.dataset
    wx.showLoading({ title: '加载中' })
    app.request('/api/song/url?id=' + id).then(urlRes => {
      wx.hideLoading()
      const url = urlRes.url || ''
      if (!url) { wx.showToast({ title: '暂无版权', icon: 'none' }); return }
      const song = { id, name, artist, url, cover: cover || '' }
      const queue = app.globalData.playQueue
      if (!queue.find(s => s.id === id)) queue.push({ id, name, artist, cover: cover || '' })
      app.globalData.queueIndex = queue.findIndex(s => s.id === id)
      app.playSong(song)
      wx.navigateTo({ url: '/pages/player/player' })
    }).catch(() => { wx.hideLoading(); wx.showToast({ title: '加载失败', icon: 'none' }) })
  },

  // 移除收藏
  removeFav(e) {
    const { id } = e.currentTarget.dataset
    wx.showModal({
      title: '取消收藏',
      content: '确定要取消收藏这首歌吗？',
      success: (res) => {
        if (res.confirm) {
          app.removeFavorite(id)
          this.loadData()
        }
      },
    })
  },

  // 添加到队列
  addToQueue(e) {
    const { id, name, artist, cover } = e.currentTarget.dataset
    app.addToQueue([{ id: id, name, artist, cover: cover || '' }])
  },

  // 清空历史
  clearHistory() {
    wx.showModal({
      title: '清空播放历史',
      success: (res) => {
        if (res.confirm) {
          app.globalData.playHistory = []
          app._saveHistory()
          this.loadData()
        }
      },
    })
  },

  // ★ 封面加载失败时替换为默认占位图（真机兼容兜底）
  onCoverError(e) {
    const { index, tab } = e.currentTarget.dataset
    if (index !== undefined) {
      const key = tab === 'history' ? 'playHistory' : 'favorites'
      this.setData({ [key + '[' + index + '].cover']: '/images/default-cover.png' })
    }
  },
})
