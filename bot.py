import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# 🔰 职级 ID 配置 (ID 绑定)
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

TIER_CONFIG = [
    {"name": "Low Rank",        "id": 1474457977699434629, "min": 0,  "max": 2},
    {"name": "Middle Rank",     "id": 1474458514721083514, "min": 3,  "max": 4},
    {"name": "High Rank",       "id": 1474458682027937863, "min": 5,  "max": 9},
    {"name": "Super High Rank", "id": 1474458976849629227, "min": 10, "max": 15},
    {"name": "Leadership Rank", "id": 1474459321906626818, "min": 16, "max": 18},
    {"name": "Ownership Rank",  "id": 1474459473920917576, "min": 19, "max": 21},
]

# 📺 日志频道 ID
LOG_RANK_CHANGE = 1454209918432182404 # 职级
LOG_MOD_ACTION  = 1454211444093616238 # 管理
LOG_WARN_ACTION = 1488080667005685850 # 警告

# ─────────────────────────────────────────────
# 🤖 初始化
# ─────────────────────────────────────────────

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())

    async def setup_hook(self):
        # 斜杠命令不需要在这里 sync，建议手动 !sync 避免速率限制
        pass

bot = MyBot()

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
# 🛠️ 警告管理指令 (LOG_WARN_ACTION)
# ─────────────────────────────────────────────

# 1. 发出警告
@bot.tree.command(name="warn", description="向成员发出正式警告")
@app_commands.describe(member="目标成员", reason="原因")
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):
    my_idx = get_rank_index(interaction.user)
    if my_idx < 10: return await interaction.response.send_message("❌ 需要 SHR 职级及以上。", ephemeral=True)
    
    embed = discord.Embed(title="⚠️ 成员警告通知", color=discord.Color.yellow(), timestamp=datetime.now())
    embed.add_field(name="目标", value=member.mention, inline=True)
    embed.add_field(name="警告人", value=interaction.user.mention, inline=True)
    embed.add_field(name="原因", value=reason, inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)
    await log_to_channel(LOG_WARN_ACTION, embed)

# 2. 撤销警告
@bot.tree.command(name="unwarn", description="撤销对成员的警告记录")
@app_commands.describe(member="目标成员", reason="撤销的原因")
async def unwarn(interaction: discord.Interaction, member: discord.Member, reason: str = "表现良好/误判"):
    my_idx = get_rank_index(interaction.user)
    if my_idx < 10: return await interaction.response.send_message("❌ 需要 SHR 职级及以上。", ephemeral=True)
    
    embed = discord.Embed(title="✅ 警告撤销记录", color=discord.Color.green(), timestamp=datetime.now())
    embed.add_field(name="目标", value=member.mention, inline=True)
    embed.add_field(name="撤销人", value=interaction.user.mention, inline=True)
    embed.add_field(name="备注", value=reason, inline=False)
    
    await interaction.response.send_message(f"✅ 已成功撤销对 {member.mention} 的警告。")
    await log_to_channel(LOG_WARN_ACTION, embed)

# ─────────────────────────────────────────────
# 🔇 禁言管理指令 (LOG_MOD_ACTION)
# ─────────────────────────────────────────────

# 1. 禁言
@bot.tree.command(name="mute", description="禁言成员 (Timeout)")
@app_commands.describe(member="目标成员", minutes="时长(分钟)", reason="原因")
async def mute(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "违规"):
    my_idx = get_rank_index(interaction.user)
    t_idx = get_rank_index(member)
    if my_idx < 10: return await interaction.response.send_message("❌ 权限不足", ephemeral=True)
    if my_idx <= t_idx: return await interaction.response.send_message("❌ 无法禁言等级比你高或平级的人", ephemeral=True)

    await member.timeout(timedelta(minutes=minutes), reason=reason)
    embed = discord.Embed(title="🔇 成员禁言", color=discord.Color.dark_gray(), timestamp=datetime.now())
    embed.add_field(name="目标", value=member.mention)
    embed.add_field(name="时长", value=f"{minutes} 分钟")
    embed.add_field(name="执行者", value=interaction.user.mention)
    
    await interaction.response.send_message(embed=embed)
    await log_to_channel(LOG_MOD_ACTION, embed)

# 2. 取消禁言
@bot.tree.command(name="unmute", description="解除成员的禁言状态")
@app_commands.describe(member="目标成员")
async def unmute(interaction: discord.Interaction, member: discord.Member):
    my_idx = get_rank_index(interaction.user)
    if my_idx < 10: return await interaction.response.send_message("❌ 权限不足", ephemeral=True)
    
    await member.timeout(None)
    embed = discord.Embed(title="🔊 禁言解除", color=discord.Color.blue(), timestamp=datetime.now())
    embed.add_field(name="目标", value=member.mention)
    embed.add_field(name="执行者", value=interaction.user.mention)
    
    await interaction.response.send_message(f"✅ 已解除 {member.mention} 的禁言。")
    await log_to_channel(LOG_MOD_ACTION, embed)

