import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 意图全开
intents = discord.Intents.all()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ─────────────────────────────────────────────
# 🔰 职级体系配置 (完全按爸爸给的列表)
# ─────────────────────────────────────────────

RANK_CATEGORIES = {
    "LR": ["服务领队", "初级管理员", "高级管理员"],
    "MR": ["主管", "经理"],
    "HR": ["初级公司", "执行实习生", "执行官", "副总裁", "总裁"],
    "SHR": ["副主席", "主席", "星球委员会", "执行委员会", "外星委员会"],
    "Leadership": ["领导力实习生", "社区官员", "专员"],
    "Ownership": ["社区经理", "副服主", "服主", "持有者"],
}

# 🔐 允许使用晋升/降级命令的类别
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
        # ✅ 精准匹配：去掉空格和特殊符号再对比
        role_name_clean = role.name.replace(" ", "").replace("【", "").replace("】", "").replace("(", "").replace(")", "")
        for rank_name in GLOBAL_RANK_ORDER:
            rank_name_clean = rank_name.replace(" ", "")
            if rank_name_clean in role_name_clean:
                idx = GLOBAL_RANK_ORDER.index(rank_name)
                if idx > best_global:
                    best_global = idx
                    best_role = rank_name
                    best_cat = next(
                        cat for cat, ranks in RANK_CATEGORIES.items() if rank_name in ranks
                    )
                break

    return best_cat, best_role, best_global


# 🔐 权限检查
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

    # 🚨 先检查机器人权限和角色顺序！
    bot_member = guild.get_member(bot.user.id)
    if not bot_member.guild_permissions.manage_roles:
        await ctx.send("❌ 机器人没有「管理角色」权限！请在服务器设置里开启！")
        return
    
    # 🔍 找新角色
    new_role = None
    new_role_clean = new_role_name.replace(" ", "")
    for role in guild.roles:
        role_clean = role.name.replace(" ", "").replace("【", "").replace("】", "").replace("(", "").replace(")", "")
        if new_role_clean in role_clean:
            new_role = role
            break

    if new_role is None:
        all_roles = [r.name for r in guild.roles if r.name != "@everyone"]
        await ctx.send(f"❌ 找不到角色「{new_role_name}」！\n服务器角色列表：\n{', '.join(all_roles[:20])}{'...' if len(all_roles)>20 else ''}")
        print(f"❌ 错误：找不到角色 {new_role_name}")
        return

    # 🚨 检查新角色是否在机器人角色下方！
    if bot_member.top_role.position <= new_role.position:
        await ctx.send(f"⚠️ 警告！角色「{new_role_name}」在机器人角色上方！\n请把机器人角色拖到所有职级角色的最顶端！否则无法添加！")
        return

    # 🗑️ 找旧角色
    old_role = None
    old_role_clean = old_role_name.replace(" ", "")
    for role in target.roles:
        role_clean = role.name.replace(" ", "").replace("【", "").replace("】", "").replace("(", "").replace(")", "")
        if old_role_clean in role_clean:
            old_role = role
            break

    try:
        # ✅ 第一步：先加新角色
        print(f"🔍 尝试添加角色: {new_role.name} (位置: {new_role.position})")
        await target.add_roles(new_role, reason=f"{action} add {new_role_name}")
        
        # ✅ 强制刷新成员缓存，确保角色生效
        await target.fetch()
        print(f"✅ 已添加，刷新后成员角色列表: {[r.name for r in target.roles if r.name != '@everyone']}")

        # ✅ 第二步：再删旧角色
        if old_role is not None:
            print(f"🔍 尝试删除角色: {old_role.name}")
            await target.remove_roles(old_role, reason=f"{action} remove {old_role_name}")
            await target.fetch()
            print(f"✅ 已删除，刷新后成员角色列表: {[r.name for r in target.roles if r.name != '@everyone']}")

        # 🎉 成功提示
        action_label = "晋升" if action == "promote" else "降级"
        action_emoji = "⬆️" if action == "promote" else "⬇️"
        await ctx.send(
            f"{action_emoji} 成功！**{target.display_name}** 「{old_role_name}」→「{new_role_name}」\n✅ 已刷新角色缓存！"
        )
        await send_rank_log(guild, action, ctx.author, target, old_role_name, new_role_name, category)

    except discord.Forbidden as e:
        await ctx.send(f"❌ 权限错误！请检查：\n1. 机器人角色是否在所有职级角色上方\n2. 是否开启了「管理角色」权限\n错误信息: {e}")
        print(f"❌ 权限错误: {e}")
        return
    except Exception as e:
        await ctx.send(f"❌ 未知错误: {e}")
        print(f"❌ 未知错误: {e}")
        return


