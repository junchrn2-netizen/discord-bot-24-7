import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 设置机器人意图
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ─────────────────────────────────────────────
# 职级体系配置
# ─────────────────────────────────────────────

RANK_CATEGORIES = {
    "LR": ["服务领队", "初级管理员", "高级管理员"],
    "MR": ["主管", "经理"],
    "HR": ["初级公司", "执行实习生", "执行官", "副总裁", "总裁"],
    "SHR": ["副主席", "主席", "星球委员会", "执行委员会", "外星委员会"],
    "Leadership": ["领导力实习生", "社区官员", "专员"],
    "Ownership": ["社区经理", "副服主", "服主", "持有者"],
}

# 允许使用晋升/降级命令的类别
ALLOWED_CATEGORIES = ["SHR", "Leadership", "Ownership"]

GLOBAL_RANK_ORDER: list[str] = []
for _ranks in RANK_CATEGORIES.values():
    GLOBAL_RANK_ORDER.extend(_ranks)

LOG_GUILD_ID = 1360354820757651657
LOG_CHANNEL_ID = 1454209918432182404


def get_member_rank_info(member: discord.Member) -> tuple[str | None, str | None, int]:
    best_global = -1
    best_role = None
    best_cat = None

    for role in member.roles:
        if role.name == "@everyone":
            continue
        # 精确匹配，名字必须完全一样
        if role.name in GLOBAL_RANK_ORDER:
            idx = GLOBAL_RANK_ORDER.index(role.name)
            if idx > best_global:
                best_global = idx
                best_role = role.name
                best_cat = next(
                    cat for cat, ranks in RANK_CATEGORIES.items() if role.name in ranks
                )

    return best_cat, best_role, best_global


# 🔐 权限检查：只要属于指定类别就有权限！
def has_permission(ctx):
    cat, _, _ = get_member_rank_info(ctx.author)
    return cat in ALLOWED_CATEGORIES


def get_next_rank(category: str, current_role: str) -> str | None:
    ranks = RANK_CATEGORIES[category]
    idx = ranks.index(current_role)
    if idx + 1 < len(ranks):
        return ranks[idx + 1]
    return None


def get_prev_rank(category: str, current_role: str) -> str | None:
    ranks = RANK_CATEGORIES[category]
    idx = ranks.index(current_role)
    if idx - 1 >= 0:
        return ranks[idx - 1]
    return None


async def send_rank_log(
    guild: discord.Guild,
    action: str,
    operator: discord.Member,
    target: discord.Member,
    old_role: str,
    new_role: str,
    category: str,
) -> None:
    log_guild = bot.get_guild(LOG_GUILD_ID)
    if log_guild is None:
        return
    log_channel = log_guild.get_channel(LOG_CHANNEL_ID)
    if log_channel is None:
        return

    action_emoji = "⬆️" if action == "promote" else "⬇️"
    action_label = "晋升" if action == "promote" else "降级"
    color = discord.Color.green() if action == "promote" else discord.Color.red()

    embed = discord.Embed(
        title=f"{action_emoji} 职级{action_label}记录",
        color=color,
    )
    embed.add_field(name="操作人", value=f"{operator} (`{operator.display_name}`)", inline=False)
    embed.add_field(name="目标成员", value=f"{target} (`{target.display_name}`)", inline=False)
    embed.add_field(name="职级类别", value=category, inline=True)
    embed.add_field(name="原职级", value=old_role, inline=True)
    embed.add_field(name="新职级", value=new_role, inline=True)
    embed.set_footer(text=f"服务器: {guild.name}")
    embed.timestamp = discord.utils.utcnow()

    await log_channel.send(embed=embed)


async def apply_rank_change(
    ctx: commands.Context,
    target: discord.Member,
    new_role_name: str,
    old_role_name: str,
    action: str,
    category: str,
) -> None:
    guild = ctx.guild

    # 🔍 找新角色
    new_role = None
    for role in guild.roles:
        if role.name == new_role_name:
            new_role = role
            break

    if new_role is None:
        await ctx.send(f"❌ 找不到角色「{new_role_name}」！")
        return

    try:
        # ➕ 只加不删！旧职位永远保留！
        await target.add_roles(new_role, reason=f"{action} by {ctx.author}")

        # 🎉 成功
        action_label = "晋升" if action == "promote" else "降级"
        action_emoji = "⬆️" if action == "promote" else "⬇️"
        await ctx.send(
            f"{action_emoji} 成功！**{target.display_name}** 获得「{new_role_name}」！"
        )
        await send_rank_log(guild, action, ctx.author, target, old_role_name, new_role_name, category)

    except discord.Forbidden:
        await ctx.send("❌ 权限不够！把机器人拖最上面！")
        return
    except Exception as e:
        await ctx.send(f"❌ 错误: {e}")
        return


