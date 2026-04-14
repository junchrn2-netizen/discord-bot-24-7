import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv

load_dotenv()
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ─────────────────────────────────────────────
# 🔰 职级顺序
# ─────────────────────────────────────────────
RANK_ORDER = [
    "服务领队", "初级管理员", "高级管理员", "主管", "经理", 
    "初级公司", "执行实习生", "执行官", "副总裁", "总裁", 
    "副主席", "主席", "理事会实习生", "星球委员会", "执行委员会", 
    "外星委员会", "领导力实习生", "专员", "社区官员", "社区经理", 
    "副服主", "服主"
]

# ─────────────────────────────────────────────
# 🗂️ 档次关键词定义（用于权限检查）
# ─────────────────────────────────────────────
RANK_TIERS = [
    {"keyword": "LR",              "min": 0,  "max": 2,  "is_admin": False},
    {"keyword": "MR",              "min": 3,  "max": 4,  "is_admin": False},
    {"keyword": "HR",              "min": 5,  "max": 9,  "is_admin": False},
    {"keyword": "SHR",             "min": 10, "max": 15, "is_admin": True},
    {"keyword": "Leadership Rank", "min": 16, "max": 18, "is_admin": True},
    {"keyword": "Ownership Rank",  "min": 19, "max": 21, "is_admin": True},
]

LOG_GUILD_ID   = 1360354820757651657
LOG_CHANNEL_ID = 1454209918432182404

# ─────────────────────────────────────────────
# 🔍 核心逻辑：获取成员职级信息
# ─────────────────────────────────────────────
def get_user_rank_info(member):
    """
    返回: (最高职级索引, 职级名称, 是否为管理层)
    """
    best_idx = -1
    best_name = None
    has_admin_tier = False

    # 1. 检查是否持有特殊的“档次角色”（如截图中的 Ownership Rank）
    for role in member.roles:
        role_name_upper = role.name.upper()
        for tier in RANK_TIERS:
            # 如果角色名包含 Ownership Rank / Leadership Rank / SHR
            if tier["keyword"].upper() in role_name_upper:
                if tier["is_admin"]:
                    has_admin_tier = True
                # 如果这个档次比当前记录的更高，更新索引
                if tier["max"] > best_idx:
                    best_idx = tier["max"]
                    best_name = RANK_ORDER[best_idx]

    # 2. 检查具体的“职位角色”（如 服主、经理）
    for role in member.roles:
        role_name_low = role.name.lower()
        for idx, rank_name in enumerate(RANK_ORDER):
            if rank_name.lower() in role_name_low:
                if idx > best_idx:
                    best_idx = idx
                    best_name = rank_name
                # 检查该职位是否属于管理档次
                for tier in RANK_TIERS:
                    if tier["min"] <= idx <= tier["max"] and tier["is_admin"]:
                        has_admin_tier = True

    return best_idx, best_name, has_admin_tier

def find_role(guild, name):
    """精确优先，关键词匹配次之"""
    name_low = name.lower()
    for role in guild.roles:
        if name_low == role.name.lower():
            return role
    for role in guild.roles:
        if name_low in role.name.lower():
            return role
    return None

def get_tier_name(index):
    for tier in RANK_TIERS:
        if tier["min"] <= index <= tier["max"]:
            return tier["keyword"]
    return "未知"

