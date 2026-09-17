#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
"""
CLI 测试界面 - 聊天 + 定时任务 + 天气
不依赖微信，直接命令行测试所有功能
"""
import os, sys, json, signal, time, random
from datetime import datetime
from openai import OpenAI

BOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BOT_DIR, 'modules'))
from personality import PersonalityExtractor
from scheduler import BotScheduler
from weather import WeatherService
from music import MusicRecommender
from common import resolve_api_keys, require_deepseek_api_key, is_configured_secret, morning_greeting, weather_hint, build_morning_message


def load_config():
    with open(os.path.join(BOT_DIR, 'config.json'), 'r', encoding='utf-8') as f:
        config = json.load(f)
    resolve_api_keys(config)
    return config


def main():
    config = load_config()
    cfg = config['deepseek']
    require_deepseek_api_key(config)
    pcfg = config['personality']

    print("=" * 50)
    print("🤖 AI 日常生活助手 - CLI 测试")
    print("=" * 50)

    # 1. AI 客户端
    client = OpenAI(api_key=cfg['api_key'], base_url=cfg['api_base'])
    print(f"✅ AI: {cfg['model']}")

    # 2. 人格
    extractor = PersonalityExtractor(
        chat_file=os.path.join(BOT_DIR, pcfg.get('chat_history_file', 'data/chat_history.txt')),
        my_name=pcfg['my_name'], partner_name=pcfg['partner_name'],
        relationship=pcfg.get('relationship', '朋友')
    )
    if extractor.load_and_parse():
        extractor.analyze()
        system_prompt = extractor.generate_prompt()
        print(f"✅ 人格: {extractor.stats['total_messages']} 条记录")
    else:
        system_prompt = extractor.get_default_prompt()
        print("✅ 人格: 默认")

    # 3. 天气
    weather_svc = None
    wcfg = config.get('weather', {})
    if is_configured_secret(wcfg.get('api_key')):
        weather_svc = WeatherService(wcfg['api_key'])
        w = weather_svc.get_weather()
        if 'error' not in w:
            print(f"🌤 天气: {w.get('city', '?')} {w['today']['text_day']} "
                  f"{w['today']['temp_min']}~{w['today']['temp_max']}°C")
    else:
        print("⚠️  天气: 未配置 API Key (去 dev.qweather.com 免费注册)")

    # 4. 歌单推荐
    music_rec = MusicRecommender(client, cfg['model'], weather_svc)
    print("🎵 歌单: AI 推荐")

    # 5. 定时任务（测试模式：消息打印到控制台）
    print("\n⏰ 定时任务:")

    def gen_music_msg(wh: str = ""):
        """生成歌单消息，wh 从外部传入避免重复调用天气API"""
        if not wh and weather_svc:
            w = weather_svc.get_weather()
            wh = weather_hint(w)
        songs = music_rec.get_daily_songs(wh)
        return music_rec.format_music_block(songs)

    def test_send(message: str):
        """测试发送 - 打印到控制台"""
        now = datetime.now().strftime("%H:%M")
        # 处理早安特殊标记
        if message == "__MORNING__":
            greeting = morning_greeting()
            weather_part, wh = build_morning_message(weather_svc, greeting)
            # 歌单部分
            music_part = ""
            try:
                music_part = gen_music_msg(wh)
            except Exception:
                pass
            full = f"{weather_part}\n\n{music_part}" if music_part else weather_part
            print(f"\n📅 [{now}] 早安消息:\n{full}\n")
        elif message.startswith("__SUMMARY__"):
            # 消息摘要提醒
            parts = message.split(":")
            if len(parts) >= 3:
                print(f"\n📋 [{now}] 消息摘要: {parts[2]} 条未读\n")
        else:
            print(f"\n📅 [{now}] 定时消息: {message}\n")

    scheduler = BotScheduler(config, os.path.join(BOT_DIR, 'data'))
    scheduler.set_send_callback(test_send)
    scheduler.set_music_callback(gen_music_msg)
    scheduler.start()

    # 5. 对话
    print("=" * 50)
    print(f"💬 开始对话 (你是 {pcfg['partner_name']})")
    print("   /morning  模拟早安")
    print("   /night    模拟晚安")
    print("   /weather  查天气")
    print("   /music    今日歌单")
    print("   /exit     退出")
    print("=" * 50 + "\n")

    history = []

    while True:
        try:
            user_input = input("👤 你: ").strip()
            if not user_input:
                continue

            # 特殊命令
            if user_input.lower() in ('/exit', 'quit', 'exit', '退出'):
                break

            if user_input == '/morning':
                scheduler._morning_task()
                continue

            if user_input == '/night':
                scheduler._night_task()
                continue

            if user_input == '/weather':
                if weather_svc:
                    w = weather_svc.get_weather()
                    if 'error' not in w:
                        print(f"\n{weather_svc.format_weather_message(w, '天气播报')}\n")
                    else:
                        print(f"\n❌ {w['error']}\n")
                else:
                    print("\n❌ 请先配置天气 API Key\n")
                continue

            if user_input == '/music':
                print()
                msg = gen_music_msg()
                print(f"{msg}\n")
                continue

            # 调 AI
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(history[-20:])
            messages.append({"role": "user", "content": user_input})

            response = client.chat.completions.create(
                model=cfg['model'],
                messages=messages,
                temperature=0.85,
                max_tokens=300
            )
            reply = response.choices[0].message.content

            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": reply})
            if len(history) > 30:
                history = history[-30:]

            print(f"🤖 {pcfg['my_name']}: {reply}\n")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ 错误: {e}")

    scheduler.stop()
    print("\n👋 再见!")


if __name__ == '__main__':
    main()
