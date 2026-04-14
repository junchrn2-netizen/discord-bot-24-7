import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv

load_dotenv()
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ─────────────────────────────────────────────
# 🔰 等级顺序（从低到高）
# ─────────────────────────────────────────────
RANK_ORDER = [
    "服务领队",        # 0
    "初级管理员",      # 1
    "高级管理员",      # 2
    "主管",            # 3
    "经理",            # 4
    "初级公司",        # 5
    "执行实习生",      # 6
    "执行官",          # 7
    "副总裁",          # 8
    "总裁",            # 9
    "副主席",          # 10
    "主席",            # 11
    "理事会实习生",    # 12
    "星球委员会",      # 13
    "执行委员会",      # 14
    "外星委员会",      # 15
    "领导力实习生",    # 16
    "专员",            # 17
    "社区官员",        # 18
    "社区经理",        # 19
    "副服主",          # 20
    "服主",            # 21
]

# ─────────────────────────────────────────────
# 🗂️ 档次划分
# ─────────────────────────────────────────────
RANK_TIERS = [
    {"keyword": "LR",              "min": 0,  "max": 2},
    {"keyword": "MR",              "min": 3,  "max": 4},
    {"keyword": "HR",              "min": 5,  "max": 9},
    {"keyword": "SHR",             "min": 10, "max": 15},
    {"keyword": "Leadership Rank", "min": 16, "max": 18},
    {"keyword": "Ownership Rank",  "min": 19, "max": 21},
]

# 🔐 SHR + Leadership + Ownership 都可以用（索引 >= 10）
PERMISSION_MIN_INDEX = 10

LOG_GUILD_ID   = 1360354820757651657
LOG_CHANNEL_ID = 1454209918432182404

# ─────────────────────────────────────────────
# 按名字长度降序排列，长名优先匹配
# ─────────────────────────────────────────────
RANK_ORDER_BY_LENGTH = sorted(
    enumerate(RANK_ORDER),
    key=lambda x: len(x[1]),
    reverse=True
)


# ─────────────────────────────────────────────
# 🔍 找角色：精确优先，子串兜底（覆盖率最高）
# ─────────────────────────────────────────────
def find_role(guild, name):
    name_low = name.lower()

    # 第一轮：精确匹配
    for role in guild.roles:
        if name_low == role.name.lower():
            return role

    # 第二轮：子串匹配，按覆盖率选最佳
    best_role = None
    best_coverage = 0
    for role in guild.roles:
        role_low = role.name.lower()
        if name_low in role_low and len(role_low) > 0:
            coverage = len(name_low) / len(role_low)
            if coverage > best_coverage:
                best_coverage = coverage
                best_role = role

    return best_role


# ─────────────────────────────────────────────
# 📋 获取成员当前最高职位和索引
# ─────────────────────────────────────────────
def get_user_rank_info(member):
    best_idx = -1
    best_name = None

    for role in member.roles:
        role_low = role.name.lower()
        for idx, rank_name in RANK_ORDER_BY_LENGTH:
            if rank_name.lower() in role_low:
                if idx > best_idx:
                    best_idx = idx
                    best_name = rank_name
                break
    return best_idx, best_name


# ─────────────────────────────────────────────
# 🗂️ 根据索引获取所属档次
# ─────────────────────────────────────────────
def get_tier(index):
    for tier in RANK_TIERS:
        if tier["min"] <= index <= tier["max"]:
            return tier["keyword"]
    return None


# ─────────────────────────────────────────────
# ⬆️ 下一个职位
# ─────────────────────────────────────────────
def next_rank(current_index):
    if current_index + 1 < len(RANK_ORDER):
        return RANK_ORDER[current_index + 1]
    return None


# ─────────────────────────────────────────────
# ⬇️ 上一个职位
# ─────────────────────────────────────────────
def prev_rank(current_index):
    if current_index - 1 >= 0:
        return RANK_ORDER[current_index - 1]
    return None


