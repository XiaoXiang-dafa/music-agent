"""单独登录脚本 - 生成二维码图片并等待扫码"""
import itchat, os, sys

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
QR_FILE = os.path.join(DATA_DIR, 'qrcode.png')
PKL_FILE = os.path.join(DATA_DIR, 'itchat.pkl')

os.makedirs(DATA_DIR, exist_ok=True)

# 清理旧文件
for f in [QR_FILE, PKL_FILE]:
    if os.path.exists(f):
        os.remove(f)

print("=" * 40)
print("正在获取微信登录二维码...")
print("二维码将显示在桌面上，请用微信小号扫描")
print("=" * 40)

# loginCallback 会在 QR 准备好时被调用
def on_qr(uuid, status, qrcode):
    pass  # itchat 内部会处理

try:
    itchat.auto_login(
        hotReload=True,
        enableCmdQR=2,  # 显示 ASCII QR 到终端
        picDir=QR_FILE,  # 同时保存为图片
    )

    user = itchat.loginInfo['User']
    print(f"\n{'=' * 40}")
    print(f"✅ 登录成功！")
    print(f"   昵称: {user['NickName']}")
    print(f"   微信号: {user.get('Alias', '未设置')}")
    print(f"   登录状态已保存，下次无需扫码")
    print(f"{'=' * 40}")

    itchat.logout()

except Exception as e:
    print(f"\n❌ 登录失败: {e}")
    sys.exit(1)
