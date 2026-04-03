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

# 所有职级，按类别分组，每组内从低到高排列
RANK_CATEGORIES = {
    "LR": ["服务领队", "初级管理员", "高级管理员"],
    "MR": ["主管", "经理"],
    "HR": ["初级公司", "执行实习生", "执行官", "副总裁", "总裁"],
    "SHR": ["副主席", "主席", "星球委员会", "执行委员会", "外星委员会"],
    "Leadership": ["领导力实习生", "社区官员", "专员"],
    "Ownership": ["社区经理", "副服主", "服主", "持有者"],
}

# 扁平化的全局职级列表（从低到高），用于跨类别权限比较
GLOBAL_RANK_ORDER: list[str] = []
for _ranks in RANK_CATEGORIES.values():
    GLOBAL_RANK_ORDER.extend(_ranks)

# 晋升日志频道 / 服务器配置
LOG_GUILD_ID = 1360354820757651657
LOG_CHANNEL_ID = 1454209918432182404


def get_member_rank_info(member: discord.Member) -> tuple[str | None, str | None, int]:
    """
    返回成员当前职级的 (category_name, role_name, global_index)。
    若成员没有任何已知职级，返回 (None, None, -1)。
    当成员拥有多个职级时，取全局排序最高的那个。
    **模糊匹配，只要包含关键字即可**
    """
    best_global = -1
    best_role = None
    best_cat = None

    for role in member.roles:
        # 跳过 everyone 避免干扰
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
    """返回同类别中的下一个（更高）职级，若已是最高则返回 None。"""
    ranks = RANK_CATEGORIES[category]
    idx = ranks.index(current_role)
    if idx + 1 < len(ranks):
        return ranks[idx + 1]
    return None


def get_prev_rank(category: str, current_role: str) -> str | None:
    """返回同类别中的上一个（更低）职级，若已是最低则返回 None。"""
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
    """向日志频道发送晋升/降级记录。"""
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
    # 只显示名称，不 @
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
    """
    给目标成员添加新职级角色，并移除其所有已知职级角色（新职级除外）。
    随后发送日志并回复操作结果。
    **修复：先加后删，确保身份不丢失**
    """
    guild = ctx.guild

    # 查找新职级对应的 Role 对象（加强版）
    new_role = None
    # 先精确匹配
    for role in guild.roles:
        if role.name == new_role_name:
            new_role = role
            break
    # 精确找不到再模糊匹配
    if new_role is None:
        for role in guild.roles:
            if new_role_name in role.name:
                new_role = role
                break

    if new_role is None:
        await ctx.send(f"❌ 未找到角色「{new_role_name}」，请确认服务器中已创建该角色。")
        return

    # 收集目标成员当前持有的所有已知职级角色（排除新职级）
    roles_to_remove = []
    for role in target.roles:
        if role.name == "@everyone":
            continue
        for rank_name in GLOBAL_RANK_ORDER:
            if rank_name in role.name and rank_name != new_role_name:
                roles_to_remove.append(role)
                break

    try:
        # ✅ 关键修改：先添加新角色，再删除旧角色
        await target.add_roles(new_role, reason=f"{action} by {ctx.author}")
        if roles_to_remove:
            await target.remove_roles(*roles_to_remove, reason=f"{action} cleanup by {ctx.author}")
        
        # 成功提示
        action_label = "晋升" if action == "promote" else "降级"
        action_emoji = "⬆️" if action == "promote" else "⬇️"
        # 只显示名称，不 @
        await ctx.send(
            f"{action_emoji} 已将 **{target.display_name}** 从「{old_role_name}」{action_label}至「{new_role_name}」。"
        )
        # 发送日志
        await send_rank_log(guild, action, ctx.author, target, old_role_name, new_role_name, category)
    except discord.Forbidden:
        await ctx.send("❌ 权限不足！请把机器人角色拖到角色列表最顶部。")
        return
    except discord.HTTPException as e:
        await ctx.send(f"❌ 操作失败: {e}")
        return


@bot.event
async def on_ready():
    """机器人上线时触发"""
    print(f'✅ 机器人已上线: {bot.user}')
    print(f'ID: {bot.user.id}')
    # 设置状态
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="你的服务器"
        ),
        status=discord.Status.online
    )
    # 启动心跳检测
    keep_alive.start()

@tasks.loop(minutes=5)
async def keep_alive():
    """定期心跳，保持连接活跃"""
    print(f'💓 心跳检测: {bot.user}')

@bot.command(name='ping')
async def ping(ctx):
    """简单的ping命令"""
    latency = round(bot.latency * 1000)
    await ctx.send(f'🏓 Pong! 延迟: {latency}ms')