# ─────────────────────────────────────────────
# 📝 日志记录
# ─────────────────────────────────────────────
async def log_action(ctx, action, target, old, new, old_tier, new_tier):
    emoji = "⬆️" if action == "promote" else "⬇️"
    action_cn = "晋升" if action == "promote" else "降级"

    await ctx.send(f"{emoji} 已将 **{target.display_name}** {action_cn}为 **{new}**")

    embed = discord.Embed(
        title=f"{emoji} 职级{action_cn}记录",
        color=discord.Color.green() if action == "promote" else discord.Color.red(),
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="操作人", value=f"{ctx.author.mention}", inline=True)
    embed.add_field(name="目标", value=f"{target.mention}", inline=True)
    embed.add_field(name="变动", value=f"从 `{old}` ({old_tier}) \n到 `{new}` ({new_tier})", inline=False)
    
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
        return await ctx.send("❌ 用法: `!promote @用户`")

    # 🔐 权限检查：检查是否有管理档次
    my_idx, my_name, is_admin = get_user_rank_info(ctx.author)
    if not is_admin:
        return await ctx.send("❌ 权限不足！你需要带有 **SHR / Leadership / Ownership** 关键词的角色。")

    target_idx, target_name, _ = get_user_rank_info(member)
    if target_idx == -1:
        return await ctx.send(f"❌ {member.display_name} 没有可识别的职级。")

    if my_idx <= target_idx:
        return await ctx.send("❌ 你的职级必须高于对方才能进行此操作。")

    if target_idx + 1 >= len(RANK_ORDER):
        return await ctx.send("❌ 对方已经是最高职级。")

    new_rank_name = RANK_ORDER[target_idx + 1]
    old_role = find_role(ctx.guild, target_name)
    new_role = find_role(ctx.guild, new_rank_name)

    if not new_role:
        return await ctx.send(f"❌ 找不到对应的服务器角色: `{new_rank_name}`")

    try:
        await member.add_roles(new_role)
        if old_role and old_role in member.roles:
            await member.remove_roles(old_role)
        
        await log_action(ctx, "promote", member, target_name, new_rank_name, get_tier_name(target_idx), get_tier_name(target_idx+1))
    except Exception as e:
        await ctx.send(f"❌ 执行失败: {e}")

# ─────────────────────────────────────────────
# !demote 降级
# ─────────────────────────────────────────────
@bot.command(name="demote")
async def demote(ctx, member: discord.Member = None):
    if not member:
        return await ctx.send("❌ 用法: `!demote @用户`")

    my_idx, my_name, is_admin = get_user_rank_info(ctx.author)
    if not is_admin:
        return await ctx.send("❌ 权限不足！")

    target_idx, target_name, _ = get_user_rank_info(member)
    if target_idx == -1:
        return await ctx.send(f"❌ 对方没有可识别的职级。")

    if my_idx <= target_idx:
        return await ctx.send("❌ 你的职级必须高于对方。")

    if target_idx - 1 < 0:
        return await ctx.send("❌ 对方已经是最低职级。")

    new_rank_name = RANK_ORDER[target_idx - 1]
    old_role = find_role(ctx.guild, target_name)
    new_role = find_role(ctx.guild, new_rank_name)

    if not new_role:
        return await ctx.send(f"❌ 找不到角色: `{new_rank_name}`")

    try:
        await member.add_roles(new_role)
        if old_role and old_role in member.roles:
            await member.remove_roles(old_role)
        
        await log_action(ctx, "demote", member, target_name, new_rank_name, get_tier_name(target_idx), get_tier_name(target_idx-1))
    except Exception as e:
        await ctx.send(f"❌ 执行失败: {e}")

# ─────────────────────────────────────────────
# 基础命令
# ─────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ {bot.user} 已上线")
    if not keep_alive.is_running():
        keep_alive.start()

@tasks.loop(minutes=5)
async def keep_alive():
    print("💓 心跳检测中...")

@bot.command()
async def myrank(ctx):
    idx, name, is_admin = get_user_rank_info(ctx.author)
    if idx != -1:
        tier = get_tier_name(idx)
        admin_status = "✅ 管理权限" if is_admin else "❌ 普通职级"
        await ctx.send(f"🔍 **职级信息**：\n- 职位：`{name}`\n- 档次：`{tier}`\n- 状态：{admin_status}")
    else:
        await ctx.send("🔍 未识别到你的职级角色。请确认你的角色名包含列表中的关键词。")

if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if token:
        bot.run(token)
    else:
        print("❌ 错误：找不到 Token")
