import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv

load_dotenv()
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ─────────────────────────────────────────────
# 🔰 职级顺序 (精准匹配列表)
# ─────────────────────────────────────────────
RANK_ORDER = [
    "服务领队", "初级管理员", "高级管理员", "主管", "经理",         # 0-4
    "初级公司", "执行实习生", "执行官", "副总裁", "总裁",             # 5-9
    "副主席", "主席", "理事会实习生", "星球委员会", "执行委员会",     # 10-14
    "外星委员会", "领导力实习生", "专员", "社区官员", "社区经理",     # 15-19
    "副服主", "服主"                                              # 20-21
]

# 按名字长度降序排列，用于精准匹配身份
LONG_MATCH_LIST = sorted(enumerate(RANK_ORDER), key=lambda x: len(x[1]), reverse=True)

# ─────────────────────────────────────────────
# 🔍 逻辑优化：精准识别与搜索
# ─────────────────────────────────────────────

def get_user_rank_info(member: discord.Member):
    """
    精准识别成员身份：长词优先匹配。
    """
    highest_idx = -1
    highest_name = None
    
    for role in member.roles:
        r_name_low = role.name.lower()
        for idx, rank_name in LONG_MATCH_LIST:
            # 这里的 rank_name 是列表里的标准词，如 "总裁"
            if rank_name.lower() in r_name_low:
                # 额外安全检查：如果匹配到 "总裁"，但角色名其实是 "副总裁"，则跳过
                if rank_name == "总裁" and "副总裁" in r_name_low: continue
                if rank_name == "主席" and "副主席" in r_name_low: continue
                if rank_name == "服主" and "副服主" in r_name_low: continue
                
                if idx > highest_idx:
                    highest_idx = idx
                    highest_name = rank_name
                break # 匹配到最长职级词后跳出，检查下一个角色
                
    is_admin = (highest_idx >= 10) # 假设 10 (副主席) 及以上为管理层
    # 辅助检查：是否有档次身份组关键词
    if not is_admin:
        is_admin = any(kw in r.name.upper() for r in member.roles for kw in ["SHR", "LEADERSHIP", "OWNERSHIP"])
        
    return highest_idx, highest_name, is_admin

def find_best_role_in_guild(guild: discord.Guild, rank_name: str):
    """
    在服务器里寻找最匹配职位的身份组，具有防误判逻辑。
    """
    # 1. 优先寻找名字完全一致的
    for role in guild.roles:
        if role.name == rank_name:
            return role
            
    # 2. 模糊匹配，但排除包含“副”字的干扰项
    for role in guild.roles:
        r_name = role.name
        if rank_name in r_name:
            # 如果我们要找 "总裁"，但搜到了 "副总裁"，排除它
            if rank_name in ["总裁", "主席", "服主"]:
                if f"副{rank_name}" in r_name:
                    continue
            return role
    return None

# ─────────────────────────────────────────────
# 🚀 核心命令：Promote / Demote
# ─────────────────────────────────────────────

async def change_rank(ctx, member: discord.Member, direction: int):
    """
    统一处理职级变动逻辑。direction 为 1 (升) 或 -1 (降)。
    """
    if not member:
        return await ctx.send("❌ 请指定一名成员。")

    # 1. 强制刷新成员缓存，防止角色识别不到
    member = await ctx.guild.fetch_member(member.id)

    # 2. 获取操作者权限
    my_idx, _, is_admin = get_user_rank_info(ctx.author)
    if not is_admin:
        return await ctx.send("❌ 你没有权限执行此操作！")

    # 3. 获取目标当前职级
    target_idx, target_name, _ = get_user_rank_info(member)
    if target_idx == -1:
        return await ctx.send(f"❌ 无法识别 **{member.display_name}** 的当前职级。请手动检查其身份组。")

    # 4. 权限高度判定
    if my_idx <= target_idx:
        return await ctx.send(f"❌ 你的职级 ({my_idx}) 必须高于对方 ({target_idx})。")

    # 5. 计算新职级
    new_idx = target_idx + direction
    if new_idx < 0 or new_idx >= len(RANK_ORDER):
        return await ctx.send("❌ 职级已达极限，无法再变动。")

    new_rank_name = RANK_ORDER[new_idx]
    
    # 6. 预先寻找身份组对象
    old_role = find_best_role_in_guild(ctx.guild, target_name)
    new_role = find_best_role_in_guild(ctx.guild, new_rank_name)

    if not new_role:
        return await ctx.send(f"❌ 找不到新职级对应的身份组: `{new_rank_name}`，请检查服务器设置。")

    try:
        # 🌟 关键：先加新角色，保证用户永远有一个职级身份，不会出现“无法识别”
        await member.add_roles(new_role, reason=f"职级变动 - 执行者: {ctx.author}")
        
        # 成功加入新角色后再删旧的
        if old_role and old_role in member.roles:
            await member.remove_roles(old_role)

        # 7. 结果反馈
        action_text = "晋升" if direction == 1 else "降级"
        await ctx.send(f"✅ 已将 {member.mention} 从 **{target_name}** {action_text}为 **{new_rank_name}**")

        # 8. 日志记录
        log_channel = bot.get_channel(1454209918432182404)
        if log_channel:
            embed = discord.Embed(
                title=f"职级变动通知 ({action_text})",
                color=0x2ecc71 if direction == 1 else 0xe74c3c,
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="操作人", value=ctx.author.display_name, inline=True)
            embed.add_field(name="目标", value=member.display_name, inline=True)
            embed.add_field(name="职位变动", value=f"{target_name} ➔ {new_rank_name}", inline=False)
            await log_channel.send(embed=embed)

    except discord.Forbidden:
        await ctx.send("❌ 权限不足！请确保机器人的身份组在服务器名单中处于较高位置。")
    except Exception as e:
        await ctx.send(f"❌ 操作失败: {e}")

@bot.command(name="promote")
async def promote(ctx, member: discord.Member = None):
    await change_rank(ctx, member, 1)

@bot.command(name="demote")
async def demote(ctx, member: discord.Member = None):
    await change_rank(ctx, member, -1)

# ─────────────────────────────────────────────
# 🛠️ 辅助工具
# ─────────────────────────────────────────────

@bot.command()
async def myrank(ctx):
    member = await ctx.guild.fetch_member(ctx.author.id)
    idx, name, admin = get_user_rank_info(member)
    if name:
        await ctx.send(f"你的职位: **{name}** (等级: {idx}, 管理权: {admin})")
    else:
        await ctx.send("无法识别你的职级。")

@bot.event
async def on_ready():
    print(f"✅ 机器人 {bot.user} 已启动并优化职级识别逻辑")

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
