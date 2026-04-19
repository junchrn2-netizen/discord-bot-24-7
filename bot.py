import discord
from discord.ext import commands
import os
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ─────────────────────────────────────────────
# 🔰 职级 ID 配置 (ID 绑定，保持不变)
# ─────────────────────────────────────────────
RANK_IDS = [
    1428876572064223322, 1433151035605647413, 1474453339969290393, 
    1474453748976849057, 1474454248057212939, 1474454457428344913, 
    1474454651477950536, 1478803086737801286, 1474455128915574976, 
    1474455312185430097, 1474455618763882725, 1474455834883784837, 
    1474456027821904018, 1474456175129919489, 1474456544903958685, 
    1474456713246674996, 1474456935800770753, 1474457200478126194, 
    1474457093833490575, 1474457288881213613, 1433508635056672808, 
    1433508180247318632
]

# 🗂️ 档次配置
TIER_CONFIG = [
    {"name": "Low Rank",        "id": 1474457977699434629, "min": 0,  "max": 2},
    {"name": "Middle Rank",     "id": 1474453339969290393, "min": 3,  "max": 4},
    {"name": "High Rank",       "id": 1474453748976849057, "min": 5,  "max": 9},
    {"name": "Super High Rank", "id": 1474458976849629227, "min": 10, "max": 15},
    {"name": "Leadership Rank", "id": 1474459321906626818, "min": 16, "max": 18},
    {"name": "Ownership Rank",  "id": 1474459473920917576, "min": 19, "max": 21},
]

# 📺 日志频道 ID
LOG_RANK_CHANGE = 1454209918432182404  # 职级变动
LOG_MOD_ACTION  = 1454211444093616238  # 踢出/封禁/清理
LOG_WARN_ACTION = 1488080667005685850  # 警告

# ─────────────────────────────────────────────
# 🔍 核心识别工具
# ─────────────────────────────────────────────

def get_rank_index(member):
    m_role_ids = [r.id for r in member.roles]
    for i in range(len(RANK_IDS)-1, -1, -1):
        if RANK_IDS[i] in m_role_ids: return i
    return -1

async def log_to_channel(channel_id, embed):
    channel = bot.get_channel(channel_id)
    if channel: await channel.send(embed=embed)

op_lock = asyncio.Lock()

# ─────────────────────────────────────────────
# 🛠️ 管理指令：清理/踢出/封禁 (LOG_MOD_ACTION)
# ─────────────────────────────────────────────

# 1. 清理消息
@bot.command(name="clear")
async def clear(ctx, amount: int):
    my_idx = get_rank_index(ctx.author)
    if my_idx < 10: return await ctx.send("❌ 需要 SHR 职级或以上。")
    
    deleted = await ctx.channel.purge(limit=amount + 1)
    
    embed = discord.Embed(title="🧹 消息清理记录", color=discord.Color.blue(), timestamp=discord.utils.utcnow())
    embed.add_field(name="执行频道", value=ctx.channel.mention, inline=True)
    embed.add_field(name="清理数量", value=f"{len(deleted)-1} 条", inline=True)
    embed.add_field(name="操作人", value=ctx.author.mention, inline=False)
    
    await log_to_channel(LOG_MOD_ACTION, embed)
    msg = await ctx.send(f"✅ 已成功清理 {len(deleted)-1} 条消息。", delete_after=3)

# 2. 踢出成员
@bot.command(name="kick")
async def kick(ctx, member: discord.Member, *, reason="违规"):
    my_idx = get_rank_index(ctx.author)
    t_idx = get_rank_index(member)
    
    if my_idx < 16: return await ctx.send("❌ 需要 Leadership Rank 或以上职级才能踢人。")
    if my_idx <= t_idx: return await ctx.send("❌ 你不能踢出职级高于或等于你的人。")

    await member.kick(reason=reason)
    
    embed = discord.Embed(title="👞 成员踢出通知", color=discord.Color.orange(), timestamp=discord.utils.utcnow())
    embed.add_field(name="目标", value=member.mention, inline=True)
    embed.add_field(name="操作人", value=ctx.author.mention, inline=True)
    embed.add_field(name="原因", value=reason, inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)
    
    await ctx.send(embed=embed)
    await log_to_channel(LOG_MOD_ACTION, embed)

# 3. 封禁成员
@bot.command(name="ban")
async def ban(ctx, member: discord.Member, *, reason="严重违规"):
    my_idx = get_rank_index(ctx.author)
    t_idx = get_rank_index(member)
    
    if my_idx < 19: return await ctx.send("❌ 需要 Ownership Rank 职级才能执行封禁。")
    if my_idx <= t_idx: return await ctx.send("❌ 权限不足，无法封禁该高级成员。")

    await member.ban(reason=reason)
    
    embed = discord.Embed(title="🔨 成员封禁通知", color=discord.Color.red(), timestamp=discord.utils.utcnow())
    embed.add_field(name="目标", value=member.mention, inline=True)
    embed.add_field(name="操作人", value=ctx.author.mention, inline=True)
    embed.add_field(name="原因", value=reason, inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)
    
    await ctx.send(embed=embed)
    await log_to_channel(LOG_MOD_ACTION, embed)

