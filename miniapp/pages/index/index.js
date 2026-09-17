/** @type {any} */
const app = getApp()

Page({
  data: {
    messages: [],
    inputText: '',
    loading: false,
    currentSong: null,
    isPlaying: false,
    showMenu: false,
    _scrollLock: false,
    avatarUser: '',
    avatarBot: 'data:image/png;base64,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',

  },

  onLoad() {
    // 加载本地缓存的头像
    const savedAvatar = wx.getStorageSync('avatarUser') || ''
    if (savedAvatar) this.setData({ avatarUser: savedAvatar })

    this.updatePlayerState()
    setInterval(() => this.updatePlayerState(), 500)

    const now = new Date()
    const hour = now.getHours()
    const day = now.getDay()
    const greetPool = hour < 5 ? [
      '还没睡呢 我在的',
      '深夜了 要听首安静的歌吗',
      '失眠了吗 陪你一会儿',
    ] : hour < 9 ? [
      '早啊 新的一天',
      '醒了？来首提神的',
      '早上好 今天想听什么',
      '早 开始元气满满的一天',
    ] : hour < 12 ? [
      '上午好 来点节奏',
      '工作学习加油 我帮你放歌',
    ] : hour < 14 ? [
      '中午好 要眯一会儿吗',
      '午休时间 来首舒缓的',
      '吃了吗 吃饱了听首好歌',
    ] : hour < 18 ? [
      '下午好 提提神',
      '下午了 来首好听的',
      '困了没 放首嗨的醒醒脑',
      '下午茶时间 配点音乐',
    ] : hour < 22 ? [
      '晚上好 放松一下',
      '回家了 听首舒服的',
      '晚上好 今天辛苦了',
    ] : [
      '夜深了 来首温柔的',
      '睡前听首歌 好梦',
      '这么晚还在 真好',
    ]

    // 周末加一点轻松感
    if (day === 0 || day === 6) {
      greetPool.push('周末快乐 尽情听歌')
      greetPool.push('休息日 音乐走起')
    }

    const greet = greetPool[Math.floor(Math.random() * greetPool.length)]

    this.setData({
      messages: [{ role: 'bot', content: greet }],
      avatarBot: '/images/avatar-bot.png',
    })

    // ★ 自动早安：早上6-11点首次打开自动推送
    if (hour >= 6 && hour <= 11) {
      try {
        const today = now.toDateString()
        const lastDate = wx.getStorageSync('lastMorningDate') || ''
        if (lastDate !== today) {
          wx.setStorageSync('lastMorningDate', today)
          setTimeout(() => this.fetchMorning(), 800)
        }
      } catch (e) { /* ignore */ }
    }
  },

  onShow() { this.updatePlayerState() },

  updatePlayerState() {
    this.setData({
      currentSong: app.globalData.currentSong,
      isPlaying: app.globalData.isPlaying,
    })
  },

  onInput(e) { this.setData({ inputText: e.detail.value }) },

  _fmtTime(ts) {
    const d = new Date(ts); const h = String(d.getHours()).padStart(2, '0'); const m = String(d.getMinutes()).padStart(2, '0')
    return `${h}:${m}`
  },

  // "+" 菜单
  toggleMenu() { this.setData({ showMenu: !this.data.showMenu }) },

  // ★ 从聊天记录中找最近提到的歌（解决「这首歌」引用问题）
  _getLastSongFromContext() {
    const messages = this.data.messages
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i]
      // 歌单卡片里的歌
      if (msg.songs && msg.songs.length > 0) {
        return msg.songs[0]
      }
      // 机器人回复里提到的歌：好 放《晴天》
      if (msg.role === 'bot' && msg.content) {
        const m1 = msg.content.match(/好[，,]\s*放\s*《?(.+?)》?(?:\s*[-—]\s*(.+))?$/)
        if (m1) return { name: m1[1].trim(), artist: (m1[2] || '').trim() }
        const m2 = msg.content.match(/《(.+?)》/)
        if (m2) return { name: m2[1].trim(), artist: '' }
      }
      // 用户消息里提到的歌名
      if (msg.role === 'user' && msg.content) {
        const m3 = msg.content.match(/《(.+?)》/)
        if (m3) return { name: m3[1].trim(), artist: '' }
      }
    }
    return null
  },

  // ★ 从关键词中分离歌名和歌手（例如 "苦茶子 Starling8" → name:苦茶子 artist:Starling8）
  _parseSongArtist(keyword) {
    const kw = keyword.trim()
    if (!kw) return { name: kw, artist: '' }
    // "XXX的YYY" → artist=XXX, song=YYY
    const deMatch = kw.match(/^(.+?)的(.+)$/)
    if (deMatch) {
      const a = deMatch[1].trim(), s = deMatch[2].trim()
      if (a.length < 30 && s.length < 30 && !/^(?:一)?首$/.test(s)) return { name: s, artist: a }
    }
    // "song name by artist"
    const byMatch = kw.match(/^(.+?)\s+by\s+(.+)$/i)
    if (byMatch) return { name: byMatch[1].trim(), artist: byMatch[2].trim() }
    // "song name artist name"（空格分隔，取第一段为歌名）
    const parts = kw.split(/\s+/)
    if (parts.length === 2 && parts[0].length >= 1 && parts[1].length >= 1) {
      return { name: parts[0], artist: parts[1] }
    }
    return { name: kw, artist: '' }
  },

  // ★ 前端检测听歌意图
  _detectSongIntent(msg) {
    const m = msg.trim()

    // ★ 纯聊天句式（「听起来不错」「听我说」等 → 不是点歌）
    if (/听起来|听我说|听说|听听看|听你/.test(m)) return null

    // ★ 去掉礼貌前缀
    const cleanMsg = m.replace(/^(好|行|那|嗯|哦|啊|可以|好吧|那就|那行|行吧)[，,、\s]*/, '').trim()

    // 切歌 — 去掉末尾语气词后匹配
    const afterClean = cleanMsg.replace(/[吧啦啊呀嘛呢哈哦噢~～]+$/, '').trim()
    if (/^(换一首|切歌|下一首|下一曲|跳过|不好听|换首|切一下|换歌|切了|不听了|不想听|不好听换|难听|切走)$/.test(afterClean)) {
      return { action: 'next' }
    }
    if (/^(上一首|上一曲|前一首|往回|倒回去)$/.test(afterClean)) {
      return { action: 'prev' }
    }

    // ★ 「换一首XXX」→ 搜索 XXX（例如「换一首周杰伦的」）
    const changePat = /^(?:换一首|换首|切到|换成)\s*(.+)$/
    const cm = cleanMsg.match(changePat)
    if (cm) {
      const raw = cm[1].trim().replace(/[吧啦啊呀嘛呢哈哦噢的歌歌曲]+$/, '')
      const sa = this._parseSongArtist(raw)
      if (sa.name && sa.name.length >= 1 && sa.name.length < 60) {
        return { action: 'search', keyword: sa.name, artist: sa.artist }
      }
    }

    // 播放/搜索指定歌名（支持多种说法）
    const playPat = /(?:放|播放|播|来首|听一下|听听|想听|放一首|播一下|听一首|点一首|来一首|听|搜|搜一下|搜索|我要听|给我放|帮我放|唱)\s*(?:一下|一首|个)?\s*['"《]?(.+?)['"》]?(?:\s*(?:来听|听听|吧|呗|嘛|看看|试一下|试试))?$/
    const pm = m.match(playPat)
    if (pm) {
      let raw = pm[1].trim().replace(/[吧啦啊呀嘛呢哈哦噢的歌歌曲]+$/, '')

      // ★ 引用词检测：「这首歌」「那首」「刚才那首」→ 从上下文找真实歌名
      if (/^(?:这|那)(?:首|个|一首|支|首歌|支歌)$/.test(raw) || /^(?:刚才|刚刚)(?:那首|那首歌|这首|这首歌|那个)$/.test(raw)) {
        const lastSong = this._getLastSongFromContext()
        if (lastSong) {
          raw = lastSong.name
        } else {
          return null
        }
      }

      // ★ 过滤通用词：提取出「首歌」「首」「歌」等无用词 → 转推荐
      if (/^(?:一)?首$|^歌$|^歌曲$|^音乐$|^曲子$/.test(raw)) {
        return { action: 'recommend' }
      }

      const sa = this._parseSongArtist(raw)
      if (sa.name && sa.name.length >= 1 && sa.name.length < 60) {
        return { action: 'search', keyword: sa.name, artist: sa.artist }
      }
    }
    // 「来点xxx」→ 搜索（如「来点周杰伦的」）
    const comeOnPat = /^来点\s*(.+)$/
    const cm2 = cleanMsg.match(comeOnPat) || m.match(comeOnPat)
    if (cm2) {
      const raw = cm2[1].trim().replace(/[吧啦啊呀嘛呢哈哦噢的歌歌曲]+$/, '').trim()
      const sa = this._parseSongArtist(raw)
      if (sa.name && sa.name.length >= 1 && sa.name.length < 40) {
        return { action: 'search', keyword: sa.name, artist: sa.artist }
      }
    }

    // 推荐/随便
    if (/推荐.*歌|推荐.*曲|来点.*歌|随机|随便.*听|什么歌|有啥.*歌|好听的.*歌|不知道听什么|来首歌|放首歌|播首歌|来一首歌|放一首歌|听首歌|随便来|放点歌|播点歌|听点歌/.test(m)) {
      return { action: 'recommend' }
    }
    return null
  },

  send() {
    const msg = this.data.inputText.trim()
    if (!msg || this.data.loading) return
    this.setData({ inputText: '', loading: true, showMenu: false })

    const messages = this.data.messages
    const timeStr = this._fmtTime(Date.now())
    messages.push({ role: 'user', content: msg, time: timeStr })
    this.setData({ messages })

    // ★ 优先检测本地听歌意图
    const intent = this._detectSongIntent(msg)
    if (intent) {
      if (intent.action === 'next' || intent.action === 'prev') {
        intent.action === 'next' ? app.playNext() : app.playPrev()
        messages.push({ role: 'bot', content: intent.action === 'next' ? '好 换一首' : '好 上一首', time: timeStr, _local: true })
        this.setData({ messages, loading: false })
        return
      }
      if (intent.action === 'search') {
        this._searchAndPlay(intent.keyword, intent.artist || '', (foundName, foundArtist, success) => {
          if (success) {
            const display = foundArtist ? `${foundName} - ${foundArtist}` : foundName
            messages.push({ role: 'bot', content: `好 放${display}`, time: timeStr, _local: true })
          }
          this.setData({ messages, loading: false })
        }, () => {
          wx.navigateTo({ url: '/pages/player/player' })
        })
        return
      }
    }

    // AI 对话
    app.request('/api/chat', 'POST', { message: msg, context: this._collectContext() }).then(res => {
      const reply = res.reply || '嗯'
      messages.push({ role: 'bot', content: reply, time: timeStr, _synced: true })
      this.setData({ messages, loading: false })
      if (res.play && res.play.song) this._searchAndPlay(res.play.song, res.play.artist)
    }).catch(() => {
      messages.push({ role: 'bot', content: '网络不太好 稍后再试', time: timeStr })
      this.setData({ messages, loading: false })
    })
  },

  sendQuick(e) {
    const msg = e.currentTarget.dataset.msg
    if (this.data.loading) return
    if (e.currentTarget.dataset.close) this.setData({ showMenu: false })
    this.setData({ inputText: msg })
    this.send()
  },

  fetchMorning() {
    this.setData({ loading: true, showMenu: false })
    app.request('/api/morning').then(res => {
      if (res.message) {
        const messages = this.data.messages
        messages.push({
          role: 'bot', content: res.message,
          time: this._fmtTime(Date.now()),
          songs: this._parseMorningSongs(res.message),
        })
        this.setData({ messages, loading: false })
      }
    }).catch(() => this.setData({ loading: false }))
  },

  fetchMusic() {
    this.setData({ loading: true, showMenu: false })
    app.request('/api/music').then(res => {
      if (res.songs) {
        const songs = this._parseMorningSongs(res.songs)
        const messages = this.data.messages
        messages.push({
          role: 'bot', content: res.songs,
          time: this._fmtTime(Date.now()), songs: songs,
        })
        this.setData({ messages, loading: false })
      }
    }).catch(() => this.setData({ loading: false }))
  },

  _parseMorningSongs(text) {
    const songs = []
    const lines = text.split('\n')
    for (const line of lines) {
      // 跳过首行标题 "今日歌单" 和空行
      if (!line.trim() || line.trim() === '今日歌单') continue
      // 格式: 歌曲名 - 歌手  推荐理由
      const m = line.match(/^(.+?)\s*[-—]\s*(.+?)(?:\s{2,}(.+))?$/)
      if (m) songs.push({
        name: m[1].trim(),
        artist: m[2].trim(),
        reason: (m[3] || '').trim(),
      })
    }
    return songs
  },

  goSearch() { this.setData({ showMenu: false }); wx.navigateTo({ url: '/pages/search/search' }) },
  goFavorites() { this.setData({ showMenu: false }); wx.navigateTo({ url: '/pages/favorites/favorites' }) },
  goPlayer() { if (app.globalData.currentSong) wx.navigateTo({ url: '/pages/player/player' }) },
  togglePlay() { app.togglePlay(); this.updatePlayerState() },

  playFromCard(e) {
    const { name, artist } = e.currentTarget.dataset
    this._searchAndPlay(name, artist, null, () => {
      wx.navigateTo({ url: '/pages/player/player' })
    })
  },

  addToQueue(e) {
    const { name, artist } = e.currentTarget.dataset
    wx.showLoading({ title: '搜索中' })
    const query = artist ? (name + ' ' + artist) : name
    app.request('/api/search?q=' + encodeURIComponent(query)).then(res => {
      wx.hideLoading()
      const songs = res.songs || []
      if (songs.length === 0) { wx.showToast({ title: '没找到这首歌', icon: 'none' }); return }
      let song = songs[0]
      if (artist) { const match = songs.find(s => s.artist && s.artist.includes(artist)); if (match) song = match }
      app.addToQueue([song])
    }).catch(() => { wx.hideLoading(); wx.showToast({ title: '添加失败', icon: 'none' }) })
  },

  // ★ 搜索并播放（优先匹配歌手，多版本时询问用户）
  _searchAndPlay(name, artist, onFound, onPlayed) {
    const query = artist ? (name + ' ' + artist) : name
    app.request('/api/search?q=' + encodeURIComponent(query)).then(res => {
      const songs = res.songs || []
      if (songs.length === 0) {
        wx.showToast({ title: '没找到 ' + name, icon: 'none' })
        if (onFound) onFound(name, artist || '', false)
        return
      }

      // 归一化函数：去空格、小写，消除格式差异
      const _n = v => (v || '').toLowerCase().replace(/\s+/g, '')
      // 评分：歌名匹配分 + 歌手匹配额外加 50
      const scored = songs.map(s => {
        let score = this._scoreMatch(name, s)
        if (artist && s.artist && _n(s.artist).includes(_n(artist))) score += 50
        return { song: s, score }
      })
      scored.sort((a, b) => b.score - a.score)

      // 歌名匹配分必须 ≥60
      if (scored[0].score < 60) {
        wx.showToast({ title: '没找到 ' + name, icon: 'none' })
        if (onFound) onFound(name, artist || '', false)
        return
      }

      // ★ 多版本检测：有 ≥2 个高分结果且歌手不同 → 让用户选
      const candidates = scored.filter(s => s.score >= 60).slice(0, 5)
      const artists = [...new Set(candidates.map(s => s.song.artist))]
      if (!artist && artists.length > 1) {
        wx.showActionSheet({
          itemList: candidates.map(s => `${s.song.name} - ${s.song.artist || '未知'}`),
          success: (r) => {
            this._playCandidate(candidates[r.tapIndex], onFound, onPlayed)
          },
          fail: () => {
            // 用户取消选择 → 直接播第一个
            this._playCandidate(candidates[0], onFound, onPlayed)
          },
        })
        return
      }

      // 单版本或用户已指定歌手 → 直接尝试播放
      this._tryPlayList(scored, 0, onFound, onPlayed)
    }).catch(() => {
      wx.showToast({ title: '搜索失败', icon: 'none' })
      if (onFound) onFound(name, artist || '', false)
    })
  },

  // ★ 播放单个候选歌曲
  _playCandidate(item, onFound, onPlayed) {
    const s = item.song
    app.request('/api/song/url?id=' + s.id).then(urlRes => {
      if (!urlRes.url) {
        wx.showToast({ title: s.name + ' 暂无版权', icon: 'none' })
        if (onFound) onFound(s.name, s.artist || '', false)
        return
      }
      this._addToQueue({ id: s.id, name: s.name, artist: s.artist, cover: s.cover || '' })
      app.playSong({ id: s.id, name: s.name, artist: s.artist, url: urlRes.url, cover: s.cover || '' })
      this.updatePlayerState()
      if (onFound) onFound(s.name, s.artist || '', true)
      if (onPlayed) onPlayed()
    }).catch(() => {
      wx.showToast({ title: s.name + ' 加载失败', icon: 'none' })
      if (onFound) onFound(s.name, s.artist || '', false)
    })
  },

  // ★ 逐个尝试播放列表中的歌曲（跳过无版权）
  _tryPlayList(list, idx, onFound, onPlayed) {
    if (idx >= list.length) {
      wx.showToast({ title: '暂无可播放版本', icon: 'none' })
      if (onFound) onFound('', '', false)
      return
    }
    const { song: s } = list[idx]
    app.request('/api/song/url?id=' + s.id).then(urlRes => {
      if (!urlRes.url) { this._tryPlayList(list, idx + 1, onFound, onPlayed); return }
      this._addToQueue({ id: s.id, name: s.name, artist: s.artist, cover: s.cover || '' })
      app.playSong({ id: s.id, name: s.name, artist: s.artist, url: urlRes.url, cover: s.cover || '' })
      this.updatePlayerState()
      if (onFound) onFound(s.name, s.artist || '', true)
      if (onPlayed) onPlayed()
    }).catch(() => this._tryPlayList(list, idx + 1, onFound, onPlayed))
  },

  // ★ 入队 + 设索引
  _addToQueue(meta) {
    const queue = app.globalData.playQueue
    if (!queue.find(q => q.id === meta.id)) {
      queue.push(meta)
      app.globalData.queueIndex = queue.length - 1
    } else {
      app.globalData.queueIndex = queue.findIndex(q => q.id === meta.id)
    }
  },

  // ★ 歌名匹配评分（越高越匹配）
  _scoreMatch(keyword, song) {
    const k = keyword.toLowerCase().replace(/\s+/g, '')
    const n = (song.name || '').toLowerCase().replace(/\s+/g, '')
    if (k === n) return 100        // 完全一致
    if (n.includes(k)) return 80   // 歌名包含关键词
    if (k.includes(n)) return 60   // 关键词包含歌名
    // 逐字匹配
    let hits = 0
    for (const ch of k) { if (n.includes(ch)) hits++ }
    return hits
  },

  // ★ 播放歌曲（传入原始封面 URL）
  _loadAndPlay(id, name, artist, coverUrl, onPlayed) {
    wx.showLoading({ title: '加载中' })
    app.request('/api/song/url?id=' + id).then(urlRes => {
      wx.hideLoading()
      const url = urlRes.url || ''
      if (!url) { wx.showToast({ title: '暂无版权', icon: 'none' }); return }
      this._addToQueue({ id, name, artist, cover: coverUrl || '' })
      app.playSong({ id, name, artist, url, cover: coverUrl || '' })
      this.updatePlayerState()
      if (onPlayed) onPlayed()
    }).catch(() => { wx.hideLoading(); wx.showToast({ title: '加载失败', icon: 'none' }) })
  },

  playSong(e) {
    const { id, name, artist } = e.currentTarget.dataset
    this._loadAndPlay(id, name, artist)
  },

  // ★ 收集前端本地产生的 bot 回复，传给后端同步对话历史
  _collectContext() {
    const ctx = []
    for (let i = this.data.messages.length - 1; i >= 0; i--) {
      const m = this.data.messages[i]
      if (m._synced) break
      if (m.role === 'bot' && m._local) {
        ctx.unshift({ role: 'assistant', content: m.content })
        m._local = false
        m._synced = true
      }
    }
    return ctx
  },

  // ★ 用户选择头像
  onChooseAvatar(e) {
    const avatarUrl = e.detail.avatarUrl
    if (!avatarUrl) return
    this.setData({ avatarUser: avatarUrl })
    wx.setStorageSync('avatarUser', avatarUrl)
  },

  // ★ 点击音乐卡片歌名 → 播放并跳转播放页
  goPlayerFromCard(e) {
    const { name, artist } = e.currentTarget.dataset
    this._searchAndPlay(name, artist, null, () => {
      if (app.globalData.currentSong) {
        wx.navigateTo({ url: '/pages/player/player' })
      }
    })
  },
})
