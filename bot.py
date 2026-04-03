import discord
from discord.ext import commands
import time

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

LOG_CHANNEL_ID = 1454209918432182404


# ========================
# 等级顺序
# ========================

RANK_ORDER = [

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
    "共同所有人",
    "所有者",
    "持有者"
]


# ========================
# 档次
# ========================

RANK_TIERS = [

    ("LR", 0, 2),
    ("MR", 3, 4),
    ("HR", 5, 9),
    ("SHR", 10, 15),
    ("Leadership Rank", 16, 18),
    ("Ownership Rank", 19, 22)
]


# ========================
# 获取职位
# ========================

def get_user_rank(member):

    for role in member.roles:

        role_name = role.name.lower()

        for i, rank in enumerate(RANK_ORDER):

            if rank.lower() in role_name:

                return i, rank, role

    return None, None, None


def find_role(guild, name):

    for role in guild.roles:
        if name in role.name:
            return role

    return None


def get_tier(index):

    for tier, min_i, max_i in RANK_TIERS:

        if min_i <= index <= max_i:
            return tier

    return "Unknown"


# ========================
# 启动
# ========================

@bot.event
async def on_ready():

    print(f"机器人上线: {bot.user}")


# ========================
# myrank
# ========================

@bot.command()
async def myrank(ctx):

    idx, name, role = get_user_rank(ctx.author)

    if name is None:
        await ctx.send("未检测到职位")
        return

    await ctx.send(
        f"你的职位: {name}\n等级: {idx}\n档次: {get_tier(idx)}"
    )


# ========================
# promote
# ========================

@bot.command()
async def promote(ctx, member: discord.Member):

    if member == ctx.author:
        await ctx.send("不能晋升自己")
        return

    my_idx, my_name, _ = get_user_rank(ctx.author)
    t_idx, t_name, t_role = get_user_rank(member)

    if my_name is None:
        await ctx.send("你没有职位")
        return

    if t_name is None:
        await ctx.send("目标没有职位")
        return

    if my_idx < 10:
        await ctx.send("只有 SHR / Leadership / Ownership 可以晋升")
        return

    if t_idx >= my_idx:
        await ctx.send("不能晋升同级或更高职位的人")
        return

    next_index = t_idx + 1

    if next_index >= len(RANK_ORDER):
        await ctx.send("已经最高职位")
        return

    new_role = find_role(ctx.guild, RANK_ORDER[next_index])

    if not new_role:
        await ctx.send("找不到下一级职位")
        return

    await member.remove_roles(t_role)
    await member.add_roles(new_role)

    await ctx.send(
        f"成功晋升 {member.name}\n{t_name} → {RANK_ORDER[next_index]}"
    )

    log_channel = bot.get_channel(LOG_CHANNEL_ID)

    if log_channel:

        await log_channel.send(
f"""📈 晋升记录

操作人: {ctx.author}
目标: {member}

原职位: {t_name}
新职位: {RANK_ORDER[next_index]}

时间: <t:{int(time.time())}:F>"""
        )


# ========================
# demote
# ========================

@bot.command()
async def demote(ctx, member: discord.Member):

    if member == ctx.author:
        await ctx.send("不能降级自己")
        return

    my_idx, my_name, _ = get_user_rank(ctx.author)
    t_idx, t_name, t_role = get_user_rank(member)

    if my_name is None:
        await ctx.send("你没有职位")
        return

    if t_name is None:
        await ctx.send("目标没有职位")
        return

    if my_idx < 10:
        await ctx.send("只有 SHR / Leadership / Ownership 可以降级")
        return

    if t_idx >= my_idx:
        await ctx.send("不能降级同级或更高职位的人")
        return

    prev_index = t_idx - 1

    if prev_index < 0:
        await ctx.send("已经最低职位")
        return

    new_role = find_role(ctx.guild, RANK_ORDER[prev_index])

    if not new_role:
        await ctx.send("找不到下一级职位")
        return

    await member.remove_roles(t_role)
    await member.add_roles(new_role)

    await ctx.send(
        f"成功降级 {member.name}\n{t_name} → {RANK_ORDER[prev_index]}"
    )

    log_channel = bot.get_channel(LOG_CHANNEL_ID)

    if log_channel:

        await log_channel.send(
f"""📉 降级记录

操作人: {ctx.author}
目标: {member}

原职位: {t_name}
新职位: {RANK_ORDER[prev_index]}

时间: <t:{int(time.time())}:F>"""
        )


bot.run("你的TOKEN")
