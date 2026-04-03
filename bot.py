import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv

load_dotenv()
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ─────────────────────────────────────────────
# 🔰 职级体系配置
# ─────────────────────────────────────────────

RANK_CATEGORIES = {
    "LR": ["服务领队", "初级管理员", "高级管理员"],
    "MR": ["主管", "经理"],
    "HR": ["初级公司", "执行实习生", "执行官", "副总裁", "总裁"],
    "SHR": ["副主席", "主席", "星球委员会", "执行委员会", "外星委员会"],
    "Leadership": ["领导力实习生", "社区官员", "专员"],
    "Ownership": ["社区经理", "副服主", "服主", "持有者"],
}

# 把所有职级展开成一个列表
ALL_RANKS = [rank for ranks in RANK_CATEGORIES.values() for rank in ranks]

# 🎯 权限关键字：只要角色名包含这些词，就能使用命令
PERMISSION_KEYWORDS = ["hr", "shr", "leadership", "ownership", "初级公司", "执行实习生", "执行官", "副总裁", "总裁", "副主席", "主席", "星球委员会", "执行委员会", "外星委员会", "领导力实习生", "社区官员", "专员", "社区经理", "副服主", "服主", "持有者"]

LOG_GUILD_ID = 1360354820757651657
LOG_CHANNEL_ID = 1454209918432182404


# 🔍 找角色：只要包含关键词就返回
def find_role(guild, name):
    name_low = name.lower()
    for role in guild.roles:
        if name_low in role.name.lower():
            return role
    return None


# 📋 获取成员当前最高职位
def get_user_rank(member):
    for role in member.roles:
        role_low = role.name.lower()
        for rank in ALL_RANKS:
            if rank.lower() in role_low:
                return rank
    return None


# 🗂️ 获取职位所属类别
def get_category(rank_name):
    for cat, ranks in RANK_CATEGORIES.items():
        if rank_name in ranks:
            return cat
    return None


# 🔐 权限检查：只要角色名包含关键字就有权限
def has_permission(member):
    for role in member.roles:
        role_low = role.name.lower()
        for keyword in PERMISSION_KEYWORDS:
            if keyword.lower() in role_low:
                return True
    return False


# ⬆️ 下一个职位
def next_rank(rank_name):
    cat = get_category(rank_name)
    if not cat:
        return None
    idx = RANK_CATEGORIES[cat].index(rank_name)
    if idx + 1 < len(RANK_CATEGORIES[cat]):
        return RANK_CATEGORIES[cat][idx + 1]
    return None


# ⬇️ 上一个职位
def prev_rank(rank_name):
    cat = get_category(rank_name)
    if not cat:
        return None
    idx = RANK_CATEGORIES[cat].index(rank_name)
    if idx - 1 >= 0:
        return RANK_CATEGORIES[cat][idx - 1]
    return None


# 📝 日志记录
async def log_action(ctx, action, target, old, new, cat):
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

    # 🔐 权限检查
    if not has_permission(ctx.author):
        await ctx.send("❌ 你没有权限使用此命令！")
        return

    my_rank = get_user_rank(ctx.author)
    target_rank = get_user_rank(member)

    if not target_rank:
        await ctx.send(f"❌ {member.display_name} 没有职位！")
        return

    # 只能操作职级比自己低的
    if ALL_RANKS.index(my_rank) <= ALL_RANKS.index(target_rank):
        await ctx.send("❌ 你只能晋升职级低于你的成员！")
        return

    new_rank_name = next_rank(target_rank)
    if not new_rank_name:
        await ctx.send("❌ 已经是最高级了！")
        return

    # 🎯 找角色
    old_role = find_role(ctx.guild, target_rank)
    new_role = find_role(ctx.guild, new_rank_name)

    if not new_role:
        await ctx.send(f"❌ 找不到角色：{new_rank_name}")
        return

    # 🚨 安全机制：先加后删，加不上就不删！
    try:
        # ✅ 第一步：先给新角色
        await member.add_roles(new_role)
        print(f"✅ 已给: {new_role.name}")

        # ✅ 刷新确认
        member = await ctx.guild.fetch_member(member.id)
        if new_role not in member.roles:
            await ctx.send(f"❌ 失败！无法添加 {new_rank_name}！旧角色已保留！")
            return

        # ✅ 第二步：再删旧角色
        if old_role:
            await member.remove_roles(old_role)
            print(f"✅ 已删: {old_role.name}")

        await ctx.send(f"⬆️ 成功！{member.display_name} 「{target_rank}」→「{new_rank_name}」")
        await log_action(ctx, "promote", member, target_rank, new_rank_name, get_category(target_rank))

    except Exception as e:
        await ctx.send(f"❌ 错误: {e}")
        print(f"❌ 错误: {e}")


# ─────────────────────────────────────────────
# !demote 降级
# ─────────────────────────────────────────────

@bot.command(name="demote")
async def demote(ctx, member: discord.Member = None):
    if not member:
        await ctx.send("❌ 用法: !demote @用户")
        return

    # 🔐 权限检查
    if not has_permission(ctx.author):
        await ctx.send("❌ 你没有权限使用此命令！")
        return

    my_rank = get_user_rank(ctx.author)
    target_rank = get_user_rank(member)

    if not target_rank:
        await ctx.send(f"❌ {member.display_name} 没有职位！")
        return

    # 只能操作职级比自己低的
    if ALL_RANKS.index(my_rank) <= ALL_RANKS.index(target_rank):
        await ctx.send("❌ 你只能降级职级低于你的成员！")
        return

    new_rank_name = prev_rank(target_rank)
    if not new_rank_name:
        await ctx.send("❌ 已经是最低级了！")
        return

    # 🎯 找角色
    old_role = find_role(ctx.guild, target_rank)
    new_role = find_role(ctx.guild, new_rank_name)

    if not new_role:
        await ctx.send(f"❌ 找不到角色：{new_rank_name}")
        return

    # 🚨 安全机制：先加后删，加不上就不删！
    try:
        # ✅ 第一步：先给新角色
        await member.add_roles(new_role)
        print(f"✅ 已给: {new_role.name}")

        # ✅ 刷新确认
        member = await ctx.guild.fetch_member(member.id)
        if new_role not in member.roles:
            await ctx.send(f"❌ 失败！无法添加 {new_rank_name}！旧角色已保留！")
            return

        # ✅ 第二步：再删旧角色
        if old_role:
            await member.remove_roles(old_role)
            print(f"✅ 已删: {old_role.name}")

        await ctx.send(f"⬇️ 成功！{member.display_name} 「{target_rank}」→「{new_rank_name}」")
        await log_action(ctx, "demote", member, target_rank, new_rank_name, get_category(target_rank))

    except Exception as e:
        await ctx.send(f"❌ 错误: {e}")
        print(f"❌ 错误: {e}")


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
    await ctx.send(f"🏓 Pong! 延迟: {round(bot.latency * 1000)}ms")

@bot.command(name="myroles")
async def myroles(ctx):
    roles = [r.name for r in ctx.author.roles if r.name != "@everyone"]
    await ctx.send(f"🔍 你的角色: {', '.join(roles)}")


if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_BOT_TOKEN"))
