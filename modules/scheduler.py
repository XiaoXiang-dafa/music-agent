# -*- coding: utf-8 -*-
"""
定时任务模块
处理早安、晚安、纪念日提醒等定时消息
"""
import os
import json
import sqlite3
from datetime import datetime, date
from apscheduler.schedulers.background import BackgroundScheduler


class BotScheduler:
    """
    微信机器人定时任务管理

    依赖: APScheduler (pip install apscheduler)
    任务:
    - 早安 7:00
    - 晚安 24:00
    - 纪念日提醒 (每天检查一次)
    - 消息摘要 (每小时检查一次)
    """

    def __init__(self, config: dict, data_dir: str):
        self.config = config
        self.data_dir = data_dir
        self.scheduler = BackgroundScheduler()
        self._send_callback = None  # 发消息的回调函数，由 bot.py 注入
        self._music_callback = None  # 歌单生成回调
        self.unread_count = {}  # 记录每个用户未读消息数

    def set_send_callback(self, callback):
        """设置发消息回调: callback(message)"""
        self._send_callback = callback

    def set_music_callback(self, callback):
        """设置歌单回调: callback() -> str 返回格式化歌单消息"""
        self._music_callback = callback

    def start(self):
        """启动所有定时任务"""
        schedule_conf = self.config.get("schedule", {})

        # 早安
        morning = schedule_conf.get("morning_time", "07:00")
        hour, minute = morning.split(":")
        self.scheduler.add_job(
            self._morning_task,
            'cron', hour=int(hour), minute=int(minute),
            id='morning', name='早安问候'
        )
        print(f"⏰ 早安定时: {morning}")

        # 每日歌单 (已合并到早安；CLI 测试可先 set_music_callback 再 start)
        print("🎵 歌单: 已并入早安消息")

        # 晚安
        night = schedule_conf.get("night_time", "00:00")
        hour, minute = night.split(":")
        self.scheduler.add_job(
            self._night_task,
            'cron', hour=int(hour), minute=int(minute),
            id='night', name='晚安问候'
        )
        print(f"⏰ 晚安定时: {night}")

        # 纪念日检查 (每天 8:00 检查一次)
        self.scheduler.add_job(
            self._anniversary_task,
            'cron', hour=8, minute=0,
            id='anniversary', name='纪念日提醒'
        )
        print("⏰ 纪念日检查: 每天 8:00")

        # 消息摘要检查 (每小时)
        self.scheduler.add_job(
            self._summary_task,
            'cron', minute=0,
            id='summary', name='消息摘要检查'
        )
        print("⏰ 消息摘要检查: 每小时")

        self.scheduler.start()
        print("✅ 所有定时任务已启动")

    def stop(self):
        self.scheduler.shutdown()
        print("定时任务已停止")

    def track_message(self, user_id: str):
        """追踪未读消息（对方发消息时调用）"""
        self.unread_count[user_id] = self.unread_count.get(user_id, 0) + 1

    def reset_unread(self, user_id: str):
        """已读某用户的所有消息（回复后调用）"""
        self.unread_count[user_id] = 0

    def _send(self, message: str):
        """通过回调发送消息"""
        if self._send_callback:
            try:
                # 回调需要知道发给谁 → 暂时用全局 partner
                # 实际使用时从数据库或配置读取 partner 的微信 ID
                self._send_callback(message)
            except Exception as e:
                print(f"[Scheduler] 发送失败: {e}")

    def _morning_task(self):
        """早安任务"""
        print(f"[{datetime.now():%H:%M}] 执行早安任务")
        # 早安消息包含天气，由 bot.py 主逻辑组装
        if self._send_callback:
            self._send_callback("__MORNING__")  # 特殊标记，bot.py 处理

    def _music_task(self):
        """每日歌单任务"""
        print(f"[{datetime.now():%H:%M}] 执行歌单任务")
        if self._music_callback:
            try:
                msg = self._music_callback()
                if msg:
                    self._send(msg)
            except Exception as e:
                print(f"[Music] 歌单生成失败: {e}")

    def _night_task(self):
        """晚安任务"""
        print(f"[{datetime.now():%H:%M}] 执行晚安任务")
        night_messages = [
            "晚安啦 早点休息",
            "今天辛苦了 好梦",
            "晚安 明天见",
            "不早啦 该睡了",
            "睡了睡了 晚安",
            "好梦",
        ]
        import random
        msg = random.choice(night_messages)
        self._send(msg)

    def _anniversary_task(self):
        """检查纪念日"""
        anniversaries = self.config.get("anniversaries", [])
        today = date.today()

        for ann in anniversaries:
            ann_date = datetime.strptime(ann["date"], "%Y-%m-%d").date()
            remind_before = ann.get("remind_before_days", 1)

            # 计算距离纪念日还有多少天
            this_year_date = date(today.year, ann_date.month, ann_date.day)
            days_left = (this_year_date - today).days

            if days_left < 0:
                # 今年的已经过了，算明年的
                next_year_date = date(today.year + 1, ann_date.month, ann_date.day)
                days_left = (next_year_date - today).days

            # 到期前 remind_before 天提醒
            if 0 <= days_left <= remind_before:
                years = today.year - ann_date.year
                if days_left == 0:
                    msg = f"🎉 今天是 {ann['name']} {years} 周年！"
                else:
                    msg = f"📅 提醒：还有 {days_left} 天就是 {ann['name']} 了（{years} 周年），别忘了准备哦"
                self._send(msg)
                print(f"[纪念日] {msg}")

    def _summary_task(self):
        """检查是否需要生成消息摘要"""
        if not self.unread_count:
            return

        for user_id, count in self.unread_count.items():
            if count >= 5:
                msg = (f"📋 你有 {count} 条未读消息，"
                       f"最后一条: \"[由 AI 生成摘要...]\" "
                       f"— 有空记得回一下哦")
                # 这里只提醒，不实际发摘要（摘要需要调 AI）
                # 真正的摘要在 bot.py 里处理
                self._send(f"__SUMMARY__:{user_id}:{count}")
