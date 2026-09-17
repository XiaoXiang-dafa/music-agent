#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
"""
AI 日常生活助手 — 微信聊天机器人
===================================
模仿指定对象的 AI 助手，跑在微信私聊窗口

使用方式:
1. 设置环境变量中的 API Key 等凭据
2. 把聊天记录放到 data/chat_history.txt（可选）
3. 运行: python3 bot.py
4. 扫码登录微信小号
5. 你的聊天对象给小号发消息即可

停止: Ctrl+C
"""

import os
import sys
import json
import time
import signal
import re
from datetime import datetime
from openai import OpenAI

# 添加 modules 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'modules'))

from personality import PersonalityExtractor
from scheduler import BotScheduler
from weather import WeatherService
from music import MusicRecommender
from common import resolve_api_keys, require_deepseek_api_key, is_configured_secret, morning_greeting, weather_hint, build_morning_message

# ==================== 全局变量 ====================
BOT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BOT_DIR, 'data')
CONFIG_PATH = os.path.join(BOT_DIR, 'config.json')

bot_config = None
ai_client = None
personality = None
scheduler = None
weather_svc = None
system_prompt = None
partner_user_id = None  # 聊天对象的微信 ID（运行时确定）
itchat = None
music_rec = None


# ==================== 初始化 ====================

def load_config():
    global bot_config
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        bot_config = json.load(f)
    resolve_api_keys(bot_config)
    print(f"📋 配置已加载: {CONFIG_PATH}")


def init_ai():
    """初始化 DeepSeek AI 客户端"""
    global ai_client
    cfg = bot_config['deepseek']
    try:
        require_deepseek_api_key(bot_config)
    except RuntimeError as exc:
        print(f"⚠️  {exc}")
        return False
    ai_client = OpenAI(
        api_key=cfg['api_key'],
        base_url=cfg.get('api_base', 'https://api.deepseek.com')
    )
    print(f"🤖 AI 已连接: {cfg.get('model', 'deepseek-chat')}")
    return True


def init_personality():
    """初始化人格模块"""
    global personality, system_prompt
    cfg = bot_config['personality']
    extractor = PersonalityExtractor(
        chat_file=os.path.join(BOT_DIR, cfg.get('chat_history_file', 'data/chat_history.txt')),
        my_name=cfg['my_name'],
        partner_name=cfg['partner_name'],
        relationship=cfg.get('relationship', '朋友')
    )

    if extractor.load_and_parse():
        extractor.analyze()
        system_prompt = extractor.generate_prompt()
        print("✅ AI 人格已生成（基于聊天记录）")
    else:
        system_prompt = extractor.get_default_prompt()
        print("✅ 使用默认 AI 人格")

    personality = extractor


def init_scheduler():
    """初始化定时任务"""
    global scheduler
    scheduler = BotScheduler(bot_config, DATA_DIR)
    scheduler.set_send_callback(_on_scheduled_message)
    # 先不启动，等微信登录成功后再启动


def init_weather():
    """初始化天气服务"""
    global weather_svc
    cfg = bot_config.get('weather', {})
    api_key = cfg.get('api_key', '')
    if is_configured_secret(api_key):
        weather_svc = WeatherService(api_key, city=bot_config['schedule'].get('weather_city', 'auto'))
        print("🌤 天气服务已就绪")


# ==================== AI 对话 ====================

