import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# (此处 RANK_IDS, TIER_CONFIG, LOG_IDS 保持不变...)
RANK_IDS = [1428876572064223322, 1433151035605647413, 1474453339969290393, 1474453748976849057, 1474454248057212939, 1474454457428344913, 1474454651477950536, 1478803086737801286, 1474455128915574976, 1474455312185430097, 1474455618763882725, 1474455834883784837, 1474456027821904018, 1474456175129919489, 1474456544903958685, 1474456713246674996, 1474456935800770753, 1474457200478126194, 1474457093833490575, 1474457288881213613, 1433508635056672808, 1433508180247318632]
TIER_CONFIG = [{"name": "Low Rank", "id": 1474457977699434629, "min": 0, "max": 2}, {"name": "Middle Rank", "id": 1474458514721083514, "min": 3, "max": 4}, {"name": "High Rank", "id": 1474458682027937863, "min": 5, "max": 9}, {"name": "Super High Rank", "id": 1474458976849629227, "min": 10, "max": 15}, {"name": "Leadership Rank", "id": 1474459321906626818, "min": 16, "max": 18}, {"name": "Ownership Rank", "id": 1474459473920917576, "min": 19, "max": 21}]
LOG_RANK_CHANGE, LOG_MOD_ACTION, LOG_WARN_ACTION = 1454209918432182404, 1454211444093616238, 1488080667005685850

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())

    async def setup_hook(self):
        print(f"--- 正在初始化 ---")

bot = MyBot()

# ─────────────────────────────────────────────
# 🔍 诊断命令 (如果 !ping 有反应，说明机器人没死)
# ─────────────────────────────────────────────
@bot.command()
async def ping(ctx):
    await ctx.send(f"🏓 机器人存活！延迟: {round(bot.latency * 1000)}ms")

@bot.command()
async def test(ctx):
    m_role_ids = [r.id for r in ctx.author.roles]
    idx = -1
    for i in range(len(RANK_IDS)-1, -1, -1):
        if RANK_IDS[i] in m_role_ids:
            idx = i
            break
    await ctx.send(f"👤 你的名称: {ctx.author.display_name}\n📊 职级索引: {idx} (需要 >= 10 才有管理权限)")

# ─────────────────────────────────────────────
# 🚀 只有同步了，/promote 才会出现
# ─────────────────────────────────────────────
@bot.command()
async def sync(ctx):
    if ctx.author.id != ctx.guild.owner_id:
        # 暂时允许群主或者你指定的 ID 同步
        pass 
    try:
        print("正在同步命令到 Discord...")
        synced = await bot.tree.sync()
        await ctx.send(f"✅ 成功同步 {len(synced)} 个斜杠命令！请稍等几分钟或重启 Discord 查看。")
    except Exception as e:
        await ctx.send(f"❌ 同步失败: {e}")

# (此处插入上一版的所有斜杠命令 /promote, /demote, /mute, /warn 等...)
# 确保在 process_rank 里使用了 await interaction.followup.send(...) 因为 defer() 之后必须用 followup

@bot.event
async def on_ready():
    print(f"✅ 机器人 {bot.user} 已成功登录服务器！")
    print(f"请在 Discord 输入 `!ping` 测试前缀命令。")
    print(f"请在 Discord 输入 `!sync` 同步斜杠命令。")

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
