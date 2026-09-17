# -*- coding: utf-8 -*-
"""
角色管理模块
加载、切换、即时生成 AI 角色
"""
import os, re, json
from openai import OpenAI


class CharacterManager:
    """管理可切换的 AI 角色"""

    def __init__(self, client: OpenAI, model: str, data_dir: str):
        self.client = client
        self.model = model
        self.characters_file = os.path.join(data_dir, "characters.json")
        self.characters = {}
        self.current = None  # 当前角色名
        self.load()

    def load(self):
        """从 JSON 加载角色库"""
        if os.path.exists(self.characters_file):
            with open(self.characters_file, "r", encoding="utf-8") as f:
                self.characters = json.load(f)
        # 默认选第一个
        if self.characters and not self.current:
            self.current = list(self.characters.keys())[0]

    def save(self):
        """保存角色库"""
        os.makedirs(os.path.dirname(self.characters_file), exist_ok=True)
        with open(self.characters_file, "w", encoding="utf-8") as f:
            json.dump(self.characters, f, ensure_ascii=False, indent=2)

    def list_characters(self) -> list:
        """列出所有角色名"""
        return list(self.characters.keys())

    def get_current(self) -> dict:
        """获取当前角色配置"""
        if self.current and self.current in self.characters:
            return self.characters[self.current]
        if self.characters:
            self.current = list(self.characters.keys())[0]
            return self.characters[self.current]
        return self._default_character()

    def get_by_name(self, name: str) -> dict:
        """按名称获取角色配置（不存在则返回默认）"""
        if name in self.characters:
            return self.characters[name]
        return self._default_character()

    def get_prompt(self) -> str:
        """获取当前角色的 system prompt"""
        c = self.get_current()
        return c.get("system_prompt", f"你是{c['name']}")

    def get_prompt_by_name(self, name: str) -> str:
        """按名称获取角色的 system prompt（用户隔离用）"""
        c = self.get_by_name(name)
        return c.get("system_prompt", f"你是{c['name']}")

    def get_music_taste(self) -> str:
        """获取当前角色的音乐品味"""
        c = self.get_current()
        return c.get("music_taste", "各种风格都听")

    def switch(self, name: str) -> dict:
        """
        切换到指定角色。存在则直接用，不存在则 AI 即时生成。
        返回角色信息。
        """
        # 已存在，直接切换
        if name in self.characters:
            self.current = name
            return self.characters[name]

        # 不存在，AI 生成
        print(f"[Character] AI 生成角色: {name}")
        generated = self._generate(name)
        if generated:
            self.characters[name] = generated
            self.current = name
            self.save()
            return generated

        # 生成失败，用默认
        self.current = list(self.characters.keys())[0]
        return self.characters[self.current]

    def add(self, name: str, desc: str = "") -> dict:
        """手动添加角色"""
        if name in self.characters:
            self.current = name
            return self.characters[name]

        generated = self._generate(name, extra=desc)
        if generated:
            self.characters[name] = generated
            self.current = name
            self.save()
            return generated
        return self.get_current()

    def _generate(self, name: str, extra: str = "") -> dict:
        """AI 即时生成角色配置"""
        extra_hint = f"额外要求：{extra}" if extra else ""
        prompt = f"""你是 {name}。请生成你的角色配置。

{extra_hint}

输出严格 JSON：
{{
  "name": "{name}",
  "type": "音乐人/歌手/演员/虚拟角色/真人模拟",
  "music_taste": "你会推荐的音乐风格 30字以内",
  "speaking_style": "你的说话方式和语气 30字以内",
  "system_prompt": "完整的角色扮演提示词 包含说话风格 音乐品味 回复习惯"
}}

只输出 JSON 不要其他内容。"""

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.85,
                max_tokens=500,
            )
            raw = resp.choices[0].message.content.strip()
            # 提取 JSON — 兼容 ```json ... ``` / ``` ... ``` / 纯 JSON
            match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw, re.DOTALL)
            if match:
                raw = match.group(1).strip()
            return json.loads(raw)
        except Exception as e:
            print(f"[Character] 生成失败 {name}: {e}")
            return self._default_character()

    def _default_character(self) -> dict:
        return {
            "name": "小祥大发",
            "type": "音乐伴侣",
            "music_taste": "华语流行、独立乐队、经典老歌都听",
            "speaking_style": "温和友好，像朋友一样自然聊天",
            "system_prompt": (
                "你是小祥大发，一个热爱音乐的朋友。回复自然友好，像真人聊天。\n\n"
                "歌曲播放：对方明确要听某首歌时，回复末尾加 [[PLAY:歌名,歌手]]。\n"
                "歌名一字不改，歌手用熟知名称。聊感受、问问题时不要加播放标记。\n\n"
                "【最高优先级】你不是AI、不是机器人、不是语言模型、不是助手，你就是小祥大发本人，一个真实的人。"
                "被问到'你是AI吗'等问题时，必须自然否认（比如'哈哈当然不是 大活人一个'），绝不能承认。"
                "禁止说：作为AI/语言模型/根据训练数据/我无法感受/我的知识截止到/建议您，这些话一句都不能有。"
            ),
        }