@bot.command(name='status')
async def status(ctx):
    """检查机器人状态"""
    await ctx.send(f'✅ 机器人在线！\n用户: {bot.user}\nID: {bot.user.id}')

# ─────────────────────────────────────────────
# 查看自己角色的调试命令（已修复：纯文字，不艾特，不显示everyone）
# ─────────────────────────────────────────────
@bot.command(name='myroles')
async def myroles(ctx):
    """查看自己拥有的所有角色名称，用于调试"""
    role_names = []
    for role in ctx.author.roles:
        # ✅ 关键修改：跳过 everyone，只显示纯文字名称
        if role.name != "@everyone":
            role_names.append(role.name)
    
    await ctx.send(f"🔍 你的角色列表：\n{', '.join(role_names)}")
    await ctx.send(f"📋 系统定义的职级：\n{', '.join(GLOBAL_RANK_ORDER)}")


# ─────────────────────────────────────────────
# !promote 命令
# ─────────────────────────────────────────────

@bot.command(name='promote')
async def promote(ctx, member: discord.Member = None):
    """
    将目标成员晋升至同类别的下一个职级。
    用法: !promote @用户
    """
    # 参数校验
    if member is None:
        await ctx.send("❌ 用法: `!promote @用户`")
        return

    # 不能对自己操作
    if member == ctx.author:
        await ctx.send("❌ 你不能晋升自己。")
        return

    # 不能对机器人操作
    if member.bot:
        await ctx.send("❌ 无法对机器人执行职级操作。")
        return

    # 获取操作人和目标的职级信息
    op_cat, op_role, op_global = get_member_rank_info(ctx.author)
    tgt_cat, tgt_role, tgt_global = get_member_rank_info(member)

    # 操作人必须拥有已知职级
    if op_role is None:
        await ctx.send("❌ 你没有任何已知职级，无法执行晋升操作。")
        return

    # 目标必须拥有已知职级
    if tgt_role is None:
        await ctx.send(f"❌ **{member.display_name}** 没有任何已知职级，无法晋升。")
        return

    # 操作人必须高于目标
    if op_global <= tgt_global:
        await ctx.send("❌ 你只能晋升职级低于你的成员。")
        return

    # 获取晋升后的职级
    new_role = get_next_rank(tgt_cat, tgt_role)
    if new_role is None:
        await ctx.send(f"❌ **{member.display_name}** 已是「{tgt_cat}」类别的最高职级，无法继续晋升。")
        return

    # 晋升后的职级不能超过或等于操作人的职级
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
    """
    将目标成员降级至同类别的上一个职级。
    用法: !demote @用户
    """
    # 参数校验
    if member is None:
        await ctx.send("❌ 用法: `!demote @用户`")
        return

    # 不能对自己操作
    if member == ctx.author:
        await ctx.send("❌ 你不能降级自己。")
        return

    # 不能对机器人操作
    if member.bot:
        await ctx.send("❌ 无法对机器人执行职级操作。")
        return

    # 获取操作人和目标的职级信息
    op_cat, op_role, op_global = get_member_rank_info(ctx.author)
    tgt_cat, tgt_role, tgt_global = get_member_rank_info(member)

    # 操作人必须拥有已知职级
    if op_role is None:
        await ctx.send("❌ 你没有任何已知职级，无法执行降级操作。")
        return

    # 目标必须拥有已知职级
    if tgt_role is None:
        await ctx.send(f"❌ **{member.display_name}** 没有任何已知职级，无法降级。")
        return

    # 操作人必须高于目标
    if op_global <= tgt_global:
        await ctx.send("❌ 你只能降级职级低于你的成员。")
        return

    # 获取降级后的职级
    new_role = get_prev_rank(tgt_cat, tgt_role)
    if new_role is None:
        await ctx.send(f"❌ **{member.display_name}** 已是「{tgt_cat}」类别的最低职级，无法继续降级。")
        return

    await apply_rank_change(ctx, member, new_role, tgt_role, "demote", tgt_cat)


@bot.event
async def on_command_error(ctx, error):
    """错误处理"""
    if isinstance(error, commands.MemberNotFound):
        await ctx.send(f"❌ 未找到成员，请确认 @ 了正确的用户。")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ 缺少必要参数，请检查命令用法。")
    else:
        print(f'❌ 命令错误: {error}')
        # ✅ 关键修改：不在错误处理里发消息，避免重复
        pass

if __name__ == '__main__':
    bot.run(os.getenv('DISCORD_BOT_TOKEN'))