# 4. 禁言 (Timeout)
@bot.command(name="mute")
async def mute(ctx, member: discord.Member, minutes: int = 10, *, reason="违规"):
    my_idx = get_rank_index(ctx.author)
    t_idx = get_rank_index(member)
    
    if my_idx < 10: return await ctx.send("❌ 需要 SHR 职级或以上。")
    if my_idx <= t_idx: return await ctx.send("❌ 无法禁言高级成员。")

    await member.timeout(timedelta(minutes=minutes), reason=reason)
    
    embed = discord.Embed(title="🔇 成员禁言通知", color=discord.Color.dark_gray(), timestamp=discord.utils.utcnow())
    embed.add_field(name="目标", value=member.mention, inline=True)
    embed.add_field(name="时长", value=f"{minutes} 分钟", inline=True)
    embed.add_field(name="原因", value=reason, inline=False)
    
    await ctx.send(embed=embed)
    await log_to_channel(LOG_MOD_ACTION, embed)

# ─────────────────────────────────────────────
# ⚠️ 管理指令：警告 (LOG_WARN_ACTION)
# ─────────────────────────────────────────────

@bot.command(name="warn")
async def warn(ctx, member: discord.Member, *, reason):
    my_idx = get_rank_index(ctx.author)
    if my_idx < 10: return await ctx.send("❌ 权限不足。")
    
    embed = discord.Embed(title="⚠️ 成员警告记录", color=discord.Color.yellow(), timestamp=discord.utils.utcnow())
    embed.add_field(name="目标", value=member.mention, inline=True)
    embed.add_field(name="警告人", value=ctx.author.mention, inline=True)
    embed.add_field(name="警告理由", value=reason, inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)
    
    await ctx.send(embed=embed)
    await log_to_channel(LOG_WARN_ACTION, embed)

# ─────────────────────────────────────────────
# 🚀 职级变动指令 (LOG_RANK_CHANGE)
# ─────────────────────────────────────────────

async def execute_rank_change(ctx, member, direction):
    async with op_lock:
        member = await ctx.guild.fetch_member(member.id)
        my_idx = get_rank_index(ctx.author)
        t_idx = get_rank_index(member)

        if my_idx < 10: return await ctx.send("❌ 需要 SHR 职级。")
        if t_idx == -1: return await ctx.send("❌ 无法识别对方职位。")
        if my_idx <= t_idx: return await ctx.send("❌ 等级不足。")

        new_idx = t_idx + direction
        if new_idx < 0 or new_idx >= len(RANK_IDS): return await ctx.send("❌ 职级达极限。")

        old_role, new_role = ctx.guild.get_role(RANK_IDS[t_idx]), ctx.guild.get_role(RANK_IDS[new_idx])
        
        # 档次检测
        old_tier = next(t for t in TIER_CONFIG if t["min"] <= t_idx <= t["max"])
        new_tier = next(t for t in TIER_CONFIG if t["min"] <= new_idx <= t["max"])

        add_list, rem_list = [new_role], [old_role]
        if old_tier["id"] != new_tier["id"]:
            add_list.append(ctx.guild.get_role(new_tier["id"]))
            rem_list.append(ctx.guild.get_role(old_tier["id"]))

        await member.add_roles(*[r for r in add_list if r])
        await member.remove_roles(*[r for r in rem_list if r and r in member.roles])

        action = "晋升" if direction == 1 else "降级"
        embed = discord.Embed(title=f"✨ 职级{action}通知", color=discord.Color.green() if direction==1 else discord.Color.red(), timestamp=discord.utils.utcnow())
        embed.add_field(name="目标", value=member.mention, inline=True)
        embed.add_field(name="变动", value=f"<@&{RANK_IDS[t_idx]}> ➜ <@&{RANK_IDS[new_idx]}>", inline=False)
        if old_tier["id"] != new_tier["id"]:
            embed.add_field(name="档次同步", value=f"`{old_tier['name']}` ➜ `{new_tier['name']}`", inline=False)
        
        await ctx.send(embed=embed)
        await log_to_channel(LOG_RANK_CHANGE, embed)

@bot.command()
async def promote(ctx, member: discord.Member = None): await execute_rank_change(ctx, member, 1)

@bot.command()
async def demote(ctx, member: discord.Member = None): await execute_rank_change(ctx, member, -1)

# ─────────────────────────────────────────────
# 🏁 启动
# ─────────────────────────────────────────────

@bot.event
async def on_ready():
    print(f"✅ 管理机器人 {bot.user} 已上线。")
    print(f"- 日志[职级]: {LOG_RANK_CHANGE}")
    print(f"- 日志[管理]: {LOG_MOD_ACTION}")
    print(f"- 日志[警告]: {LOG_WARN_ACTION}")

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