def ai_chat(user_message: str, conversation_history: list = None) -> str:
    """
    调用 AI 生成回复

    Args:
        user_message: 对方发来的消息
        conversation_history: 最近的对话历史 [{"role": "user/assistant", "content": "..."}]

    Returns:
        AI 生成的回复文本
    """
    messages = [{"role": "system", "content": system_prompt}]

    # 加入最近对话历史（避免上下文太长，只取最近 10 轮）
    if conversation_history:
        messages.extend(conversation_history[-20:])  # 10 轮 = 20 条

    messages.append({"role": "user", "content": user_message})

    try:
        response = ai_client.chat.completions.create(
            model=bot_config['deepseek'].get('model', 'deepseek-chat'),
            messages=messages,
            temperature=0.8,   # 稍高温度让回复更自然
            max_tokens=500,    # 微信消息不用太长
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[AI Error] {e}")
        return "（消息发送失败，请稍后再试）"


def load_partner_id():
    """从磁盘加载聊天对象 ID（重启后保留）"""
    global partner_user_id
    partner_file = os.path.join(DATA_DIR, 'partner_id.txt')
    if os.path.exists(partner_file):
        with open(partner_file, 'r') as f:
            partner_user_id = f.read().strip()
        print(f"📌 已加载聊天对象 ID")


def save_partner_id():
    """保存聊天对象 ID 到磁盘"""
    partner_file = os.path.join(DATA_DIR, 'partner_id.txt')
    with open(partner_file, 'w') as f:
        f.write(partner_user_id)

def _on_scheduled_message(message: str):
    """
    定时任务回调
    message 可能是:
    - 普通文本: 直接发送
    - "__MORNING__": 早安，需要组装天气
    - "__SUMMARY__:user_id:count": 消息摘要提醒
    """
    global partner_user_id
    if not partner_user_id:
        print("[Scheduler] 尚未确定聊天对象，跳过")
        return

    if message == "__MORNING__":
        # 组装早安消息（含天气）
        greeting = morning_greeting()
        weather_part, _ = build_morning_message(weather_svc, greeting)
        itchat.send(weather_part, toUserName=partner_user_id)
        print(f"[早安] 已发送")

    elif message.startswith("__SUMMARY__"):
        # 消息摘要提醒发给 bot 主人（可以用主号）
        # 这里暂时不做，后续完善
        pass
    else:
        # 普通消息（晚安等）
        if itchat:
            itchat.send(message, toUserName=partner_user_id)
            print(f"[定时] 已发送: {message[:30]}...")


# 对话历史缓存（内存中，重启丢失）
conversation_history = {}  # {user_id: [{"role": ..., "content": ...}]}
MAX_HISTORY = 30  # 最多保留 15 轮对话


def handle_message(msg):
    """处理收到的微信消息"""
    global partner_user_id

    from_user = msg.get('FromUserName', '')
    to_user = msg.get('ToUserName', '')
    text = msg.get('Text', '').strip()
    msg_type = msg.get('Type', '')

    # 只处理私聊消息，忽略群聊和系统消息
    if msg_type != 'Text':
        return

    # 忽略自己发的
    if from_user == itchat.loginInfo['User']['UserName']:
        return

    # 记录聊天对象（首次保存到磁盘）
    if partner_user_id != from_user:
        partner_user_id = from_user
        save_partner_id()

    # 获取对方昵称
    nick = itchat.search_friends(userName=from_user)
    if nick:
        nick = nick.get('NickName', '未知')

    print(f"\n💬 [{nick}] {text[:80]}")

    # 追踪未读消息
    scheduler.track_message(from_user)

    # 构建对话历史
    if from_user not in conversation_history:
        conversation_history[from_user] = []

    history = conversation_history[from_user]

    # 调用 AI 生成回复
    reply = ai_chat(text, history)

    # 保存对话历史
    history.append({"role": "user", "content": text})
    history.append({"role": "assistant", "content": reply})

    # 限制历史长度
    if len(history) > MAX_HISTORY:
        conversation_history[from_user] = history[-MAX_HISTORY:]

    # 发送回复
    itchat.send(reply, toUserName=from_user)
    print(f"🤖 [回复] {reply[:80]}")

    # 重置未读计数
    scheduler.reset_unread(from_user)


# ==================== 主程序 ====================

def main():
    global itchat

    print("=" * 50)
    print("   AI 日常生活助手 - 微信聊天机器人")
    print("=" * 50)

    # 1. 加载配置
    load_config()

    # 1.5 加载历史聊天对象 ID
    load_partner_id()

    # 2. 初始化 AI
    if not init_ai():
        print("请配置 DeepSeek API Key 后重新运行")
        return

    # 3. 初始化人格
    init_personality()

    # 4. 初始化天气
    init_weather()

    # 5. 初始化定时任务（需要在微信登录后才启动）
    init_scheduler()

    # 6. 登录微信
    print("\n📱 正在启动微信登录...")
    import itchat as itchat_module
    itchat = itchat_module

    # 注册消息处理器（必须在 auto_login 之前）
    itchat.msg_register(['Text', 'Note'])(handle_message)

    # itchat-uos 热登录（避免每次扫码）
    itchat.auto_login(
        hotReload=True,
        enableCmdQR=2,  # 命令行显示二维码
    )

    # 7. 微信登录成功后启动定时任务
    scheduler.start()

    # 8. 打印运行信息
    print("\n" + "=" * 50)
    print("✅ 机器人已启动！")
    print(f"   AI 人格: {bot_config['personality']['my_name']}")
    print(f"   聊天对象: {bot_config['personality']['partner_name']}")
    print(f"   早安: {bot_config['schedule']['morning_time']}")
    print(f"   晚安: {bot_config['schedule']['night_time']}")
    print("   按 Ctrl+C 停止")
    print("=" * 50 + "\n")

    # 9. 进入消息循环
    itchat.run()


def cleanup():
    """退出清理"""
    print("\n🛑 正在关闭...")
    if scheduler:
        scheduler.stop()
    if itchat:
        itchat.logout()
    print("👋 已退出")


if __name__ == '__main__':
    # 注册退出信号
    signal.signal(signal.SIGINT, lambda sig, frame: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda sig, frame: sys.exit(0))

    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cleanup()