@bot.event
async def on_ready():
    print(f'✅ 机器人已上线: {bot.user}')
    print(f'ID: {bot.user.id}')
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="你的服务器"
        ),
        status=discord.Status.online
    )
    keep_alive.start()

@tasks.loop(minutes=5)
async def keep_alive():
    print(f'💓 心跳检测: {bot.user}')

@bot.command(name='ping')
async def ping(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(f'🏓 Pong! 延迟: {latency}ms')

@bot.command(name='status')
async def status(ctx):
    await ctx.send(f'✅ 机器人在线！\n用户: {bot.user}\nID: {bot.user.id}')

@bot.command(name='myroles')
async def myroles(ctx):
    role_names = []
    for role in ctx.author.roles:
        if role.name != "@everyone":
            role_names.append(role.name)
    
    await ctx.send(f"🔍 你的角色列表：\n{', '.join(role_names)}")
    await ctx.send(f"📋 系统定义的职级：\n{', '.join(GLOBAL_RANK_ORDER)}")


# ─────────────────────────────────────────────
# !promote 命令
# ─────────────────────────────────────────────

@bot.command(name='promote')
@commands.check(has_permission)  # 🔐 权限检查
async def promote(ctx, member: discord.Member = None):
    if member is None:
        await ctx.send("❌ 用法: `!promote @用户`")
        return

    if member == ctx.author:
        await ctx.send("❌ 你不能晋升自己。")
        return

    if member.bot:
        await ctx.send("❌ 无法对机器人操作。")
        return

    op_cat, op_role, op_global = get_member_rank_info(ctx.author)
    tgt_cat, tgt_role, tgt_global = get_member_rank_info(member)

    if op_role is None:
        await ctx.send("❌ 你没有职位。")
        return

    if tgt_role is None:
        await ctx.send(f"❌ **{member.display_name}** 没有职位。")
        return

    # 🔓 去掉等级限制！只要类别对就能用！
    # if op_global <= tgt_global:
    #     await ctx.send("❌ 你只能晋升比你低的。")
    #     return

    new_role = get_next_rank(tgt_cat, tgt_role)
    if new_role is None:
        await ctx.send(f"❌ 已经是最高级了。")
        return

    await apply_rank_change(ctx, member, new_role, tgt_role, "promote", tgt_cat)


# ─────────────────────────────────────────────
# !demote 命令
# ─────────────────────────────────────────────

@bot.command(name='demote')
@commands.check(has_permission)  # 🔐 权限检查
async def demote(ctx, member: discord.Member = None):
    if member is None:
        await ctx.send("❌ 用法: `!demote @用户`")
        return

    if member == ctx.author:
        await ctx.send("❌ 你不能降级自己。")
        return

    if member.bot:
        await ctx.send("❌ 无法对机器人操作。")
        return

    op_cat, op_role, op_global = get_member_rank_info(ctx.author)
    tgt_cat, tgt_role, tgt_global = get_member_rank_info(member)

    if op_role is None:
        await ctx.send("❌ 你没有职位。")
        return

    if tgt_role is None:
        await ctx.send(f"❌ **{member.display_name}** 没有职位。")
        return

    # 🔓 去掉等级限制！只要类别对就能用！
    # if op_global <= tgt_global:
    #     await ctx.send("❌ 你只能降级比你低的。")
    #     return

    new_role = get_prev_rank(tgt_cat, tgt_role)
    if new_role is None:
        await ctx.send(f"❌ 已经是最低级了。")
        return

    await apply_rank_change(ctx, member, new_role, tgt_role, "demote", tgt_cat)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MemberNotFound):
        await ctx.send(f"❌ 未找到成员。")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ 用法不对。")
    elif isinstance(error, commands.CheckFailure):
        await ctx.send("❌ 你没有权限使用此命令！")
    else:
        print(f'❌ 错误: {error}')

if __name__ == '__main__':
    bot.run(os.getenv('DISCORD_BOT_TOKEN'))