# ─────────────────────────────────────────────
# 🔨 踢出/封禁/清理 (LOG_MOD_ACTION)
# ─────────────────────────────────────────────

@bot.tree.command(name="clear", description="清理消息")
async def clear(interaction: discord.Interaction, amount: int):
    my_idx = get_rank_index(interaction.user)
    if my_idx < 10: return await interaction.response.send_message("❌ 权限不足", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"✅ 已清理 {len(deleted)} 条消息。")

@bot.tree.command(name="kick", description="踢出成员")
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "违规"):
    my_idx = get_rank_index(interaction.user)
    t_idx = get_rank_index(member)
    if my_idx < 16: return await interaction.response.send_message("❌ 需要 Leadership Rank+", ephemeral=True)
    if my_idx <= t_idx: return await interaction.response.send_message("❌ 职级压制失败", ephemeral=True)
    await member.kick(reason=reason)
    await interaction.response.send_message(f"👞 已踢出 {member.name}")

@bot.tree.command(name="ban", description="封禁成员")
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "严重违规"):
    my_idx = get_rank_index(interaction.user)
    t_idx = get_rank_index(member)
    if my_idx < 19: return await interaction.response.send_message("❌ 需要 Ownership Rank", ephemeral=True)
    if my_idx <= t_idx: return await interaction.response.send_message("❌ 职级压制失败", ephemeral=True)
    await member.ban(reason=reason)
    await interaction.response.send_message(f"🔨 已永久封禁 {member.name}")

# ─────────────────────────────────────────────
# 🚀 职级变动指令 (LOG_RANK_CHANGE)
# ─────────────────────────────────────────────

async def process_rank(interaction, member, direction):
    async with op_lock:
        await interaction.response.defer()
        member = await interaction.guild.fetch_member(member.id)
        my_idx = get_rank_index(interaction.user)
        t_idx = get_rank_index(member)

        if my_idx < 10: return await interaction.followup.send("❌ 权限不足")
        if t_idx == -1: return await interaction.followup.send("❌ 无法识别对方职级")
        if my_idx <= t_idx: return await interaction.followup.send("❌ 你不能操作比你高级的人")

        new_idx = t_idx + direction
        if new_idx < 0 or new_idx >= len(RANK_IDS): return await interaction.followup.send("❌ 职级已达极限")

        # 身份组操作
        old_r, new_r = interaction.guild.get_role(RANK_IDS[t_idx]), interaction.guild.get_role(RANK_IDS[new_idx])
        old_t = next(t for t in TIER_CONFIG if t["min"] <= t_idx <= t["max"])
        new_t = next(t for t in TIER_CONFIG if t["min"] <= new_idx <= t["max"])

        add_l, rem_l = [new_r], [old_r]
        if old_t["id"] != new_t["id"]:
            add_l.append(interaction.guild.get_role(new_t["id"]))
            rem_l.append(interaction.guild.get_role(old_t["id"]))

        await member.add_roles(*[r for r in add_l if r])
        await member.remove_roles(*[r for r in rem_l if r and r in member.roles])

        action = "晋升" if direction == 1 else "降级"
        embed = discord.Embed(title=f"✨ 职级{action}通知", color=discord.Color.green() if direction==1 else discord.Color.red())
        embed.add_field(name="目标", value=member.mention, inline=True)
        embed.add_field(name="变动", value=f"<@&{RANK_IDS[t_idx]}> ➜ <@&{RANK_IDS[new_idx]}>", inline=False)
        await interaction.followup.send(embed=embed)
        await log_to_channel(LOG_RANK_CHANGE, embed)

@bot.tree.command(name="promote", description="晋升职级")
async def promote(interaction: discord.Interaction, member: discord.Member):
    await process_rank(interaction, member, 1)

@bot.tree.command(name="demote", description="降级职级")
async def demote(interaction: discord.Interaction, member: discord.Member):
    await process_rank(interaction, member, -1)

# ─────────────────────────────────────────────
# ⚙️ 系统指令
# ─────────────────────────────────────────────

@bot.command()
@commands.is_owner()
async def sync(ctx):
    synced = await bot.tree.sync()
    await ctx.send(f"✅ 已同步 {len(synced)} 个斜杠命令！")

@bot.event
async def on_ready():
    print(f"✅ 管理机器人 {bot.user} 已上线。")

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
