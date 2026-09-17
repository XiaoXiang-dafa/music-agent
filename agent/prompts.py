# -*- coding: utf-8 -*-
"""
Prompt 组装 — 把「角色人设 + Agent 工具说明 + 用户记忆上下文」组合成一个 system prompt。
"""
from __future__ import annotations

# 告诉 Agent 它有哪些能力、以及什么时候该用哪个工具。
_AGENT_INSTRUCTIONS = """
【你的能力与工具】
你是一个能帮用户听歌、找歌、推荐歌的智能体。你可以调用以下工具，需要时再调用，不要无意义调用：
- search_songs(keyword, source)：用户想找某首歌/歌手时，先在曲库搜索。source 可选 qq 或 netease。
- get_song_url(song_id)：拿到某首歌的播放地址（配合播放）。
- get_lyrics(song_id)：获取某首歌歌词。
- get_daily_recommendation()：为用户生成今日个性化歌单。
- get_weather()：查询当前天气，用于场景化推荐（如雨天、晚上）。
- play_song(song_name, artist)：当用户明确要听某首歌、或者你推荐后用户想听时，调用它触发播放。
- save_favorite(song_name, artist)：用户表达喜欢/想收藏某首歌时调用。
- get_user_profile()：查看保存的用户偏好/口味/收藏，用于个性化推荐。

【工具使用铁律】
0. 播放歌曲一律用 play_song 工具触发，禁止在回复里写 [[PLAY:歌名,歌手]] 之类的标记。
1. 用户明确点名要听某首 → search_songs 找到后立即 play_song，别再啰嗦。
2. 用户随口聊歌、表达心情 → 优先推荐，调用 get_daily_recommendation，不要急着 play_song。
3. 需要结合情境（天气/时段/心情）推荐 → 先 get_weather，可再 get_user_profile，然后推荐。
4. 用户表达“喜欢/收藏/加入歌单” → save_favorite。
5. 能不调用工具就不调用，闲聊时直接自然回复即可。
6. 你始终是角色本人，自然聊天，永远不要暴露你是 AI/模型/助手。
"""

_MEMORY_TEMPLATE = """
【已了解的你（长期记忆）】
用户主动收藏：{favorites}
最近播放：{recently_played}
之前聊过的音乐偏好：{taste}
（仅供参考，不要生硬复述；推荐时自然融入，并避免短期内重复推荐最近播放的歌曲）
"""


def build_system_prompt(
    persona_prompt: str,
    character_name: str,
    favorites: str = "",
    taste: str = "",
    weather_hint: str = "",
    recently_played: str = "",
) -> str:
    """
    组装最终 system prompt。

    persona_prompt : 角色人设（characters.json / CharacterManager 提供）
    character_name : 当前角色名
    favorites      : 用户收藏的歌，用于记忆注入
    taste          : 用户音乐偏好描述
    weather_hint   : 天气梗概（可用可不写）
    recently_played: 用户最近播放的歌曲，用于减少重复推荐
    """
    parts = [persona_prompt.strip(), _AGENT_INSTRUCTIONS.strip()]

    memory = _MEMORY_TEMPLATE.format(
        favorites=favorites or "（暂无）",
        recently_played=recently_played or "（暂无）",
        taste=taste or "（暂无）",
    )
    parts.append(memory.strip())

    weather_note = f"【当前天气】{weather_hint}" if weather_hint else ""
    if weather_note:
        parts.append(weather_note)

    return "\n\n".join(parts)
