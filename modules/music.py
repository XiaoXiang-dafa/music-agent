# -*- coding: utf-8 -*-
"""
每日歌单推荐模块
AI 根据天气+季节+时段+个人品味推荐歌曲
"""
import json, re, random, requests as http_requests
from openai import OpenAI


class MusicRecommender:
    """每日歌单推送"""

    def __init__(self, client: OpenAI, model: str, weather_svc=None):
        self.client = client
        self.model = model
        self.weather_svc = weather_svc

    # 用户音乐品味（从聊天记录提取）
    MUSIC_TASTE = (
        "你是什么歌都听的人 歌库很杂 "
        "喜欢初高中时期的老歌 林俊杰 陈奕迅那批 "
        "也听独立乐队和摇滚 偶尔整点英文歌 "
        "不爱太矫情的 喜欢有旋律感的"
    )

    # 网易云无版权/下架的重灾区歌手（不要推荐）
    BLOCKED_ARTISTS = []  # QQ 音乐版权覆盖广，无需屏蔽

    def get_daily_songs(self, weather_info: str = "", custom_taste: str = "") -> list[dict]:
        """
        AI 生成歌单。custom_taste 为当前角色的音乐品味（可选，覆盖默认）
        """
        from datetime import datetime
        now = datetime.now()
        month = now.month
        hour = now.hour
        weekday = now.weekday()
        day_of_month = now.day

        # 季节
        if month in [3, 4, 5]:
            season = "春天"
        elif month in [6, 7, 8]:
            season = "夏天"
        elif month in [9, 10, 11]:
            season = "秋天"
        else:
            season = "冬天"

        # 时段
        if 5 <= hour < 8:
            time_of_day = "清晨刚起床"
        elif 8 <= hour < 12:
            time_of_day = "上午"
        elif 12 <= hour < 14:
            time_of_day = "午后"
        elif 14 <= hour < 18:
            time_of_day = "下午"
        elif 18 <= hour < 22:
            time_of_day = "傍晚"
        else:
            time_of_day = "深夜"

        # 随机氛围词（每次不同 防止重复推荐）
        vibes = [
            "来点小众宝藏 不推大众热单",
            "选几首旋律抓耳但不烂大街的歌",
            "挖掘一些冷门好歌 不要重复之前的",
            "今天换换口味 推荐平时不太会主动听的",
            "来点有故事感的歌 不要太甜的",
            "挑三首气质完全不一样的 风格混搭",
            "别走常规路线 今天大胆一点",
        ]
        vibe = random.choice(vibes)

        # 日期相关的随机种子（每天变化 避免同一季节总推一样的）
        date_anchors = [
            f"今天是{month}月{day_of_month}日 周{['一二三四五六日'][weekday]}",
            f"日期锚点：{month}-{day_of_month} 星期{weekday+1}",
        ]
        date_anchor = random.choice(date_anchors)

        weather_hint = f"天气：{weather_info}。" if weather_info else ""

        blocked = "、".join(self.BLOCKED_ARTISTS)
        prompt = f"""推荐 3 首歌做成今日歌单。

{date_anchor}
{weather_hint}季节：{season}  时段：{time_of_day}
🎲 随机指令：{vibe}

听众品味：{custom_taste or self.MUSIC_TASTE}

要求：
- 歌名和歌手必须真实存在 不能编造
- 严格根据天气 + 季节 + 时段 + 个人品味来选歌 不要随机堆砌
- 推荐理由像朋友分享歌那样自然 不要写乐评 不要用专业术语
- 不要提乐器名 比如不要说萨克斯吉他钢琴 直接说听起来的感受就行
- 铁律：绝对不要推荐以下歌手的歌：{blocked}
- ⚠️ 每次推荐都要不一样 不要总推那几首常见的热门歌

输出格式（严格 JSON）：
[{{"song": "歌名", "artist": "歌手", "reason": "一句话感受"}}]

直接输出 JSON。"""

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=1.2,  # 拉高温度 更多随机性
                max_tokens=400,
            )
            raw = resp.choices[0].message.content.strip()
            # 提取 JSON — 兼容 ```json ... ``` / ``` ... ``` / 纯 JSON
            match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw, re.DOTALL)
            if match:
                raw = match.group(1).strip()
            songs = json.loads(raw)[:3]
        except Exception as e:
            print(f"[Music] AI 生成失败: {e}")
            songs = self._fallback_songs()

        # ★ 过滤无版权的歌曲
        songs = self._filter_playable(songs)

        return songs

    def _check_song_url(self, song_name: str, artist: str) -> bool:
        """检查歌曲是否有可播放的 URL"""
        try:
            from qqmusic import search as ns_search, song_url as ns_url
            results = ns_search(f"{song_name} {artist}", limit=3)
            for r in results:
                if not r.get("id"):
                    continue
                url = ns_url(r["id"])
                if url:
                    return True
            return False
        except Exception:
            return False

    def _filter_playable(self, songs: list[dict]) -> list[dict]:
        """过滤掉无版权的歌曲，返回可播放的"""
        playable = []
        for s in songs:
            name = s.get("song", "")
            artist = s.get("artist", "")
            if self._check_song_url(name, artist):
                playable.append(s)
            else:
                print(f"[Music] 跳过无版权: {name} - {artist}")
        if not playable:
            playable = self._fallback_songs()
        return playable

    def _fallback_songs(self) -> list[dict]:
        """AI 失败时用备用歌单 — 按天气/时段从大池随机抽 3 首"""
        from datetime import datetime
        hour = datetime.now().hour

        # 大类风格池（按时段和心情分）
        morning = [
            {"song": "起风了", "artist": "买辣椒也用券", "reason": "清晨的风和这首歌很搭"},
            {"song": "早安", "artist": "刘瑞琦", "reason": "元气满满的一天开始了"},
            {"song": "晴天", "artist": "周杰伦", "reason": "青春的经典回忆"},
            {"song": "明天你好", "artist": "牛奶咖啡", "reason": "充满希望的感觉"},
            {"song": "少年", "artist": "梦然", "reason": "早上来点活力"},
            {"song": "平凡之路", "artist": "朴树", "reason": "出发的感觉"},
            {"song": "夜空中最亮的星", "artist": "逃跑计划", "reason": "开启新的一天"},
        ]
        afternoon = [
            {"song": "春风十里", "artist": "鹿先森乐队", "reason": "慵懒的午后时光"},
            {"song": "后来", "artist": "刘若英", "reason": "回忆里的味道"},
            {"song": "光年之外", "artist": "邓紫棋", "reason": "午后提提神"},
            {"song": "那些年", "artist": "胡夏", "reason": "想起学生时代"},
            {"song": "蓝莲花", "artist": "许巍", "reason": "自由自在的感觉"},
            {"song": "卡农", "artist": "押尾光太郎", "reason": "安静又舒服"},
            {"song": "匆匆那年", "artist": "王菲", "reason": "慢慢回忆"},
        ]
        evening = [
            {"song": "安和桥", "artist": "宋冬野", "reason": "傍晚就该听听民谣"},
            {"song": "云烟成雨", "artist": "房东的猫", "reason": "治愈又安静"},
            {"song": "南山南", "artist": "马頔", "reason": "夜晚的旋律最对味"},
            {"song": "借我", "artist": "谢春花", "reason": "轻轻柔柔刚刚好"},
            {"song": "理想三旬", "artist": "陈鸿宇", "reason": "低沉嗓音配夜晚"},
            {"song": "不再见", "artist": "陈学冬", "reason": "睡前听一首温柔的歌"},
            {"song": "岁月神偷", "artist": "金玟岐", "reason": "适合晚上一个人听"},
        ]
        rainy = [
            {"song": "下雨天", "artist": "南拳妈妈", "reason": "下雨天听下雨天 没毛病"},
            {"song": "阴天快乐", "artist": "陈奕迅", "reason": "阴雨天也需要快乐"},
            {"song": "听见下雨的声音", "artist": "魏如昀", "reason": "雨天专属bgm"},
            {"song": "大雨将至", "artist": "徐佳莹", "reason": "雨天氛围感拉满"},
            {"song": "雨天", "artist": "孙燕姿", "reason": "经典雨天歌曲"},
        ]

        # 按时段选主池
        if 5 <= hour < 10:
            pool = morning
        elif 10 <= hour < 17:
            pool = afternoon
        else:
            pool = evening

        # 下雨天混入雨天歌
        weather = ""
        try:
            if self.weather_svc:
                w = self.weather_svc.get_weather()
                weather = w.get("text", "")
        except Exception:
            pass
        if "雨" in weather:
            pool = pool + rainy

        # 随机打乱取 3 首
        random.shuffle(pool)
        return pool[:3]

    def format_music_block(self, songs: list[dict]) -> str:
        """歌单块，接在早安消息后面"""
        lines = ["今日歌单"]
        for i, s in enumerate(songs):
            lines.append(f"{s['song']} - {s['artist']}  {s.get('reason', '')}")
        return "\n".join(lines)
