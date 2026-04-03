import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv

load_dotenv()
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ─────────────────────────────────────────────
# 🔰 等级顺序
# ─────────────────────────────────────────────

RANK_ORDER = [
    "初级机器人",      # 0
    "高级机器人",      # 1
    "服务领队",        # 2
    "初级管理员",      # 3
    "高级管理员",      # 4
    "主管",            # 5
    "经理",            # 6
    "初级公司",        # 7
    "执行实习生",      # 8
    "执行官",          # 9
    "副总裁",          # 10
    "总裁",            # 11
    "副主席",          # 12
    "主席",            # 13
    "理事会实习生",    # 14
    "星球委员会",      # 15
    "执行委员会",      # 16
    "外星委员会",      # 17
    "领导力实习生",    # 18
    "专员",            # 19
    "社区官员",        # 20
    "社区经理",        # 21
    "副服主",          # 22
    "服主",            # 23
]

# ─────────────────────────────────────────────
# 🗂️ 档次划分
# ─────────────────────────────────────────────

RANK_TIERS = [
    {"keyword": "LR", "min": 0, "max": 4},
    {"keyword": "MR", "min": 5, "max": 6},
    {"keyword": "HR", "min": 7, "max": 11},
    {"keyword": "SHR", "min": 12, "max": 17},
    {"keyword": "Leadership Rank", "min": 18, "max": 20},
    {"keyword": "Ownership Rank", "min": 21, "max": 23},
]

PERMISSION_MIN_INDEX = 7

LOG_GUILD_ID = 1360354820757651657
LOG_CHANNEL_ID = 1454209918432182404


# 🔍 找角色
def find_role(guild, name):
    name_low = name.lower()
    for role in guild.roles:
        if name_low in role.name.lower():
            return role
    return None


# 📋 获取职位
def get_user_rank_info(member):
    for role in member.roles:
        role_low = role.name.lower()
        for idx, rank_name in enumerate(RANK_ORDER):
            if rank_name.lower() in role_low:
                return idx, rank_name
    return -1, None


# 🗂️ 获取档次
def get_tier(index):
    for tier in RANK_TIERS:
        if tier["min"] <= index <= tier["max"]:
            return tier["keyword"]
    return None


# ⬆️ 下一个
def next_rank(i):
    return RANK_ORDER[i+1] if i+1 < len(RANK_ORDER) else None

# ⬇️ 上一个
def prev_rank(i):
    return RANK_ORDER[i-1] if i-1 >= 0 else None


# 📝 日志
async def log_action(ctx, action, target, old, new, tier):
    log_guild = bot.get_guild(LOG_GUILD_ID)
    channel = log_guild.get_channel(LOG_CHANNEL_ID) if log_guild else None
    if not channel:
        return
    emoji = "⬆️" if action == "promote" else "⬇️"
    embed = discord.Embed(
        title=f"{emoji} 职级{action}记录",
        color=discord.Color.green() if action == "promote" else discord.Color.red()
    )
    embed.add_field(name="操作人", value=f"{ctx.author} (`{ctx.author.display_name}`)", inline=False)
    embed.add_field(name="目标", value=f"{target} (`{target.display_name}`)", inline=False)
    embed.add_field(name="原职位", value=old, inline=True)
    embed.add_field(name="新职位", value=new, inline=True)
    embed.add_field(name="档次", value=tier, inline=True)
    embed.set_footer(text=f"服务器: {ctx.guild.name}")
    embed.timestamp = discord.utils.utcnow()
    await channel.send(embed=embed)


# ─────────────────────────────────────────────
# !promote 晋升
# ─────────────────────────────────────────────

@bot.command(name="promote")
async def promote(ctx, member: discord.Member = None):
    if not member:
        await ctx.send("❌ 用法: !promote @用户")
        return

    my_idx, my_rank = get_user_rank_info(ctx.author)
    target_idx, target_rank = get_user_rank_info(member)

    if my_idx < PERMISSION_MIN_INDEX:
        await ctx.send("❌ 权限不足！")
        return
    if target_idx == -1:
        await ctx.send("❌ 没有职位！")
        return
    if my_idx <= target_idx:
        await ctx.send("❌ 只能操作比你低的！")
        return

    new_rank_name = next_rank(target_idx)
    if not new_rank_name:
        await ctx.send("❌ 已经最高了！")
        return

    old_role = find_role(ctx.guild, target_rank)
    new_role = find_role(ctx.guild, new_rank_name)

    if not new_role:
        await ctx.send(f"❌ 找不到：{new_rank_name}")
        return

    # ⚡⚡⚡ 纯执行！什么都没有！
    await member.add_roles(new_role)
    if old_role:
        await member.remove_roles(old_role)

    await ctx.send(f"⬆️ 完成！{member.display_name} 「{target_rank}」→「{new_rank_name}」")
    await log_action(ctx, "promote", member, target_rank, new_rank_name, get_tier(target_idx))


# ─────────────────────────────────────────────
# !demote 降级
# ─────────────────────────────────────────────

@bot.command(name="demote")
async def demote(ctx, member: discord.Member = None):
    if not member:
        await ctx.send("❌ 用法: !demote @用户")
        return

    my_idx, my_rank = get_user_rank_info(ctx.author)
    target_idx, target_rank = get_user_rank_info(member)

    if my_idx < PERMISSION_MIN_INDEX:
        await ctx.send("❌ 权限不足！")
        return
    if target_idx == -1:
        await ctx.send("❌ 没有职位！")
        return
    if my_idx <= target_idx:
        await ctx.send("❌ 只能操作比你低的！")
        return

    new_rank_name = prev_rank(target_idx)
    if not new_rank_name:
        await ctx.send("❌ 已经最低了！")
        return

    old_role = find_role(ctx.guild, target_rank)
    new_role = find_role(ctx.guild, new_rank_name)

    if not new_role:
        await ctx.send(f"❌ 找不到：{new_rank_name}")
        return

    # ⚡⚡⚡ 纯执行！什么都没有！
    await member.add_roles(new_role)
    if old_role:
        await member.remove_roles(old_role)

    await ctx.send(f"⬇️ 完成！{member.display_name} 「{target_rank}」→「{new_rank_name}」")
    await log_action(ctx, "demote", member, target_rank, new_rank_name, get_tier(target_idx))


# ─────────────────────────────────────────────
# 基础功能
# ─────────────────────────────────────────────

@bot.event
async def on_ready():
    print(f"✅ 机器人已上线: {bot.user}")
    await bot.change_presence(activity=discord.Activity(name="职级系统", type=discord.ActivityType.watching))
    keep_alive.start()

@tasks.loop(minutes=5)
async def keep_alive():
    print(f"💓 心跳检测")

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send(f"🏓 Pong! {round(bot.latency * 1000)}ms")

@bot.command(name="myrank")
async def myrank(ctx):
    idx, name = get_user_rank_info(ctx.author)
    if name:
        await ctx.send(f"🔍 你的职级：{name} ({idx})")
    else:
        await ctx.send("🔍 未检测到职级")


if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_BOT_TOKEN"))
