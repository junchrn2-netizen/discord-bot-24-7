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
        for rank_name in GLOBAL_RANK_ORDER:
            if rank_name in role.name:
                idx = GLOBAL_RANK_ORDER.index(rank_name)
                if idx > best_global:
                    best_global = idx
                    best_role = rank_name
                    best_cat = next(
                        cat for cat, ranks in RANK_CATEGORIES.items() if rank_name in ranks
                    )
                break

    return best_cat, best_role, best_global


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

    # 🚨 第一步：先找到新角色，找不到直接报错，绝不删东西
    new_role = None
    for role in guild.roles:
        if role.name == new_role_name:
            new_role = role
            break
    if new_role is None:
        for role in guild.roles:
            if new_role_name in role.name:
                new_role = role
                break

    if new_role is None:
        await ctx.send(f"❌ 致命错误：服务器里找不到「{new_role_name}」这个角色！请先创建它！")
        return

    # 🚨 第二步：先加新角色
    try:
        await target.add_roles(new_role, reason=f"{action} by {ctx.author}")
    except discord.Forbidden:
        await ctx.send("❌ 权限不够！机器人角色必须在最顶端！")
        return
    except Exception as e:
        await ctx.send(f"❌ 添加失败: {e}")
        return

    # ✅ 第三步：只有加上了，才敢删旧的！
    roles_to_remove = []
    for role in target.roles:
        if role.name == "@everyone":
            continue
        for rank_name in GLOBAL_RANK_ORDER:
            if rank_name in role.name and rank_name != new_role_name:
                roles_to_remove.append(role)
                break

    if roles_to_remove:
        try:
            await target.remove_roles(*roles_to_remove, reason=f"{action} cleanup")
        except Exception as e:
            # 删失败没关系，反正新的已经加上了
            print(f"删除旧角色时出现小问题: {e}")

    # 🎉 完成
    action_label = "晋升" if action == "promote" else "降级"
    action_emoji = "⬆️" if action == "promote" else "⬇️"
    await ctx.send(
        f"{action_emoji} 成功！**{target.display_name}** 从「{old_role_name}」→「{new_role_name}」"
    )
    await send_rank_log(guild, action, ctx.author, target, old_role_name, new_role_name, category)


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
async def promote(ctx, member: discord.Member = None):
    if member is None:
        await ctx.send("❌ 用法: `!promote @用户`")
        return

    if member == ctx.author:
        await ctx.send("❌ 你不能晋升自己。")
        return

    if member.bot:
        await ctx.send("❌ 无法对机器人执行职级操作。")
        return

    op_cat, op_role, op_global = get_member_rank_info(ctx.author)
    tgt_cat, tgt_role, tgt_global = get_member_rank_info(member)

    if op_role is None:
        await ctx.send("❌ 你没有任何已知职级，无法执行晋升操作。")
        return

    if tgt_role is None:
        await ctx.send(f"❌ **{member.display_name}** 没有任何已知职级，无法晋升。")
        return

    if op_global <= tgt_global:
        await ctx.send("❌ 你只能晋升职级低于你的成员。")
        return

    new_role = get_next_rank(tgt_cat, tgt_role)
    if new_role is None:
        await ctx.send(f"❌ **{member.display_name}** 已是「{tgt_cat}」类别的最高职级，无法继续晋升。")
        return

    new_global = GLOBAL_RANK_ORDER.index(new_role)
    if new_global >= op_global:
        await ctx.send(f"❌ 无法晋升，目标职级「{new_role}」不低于你的职级。")
        return

    await apply_rank_change(ctx, member, new_role, tgt_role, "promote", tgt_cat)


# ─────────────────────────────────────────────
# !demote 命令
# ─────────────────────────────────────────────

@bot.command(name='demote')
async def demote(ctx, member: discord.Member = None):
    if member is None:
        await ctx.send("❌ 用法: `!demote @用户`")
        return

    if member == ctx.author:
        await ctx.send("❌ 你不能降级自己。")
        return

    if member.bot:
        await ctx.send("❌ 无法对机器人执行职级操作。")
        return

    op_cat, op_role, op_global = get_member_rank_info(ctx.author)
    tgt_cat, tgt_role, tgt_global = get_member_rank_info(member)

    if op_role is None:
        await ctx.send("❌ 你没有任何已知职级，无法执行降级操作。")
        return

    if tgt_role is None:
        await ctx.send(f"❌ **{member.display_name}** 没有任何已知职级，无法降级。")
        return

    if op_global <= tgt_global:
        await ctx.send("❌ 你只能降级职级低于你的成员。")
        return

    new_role = get_prev_rank(tgt_cat, tgt_role)
    if new_role is None:
        await ctx.send(f"❌ **{member.display_name}** 已是「{tgt_cat}」类别的最低职级，无法继续降级。")
        return

    await apply_rank_change(ctx, member, new_role, tgt_role, "demote", tgt_cat)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MemberNotFound):
        await ctx.send(f"❌ 未找到成员，请确认 @ 了正确的用户。")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ 缺少必要参数，请检查命令用法。")
    else:
        print(f'❌ 命令错误: {error}')

if __name__ == '__main__':
    bot.run(os.getenv('DISCORD_BOT_TOKEN'))