@bot.event
async def on_ready():
    print(f'✅ 机器人已上线: {bot.user}')
    print(f'ID: {bot.user.id}')
    print(f"📋 系统定义职级: {', '.join(GLOBAL_RANK_ORDER)}")
    
    # 🚨 启动时自动检查权限和角色顺序
    for guild in bot.guilds:
        bot_member = guild.get_member(bot.user.id)
        print(f"\n🏰 服务器: {guild.name}")
        print(f"🔐 机器人权限 - 管理角色: {bot_member.guild_permissions.manage_roles}")
        print(f"⬆️ 机器人最高角色位置: {bot_member.top_role.position}")
        
        # 检查所有职级角色位置
        for rank_name in GLOBAL_RANK_ORDER:
            rank_clean = rank_name.replace(" ", "")
            for role in guild.roles:
                role_clean = role.name.replace(" ", "").replace("【", "").replace("】", "").replace("(", "").replace(")", "")
                if rank_clean in role_clean:
                    print(f"📌 {role.name} 位置: {role.position}")
                    if bot_member.top_role.position <= role.position:
                        print(f"⚠️  警告！{role.name} 在机器人角色上方！")
                    break
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="职级系统"
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
    await ctx.send(f"✅ 机器人在线！\n用户: {bot.user}\nID: {bot.user.id}")

@bot.command(name='myroles')
async def myroles(ctx):
    role_names = [r.name for r in ctx.author.roles if r.name != "@everyone"]
    await ctx.send(f"🔍 你的角色列表：\n{', '.join(role_names)}")
    await ctx.send(f"📋 系统定义的职级：\n{', '.join(GLOBAL_RANK_ORDER)}")

# 🆕 新增命令：检查机器人权限
@bot.command(name='checkperm')
async def checkperm(ctx):
    bot_member = ctx.guild.get_member(bot.user.id)
    perm_status = f"🔐 机器人权限检查：\n管理角色: {'✅ 已开启' if bot_member.guild_permissions.manage_roles else '❌ 未开启'}\n最高角色: {bot_member.top_role.name} (位置: {bot_member.top_role.position})"
    await ctx.send(perm_status)


# ─────────────────────────────────────────────
# !promote 晋升命令
# ─────────────────────────────────────────────

@bot.command(name='promote')
@commands.check(has_permission)
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

    if op_global <= tgt_global:
        await ctx.send("❌ 你只能晋升职级低于你的成员。")
        return

    new_role = get_next_rank(tgt_cat, tgt_role)
    if new_role is None:
        await ctx.send(f"❌ 已经是最高级了。")
        return

    await apply_rank_change(ctx, member, new_role, tgt_role, "promote", tgt_cat)


# ─────────────────────────────────────────────
# !demote 降级命令
# ─────────────────────────────────────────────

@bot.command(name='demote')
@commands.check(has_permission)
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

    if op_global <= tgt_global:
        await ctx.send("❌ 你只能降级职级低于你的成员。")
        return

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
        await ctx.send(f"❌ 错误: {error}")
        print(f"❌ 错误: {error}")

if __name__ == '__main__':
    bot.run(os.getenv('DISCORD_BOT_TOKEN'))