# ─────────────────────────────────────────────
# 📝 日志记录（命令频道简短确认 + 日志频道详细embed）
# ─────────────────────────────────────────────
async def log_action(ctx, action, target, old, new, old_tier, new_tier):
    emoji = "⬆️" if action == "promote" else "⬇️"
    action_cn = "晋升" if action == "promote" else "降级"

    # 命令频道：简短确认
    await ctx.send(
        f"{emoji} 已将 **{target.display_name}** 从 **{old}**({old_tier}) "
        f"{action_cn}为 **{new}**({new_tier})"
    )

    # 日志频道：详细 embed
    embed = discord.Embed(
        title=f"{emoji} 职级{action_cn}记录",
        color=discord.Color.green() if action == "promote" else discord.Color.red()
    )
    embed.add_field(name="操作人", value=f"{ctx.author} ({ctx.author.display_name})", inline=False)
    embed.add_field(name="目标",   value=f"{target} ({target.display_name})", inline=False)
    embed.add_field(name="原职位", value=old, inline=True)
    embed.add_field(name="新职位", value=new, inline=True)
    embed.add_field(name="原档次", value=old_tier or "无", inline=True)
    embed.add_field(name="新档次", value=new_tier or "无", inline=True)
    embed.set_footer(text=f"服务器: {ctx.guild.name}")
    embed.timestamp = discord.utils.utcnow()

    log_guild = bot.get_guild(LOG_GUILD_ID)
    log_channel = log_guild.get_channel(LOG_CHANNEL_ID) if log_guild else None
    if log_channel:
        await log_channel.send(embed=embed)


# ─────────────────────────────────────────────
# !promote 晋升
# ─────────────────────────────────────────────
@bot.command(name="promote")
async def promote(ctx, member: discord.Member = None):
    if not member:
        await ctx.send("❌ 用法: `!promote @用户`")
        return

    my_idx, my_rank = get_user_rank_info(ctx.author)
    if my_idx < PERMISSION_MIN_INDEX:
        await ctx.send("❌ 你没有权限！需要 **SHR / Leadership / Ownership** 职级！")
        return

    target_idx, target_rank = get_user_rank_info(member)
    if target_idx == -1:
        await ctx.send(f"❌ {member.display_name} 没有职位！")
        return

    if my_idx <= target_idx:
        await ctx.send("❌ 你只能晋升职级低于你的成员！")
        return

    new_rank_name = next_rank(target_idx)
    if not new_rank_name:
        await ctx.send("❌ 已经是最高级了！")
        return

    old_role = find_role(ctx.guild, target_rank)
    new_role = find_role(ctx.guild, new_rank_name)

    if not new_role:
        await ctx.send(f"❌ 找不到角色：{new_rank_name}")
        return

    # 安全检查：防止新旧角色是同一个
    if old_role and old_role.id == new_role.id:
        await ctx.send(
            f"❌ 角色匹配错误！「{target_rank}」和「{new_rank_name}」"
            f"匹配到了同一个角色：**{old_role.name}**\n"
            f"请检查服务器角色名称是否正确！"
        )
        return

    try:
        # 第一步：加新角色
        await member.add_roles(new_role)
        print(f"✅ 已给: {new_role.name}")

        # 刷新确认
        member = await ctx.guild.fetch_member(member.id)
        if new_role not in member.roles:
            await ctx.send(f"❌ 失败！无法添加 {new_rank_name}！旧角色已保留！")
            return

        # 第二步：删旧角色
        if old_role and old_role in member.roles:
            await member.remove_roles(old_role)
            print(f"✅ 已删: {old_role.name}")

        new_idx = target_idx + 1
        await log_action(
            ctx, "promote", member,
            target_rank, new_rank_name,
            get_tier(target_idx), get_tier(new_idx)
        )

    except Exception as e:
        await ctx.send(f"❌ 错误: {e}")
        print(f"❌ 错误: {e}")


