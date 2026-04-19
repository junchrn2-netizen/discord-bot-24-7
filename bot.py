import discord
from discord.ext import commands
import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ─────────────────────────────────────────────
# 🔰 职级 ID 精准绑定
# ─────────────────────────────────────────────
RANK_IDS = [
    1428876572064223322, # 0: 服务领队
    1433151035605647413, # 1: 初级管理员
    1474453339969290393, # 2: 高级管理员
    1474453748976849057, # 3: 主管
    1474454248057212939, # 4: 经理
    1474454457428344913, # 5: 初级公司
    1474454651477950536, # 6: 执行实习生
    1478803086737801286, # 7: 执行官
    1474455128915574976, # 8: 副总裁
    1474455312185430097, # 9: 总裁
    1474455618763882725, # 10: 副主席
    1474455834883784837, # 11: 主席
    1474456027821904018, # 12: 理事会实习生
    1474456175129919489, # 13: 星球委员会
    1474456544903958685, # 14: 执行委员会
    1474456713246674996, # 15: 外星委员会
    1474456935800770753, # 16: 领导力实习生
    1474457200478126194, # 17: 专员
    1474457093833490575, # 18: 社区官员
    1474457288881213613, # 19: 社区经理
    1433508635056672808, # 20: 副服主
    1433508180247318632  # 21: 服主
]

# 🗂️ 档次 ID 绑定
TIER_CONFIG = [
    {"name": "Low Rank",        "id": 1474457977699434629, "min": 0,  "max": 2},
    {"name": "Middle Rank",     "id": 1474458514721083514, "min": 3,  "max": 4},
    {"name": "High Rank",       "id": 1474458682027937863, "min": 5,  "max": 9},
    {"name": "Super High Rank", "id": 1474458976849629227, "min": 10, "max": 15},
    {"name": "Leadership Rank", "id": 1474459321906626818, "min": 16, "max": 18},
    {"name": "Ownership Rank",  "id": 1474459473920917576, "min": 19, "max": 21},
]

# ─────────────────────────────────────────────
# 🔍 核心识别工具
# ─────────────────────────────────────────────

def get_rank_index(member):
    m_role_ids = [r.id for r in member.roles]
    for i in range(len(RANK_IDS)-1, -1, -1):
        if RANK_IDS[i] in m_role_ids:
            return i
    return -1

def get_tier_data(index):
    for t in TIER_CONFIG:
        if t["min"] <= index <= t["max"]:
            return t
    return None

op_lock = asyncio.Lock()

# ─────────────────────────────────────────────
# 🚀 变动核心处理
# ─────────────────────────────────────────────

async def change_rank(ctx, member, direction):
    if not member:
        embed = discord.Embed(description="❌ 请提及一名成员进行操作。", color=discord.Color.red())
        return await ctx.send(embed=embed)
    
    async with op_lock:
        try:
            member = await ctx.guild.fetch_member(member.id)
        except:
            return await ctx.send("❌ 无法获取成员。")

        # 权限校验
        my_idx = get_rank_index(ctx.author)
        if my_idx < 10:
            embed = discord.Embed(description="❌ **权限不足**！你需要 SHR 或更高级别身份组。", color=discord.Color.red())
            return await ctx.send(embed=embed)

        t_idx = get_rank_index(member)
        if t_idx == -1:
            return await ctx.send("❌ 无法识别对方职位 ID。")

        if my_idx <= t_idx:
            embed = discord.Embed(description=f"❌ **操作被拒**：你的职级 ({my_idx}) 必须高于对方 ({t_idx})。", color=discord.Color.red())
            return await ctx.send(embed=embed)

        new_idx = t_idx + direction
        if new_idx < 0 or new_idx >= len(RANK_IDS):
            return await ctx.send("❌ 职级已达极限。")

        # 准备数据
        action = "晋升" if direction == 1 else "降级"
        embed_color = discord.Color.green() if direction == 1 else discord.Color.red()
        
        old_pos_role = ctx.guild.get_role(RANK_IDS[t_idx])
        new_pos_role = ctx.guild.get_role(RANK_IDS[new_idx])
        old_tier = get_tier_data(t_idx)
        new_tier = get_tier_data(new_idx)

        add_list = [new_pos_role]
        rem_list = [old_pos_role]

        if old_tier and new_tier and old_tier["id"] != new_tier["id"]:
            add_list.append(ctx.guild.get_role(new_tier["id"]))
            rem_list.append(ctx.guild.get_role(old_tier["id"]))

        try:
            add_list = [r for r in add_list if r and r not in member.roles]
            rem_list = [r for r in rem_list if r and r in member.roles]

            await member.add_roles(*add_list)
            await member.remove_roles(*rem_list)

            # 🌟 构建嵌入消息
            embed = discord.Embed(
                title=f"✨ 职级{action}通知",
                color=embed_color,
                timestamp=datetime.now()
            )
            embed.add_field(name="👤 目标对象", value=member.mention, inline=True)
            embed.add_field(name="🛡️ 执行者", value=ctx.author.mention, inline=True)
            embed.add_field(name="📝 变动详情", value=f"<@&{RANK_IDS[t_idx]}> ➜ <@&{RANK_IDS[new_idx]}>", inline=False)
            
            if old_tier["id"] != new_tier["id"]:
                embed.add_field(name="📊 档次变更", value=f"`{old_tier['name']}` ➜ `{new_tier['name']}`", inline=False)
            
            embed.set_footer(text=f"来自服务器: {ctx.guild.name}")
            embed.set_thumbnail(url=member.display_avatar.url)
            
            await ctx.send(embed=embed)
            
            # 日志频道记录
            log_chan = bot.get_channel(1454209918432182404)
            if log_chan:
                await log_chan.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ 运行失败: {e}")

# ─────────────────────────────────────────────
# ⌨️ 命令入口
# ─────────────────────────────────────────────

@bot.command()
@commands.cooldown(1, 4, commands.BucketType.user)
async def promote(ctx, member: discord.Member = None):
    await change_rank(ctx, member, 1)

@bot.command()
@commands.cooldown(1, 4, commands.BucketType.user)
async def demote(ctx, member: discord.Member = None):
    await change_rank(ctx, member, -1)

@bot.event
async def on_ready():
    print(f"✅ {bot.user} 已上线 (Embed 美化版)")

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
