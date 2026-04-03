import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ─────────────────────────────
# 职级顺序
# ─────────────────────────────

RANK_ORDER = [
    "初级机器人",
    "高级机器人",
    "服务领队",
    "初级管理员",
    "高级管理员",
    "主管",
    "经理",
    "初级公司",
    "执行实习生",
    "执行官",
    "副总裁",
    "总裁",
    "副主席",
    "主席",
    "理事会实习生",
    "星球委员会",
    "执行委员会",
    "外星委员会",
    "领导力实习生",
    "专员",
    "社区官员",
    "社区经理",
    "副服主",
    "服主"
]

# ─────────────────────────────
# 档次
# ─────────────────────────────

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


# ─────────────────────────────
# 找角色（精确）
# ─────────────────────────────

def find_role(guild, name):
    return discord.utils.get(guild.roles, name=name)


# ─────────────────────────────
# 获取职位
# ─────────────────────────────

def get_user_rank_info(member):
    for role in member.roles:
        for idx, rank_name in enumerate(RANK_ORDER):
            if role.name == rank_name:
                return idx, rank_name
    return -1, None


# ─────────────────────────────
# 获取档次
# ─────────────────────────────

def get_tier(index):
    for tier in RANK_TIERS:
        if tier["min"] <= index <= tier["max"]:
            return tier["keyword"]
    return "未知"


# ─────────────────────────────
# 上下级
# ─────────────────────────────

def next_rank(i):
    if i + 1 < len(RANK_ORDER):
        return RANK_ORDER[i + 1]
    return None


def prev_rank(i):
    if i - 1 >= 0:
        return RANK_ORDER[i - 1]
    return None


# ─────────────────────────────
# 日志
# ─────────────────────────────

async def log_action(ctx, action, target, old, new, tier):
    log_guild = bot.get_guild(LOG_GUILD_ID)
    if not log_guild:
        return

    channel = log_guild.get_channel(LOG_CHANNEL_ID)
    if not channel:
        return

    emoji = "⬆️" if action == "promote" else "⬇️"

    embed = discord.Embed(
        title=f"{emoji} 职级{action}记录",
        color=discord.Color.green() if action == "promote" else discord.Color.red()
    )

    embed.add_field(name="操作人", value=f"{ctx.author} ({ctx.author.id})", inline=False)
    embed.add_field(name="目标", value=f"{target} ({target.id})", inline=False)
    embed.add_field(name="原职位", value=old, inline=True)
    embed.add_field(name="新职位", value=new, inline=True)
    embed.add_field(name="档次", value=tier, inline=True)

    embed.timestamp = discord.utils.utcnow()

    await channel.send(embed=embed)


# ─────────────────────────────
# 晋升
# ─────────────────────────────

@bot.command()
async def promote(ctx, member: discord.Member = None):

    if not member:
        await ctx.send("❌ 用法: !promote @用户")
        return

    my_idx, my_rank = get_user_rank_info(ctx.author)
    target_idx, target_rank = get_user_rank_info(member)

    if my_idx < PERMISSION_MIN_INDEX:
        await ctx.send("❌ 权限不足")
        return

    if target_idx == -1:
        await ctx.send("❌ 对方没有职位")
        return

    if my_idx <= target_idx:
        await ctx.send("❌ 只能晋升比你低的人")
        return

    new_rank_name = next_rank(target_idx)

    if not new_rank_name:
        await ctx.send("❌ 已是最高职位")
        return

    old_role = find_role(ctx.guild, target_rank)
    new_role = find_role(ctx.guild, new_rank_name)

    if not new_role:
        await ctx.send(f"❌ 找不到新职位: {new_rank_name}")
        return

    await member.add_roles(new_role)

    if old_role:
        await member.remove_roles(old_role)

    await ctx.send(
        f"⬆️ 晋升成功\n"
        f"{member.display_name}\n"
        f"{target_rank} → {new_rank_name}"
    )

    await log_action(
        ctx,
        "promote",
        member,
        target_rank,
        new_rank_name,
        get_tier(target_idx)
    )


# ─────────────────────────────
# 降级
# ─────────────────────────────

@bot.command()
async def demote(ctx, member: discord.Member = None):

    if not member:
        await ctx.send("❌ 用法: !demote @用户")
        return

    my_idx, my_rank = get_user_rank_info(ctx.author)
    target_idx, target_rank = get_user_rank_info(member)

    if my_idx < PERMISSION_MIN_INDEX:
        await ctx.send("❌ 权限不足")
        return

    if target_idx == -1:
        await ctx.send("❌ 对方没有职位")
        return

    if my_idx <= target_idx:
        await ctx.send("❌ 只能操作比你低的人")
        return

    new_rank_name = prev_rank(target_idx)

    if not new_rank_name:
        await ctx.send("❌ 已是最低职位")
        return

    old_role = find_role(ctx.guild, target_rank)
    new_role = find_role(ctx.guild, new_rank_name)

    if not new_role:
        await ctx.send(f"❌ 找不到职位: {new_rank_name}")
        return

    await member.add_roles(new_role)

    if old_role:
        await member.remove_roles(old_role)

    await ctx.send(
        f"⬇️ 降级成功\n"
        f"{member.display_name}\n"
        f"{target_rank} → {new_rank_name}"
    )

    await log_action(
        ctx,
        "demote",
        member,
        target_rank,
        new_rank_name,
        get_tier(target_idx)
    )


# ─────────────────────────────
# 基础功能
# ─────────────────────────────

@bot.event
async def on_ready():
    print(f"✅ 已上线: {bot.user}")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="职级系统运行中"
        )
    )
    keep_alive.start()


@tasks.loop(minutes=5)
async def keep_alive():
    print("💓 心跳正常")


@bot.command()
async def ping(ctx):
    await ctx.send(f"🏓 {round(bot.latency*1000)}ms")


@bot.command()
async def myrank(ctx):
    idx, name = get_user_rank_info(ctx.author)

    if name:
        await ctx.send(f"你的职位: {name} ({idx})")
    else:
        await ctx.send("未检测到职位")


# ─────────────────────────────
# 启动
# ─────────────────────────────

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