# ─────────────────────────────────────────────
# !demote 降级
# ─────────────────────────────────────────────
@bot.command(name="demote")
async def demote(ctx, member: discord.Member = None):
    if not member:
        await ctx.send("❌ 用法: `!demote @用户`")
        return

    my_idx, my_rank = get_user_rank_info(ctx.author)
    if my_idx < PERMISSION_MIN_INDEX:
        await ctx.send("❌ 你没有权限！需要 **SHR / Leadership / Ownership** 职级！")
        return

    target_idx, target_rank = get_user_rank_info(member)
    if target_idx == -1:
        await ctx.send(f"❌ {member.display_name} 没有职位！")
        return

    if my_idx <= target_idx:
        await ctx.send("❌ 你只能降级职级低于你的成员！")
        return

    new_rank_name = prev_rank(target_idx)
    if not new_rank_name:
        await ctx.send("❌ 已经是最低级了！")
        return

    old_role = find_role(ctx.guild, target_rank)
    new_role = find_role(ctx.guild, new_rank_name)

    if not new_role:
        await ctx.send(f"❌ 找不到角色：{new_rank_name}")
        return

    # 安全检查：防止新旧角色是同一个
    if old_role and old_role.id == new_role.id:
        await ctx.send(
            f"❌ 角色匹配错误！「{target_rank}」和「{new_rank_name}」"
            f"匹配到了同一个角色：**{old_role.name}**\n"
            f"请检查服务器角色名称是否正确！"
        )
        return

    try:
        # 第一步：加新角色
        await member.add_roles(new_role)
        print(f"✅ 已给: {new_role.name}")

        # 刷新确认
        member = await ctx.guild.fetch_member(member.id)
        if new_role not in member.roles:
            await ctx.send(f"❌ 失败！无法添加 {new_rank_name}！旧角色已保留！")
            return

        # 第二步：删旧角色
        if old_role and old_role in member.roles:
            await member.remove_roles(old_role)
            print(f"✅ 已删: {old_role.name}")

        new_idx = target_idx - 1
        await log_action(
            ctx, "demote", member,
            target_rank, new_rank_name,
            get_tier(target_idx), get_tier(new_idx)
        )

    except Exception as e:
        await ctx.send(f"❌ 错误: {e}")
        print(f"❌ 错误: {e}")


# ─────────────────────────────────────────────
# 基础功能
# ─────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ 机器人已上线: {bot.user}")
    print(f"📋 等级数量: {len(RANK_ORDER)} 个")
    await bot.change_presence(
        activity=discord.Activity(name="职级系统", type=discord.ActivityType.watching)
    )
    if not keep_alive.is_running():
        keep_alive.start()


@tasks.loop(minutes=5)
async def keep_alive():
    print("💓 心跳检测")


@bot.command(name="ping")
async def ping(ctx):
    await ctx.send(f"🏓 Pong! 延迟: {round(bot.latency * 1000)}ms")


@bot.command(name="myrank")
async def myrank(ctx):
    idx, name = get_user_rank_info(ctx.author)
    if name:
        tier = get_tier(idx)
        await ctx.send(f"🔍 你的职级：**{name}** (索引: {idx}, 档次: {tier})")
    else:
        await ctx.send("🔍 未检测到职级角色")


@bot.command(name="ranklist")
async def ranklist(ctx):
    """查看所有职级列表"""
    lines = []
    for idx, name in enumerate(RANK_ORDER):
        tier = get_tier(idx)
        role = find_role(ctx.guild, name)
        status = f"✅ → {role.name}" if role else "❌ 未找到"
        lines.append(f"`{idx:2d}` | {name} ({tier}) {status}")

    embed = discord.Embed(title="📋 职级列表", description="\n".join(lines))
    await ctx.send(embed=embed)


# ─────────────────────────────────────────────
# 启动
# ─────────────────────────────────────────────
if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("❌ 错误：未找到 DISCORD_BOT_TOKEN，请检查 .env 文件！")
    else:
        bot.run(token)
